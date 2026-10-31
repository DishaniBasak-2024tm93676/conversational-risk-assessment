"""
run_evaluation.py

Runs every scenario in corpus.py through the full pipeline, checkpointing
results to a JSON file after each one — so if a daily API quota limit is hit
partway through, nothing already completed is lost. Re-running this script
automatically skips scenarios already recorded in the checkpoint file and
continues from where it left off.

Setup (one-time):
    pip3 install pandas openpyxl

Usage:
    python3 evaluation/run_evaluation.py
    (safe to run again later — it will resume, not restart)

Output:
    evaluation/checkpoint_results.json   (raw results, safe to re-run against)
    evaluation/Framework_Evaluation_Matrix.xlsx   (final formatted matrix)
"""

import sys
import os
import json
import time
import pandas as pd
from openpyxl.styles import PatternFill, Font, Alignment

# The framework/ package (pipeline.py, llm_client.py, preprocessing.py) lives
# one level up from evaluation/, as a sibling folder rather than a
# sub-package — so it isn't importable by name until its folder is added to
# sys.path. This line does that, relative to this file's own location, so it
# works no matter where the script is run from.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "framework"))
from pipeline import run_pipeline

# CORPUS is the list of all 49 scenario dicts (text, category, domains,
# expected_risk, rationale) — defined once in corpus.py and imported here so
# this script and corpus.py never fall out of sync with each other.
from corpus import CORPUS

# Checkpoint file: a running log of every scenario's result so far, keyed by
# scenario id. Read at the start of a run to decide what to skip; written
# after every single scenario (not just at the end) so a crash or quota cutoff
# never loses more than the one scenario in flight.
CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), "checkpoint_results.json")

# Final human-readable deliverable: the formatted Excel matrix built from
# whatever is in the checkpoint once the run (or resume) finishes.
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "Framework_Evaluation_Matrix.xlsx")


def load_checkpoint():
    """Loads already-completed results from a previous run, if any exist."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {}     # First-ever run: no checkpoint file yet, start from an empty record.


def save_checkpoint(checkpoint):
    """Saves current progress to disk immediately after each scenario."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)


def run_full_evaluation():
    checkpoint = load_checkpoint()
    total = len(CORPUS)
    already_done = len(checkpoint)
    if already_done:
        print(f"Resuming: {already_done}/{total} scenarios already completed in a previous run.\n")

    for i, scenario in enumerate(CORPUS):
        scenario_id = scenario["id"]

        # Only skip if this scenario previously SUCCEEDED. A scenario that
        # errored before (e.g. a dropped network connection) should be
        # retried, not permanently skipped just because it exists in the
        # checkpoint file.
        #
        # This is also why checkpointing does NOT, by itself, explain
        # "same scenario run twice gives a different result" — a scenario
        # that already succeeded is never re-run through this script again.
        # Any observed run-to-run variability has to come from somewhere
        # else (e.g. manual re-testing through the Streamlit app, or
        # deliberately re-running a specific scenario as a sanity check),
        # not from this skip/retry logic.
        already_succeeded = (
            scenario_id in checkpoint and checkpoint[scenario_id].get("Match?") != "ERROR"
        )
        if already_succeeded:
            print(f"[{i + 1}/{total}] {scenario_id} — already done, skipping.")
            continue

        print(f"[{i + 1}/{total}] Running {scenario_id} ({scenario['category']})...")

        # Pre-fill the row with everything known about the scenario BEFORE
        # it's run — the expected risk and rationale were fixed at corpus
        # design time, independent of what the pipeline is about to return.
        # This is what lets the report claim "expectations fixed before
        # seeing results."
        row = {
            "Scenario ID": scenario_id,
            "Category": scenario["category"],
            "Domain(s) Demonstrated": ", ".join(scenario["domains"]),
            "Input Conversation": scenario["conversation"].strip(),
            "Expected Risk": scenario["expected_risk"],
            "Rationale": scenario["rationale"],
        }

        try:
            # This is the exact same call app.py makes on a button click —
            # the evaluation harness exercises the real production pipeline,
            # not a separate test-only code path.
            result = run_pipeline(scenario["conversation"])
            analysis = result["analysis"]

            actual_risk = analysis.get("overall_risk", "ERROR")
            matches_expected = (actual_risk == scenario["expected_risk"])

            # Pull out just the indicators that actually fired at a
            # noteworthy level, for a compact "what tripped this" summary
            # column — the full per-indicator detail still lives in the
            # "Full JSON" column below if anyone needs to dig deeper.
            indicators = analysis.get("indicators", {})
            flagged_indicators = [
                name for name, details in indicators.items()
                if details.get("level") in ("medium", "high")
            ]

            row.update({
                "Actual Risk": actual_risk,
                "Match?": "YES" if matches_expected else "NO - REVIEW",
                "Flagged Indicators": ", ".join(flagged_indicators) if flagged_indicators else "(none)",
                "Explanation": analysis.get("explanation", ""),
                "Recommended Action": analysis.get("recommended_action", ""),
                "Full JSON (for reference)": json.dumps(analysis), # Keep the raw model output around too, so a mismatch can be
                                                                   # fully re-inspected later without having to re-run the API call.
            })
            print(f"  -> {actual_risk} (expected {scenario['expected_risk']}) "
                  f"{'MATCH' if matches_expected else 'MISMATCH'}")

        except Exception as e:
            # Anything can go wrong here — a network hiccup, a malformed JSON response, an API error. Record it as 
            # an explicit ERROR row rather than letting the whole script crash and lose progress on every scenario
            #  after this one.
            row.update({
                "Actual Risk": "ERROR",
                "Match?": "ERROR",
                "Flagged Indicators": "",
                "Explanation": f"Scenario failed: {e}",
                "Recommended Action": "",
                "Full JSON (for reference)": "",
            })
            print(f"  ⚠️  {scenario_id} failed: {e}")

            # Special case: the free-tier API's DAILY quota (not the per-minute one llm_client.py's retry logic 
            # already handles) has been exhausted. There's no point continuing to try the remaining scenarios today — 
            # save what's done and stop cleanly so tomorrow's run can resume exactly here.
            if "RESOURCE_EXHAUSTED" in str(e) and "PerDay" in str(e):
                checkpoint[scenario_id] = row
                save_checkpoint(checkpoint)
                print("\n⚠️  Daily quota limit reached. Progress saved. "
                      "Re-run this script after the quota resets to continue.")
                return checkpoint

        # Save after EVERY scenario (success or ordinary error), not just at the end of the loop — this is what 
        # makes the run resumable: at most one scenario's work is ever at risk if the script is interrupted unexpectedly.
        checkpoint[scenario_id] = row
        save_checkpoint(checkpoint)

        # A small pause between API calls to stay comfortably under the free tier's per-minute rate limit 
        # — skipped after the very last scenario since there's nothing left to wait for.
        is_last = (i == total - 1)
        if not is_last:
            time.sleep(13)

    return checkpoint


def write_excel_matrix(checkpoint, output_path):
    """Formats the checkpoint's raw dict of results into the polished,
    reviewer-facing Framework_Evaluation_Matrix.xlsx."""
    rows = list(checkpoint.values())
    df = pd.DataFrame(rows)

    # Explicit column order for the spreadsheet — dict insertion ordernisn't guaranteed to match what's easiest 
    # to read left-to-right (expected vs. actual risk should sit next to each other, for example).
    column_order = [
        "Scenario ID", "Category", "Domain(s) Demonstrated", "Input Conversation",
        "Expected Risk", "Actual Risk", "Match?",
        "Flagged Indicators", "Explanation", "Recommended Action",
        "Rationale", "Full JSON (for reference)",
    ]
    df = df[[c for c in column_order if c in df.columns]]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Evaluation Matrix", index=False)
        worksheet = writer.sheets["Evaluation Matrix"]
       
        # Manually tuned column widths so long text (conversations, explanations) doesn't get truncated or 
        # wrapped into an unreadable sliver of a column.
        widths = {
            "Scenario ID": 12, "Category": 20, "Domain(s) Demonstrated": 25,
            "Input Conversation": 45, "Expected Risk": 12, "Actual Risk": 12,
            "Match?": 12, "Flagged Indicators": 30, "Explanation": 45,
            "Recommended Action": 40, "Rationale": 40, "Full JSON (for reference)": 30,
        }
        for i, col in enumerate(df.columns):
            worksheet.column_dimensions[chr(65 + i)].width = widths.get(col, 20)

        # Header row styling: blue fill, white bold text.
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font

        # Wrap text and top-align every data cell so multi-line conversation
        # transcripts and explanations are fully visible, not cut off.
        for row_cells in worksheet.iter_rows(min_row=2):
            for cell in row_cells:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

        # Color the "Match?" column green/red so a reviewer can scan the whole matrix at a glance without 
        # reading every row's text.
        match_col_index = df.columns.get_loc("Match?") + 1
        green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        for row_num in range(2, len(df) + 2):
            cell = worksheet.cell(row=row_num, column=match_col_index)
            cell.fill = green_fill if cell.value == "YES" else red_fill

        # Note: anything not exactly "YES" (including "NO - REVIEW" and "ERROR") is colored red here — both 
        # genuine mismatches and run failures stand out the same way, by design, so neither
        # gets missed on a quick visual scan.

    print(f"\nDone. Evaluation matrix written to: {output_path}")


if __name__ == "__main__":
    results = run_full_evaluation()

    # Only count/write entries that correspond to scenarios currently in the
    # corpus - protects against stale leftover checkpoint entries if the
    # corpus itself was edited between runs.
    current_ids = {s["id"] for s in CORPUS}
    results = {k: v for k, v in results.items() if k in current_ids}

    write_excel_matrix(results, OUTPUT_FILE)

    # Final console summary — a quick sanity check printed right after the
    # run, independent of actually opening the generated spreadsheet.
    total_run = len(results)
    matched = sum(1 for r in results.values() if r.get("Match?") == "YES")
    errored = sum(1 for r in results.values() if r.get("Match?") == "ERROR")
    print(f"\nSummary: {matched}/{len(CORPUS)} matched expected risk. "
          f"{errored} errored. {len(CORPUS) - total_run} not yet run.")