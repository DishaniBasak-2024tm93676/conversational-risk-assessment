"""
hybrid.py

The deterministic layer that wraps the Gemini analysis (llm_client.py) into the
final, explainable framework output. It adds what an LLM cannot do reliably on its own:

  1. Privacy masking before text leaves the machine (redact)
  2. Independent lexical indicator scores (a second opinion on the six indicators)
  3. Technical email checks the LLM never sees: SPF/DKIM/DMARC results, Reply-To
     mismatch, look-alike domains, link text vs real link target, URL shorteners,
     risky attachments
  4. A transparent, fixed-weight fusion into a 0-100 risk score
  5. Escalation rules R1-R4 for classic social-engineering combinations
  6. A template-based explanation: every sentence is traceable to a computed value

No network access in this file. All numbers and word lists live in risk_config.json
(single source of truth). The Gmail add-on has a line-for-line port of this logic
(gmail_addon/Core.gs), kept identical by tools/test_parity.py.

Usage:
    from hybrid import hybrid_assess
    result = hybrid_assess(text, meta, llm_analysis)
"""

import json
import os
import re

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "risk_config.json")
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    CFG = json.load(_f)

INDICATORS = CFG["indicators"]
WEIGHTS = CFG["weights"]
THRESH = CFG["thresholds"]
LEVELS = ["low", "medium", "high"]
BRANDS = CFG["brands"]


# ------------------------------------------------------------------ 1. privacy masking
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_LONG_NUMBER = re.compile(r"(?<!\w)\+?\d(?:[ -]?\d){9,}(?!\w)")


def redact(text: str) -> str:
    """Data minimisation: mask mailbox names (keep the domain, which is evidence) and
    long digit strings (phone / account numbers) before text is sent to any external API."""
    text = _EMAIL.sub(r"[email]@\1", text)
    return _LONG_NUMBER.sub("[number]", text)


# ------------------------------------------------------------------ 2. lexical indicators
_LEX_RX = {
    ind: [(p, re.compile(r"\b" + re.escape(p) + r"\b", re.I)) for p in CFG["lexicons"][ind]]
    for ind in INDICATORS
}


def lexical_scores(text: str) -> dict:
    """Score 0-3 per indicator = number of distinct lexicon phrases found (capped at 3)."""
    out = {}
    for ind in INDICATORS:
        hits = [p for p, rx in _LEX_RX[ind] if rx.search(text)]
        out[ind] = {"score": min(3, len(hits)), "hits": hits}
    return out


# ------------------------------------------------------------------ 3. technical email checks
_URL = re.compile(
    r"https?://[^\s<>\"')\]]+|(?<![@\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}/[^\s<>\"')\]]*", re.I)
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}


def extract_urls(text: str) -> list:
    return [u.rstrip(".,;:!?") for u in _URL.findall(text)]


def url_parts(url: str):
    m = re.match(r"^(https?)://([^/?#]+)", url, re.I)
    if m:
        scheme, authority = m.group(1).lower(), m.group(2)
    else:
        scheme, authority = "", re.match(r"^([^/?#]+)", url).group(1)
    host = authority.split("@")[-1].split(":")[0].lower()
    return scheme, host


def reg_domain(host: str) -> str:
    """Registered domain, e.g. mail.novabank.co.in -> novabank.co.in (small heuristic, no PSL)."""
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(b)]


def lookalike(domain: str):
    """Brand imitated by a registered domain (contains the brand name, or one typo away), else None.
    Returns None for the brand's own legitimate domains."""
    for legit in BRANDS.values():
        if domain in legit:
            return None
    label = domain.split(".")[0].replace("-", "")
    for brand in BRANDS:
        if len(brand) >= 5 and brand in label:
            return brand
        if len(label) >= 5 and levenshtein(label, brand) == 1:
            return brand
    return None


def parse_addr(s: str):
    s = s or ""
    m = re.match(r'^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$', s)
    if m:
        return m.group(1).strip(), m.group(2).strip().lower()
    return "", s.strip().lower()


def _domain_of(addr: str) -> str:
    return addr.split("@")[-1] if "@" in addr else ""


def technical_flags(text: str, meta: dict) -> list:
    """meta keys (all optional): from, reply_to, auth, attachments[], links[{text, href}]"""
    meta = meta or {}
    flags, seen = [], set()
    pts = CFG["tech_points"]

    def add(flag_id, detail):
        if flag_id in seen:
            return
        seen.add(flag_id)
        flags.append({"id": flag_id, "label": pts[flag_id]["label"],
                      "points": pts[flag_id]["points"], "detail": detail})

    urls = extract_urls(text)
    for link in meta.get("links") or []:
        if link.get("href") and link["href"] not in urls:
            urls.append(link["href"])
    for u in urls:
        scheme, host = url_parts(u)
        if not host:
            continue
        reg = reg_domain(host)
        if scheme == "http":
            add("insecure_http", u)
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
            add("ip_url", host)
        if reg in CFG["shorteners"]:
            add("url_shortener", reg)
        if "." + reg.split(".")[-1] in CFG["suspicious_tlds"]:
            add("suspicious_tld", reg)
        brand = lookalike(reg)
        if brand:
            add("lookalike_domain", f"{reg} imitates '{brand}'")

    display, addr = parse_addr(meta.get("from", ""))
    sender_dom = reg_domain(_domain_of(addr)) if addr else ""
    if sender_dom:
        brand = lookalike(sender_dom)
        if brand:
            add("lookalike_domain", f"sender {sender_dom} imitates '{brand}'")
        flat = re.sub(r"[^a-z0-9]", "", display.lower())
        for b, legit in BRANDS.items():
            if len(b) >= 5 and b in flat and sender_dom not in legit:
                add("display_name_mismatch", f"'{display}' sent from {sender_dom}")
                break
    if meta.get("reply_to"):
        _, reply_addr = parse_addr(meta["reply_to"])
        reply_dom = reg_domain(_domain_of(reply_addr)) if reply_addr else ""
        if sender_dom and reply_dom and reply_dom != sender_dom:
            add("reply_to_mismatch", f"{sender_dom} vs {reply_dom}")
    if meta.get("auth"):
        m = re.search(r"\b(spf|dkim|dmarc)=(fail|softfail|permerror)\b", meta["auth"], re.I)
        if m:
            add("auth_fail", m.group(0))
    for name in meta.get("attachments") or []:
        if any(name.lower().endswith(ext) for ext in CFG["risky_extensions"]):
            add("risky_attachment", name)
    for link in meta.get("links") or []:
        shown = (link.get("text") or "").strip().lower()
        if re.fullmatch(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?", shown) and link.get("href"):
            _, shown_host = url_parts(shown)
            _, real_host = url_parts(link["href"])
            if reg_domain(shown_host) != reg_domain(real_host):
                add("link_text_mismatch",
                    f"shows {reg_domain(shown_host)}, goes to {reg_domain(real_host)}")
    return flags


# ------------------------------------------------------------------ 4. fusion + 5. rules
def llm_scores(analysis: dict) -> dict:
    """Convert Gemini's none/low/medium/high levels (llm_client schema) to 0-3 numbers + evidence."""
    out = {}
    ind = (analysis or {}).get("indicators", {}) or {}
    for name in INDICATORS:
        d = ind.get(name) or {}
        level = str(d.get("level", "none")).lower()
        out[name] = {"score": CFG["level_to_score"].get(level, 0), "evidence": str(d.get("evidence", "") or "")}
    return out


def fuse(llm_score: float, lex_score: float) -> float:
    f = CFG["fusion"]
    return f["llm_weight"] * llm_score + f["lex_weight"] * lex_score


def score_to_level(x: float) -> str:
    """Indicator-level label for a 0-3 fused score."""
    return "none" if x < 0.5 else "low" if x < 1.5 else "medium" if x < 2.5 else "high"


def _raise_to(level: str, floor: str) -> str:
    return floor if LEVELS.index(floor) > LEVELS.index(level) else level


def _lift_score(risk: float, level: str) -> float:
    """After a rule or floor raises the level, lift the number to that level's threshold so the
    score shown to the user never contradicts the label."""
    if level == "high":
        return max(risk, THRESH["high"])
    if level == "medium":
        return max(risk, THRESH["medium"])
    return risk


def assess(scores: dict, flags: list, use_tech: bool = True, use_rules: bool = True) -> dict:
    """Risk score = content score (weighted indicators) + tech_weight * technical score, then rule floors."""
    content = sum(WEIGHTS[i] * scores[i] / 3.0 for i in INDICATORS) * 100
    tech = min(100, sum(f["points"] for f in flags)) if use_tech else 0
    risk = min(100, content + CFG["tech_weight"] * tech)
    level = "high" if risk >= THRESH["high"] else "medium" if risk >= THRESH["medium"] else "low"
    fired = []
    if use_rules:
        s = scores
        strong = [f["id"] for f in flags if f["id"] in CFG["strong_flags"]]
        if s["sensitive_info_requests"] >= 2 and max(s["authority_claims"], s["urgency"], s["fear_threat"]) >= 2:
            fired.append(("R1", "high", "A sensitive-information request combined with authority, urgency or threat is the core social-engineering pattern."))
        if strong and s["sensitive_info_requests"] >= 1:
            fired.append(("R2", "high", "A sensitive-information request arrived with technical signs of spoofing."))
        if s["financial_pressure"] >= 2 and (s["urgency"] >= 2 or s["authority_claims"] >= 2):
            fired.append(("R3", "medium", "A payment demand under time pressure or claimed authority needs verification."))
        if s["financial_pressure"] >= 2 and s["emotional_pressure"] >= 2:
            fired.append(("R4", "high", "A money request wrapped in emotional pressure matches relationship/advance-fee fraud."))
        for _, floor, _ in fired:
            level = _raise_to(level, floor)
    risk = _lift_score(risk, level)
    return {"content_score": content, "tech_score": tech, "risk_score": risk, "risk_level": level,
            "rules_fired": [{"id": r, "floor": fl, "why": why} for r, fl, why in fired]}


# ------------------------------------------------------------------ 6. explanation
def _shorten(s: str, n: int = 140) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def explain(level, risk, indicators, flags, rules, llm_overall=None) -> str:
    labels = CFG["labels"]
    lines = [f"Overall conversational risk: {level.upper()} (score {risk:.0f}/100)."]
    ranked = sorted(INDICATORS, key=lambda i: -WEIGHTS[i] * indicators[i]["fused"])
    shown = [i for i in ranked if indicators[i]["fused"] >= 1.0][:3]
    if shown:
        lines.append("Main reasons:")
        for i in shown:
            ev = indicators[i]["evidence"]
            lines.append(f"- {labels[i]} ({score_to_level(indicators[i]['fused'])}): "
                         f"{_shorten(ev) if ev else 'keyword match'}")
    else:
        lines.append("No strong manipulation indicator was found in the text.")
    if flags:
        lines.append("Technical signals: " + "; ".join(f["label"] for f in flags[:4]) + ".")
    for r in rules:
        lines.append(f"Escalation rule {r['id']}: {r['why']}")
    if llm_overall and llm_overall != level:
        lines.append(f"Note: the language model alone rated this '{llm_overall}'; "
                     f"the combined analysis rated it '{level}'. When the two differ, take extra care.")
    lines.append("What to do: " + CFG["actions"][level])
    return "\n".join(lines)


# ------------------------------------------------------------------ evidence-grounding check
def grounding(analysis: dict, source_text: str):
    """Gemini is asked for 'a short quote or close paraphrase'. This counts how many text spans the
    model put in quotation marks really occur in the input. Returns (quoted_spans, verified_spans)."""
    seen = re.sub(r"\s+", " ", source_text).lower()
    total = ok = 0
    for d in ((analysis or {}).get("indicators") or {}).values():
        ev = str((d or {}).get("evidence", "") or "")
        for q in re.findall(r"'([^']{4,})'|\"([^\"]{4,})\"|“([^”]{4,})”", ev):
            span = next(x for x in q if x)
            total += 1
            ok += re.sub(r"\s+", " ", span).lower().strip(" .,;:!?") in seen
    return total, ok


# ------------------------------------------------------------------ single entry point
def hybrid_assess(text: str, meta: dict = None, llm_analysis: dict = None,
                  use_llm: bool = True, use_lex: bool = True, use_tech: bool = True,
                  use_rules: bool = True, llm_floor: bool = True) -> dict:
    """
    text         : the message text analysed (subject + body, or chat turns)
    meta         : optional email metadata (from, reply_to, auth, attachments, links)
    llm_analysis : dict returned by llm_client.analyze_conversation (needed when use_llm=True)

    Switches let the evaluation run ablations on the SAME LLM output:
      full hybrid          : use_llm, use_lex, use_tech, use_rules (all True)
      rules only (B1)      : use_llm=False
      hybrid w/o technical : use_tech=False        hybrid w/o rules : use_rules=False
      score-only fusion    : llm_floor=False
    llm_floor=True (default) means the deterministic layer can only RAISE Gemini's own overall_risk,
    never lower it (asymmetric cost: a missed scam is worse than an extra caution).
    """
    if use_llm and llm_analysis is None:
        raise ValueError("llm_analysis is required when use_llm=True")
    text = text[: CFG["max_chars"]]
    lex = lexical_scores(text)
    flags = technical_flags(text, meta or {}) if use_tech else []
    llm = llm_scores(llm_analysis) if use_llm else None

    scores, indicators = {}, {}
    for i in INDICATORS:
        l = llm[i]["score"] if llm else 0
        x = lex[i]["score"] if use_lex else 0
        if use_llm and use_lex:
            s = fuse(l, x)
        elif use_llm:
            s = l
        else:
            s = x
        scores[i] = s
        ev = llm[i]["evidence"] if llm else ""
        if not ev and lex[i]["hits"] and use_lex:
            ev = "keyword match: " + ", ".join(lex[i]["hits"][:3])
        indicators[i] = {"llm": l if llm else None, "lex": lex[i]["score"], "fused": s,
                         "level": score_to_level(s), "evidence": ev,
                         "contribution": WEIGHTS[i] * s / 3.0 * 100}
    res = assess(scores, flags, use_tech=use_tech, use_rules=use_rules)
    llm_overall = str((llm_analysis or {}).get("overall_risk", "")).lower() or None
    floor_applied = False
    if use_llm and llm_floor and llm_overall in LEVELS and LEVELS.index(llm_overall) > LEVELS.index(res["risk_level"]):
        res["risk_level"] = llm_overall
        res["risk_score"] = _lift_score(res["risk_score"], llm_overall)
        floor_applied = True
    res.update({
        "llm_floor_applied": floor_applied,
        "indicators": indicators,
        "technical_flags": flags,
        "present": sorted(i for i in INDICATORS if scores[i] >= THRESH["present"]),
        "llm_overall_risk": llm_overall,
        "agrees_with_llm": (llm_overall == res["risk_level"]) if llm_overall else None,
        "recommended_action": CFG["actions"][res["risk_level"]],
    })
    res["explanation"] = explain(res["risk_level"], res["risk_score"], indicators, flags,
                                 res["rules_fired"], llm_overall)
    return res