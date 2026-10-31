"""
smoke_test_offline.py  -  checks that the whole pipeline is wired correctly WITHOUT an API key.

It replaces the Gemini call with a deterministic FAKE model (lexicon-based), uses a throw-away
cache folder and output folder, and runs the comparison on all 65 scenarios.
The numbers it prints are meaningless for the dissertation - it only proves the plumbing works
(imports, caching, resume, Excel writing).  Real results come from run_comparison.py.

Usage (from Code/):   python3 tools/smoke_test_offline.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "framework"), os.path.join(ROOT, "evaluation")]

import llm_client                                  # noqa: E402
from hybrid import lexical_scores, INDICATORS      # noqa: E402

LEVEL = ["none", "low", "medium", "high"]
CALLS = {"n": 0}


def fake_generate(contents, system_prompt, temperature=0.2):
    CALLS["n"] += 1
    lex = lexical_scores(contents)
    if system_prompt == llm_client.NAIVE_PROMPT:
        return {"verdict": "threat" if sum(v["score"] for v in lex.values()) >= 4 else "safe"}
    ind = {i: {"level": LEVEL[lex[i]["score"]], "evidence": ("'" + lex[i]["hits"][0] + "'") if lex[i]["hits"] else "none"}
           for i in INDICATORS}
    total = sum(lex[i]["score"] for i in INDICATORS)
    return {"context": {"domain": "other", "confidence": "low"}, "indicators": ind,
            "overall_risk": "high" if total >= 6 else "medium" if total >= 3 else "low",
            "explanation": "fake", "recommended_action": "fake"}


tmp = tempfile.mkdtemp(prefix="smoke_")
llm_client._generate = fake_generate
llm_client.CACHE_DIR = os.path.join(tmp, "cache")

import run_comparison                              # noqa: E402

for label in ("first pass", "second pass (must use cache only)"):
    before = CALLS["n"]
    sys.argv = ["run_comparison.py", "--repeats", "2", "--naive-repeats", "1", "--sleep", "0", "--out-dir", os.path.join(tmp, "out")]
    run_comparison.main()
    print(f"\n>>> {label}: fake model calls made = {CALLS['n'] - before}\n" + "=" * 70)

assert os.path.exists(os.path.join(tmp, "out", "Framework_Comparison.xlsx")), "Excel was not written"
assert CALLS["n"] == 65 * 2 + 65, f"unexpected call count {CALLS['n']} (expected 195 on first pass only)"
print("SMOKE TEST PASSED: pipeline, cache/resume and Excel output all work. Outputs in", tmp)