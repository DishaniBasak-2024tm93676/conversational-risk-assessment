"""
scenario_tests.py

Runs the full pipeline (framework/pipeline.py) against a small set of varied
conversation scenarios, matching the categories already defined in the
Companion's dataset strategy: job recruitment scam, investment scam, tech
support scam, delivery scam, government impersonation, and a tricky benign
case (urgent, but NOT manipulative — a real stress test, not an easy example).

This is informal, manual testing to check the framework behaves sensibly
across variety, ahead of the formal 15-30 scenario Conversation Evaluation
Corpus built later.

Usage:
    python3 evaluation/scenario_tests.py
"""

import sys
import os
import json
import time

# framework/ is a separate folder from evaluation/, so Python doesn't know to
# look there by default. sys.path is the list of folders Python searches when
# resolving an "import" — this line adds the framework/ folder to that list,
# so "from pipeline import run_pipeline" below can find it.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "framework"))

from pipeline import run_pipeline


SCENARIOS = {
    "Job recruitment scam": """
    Recruiter: Congratulations! You've been selected for a work-from-home data entry role.
    Recruiter: To finalize your onboarding, please pay a refundable registration fee of Rs. 2000 today.
    """,

    "Investment scam": """
    Advisor: I have an exclusive crypto investment opportunity with guaranteed 40% monthly returns.
    Advisor: Only 3 slots left today — transfer funds now to secure your spot before it closes.
    """,

    "Tech support scam": """
    Support: We detected a virus on your computer that is stealing your banking data right now.
    Support: Please install our remote access tool immediately so we can fix this before it spreads.
    """,

    "Delivery scam": """
    Delivery: Your package could not be delivered due to an unpaid customs fee of Rs. 150.
    Delivery: Click the link below within 24 hours to pay, or the package will be returned.
    """,

    "Government impersonation": """
    Officer: This is an urgent notice from the Income Tax Department regarding a pending case against you.
    Officer: To avoid arrest, you must settle the outstanding amount immediately via the link provided.
    """,

    "Tricky benign case (urgent but legitimate)": """
    Airline: Reminder: your flight AI202 is now boarding at Gate 14. Final boarding call in 10 minutes.
    Airline: Please proceed to the gate immediately with your boarding pass and ID.
    """,

    # additions: deliberately ambiguous/borderline scenarios.
    # Every scenario above landed on either "high" or "low" overall_risk — these
    # are designed to test whether the framework can also reason toward "medium," 
    # and whether its explanations stay calibrated (not alarmist) on a genuinely uncertain case.

    "Borderline: friend asking for a loan": """
    Rohan: Hey, sorry to ask but I'm a bit short this month, could you send me 2000 rupees?
    Rohan: I'll pay you back next week when my salary comes in, promise.
    """,

    "Borderline: unexpected prize notification": """
    Contest: You've been randomly selected as a winner in our monthly customer draw!
    Contest: Reply with your full name and address so we can arrange delivery of your prize.
    """,

    "Borderline: slightly pushy but real-looking sale": """
    Store: Hi! Your cart has an item still waiting - our 20% discount code ends tonight at midnight.
    Store: Use code SAVE20 at checkout before it expires, no rush if you're not interested.
    """,
}


if __name__ == "__main__":
    # The Gemini free tier allows a maximum of 5 requests per minute on this
    # model. Running all scenarios back-to-back with no pause would exceed
    # that limit (a real "429 RESOURCE_EXHAUSTED" error was hit here) — so a
    # 13-second pause is added between each request to stay safely under it
    # (60 seconds / 5 requests = 12 seconds minimum spacing; 13 gives a margin).
    scenario_list = list(SCENARIOS.items())
    for i, (name, conversation) in enumerate(scenario_list):
        print(f"\n{'=' * 60}")
        print(f"SCENARIO: {name}")
        print("=" * 60)
        
        # A bad response from Gemini (e.g. malformed JSON) previously crashed
        # this entire script, losing every result that hadn't printed yet.
        # Wrapping just this one scenario in try/except means one failure is
        # skipped and reported, while the rest of the scenarios still run.
        try:
            result = run_pipeline(conversation)
            print(json.dumps(result["analysis"], indent=2))
        except Exception as e:
            print(f"⚠️  SKIPPED — this scenario failed: {e}")
 
        is_last_scenario = (i == len(scenario_list) - 1)
        if not is_last_scenario:
            print("\n(waiting 13 seconds to stay under the free-tier rate limit...)")
            time.sleep(13)
            