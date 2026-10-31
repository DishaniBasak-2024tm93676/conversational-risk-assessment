// Runs the Apps Script core (Config.gs + Core.gs) under Node. Usage: node tools/parity.js <cases.json>
// cases.json: [{id, text, meta, analysis}]  ->  prints results for 5 configurations as JSON.
const fs = require('fs'), path = require('path'), vm = require('vm');
const root = path.join(__dirname, '..');
const src = ['Config.gs', 'Core.gs'].map(f => fs.readFileSync(path.join(root, 'gmail_addon', f), 'utf8')).join('\n');
const api = vm.runInNewContext(src + '\n;({hybridAssess, redact, buildEmailInput})', {});
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const CFGS = { hybrid: {}, rules: { useLlm: false }, noTech: { useTech: false }, noRules: { useRules: false }, scoreOnly: { llmFloor: false } };
const out = {};
cases.forEach(c => {
    out[c.id] = { redacted: api.redact(c.text) };
    Object.keys(CFGS).forEach(k => {
        const r = api.hybridAssess(c.text, c.meta, c.analysis, CFGS[k]);
        out[c.id][k] = {
            risk_score: r.risk_score, risk_level: r.risk_level, present: r.present, flags: r.technical_flags.map(f => f.id),
            rules: r.rules_fired.map(x => x.id), floor: r.llm_floor_applied
        };
    });
});
process.stdout.write(JSON.stringify(out));