/**
 * Core.gs - the deterministic layer (no Apps Script services used).
 * Line-for-line port of framework/hybrid.py. tools/test_parity.py proves both give identical results.
 * Needs Config.gs (generated): CONFIG, SYSTEM_PROMPT, DEFAULT_MODEL, TEMPERATURE.
 */
const LEVELS = ['low', 'medium', 'high'];
const SECOND_LEVEL = ['co', 'com', 'org', 'net', 'gov', 'ac', 'edu'];

// ---- privacy masking
function redact(text) {
  text = text.replace(/[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})/g, '[email]@$1');
  return text.replace(/(?<!\w)\+?\d(?:[ -]?\d){9,}(?!\w)/g, '[number]');
}

function escapeRegex_(p) { return p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

// ---- lexical indicators
function lexicalScores(text) {
  const out = {};
  CONFIG.indicators.forEach(function (ind) {
    const hits = CONFIG.lexicons[ind].filter(function (p) { return new RegExp('\\b' + escapeRegex_(p) + '\\b', 'i').test(text); });
    out[ind] = { score: Math.min(3, hits.length), hits: hits };
  });
  return out;
}

// ---- technical checks
function extractUrls(text) {
  const m = text.match(/https?:\/\/[^\s<>"')\]]+|(?<![@\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}\/[^\s<>"')\]]*/gi) || [];
  return m.map(function (u) { return u.replace(/[.,;:!?]+$/, ''); });
}

function urlParts(u) {
  let scheme = '', auth;
  const m = u.match(/^(https?):\/\/([^/?#]+)/i);
  if (m) { scheme = m[1].toLowerCase(); auth = m[2]; } else { auth = u.match(/^([^/?#]+)/)[1]; }
  return { scheme: scheme, host: auth.split('@').pop().split(':')[0].toLowerCase() };
}

function regDomain(host) {
  const p = host.split('.').filter(function (x) { return x; });
  if (p.length >= 3 && SECOND_LEVEL.indexOf(p[p.length - 2]) >= 0 && p[p.length - 1].length === 2) return p.slice(-3).join('.');
  return p.length >= 2 ? p.slice(-2).join('.') : host;
}

function levenshtein(a, b) {
  let prev = []; for (let j = 0; j <= b.length; j++) prev.push(j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
    prev = cur;
  }
  return prev[b.length];
}

function lookalike(domain) {
  const brands = Object.keys(CONFIG.brands);
  for (let k = 0; k < brands.length; k++) if (CONFIG.brands[brands[k]].indexOf(domain) >= 0) return null;
  const label = domain.split('.')[0].replace(/-/g, '');
  for (let k = 0; k < brands.length; k++) {
    const b = brands[k];
    if (b.length >= 5 && label.indexOf(b) >= 0) return b;
    if (label.length >= 5 && levenshtein(label, b) === 1) return b;
  }
  return null;
}

function parseAddr(s) {
  s = s || '';
  const m = s.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
  if (m) return { display: m[1].trim(), addr: m[2].trim().toLowerCase() };
  return { display: '', addr: s.trim().toLowerCase() };
}

function domainOf(addr) { return addr.indexOf('@') >= 0 ? addr.split('@').pop() : ''; }

function technicalFlags(text, meta) {
  meta = meta || {};
  const flags = [], seen = {}, pts = CONFIG.tech_points;
  function add(id, detail) {
    if (seen[id]) return; seen[id] = true;
    flags.push({ id: id, label: pts[id].label, points: pts[id].points, detail: detail });
  }
  const urls = extractUrls(text);
  (meta.links || []).forEach(function (l) { if (l.href && urls.indexOf(l.href) < 0) urls.push(l.href); });
  urls.forEach(function (u) {
    const p = urlParts(u);
    if (!p.host) return;
    const reg = regDomain(p.host);
    if (p.scheme === 'http') add('insecure_http', u);
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(p.host)) add('ip_url', p.host);
    if (CONFIG.shorteners.indexOf(reg) >= 0) add('url_shortener', reg);
    if (CONFIG.suspicious_tlds.indexOf('.' + reg.split('.').pop()) >= 0) add('suspicious_tld', reg);
    const b = lookalike(reg);
    if (b) add('lookalike_domain', reg + " imitates '" + b + "'");
  });
  const pa = parseAddr(meta.from || '');
  const senderDom = pa.addr ? regDomain(domainOf(pa.addr)) : '';
  if (senderDom) {
    const b = lookalike(senderDom);
    if (b) add('lookalike_domain', 'sender ' + senderDom + " imitates '" + b + "'");
    const flat = pa.display.toLowerCase().replace(/[^a-z0-9]/g, '');
    const names = Object.keys(CONFIG.brands);
    for (let k = 0; k < names.length; k++) {
      if (names[k].length >= 5 && flat.indexOf(names[k]) >= 0 && CONFIG.brands[names[k]].indexOf(senderDom) < 0) {
        add('display_name_mismatch', "'" + pa.display + "' sent from " + senderDom); break;
      }
    }
  }
  if (meta.reply_to) {
    const ra = parseAddr(meta.reply_to);
    const rdom = ra.addr ? regDomain(domainOf(ra.addr)) : '';
    if (senderDom && rdom && rdom !== senderDom) add('reply_to_mismatch', senderDom + ' vs ' + rdom);
  }
  if (meta.auth) {
    const m = meta.auth.match(/\b(spf|dkim|dmarc)=(fail|softfail|permerror)\b/i);
    if (m) add('auth_fail', m[0]);
  }
  (meta.attachments || []).forEach(function (name) {
    const n = name.toLowerCase();
    if (CONFIG.risky_extensions.some(function (e) { return n.endsWith(e); })) add('risky_attachment', name);
  });
  (meta.links || []).forEach(function (l) {
    const shown = (l.text || '').trim().toLowerCase();
    if (/^(?:https?:\/\/)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/\S*)?$/.test(shown) && l.href) {
      const sd = regDomain(urlParts(shown).host), rd = regDomain(urlParts(l.href).host);
      if (sd !== rd) add('link_text_mismatch', 'shows ' + sd + ', goes to ' + rd);
    }
  });
  return flags;
}

// ---- LLM levels -> numbers, fusion, rules
function llmScores(analysis) {
  const out = {}, ind = (analysis && analysis.indicators) || {};
  CONFIG.indicators.forEach(function (name) {
    const d = ind[name] || {};
    const level = String(d.level === undefined ? 'none' : d.level).toLowerCase();
    const sc = CONFIG.level_to_score[level];
    out[name] = { score: sc === undefined ? 0 : sc, evidence: String(d.evidence || '') };
  });
  return out;
}

function fuse(l, x) { return CONFIG.fusion.llm_weight * l + CONFIG.fusion.lex_weight * x; }
function scoreToLevel(x) { return x < 0.5 ? 'none' : x < 1.5 ? 'low' : x < 2.5 ? 'medium' : 'high'; }
function raiseTo(level, floor) { return LEVELS.indexOf(floor) > LEVELS.indexOf(level) ? floor : level; }
function liftScore(risk, level) {
  if (level === 'high') return Math.max(risk, CONFIG.thresholds.high);
  if (level === 'medium') return Math.max(risk, CONFIG.thresholds.medium);
  return risk;
}

function assess(scores, flags, useTech, useRules) {
  const W = CONFIG.weights, TH = CONFIG.thresholds;
  let content = 0; CONFIG.indicators.forEach(function (i) { content += W[i] * scores[i] / 3.0; }); content *= 100;
  let tech = 0; if (useTech) { flags.forEach(function (f) { tech += f.points; }); tech = Math.min(100, tech); }
  let risk = Math.min(100, content + CONFIG.tech_weight * tech);
  let level = risk >= TH.high ? 'high' : risk >= TH.medium ? 'medium' : 'low';
  const rules = [];
  if (useRules) {
    const s = scores;
    const strong = flags.filter(function (f) { return CONFIG.strong_flags.indexOf(f.id) >= 0; });
    if (s.sensitive_info_requests >= 2 && Math.max(s.authority_claims, s.urgency, s.fear_threat) >= 2)
      rules.push({ id: 'R1', floor: 'high', why: 'A sensitive-information request combined with authority, urgency or threat is the core social-engineering pattern.' });
    if (strong.length && s.sensitive_info_requests >= 1)
      rules.push({ id: 'R2', floor: 'high', why: 'A sensitive-information request arrived with technical signs of spoofing.' });
    if (s.financial_pressure >= 2 && (s.urgency >= 2 || s.authority_claims >= 2))
      rules.push({ id: 'R3', floor: 'medium', why: 'A payment demand under time pressure or claimed authority needs verification.' });
    if (s.financial_pressure >= 2 && s.emotional_pressure >= 2)
      rules.push({ id: 'R4', floor: 'high', why: 'A money request wrapped in emotional pressure matches relationship/advance-fee fraud.' });
    rules.forEach(function (r) { level = raiseTo(level, r.floor); });
  }
  risk = liftScore(risk, level);
  return { content_score: content, tech_score: tech, risk_score: risk, risk_level: level, rules_fired: rules };
}

// ---- explanation
function shorten_(s, n) {
  s = String(s).replace(/\s+/g, ' ').trim();
  return s.length <= n ? s : s.substring(0, n - 1) + '…';
}

function explain(level, risk, indicators, flags, rules, llmOverall) {
  const W = CONFIG.weights, labels = CONFIG.labels;
  const lines = ['Overall conversational risk: ' + level.toUpperCase() + ' (score ' + Math.round(risk) + '/100).'];
  const shown = CONFIG.indicators.slice().sort(function (a, b) { return W[b] * indicators[b].fused - W[a] * indicators[a].fused; })
    .filter(function (i) { return indicators[i].fused >= 1.0; }).slice(0, 3);
  if (shown.length) {
    lines.push('Main reasons:');
    shown.forEach(function (i) {
      const ev = indicators[i].evidence;
      lines.push('- ' + labels[i] + ' (' + scoreToLevel(indicators[i].fused) + '): ' + (ev ? shorten_(ev, 140) : 'keyword match'));
    });
  } else lines.push('No strong manipulation indicator was found in the text.');
  if (flags.length) lines.push('Technical signals: ' + flags.slice(0, 4).map(function (f) { return f.label; }).join('; ') + '.');
  rules.forEach(function (r) { lines.push('Escalation rule ' + r.id + ': ' + r.why); });
  if (llmOverall && llmOverall !== level)
    lines.push("Note: the language model alone rated this '" + llmOverall + "'; the combined analysis rated it '" + level + "'. When the two differ, take extra care.");
  lines.push('What to do: ' + CONFIG.actions[level]);
  return lines.join('\n');
}

// ---- single entry point (same switches as hybrid.py)
function hybridAssess(text, meta, llmAnalysis, opts) {
  opts = opts || {};
  const useLlm = opts.useLlm !== false, useLex = opts.useLex !== false, useTech = opts.useTech !== false,
        useRules = opts.useRules !== false, llmFloor = opts.llmFloor !== false;
  if (useLlm && !llmAnalysis) throw new Error('llmAnalysis required');
  text = text.substring(0, CONFIG.max_chars);
  const lex = lexicalScores(text);
  const flags = useTech ? technicalFlags(text, meta || {}) : [];
  const llm = useLlm ? llmScores(llmAnalysis) : null;
  const scores = {}, indicators = {};
  CONFIG.indicators.forEach(function (i) {
    const l = llm ? llm[i].score : 0, x = useLex ? lex[i].score : 0;
    const s = (useLlm && useLex) ? fuse(l, x) : useLlm ? l : x;
    scores[i] = s;
    let ev = llm ? llm[i].evidence : '';
    if (!ev && lex[i].hits.length && useLex) ev = 'keyword match: ' + lex[i].hits.slice(0, 3).join(', ');
    indicators[i] = { llm: llm ? l : null, lex: lex[i].score, fused: s, level: scoreToLevel(s), evidence: ev,
      contribution: CONFIG.weights[i] * s / 3.0 * 100 };
  });
  const res = assess(scores, flags, useTech, useRules);
  const raw = llmAnalysis && llmAnalysis.overall_risk ? String(llmAnalysis.overall_risk).toLowerCase() : '';
  const llmOverall = raw || null;
  let floorApplied = false;
  if (useLlm && llmFloor && LEVELS.indexOf(llmOverall) >= 0 && LEVELS.indexOf(llmOverall) > LEVELS.indexOf(res.risk_level)) {
    res.risk_level = llmOverall; res.risk_score = liftScore(res.risk_score, llmOverall); floorApplied = true;
  }
  res.llm_floor_applied = floorApplied;
  res.indicators = indicators;
  res.technical_flags = flags;
  res.present = CONFIG.indicators.filter(function (i) { return scores[i] >= CONFIG.thresholds.present; }).sort();
  res.llm_overall_risk = llmOverall;
  res.agrees_with_llm = llmOverall ? llmOverall === res.risk_level : null;
  res.recommended_action = CONFIG.actions[res.risk_level];
  res.explanation = explain(res.risk_level, res.risk_score, indicators, flags, res.rules_fired, llmOverall);
  return res;
}

// ---- input assembly (mirror of pipeline.build_email_input)
function buildEmailInput(meta, body) {
  const parts = ['[Email]'];
  if (meta.from) parts.push('From: ' + redact(meta.from));
  if (meta.subject) parts.push('Subject: ' + meta.subject);
  return redact(parts.join('\n') + '\n\n' + String(body || '').trim()).substring(0, CONFIG.max_chars);
}

function validateAnalysis(raw) {
  if (!raw || typeof raw !== 'object' || !raw.indicators) throw new Error('Model did not return the expected JSON structure.');
  return raw;
}