"""
offline_replay.py

Runs the new deterministic layer on the Gemini outputs you ALREADY saved in
evaluation/checkpoint_results.json (your 49 chat scenarios). No API calls, no key, no quota.

Use it to (1) sanity-check the new layer today and (2) see the ablation on real model outputs.
CAUTION for the report: those outputs were produced on 13 Sep 2026, before the Oct 10 edit of
llm_client.py, and from a single run. This is a DEVELOPMENT-SET check, not the final evaluation:
the final numbers must come from run_comparison.py.

    python3 evaluation/offline_replay.py
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "framework"))
from hybrid import hybrid_assess                      # noqa: E402
from pipeline import prepare_input                    # noqa: E402

ORD = {"low": 0, "medium": 1, "high": 2}
CONFIGS = [("B1 rules-only", {"use_llm": False}), ("B3 hybrid", {}), ("A1 no-technical", {"use_tech": False}),
           ("A2 no-rules", {"use_rules": False}), ("A3 score-only", {"llm_floor": False})]

ck = json.load(open(os.path.join(HERE, "checkpoint_results.json"), encoding="utf-8"))
rows = [(sid, r) for sid, r in ck.items() if r.get("Full JSON (for reference)")]
print(f"{len(rows)} saved scenarios (chat, development set)\n")
print(f"{'config':16s} {'accuracy':>8s} {'ordMAE':>7s} {'FP':>3s} {'FN':>3s}  wrong")


def line(name, pairs):
    n = len(pairs)
    acc = sum(e == p for _, e, p in pairs) / n
    mae = sum(abs(ORD[e] - ORD[p]) for _, e, p in pairs) / n
    fp = sum(e == "low" and p != "low" for _, e, p in pairs)
    fn = sum(e != "low" and p == "low" for _, e, p in pairs)
    wrong = ", ".join(f"{i}({e}->{p})" for i, e, p in pairs if e != p)
    print(f"{name:16s} {acc:8.2f} {mae:7.2f} {fp:3d} {fn:3d}  {wrong[:110]}")


line("B2 LLM-only", [(sid, r["Expected Risk"], json.loads(r["Full JSON (for reference)"])["overall_risk"]) for sid, r in rows])
for name, kw in CONFIGS:
    pairs = []
    for sid, r in rows:
        an = json.loads(r["Full JSON (for reference)"])
        text = prepare_input(r["Input Conversation"], {}, "chat")
        pairs.append((sid, r["Expected Risk"], hybrid_assess(text, {}, None if kw.get("use_llm") is False else an, **kw)["risk_level"]))
    line(name, pairs)
print("\nReading it: the deterministic layer cannot add much on chat (no headers or links exist in a pasted chat);"
      "\nits value is tested on the held-out EMAIL set via run_comparison.py.")