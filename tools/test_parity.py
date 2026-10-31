"""
test_parity.py - proves the Gmail add-on logic (Core.gs) gives the SAME results as the Python
reference (hybrid.py) on every scenario and 5 configurations (hybrid, rules-only, no-technical,
no-rules, score-only).  Needs Node.js.

    python3 tools/test_parity.py

Chat scenarios use YOUR saved Gemini outputs from evaluation/checkpoint_results.json;
email scenarios (no saved output yet) use a deterministic lexicon-based stand-in. Only the
agreement between the two implementations matters here, not the numbers.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "framework"), os.path.join(ROOT, "evaluation")]

from full_corpus import ALL_CORPUS            # noqa: E402
from pipeline import prepare_input            # noqa: E402
from hybrid import hybrid_assess, lexical_scores, redact, INDICATORS   # noqa: E402

subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_addon.py")], check=True, capture_output=True)

saved = {}
ck = os.path.join(ROOT, "evaluation", "checkpoint_results.json")
if os.path.exists(ck):
    for sid, row in json.load(open(ck, encoding="utf-8")).items():
        if row.get("Full JSON (for reference)"):
            saved[sid] = json.loads(row["Full JSON (for reference)"])

LEVEL = ["none", "low", "medium", "high"]


def stand_in(text):
    lex = lexical_scores(text)
    t = sum(v["score"] for v in lex.values())
    return {"indicators": {i: {"level": LEVEL[lex[i]["score"]], "evidence": ("'" + lex[i]["hits"][0] + "'") if lex[i]["hits"] else ""} for i in INDICATORS},
            "overall_risk": "high" if t >= 6 else "medium" if t >= 3 else "low"}


cases = []
for s in ALL_CORPUS:
    text = prepare_input(s["conversation"], s["meta"], s["channel"])
    cases.append({"id": s["id"], "text": text, "meta": s["meta"], "analysis": saved.get(s["id"]) or stand_in(text)})
fx = os.path.join(tempfile.mkdtemp(), "cases.json")
json.dump(cases, open(fx, "w"))
js = json.loads(subprocess.run(["node", os.path.join(ROOT, "tools", "parity.js"), fx], check=True, capture_output=True, text=True).stdout)

KW = {"hybrid": {}, "rules": {"use_llm": False}, "noTech": {"use_tech": False}, "noRules": {"use_rules": False}, "scoreOnly": {"llm_floor": False}}
bad = total = 0
for c in cases:
    if js[c["id"]]["redacted"] != redact(c["text"]):
        bad += 1; print(c["id"], "redaction differs")
    for k, kw in KW.items():
        total += 1
        p = hybrid_assess(c["text"], c["meta"], None if k == "rules" else c["analysis"], **kw)
        j = js[c["id"]][k]
        problems = []
        if abs(p["risk_score"] - j["risk_score"]) > 1e-6: problems.append(f"score {p['risk_score']:.3f} vs {j['risk_score']:.3f}")
        if p["risk_level"] != j["risk_level"]: problems.append(f"level {p['risk_level']} vs {j['risk_level']}")
        if p["present"] != j["present"]: problems.append("present differs")
        if [f["id"] for f in p["technical_flags"]] != j["flags"]: problems.append("flags differ")
        if [r["id"] for r in p["rules_fired"]] != j["rules"]: problems.append("rules differ")
        if p["llm_floor_applied"] != j["floor"]: problems.append("floor differs")
        if problems:
            bad += 1; print(c["id"], k, "; ".join(problems))
print(f"parity: {total - bad}/{total} scenario x configuration checks identical ({len(cases)} scenarios, {len(saved)} with your saved Gemini output)")
sys.exit(1 if bad else 0)