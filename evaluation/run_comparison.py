"""
run_comparison.py

Compares the proposed hybrid framework against baselines and ablations on the full corpus
(49 chat = development set, 16 email = held-out test set):

    B0  naive prompt        one Gemini call: "is this spam / a threat?"                  (API call)
    B1  rules only          lexicon + technical checks + escalation rules, NO Gemini      (offline)
    B2  LLM only            Gemini's own overall_risk (your existing pipeline)            (API call)
    B3  hybrid (proposed)   Gemini indicators + lexicon + technical checks + rules
                            + "never lower Gemini's rating" floor                         (same call as B2)
    A1  hybrid w/o technical checks     A2  hybrid w/o rules     A3  score-only (no Gemini floor)
        (A1-A3 are computed from the SAME Gemini outputs, so they cost no extra calls)

Gemini calls are cached on disk (Code/.llm_cache), so the script is resumable and free to re-run.
Order of work: run 0 for ALL scenarios first, then run 1, then run 2 ... so if a daily quota cuts
you off you still have complete coverage of the first run.

Usage (from the Code/ folder):
    python3 evaluation/run_comparison.py --dry-run               # how many API calls are needed?
    python3 evaluation/run_comparison.py --repeats 1             # first full pass
    python3 evaluation/run_comparison.py --repeats 3             # adds consistency measurement
    python3 evaluation/run_comparison.py --source email          # only the held-out email set
    python3 evaluation/run_comparison.py --max-calls 150         # stop after N real API calls today
    python3 evaluation/run_comparison.py --report-only           # rebuild the Excel from cache, no calls
    (add --out-dir some/folder to write the outputs somewhere else)

Output:  evaluation/Framework_Comparison.xlsx, comparison_summary.json, comparison_summary.md
"""

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "framework"))
sys.path.append(HERE)

from full_corpus import ALL_CORPUS                      # noqa: E402
from hybrid import hybrid_assess, grounding             # noqa: E402
from pipeline import prepare_input                      # noqa: E402
import llm_client                                       # noqa: E402

ORD = {"low": 0, "medium": 1, "high": 2}
CONFIGS = ["B0 naive", "B1 rules-only", "B2 LLM-only", "B3 hybrid", "A1 no-technical", "A2 no-rules", "A3 score-only"]
HYBRID_KW = {
    "B3 hybrid": {},
    "A1 no-technical": {"use_tech": False},
    "A2 no-rules": {"use_rules": False},
    "A3 score-only": {"llm_floor": False},
}


def select(source, ids):
    sc = [s for s in ALL_CORPUS if source == "all" or s["channel"] == source]
    if ids:
        sc = [s for s in sc if s["id"] in ids]
    return sc


def text_of(s):
    return prepare_input(s["conversation"], s["meta"], s["channel"])


# ------------------------------------------------------------------ phase 1: API calls
def plan(scenarios, repeats, naive_repeats):
    """Ordered task list [(kind, scenario, run)], run 0 of everything first."""
    tasks = []
    for r in range(max(repeats, naive_repeats)):
        for s in scenarios:
            if r < repeats:
                tasks.append(("analysis", s, r))
            if r < naive_repeats:
                tasks.append(("naive", s, r))
    return tasks


def execute(tasks, sleep_s, max_calls):
    calls = errors = 0
    for n, (kind, s, r) in enumerate(tasks, 1):
        text = text_of(s)
        if llm_client.is_cached(kind, text, r):
            continue
        if max_calls is not None and calls >= max_calls:
            print(f"\nReached --max-calls {max_calls}. Re-run later; cached work is kept.")
            return calls, errors
        print(f"[{n}/{len(tasks)}] {kind} {s['id']} run {r} ...", end=" ", flush=True)
        try:
            if kind == "analysis":
                res, _ = llm_client.analyze_cached(text, run=r)
                print(res.get("overall_risk", "?"))
            else:
                res, _ = llm_client.naive_verdict(text, run=r)
                print(res["verdict"])
            calls += 1
            time.sleep(sleep_s)   # stay under the free-tier per-minute limit (real calls only)
        except Exception as e:    # keep going; a failed task is simply retried next run
            errors += 1
            msg = str(e)
            print("FAILED:", msg[:160].replace("\n", " "))
            if "RESOURCE_EXHAUSTED" in msg and "PerDay" in msg:
                print("\nDaily quota exhausted. Everything done so far is cached; re-run after the quota resets.")
                return calls, errors
    return calls, errors


# ------------------------------------------------------------------ phase 2: rows from cache (no API)
def build_rows(scenarios, repeats, naive_repeats):
    rows = []
    for s in scenarios:
        text = text_of(s)
        base = {"id": s["id"], "split": s["split"], "channel": s["channel"], "category": s["category"],
                "expected": s["expected_risk"]}
        # B1: deterministic, no Gemini
        h = hybrid_assess(text, s["meta"], None, use_llm=False)
        rows.append(dict(base, config="B1 rules-only", run=0, pred=h["risk_level"], score=round(h["risk_score"], 1),
                         flags="|".join(f["id"] for f in h["technical_flags"]),
                         rules="|".join(r["id"] for r in h["rules_fired"]), explanation=h["explanation"]))
        for r in range(repeats):
            if not llm_client.is_cached("analysis", text, r):
                continue
            an, _ = llm_client.analyze_cached(text, run=r)
            q, v = grounding(an, text)
            rows.append(dict(base, config="B2 LLM-only", run=r, pred=str(an.get("overall_risk", "")).lower()))
            for cfg, kw in HYBRID_KW.items():
                h = hybrid_assess(text, s["meta"], an, **kw)
                rows.append(dict(base, config=cfg, run=r, pred=h["risk_level"], score=round(h["risk_score"], 1),
                                 flags="|".join(f["id"] for f in h["technical_flags"]),
                                 rules="|".join(x["id"] for x in h["rules_fired"]),
                                 agrees=h["agrees_with_llm"], quotes=q, quotes_ok=v,
                                 explanation=h["explanation"]))
        for r in range(naive_repeats):
            if llm_client.is_cached("naive", text, r):
                nv, _ = llm_client.naive_verdict(text, run=r)
                rows.append(dict(base, config="B0 naive", run=r, pred=nv["risk_level"]))
    return rows


# ------------------------------------------------------------------ phase 3: metrics
def majority(preds):
    c = Counter(preds)
    top = max(c.values())
    return max((p for p, n in c.items() if n == top), key=lambda p: ORD.get(p, -1))  # tie -> safer (higher)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def per_scenario(rows):
    """{config: {id: (expected, majority_pred, consistency, n_runs)}}"""
    g = defaultdict(lambda: defaultdict(list))
    meta = {}
    for r in rows:
        if r["pred"] in ORD:
            g[r["config"]][r["id"]].append(r["pred"])
            meta[r["id"]] = r
    out = {}
    for cfg, d in g.items():
        out[cfg] = {}
        for sid, preds in d.items():
            m = majority(preds)
            out[cfg][sid] = (meta[sid]["expected"], m, preds.count(m) / len(preds), len(preds), meta[sid]["split"])
    return out


def metrics_for(items):
    """items: list of (expected, pred, consistency, n_runs)."""
    if not items:
        return {"n": 0}
    n = len(items)
    acc = sum(e == p for e, p, *_ in items) / n
    mae = sum(abs(ORD[e] - ORD[p]) for e, p, *_ in items) / n
    tp = sum(e != "low" and p != "low" for e, p, *_ in items)
    fp = sum(e == "low" and p != "low" for e, p, *_ in items)
    fn = sum(e != "low" and p == "low" for e, p, *_ in items)
    tn = sum(e == "low" and p == "low" for e, p, *_ in items)
    pr, rc, f1 = prf(tp, fp, fn)
    multi = [c for *_, c, k in items if k > 1]
    return {"n": n, "accuracy": acc, "ordinal_mae": mae, "precision": pr, "recall": rc, "f1": f1,
            "benign_fp_rate": fp / (fp + tn) if fp + tn else 0.0, "false_negatives": fn, "false_positives": fp,
            "consistency": (sum(multi) / len(multi)) if multi else None}


def summarize(rows):
    ps = per_scenario(rows)
    summary = {}
    for cfg in CONFIGS:
        if cfg not in ps:
            continue
        entry = {}
        for label, pick in (("ALL", lambda sp: True), ("dev (chat)", lambda sp: sp == "dev"), ("test (email)", lambda sp: sp == "test")):
            items = [(e, p, c, k) for (e, p, c, k, sp) in ps[cfg].values() if pick(sp)]
            entry[label] = metrics_for(items)
        summary[cfg] = entry
    b3 = [r for r in rows if r["config"] == "B3 hybrid"]
    extra = {}
    if b3:
        q = sum(r.get("quotes", 0) for r in b3)
        extra["quoted_evidence_spans"] = q
        extra["quoted_evidence_verified_rate"] = (sum(r.get("quotes_ok", 0) for r in b3) / q) if q else None
        ag = [r["agrees"] for r in b3 if r.get("agrees") is not None]
        extra["hybrid_agrees_with_llm_rate"] = (sum(ag) / len(ag)) if ag else None
    return summary, extra


def fmt(x):
    return "-" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))


def to_markdown(summary, extra, calls_info):
    L = ["# Framework comparison", "", calls_info, ""]
    for split in ("ALL", "dev (chat)", "test (email)"):
        L += [f"## {split}", "", "| Config | n | accuracy | ordinal MAE | precision | recall | F1 | benign FP rate | FN | consistency |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for cfg in CONFIGS:
            if cfg in summary and summary[cfg][split].get("n"):
                m = summary[cfg][split]
                L.append(f"| {cfg} | {m['n']} | {fmt(m['accuracy'])} | {fmt(m['ordinal_mae'])} | {fmt(m['precision'])} | "
                         f"{fmt(m['recall'])} | {fmt(m['f1'])} | {fmt(m['benign_fp_rate'])} | {m['false_negatives']} | {fmt(m['consistency'])} |")
        L.append("")
    if extra:
        L += ["Evidence grounding (B3): " + (f"{extra['quoted_evidence_spans']} quoted spans, "
              f"{fmt(extra['quoted_evidence_verified_rate'])} verified present in the input" if extra['quoted_evidence_spans'] else "no quoted spans found"),
              "Hybrid agrees with Gemini's own rating: " + fmt(extra.get("hybrid_agrees_with_llm_rate")), ""]
    L += ["Notes: metrics use the majority prediction per scenario across runs (ties -> higher risk). 'consistency' = share of "
          "runs agreeing with the majority. dev = used while designing the framework; test = held out (email). "
          "Positive class for precision/recall = medium or high."]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ phase 4: Excel
def write_excel(rows, summary, path):
    import pandas as pd
    from openpyxl.styles import Alignment, Font, PatternFill

    ps = per_scenario(rows)
    first = {}
    for r in rows:
        if r["config"] == "B3 hybrid" and r["run"] == 0:
            first[r["id"]] = r
    b1 = {r["id"]: r for r in rows if r["config"] == "B1 rules-only"}
    ids = []
    for r in rows:
        if r["id"] not in ids:
            ids.append(r["id"])
    scen = {s["id"]: s for s in ALL_CORPUS}
    table = []
    for sid in ids:
        s = scen[sid]
        row = {"Scenario ID": sid, "Split": s["split"], "Channel": s["channel"], "Category": s["category"],
               "Expected": s["expected_risk"]}
        for cfg in CONFIGS:
            row[cfg] = ps.get(cfg, {}).get(sid, (None, "",))[1]
        row["B3 consistency"] = ps.get("B3 hybrid", {}).get(sid, (0, 0, "", 0))[2]
        f = first.get(sid) or b1.get(sid) or {}
        row["B3 score"] = f.get("score", "")
        row["Technical flags"] = f.get("flags", "")
        row["Rules fired"] = f.get("rules", "")
        row["Hybrid explanation (run 0)"] = f.get("explanation", "")
        row["Input (preview)"] = s["conversation"].strip()[:300]
        row["Rationale"] = s["rationale"]
        table.append(row)
    df = pd.DataFrame(table)

    sum_rows = []
    for cfg in CONFIGS:
        for split in ("ALL", "dev (chat)", "test (email)"):
            m = summary.get(cfg, {}).get(split, {})
            if m.get("n"):
                sum_rows.append({"Config": cfg, "Split": split, "n": m["n"], "Accuracy": m["accuracy"],
                                 "Ordinal MAE": m["ordinal_mae"], "Precision": m["precision"], "Recall": m["recall"],
                                 "F1": m["f1"], "Benign FP rate": m["benign_fp_rate"], "False negatives": m["false_negatives"],
                                 "Consistency": m["consistency"]})
    sdf = pd.DataFrame(sum_rows)
    rdf = pd.DataFrame([{k: v for k, v in r.items() if k != "explanation"} for r in rows])

    with pd.ExcelWriter(path, engine="openpyxl") as w:
        sdf.to_excel(w, sheet_name="Summary", index=False)
        df.to_excel(w, sheet_name="Per-scenario", index=False)
        rdf.to_excel(w, sheet_name="Raw rows", index=False)
        head = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        for name in ("Summary", "Per-scenario", "Raw rows"):
            ws = w.sheets[name]
            for c in ws[1]:
                c.fill, c.font = head, Font(color="FFFFFF", bold=True)
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(60, max(10, max(len(str(c.value or "")) for c in col[:30]) * 0.9))
        ws = w.sheets["Per-scenario"]
        green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        cols = {c.value: c.column for c in ws[1]}
        for rn in range(2, ws.max_row + 1):
            exp = ws.cell(rn, cols["Expected"]).value
            for cfg in CONFIGS:
                if cfg in cols:
                    cell = ws.cell(rn, cols[cfg])
                    if cell.value:
                        cell.fill = green if cell.value == exp else red
            for cell in ws[rn]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for name in ("Hybrid explanation (run 0)", "Input (preview)", "Rationale"):
            ws.column_dimensions[ws.cell(1, cols[name]).column_letter].width = 55


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=3, help="Gemini analysis runs per scenario (default 3)")
    ap.add_argument("--naive-repeats", type=int, default=1, help="runs of the naive baseline (default 1)")
    ap.add_argument("--source", choices=["all", "chat", "email"], default="all")
    ap.add_argument("--ids", nargs="*", help="only these scenario ids")
    ap.add_argument("--sleep", type=float, default=13.0, help="seconds to wait after each REAL API call")
    ap.add_argument("--max-calls", type=int, default=None, help="stop after this many real API calls")
    ap.add_argument("--dry-run", action="store_true", help="only print how many API calls are needed")
    ap.add_argument("--report-only", action="store_true", help="skip API calls; build report from cache")
    ap.add_argument("--out-dir", default=HERE, help="where to write the Excel / summary files (default: evaluation/)")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    scenarios = select(a.source, a.ids)
    tasks = plan(scenarios, a.repeats, a.naive_repeats)
    todo = [t for t in tasks if not llm_client.is_cached(t[0], text_of(t[1]), t[2])]
    print(f"Model: {llm_client.MODEL_NAME}")
    print(f"Scenarios: {len(scenarios)} | planned Gemini calls: {len(tasks)} | already cached: {len(tasks) - len(todo)} "
          f"| still needed: {len(todo)} (~{len(todo) * a.sleep / 60:.0f} min at {a.sleep:.0f}s spacing)")
    if a.dry_run:
        by = Counter((k, r) for k, _, r in todo)
        for (k, r), n in sorted(by.items(), key=lambda x: (x[0][1], x[0][0])):
            print(f"   still needed: {k} run {r}: {n} calls")
        return

    calls = errors = 0
    if not a.report_only:
        calls, errors = execute(tasks, a.sleep, a.max_calls)
        print(f"\nReal API calls made now: {calls}; failed: {errors}")

    rows = build_rows(scenarios, a.repeats, a.naive_repeats)
    summary, extra = summarize(rows)
    remaining = len([t for t in plan(scenarios, a.repeats, a.naive_repeats) if not llm_client.is_cached(t[0], text_of(t[1]), t[2])])
    info = (f"Model {llm_client.MODEL_NAME}; scenarios {len(scenarios)}; repeats {a.repeats}; "
            f"calls still missing: {remaining} " + ("(RESULTS INCOMPLETE)" if remaining else "(complete)"))
    md = to_markdown(summary, extra, info)
    print("\n" + md)
    with open(os.path.join(a.out_dir, "comparison_summary.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(a.out_dir, "comparison_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "extra": extra, "info": info}, f, indent=2)
    out = os.path.join(a.out_dir, "Framework_Comparison.xlsx")
    write_excel(rows, summary, out)
    print("Excel written to:", out)


if __name__ == "__main__":
    main()