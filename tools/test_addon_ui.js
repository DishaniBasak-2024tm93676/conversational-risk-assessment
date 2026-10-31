// Runs gmail_addon/Code.gs end-to-end under Node with STAND-INS for Google's services
// (CardService, GmailApp, UrlFetchApp, ...). It checks our code paths, not Google's rendering.
//   node tools/test_addon_ui.js
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const root = path.join(__dirname, '..');

// A chainable stand-in: any method call returns the same object, and we record the text set on widgets.
const texts = [];
function chain() {
    const o = new Proxy(function () { }, {
        get: (t, k) => (k === 'build' ? () => ({ built: true }) : (...a) => { a.forEach(x => { if (typeof x === 'string') texts.push(x); }); return o; }),
        apply: () => o
    });
    return o;
}
const CardService = new Proxy({}, { get: (t, k) => (k === 'TextButtonStyle' ? { FILLED: 'FILLED' } : (k.startsWith('new') ? () => chain() : undefined)) });

const props = { GEMINI_API_KEY: 'test-key' };
let fetchCalls = 0, lastPayload = null;
const fakeAnalysis = (risk) => ({
    context: { domain: 'banking', confidence: 'high' },
    indicators: Object.fromEntries(['authority_claims', 'urgency', 'fear_threat', 'sensitive_info_requests', 'emotional_pressure', 'financial_pressure']
        .map(k => [k, { level: k === 'sensitive_info_requests' ? 'high' : 'none', evidence: "'enter your password'" }])),
    overall_risk: risk, explanation: 'Fake model explanation.', recommended_action: 'x'
});
let respond = () => ({ code: 200, body: JSON.stringify({ candidates: [{ content: { parts: [{ text: JSON.stringify(fakeAnalysis('medium')) }] } }] }) });
const store = {};
const message = {
    getFrom: () => 'NovaBank Security <alerts@novabank-secure.co>', getReplyTo: () => 'help@novabank-help.co',
    getSubject: () => 'URGENT verify', getPlainBody: () => 'Click http://novabank-secure.co/verify and enter your password. Call 9876543210.',
    getBody: () => '<a href="https://novabank.com/x">https://novabank.com/x</a>',
    getRawContent: () => 'Authentication-Results: mx.google.com; spf=fail smtp.mailfrom=novabank-secure.co\r\nFrom: x\r\n\r\nbody',
    getAttachments: () => [{ getName: () => 'invoice.html' }], getThread: () => ({ getMessages: () => [message, message] })
};
const ctx = {
    CardService, console,
    GmailApp: { setCurrentMessageAccessToken() { }, getMessageById: () => message },
    PropertiesService: { getScriptProperties: () => ({ getProperty: k => props[k] || null }) },
    CacheService: { getUserCache: () => ({ get: k => store[k] || null, put: (k, v) => { store[k] = v; } }) },
    Utilities: {
        base64EncodeWebSafe: a => Buffer.from(JSON.stringify(a)).toString('base64'), computeDigest: (alg, s) => [...Buffer.from(s)].slice(0, 16),
        DigestAlgorithm: { SHA_256: 'sha' }, sleep() { }
    },
    UrlFetchApp: { fetch: (url, opts) => { fetchCalls++; lastPayload = JSON.parse(opts.payload); const r = respond(); return { getResponseCode: () => r.code, getContentText: () => r.body }; } }
};
vm.createContext(ctx);
const src = ['Config.gs', 'Core.gs', 'Code.gs'].map(f => fs.readFileSync(path.join(root, 'gmail_addon', f), 'utf8')).join('\n');
vm.runInContext(src + '\n;this.__api = {onHomepage, onGmailMessageOpen, analyzeMessage, getModel_};', ctx);
const api = ctx.__api;

const ev = (scope) => ({ gmail: { messageId: 'm1', accessToken: 't' }, parameters: { messageId: 'm1', accessToken: 't', scope } });
assert(api.onHomepage().built, 'homepage card');
assert(api.onGmailMessageOpen(ev('message')).built, 'message-open card');

texts.length = 0;
const r1 = api.analyzeMessage(ev('message'));
assert(r1 && fetchCalls === 1, 'one Gemini call on first analyze');
const sent = lastPayload.contents[0].parts[0].text;
assert(!/9876543210/.test(sent), 'long number must be masked before sending');
assert(!/alerts@/.test(sent) && /\[email\]@novabank-secure\.co/.test(sent), 'mailbox name masked, domain kept');
assert(lastPayload.generationConfig.responseMimeType === 'application/json', 'JSON mode on');
assert(lastPayload.systemInstruction.parts[0].text.includes('authority_claims'), 'uses the shared prompt');
assert(texts.some(t => /Risk: HIGH/.test(t)), 'technical flags + rules must raise this to HIGH (R1/R2): ' + texts.filter(t => /Risk/.test(t)));
assert(texts.some(t => /Look-alike/.test(t)), 'technical signal shown');

api.analyzeMessage(ev('message'));
assert(fetchCalls === 1, 'second identical analyze must come from cache (no new API call)');

respond = () => ({ code: 429, body: 'RESOURCE_EXHAUSTED PerDay' });
for (const k in store) delete store[k];
texts.length = 0;
api.analyzeMessage(ev('thread'));
assert(texts.some(t => /Gemini error/.test(t)), 'quota error is shown to the user as a card');
delete props.GEMINI_API_KEY; texts.length = 0;
api.analyzeMessage(ev('message'));
assert(texts.some(t => /GEMINI_API_KEY is not set/.test(t)), 'missing key message');
console.log('ADD-ON UI TEST PASSED (card building, masking, shared prompt, caching, error handling)');