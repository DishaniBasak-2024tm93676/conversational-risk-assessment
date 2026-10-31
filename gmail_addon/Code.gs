/**
 * Code.gs - Gmail add-on UI + Gemini call.
 *
 * PRIVACY BY DESIGN: nothing is read or sent until the user presses a button. There is no trigger
 * that scans the inbox and no background processing. Mailbox names and long numbers are masked
 * before any text leaves Google (redact in Core.gs).
 *
 * Setup: Project Settings > Script properties > add GEMINI_API_KEY (optional: GEMINI_MODEL).
 * The prompt, model name and all parameters come from Config.gs, generated from the Python project.
 */

function getModel_() {
  return PropertiesService.getScriptProperties().getProperty('GEMINI_MODEL') || DEFAULT_MODEL;
}

// ------------------------------------------------------------------ cards
function onHomepage() {
  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Conversational Risk Assessor').setSubtitle('Explainable decision support'))
    .addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(
      'Open an email and press <b>Analyze</b>. Nothing is read or sent until you press it, and this tool never scans your inbox in the background.')))
    .build();
}

function onGmailMessageOpen(e) {
  const params = { messageId: e.gmail.messageId, accessToken: e.gmail.accessToken };
  const section = CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText(
      'Checks this message for fake authority, urgency, threats and requests for sensitive data, plus sender and link checks. Content is analysed <b>only when you press a button</b>.'))
    .addWidget(CardService.newButtonSet()
      .addButton(CardService.newTextButton().setText('Analyze this email').setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(CardService.newAction().setFunctionName('analyzeMessage').setParameters(Object.assign({ scope: 'message' }, params))))
      .addButton(CardService.newTextButton().setText('Analyze whole thread')
        .setOnClickAction(CardService.newAction().setFunctionName('analyzeMessage').setParameters(Object.assign({ scope: 'thread' }, params)))));
  return CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle('Conversational Risk Assessor')).addSection(section).build();
}

function errorCard_(msg) {
  return CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle('Could not analyze'))
    .addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(esc_(msg)))).build();
}

function push_(card) {
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card)).build();
}

function esc_(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function resultCard_(res, analysis, authAvailable, timeline, note) {
  const colour = { high: '#B00020', medium: '#B26A00', low: '#1B7F3B' }[res.risk_level];
  const head = CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText('<font color="' + colour + '"><b>Risk: ' + res.risk_level.toUpperCase() + ' (' + Math.round(res.risk_score) + '/100)</b></font>'))
    .addWidget(CardService.newTextParagraph().setText(esc_(res.recommended_action)));

  if (timeline) head.addWidget(CardService.newTextParagraph().setText('<i>Showing the highest-risk message of the conversation.' + (note || '') + '</i>'));
  const ind = CardService.newCardSection().setHeader('Manipulation indicators');
  CONFIG.indicators.forEach(function (i) {
    const d = res.indicators[i];
    ind.addWidget(CardService.newDecoratedText().setTopLabel(CONFIG.labels[i]).setText('<b>' + d.level + '</b>')
      .setBottomLabel(d.evidence ? esc_(shorten_(d.evidence, 120)) : '').setWrapText(true));
  });

  const card = CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle('Assessment')).addSection(head);
  if (timeline) card.addSection(timeline);
  card.addSection(ind);

  const tech = CardService.newCardSection().setHeader('Technical signals');
  if (res.technical_flags.length) {
    res.technical_flags.forEach(function (f) { tech.addWidget(CardService.newDecoratedText().setText(esc_(f.label)).setBottomLabel(esc_(f.detail)).setWrapText(true)); });
  } else {
    tech.addWidget(CardService.newTextParagraph().setText('No sender, link or attachment warning signs found.'));
  }
  if (!authAvailable) tech.addWidget(CardService.newTextParagraph().setText('<i>Sender-authentication results (SPF/DKIM/DMARC) were not available for this message.</i>'));
  card.addSection(tech);

  card.addSection(CardService.newCardSection().setHeader('Why this rating').setCollapsible(true).setNumUncollapsibleWidgets(0)
    .addWidget(CardService.newTextParagraph().setText(esc_(res.explanation).replace(/\n/g, '<br>'))));
  if (analysis && analysis.explanation) {
    card.addSection(CardService.newCardSection().setHeader('Gemini’s own reasoning').setCollapsible(true).setNumUncollapsibleWidgets(0)
      .addWidget(CardService.newTextParagraph().setText(esc_(analysis.explanation))));
  }
  card.addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(
    '<i>Decision support only. It can be wrong and does not guarantee that a message is safe or unsafe.</i>')));
  return card.build();
}

// ------------------------------------------------------------------ data collection (only on click)
function collectOne_(msg, body) {
  const links = [], re = /<a\s[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let m;
  const html = msg.getBody();
  while ((m = re.exec(html)) !== null) links.push({ href: m[1], text: m[2].replace(/<[^>]+>/g, '').trim() });
  let auth = '';
  try {
    const raw = msg.getRawContent();
    const end = raw.indexOf('\r\n\r\n');
    auth = raw.substring(0, end > 0 ? end : 20000);
  } catch (err) { auth = ''; }
  return {
    meta: {
      from: msg.getFrom(), reply_to: msg.getReplyTo() === msg.getFrom() ? '' : msg.getReplyTo(), auth: auth,
      subject: msg.getSubject(),
      attachments: msg.getAttachments({ includeInlineImages: false }).map(function (a) { return a.getName(); }),
      links: links.slice(0, 60)
    },
    body: body === undefined ? msg.getPlainBody() : body
  };
}

// ------------------------------------------------------------------ Gemini (same prompt as llm_client.py)
function callGemini_(inputText) {
  const key = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!key) throw new Error('GEMINI_API_KEY is not set in Project Settings > Script properties.');
  const body = {
    systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
    contents: [{ role: 'user', parts: [{ text: inputText }] }],
    generationConfig: { temperature: TEMPERATURE, responseMimeType: 'application/json' }
  };
  let lastErr = '';
  for (let a = 0; a < 3; a++) {
    const r = UrlFetchApp.fetch('https://generativelanguage.googleapis.com/v1beta/models/' + getModel_() + ':generateContent',
      { method: 'post', contentType: 'application/json', headers: { 'x-goog-api-key': key }, payload: JSON.stringify(body), muteHttpExceptions: true });
    const code = r.getResponseCode();
    if (code === 200) {
      return validateAnalysis(JSON.parse(JSON.parse(r.getContentText()).candidates[0].content.parts[0].text));
    }
    lastErr = code + ' ' + r.getContentText().substring(0, 200);
    if ([429, 500, 503].indexOf(code) < 0 || lastErr.indexOf('PerDay') >= 0) break;
    Utilities.sleep(3000 * (a + 1));
  }
  throw new Error('Gemini error: ' + lastErr);
}

// ------------------------------------------------------------------ button handler
const MAX_THREAD_MESSAGES = 5;   // keeps the run inside the add-on time limit and the API quota

function assessOne_(c) {
  const input = buildEmailInput(c.meta, c.body);
  const cache = CacheService.getUserCache();
  const ck = 'r_' + Utilities.base64EncodeWebSafe(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, getModel_() + input));
  let analysis = cache.get(ck);
  if (analysis) analysis = JSON.parse(analysis);
  else { analysis = callGemini_(input); cache.put(ck, JSON.stringify(analysis), 3600); }
  return { res: hybridAssess(input, c.meta, analysis), analysis: analysis, hasAuth: !!c.meta.auth };
}

function timelineSection_(rows) {
  const colours = { high: '#B00020', medium: '#B26A00', low: '#1B7F3B' };
  const sec = CardService.newCardSection().setHeader('Conversation timeline (' + rows.length + ' messages, oldest first)');
  rows.forEach(function (r, k) {
    const why = r.out.res.present.length ? r.out.res.present.map(function (i) { return CONFIG.labels[i]; }).join(', ') : 'no manipulation indicators';
    sec.addWidget(CardService.newDecoratedText()
      .setTopLabel((k + 1) + '. ' + esc_(shorten_(r.from, 45)))
      .setText('<font color="' + colours[r.out.res.risk_level] + '"><b>' + r.out.res.risk_level.toUpperCase() + ' (' + Math.round(r.out.res.risk_score) + ')</b></font>')
      .setBottomLabel(esc_(why)).setWrapText(true));
  });
  const first = rows[0].out.res.risk_score, last = rows[rows.length - 1].out.res.risk_score;
  let note;
  if (last - first >= 20) note = 'Risk <b>rises</b> through the conversation (' + Math.round(first) + ' to ' + Math.round(last) + '): possible escalation, a pattern typical of social engineering.';
  else if (rows.some(function (r) { return r.out.res.risk_level === 'high'; })) note = 'At least one message in this conversation is high risk.';
  else note = 'No escalation detected across the conversation.';
  sec.addWidget(CardService.newTextParagraph().setText(note));
  return sec;
}

function analyzeMessage(e) {
  try {
    GmailApp.setCurrentMessageAccessToken(e.parameters.accessToken);
    const msg = GmailApp.getMessageById(e.parameters.messageId);
    if (e.parameters.scope === 'thread') {
      let messages = [msg];
      try { messages = msg.getThread().getMessages(); } catch (err) { messages = [msg]; }
      if (messages.length > 1) {
        const used = messages.slice(-MAX_THREAD_MESSAGES);
        const rows = used.map(function (m) { return { from: m.getFrom(), out: assessOne_(collectOne_(m)) }; });
        let worst = rows[0];
        rows.forEach(function (r) { if (r.out.res.risk_score > worst.out.res.risk_score) worst = r; });
        const note = messages.length > used.length ? ' Only the latest ' + used.length + ' of ' + messages.length + ' messages were analysed.' : '';
        const card = resultCard_(worst.out.res, worst.out.analysis, worst.out.hasAuth, timelineSection_(rows), note);
        return push_(card);
      }
    }
    const out = assessOne_(collectOne_(msg));
    return push_(resultCard_(out.res, out.analysis, out.hasAuth));
  } catch (err) {
    return push_(errorCard_(String(err.message || err)));
  }
}