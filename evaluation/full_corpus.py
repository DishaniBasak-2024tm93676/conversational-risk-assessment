"""
full_corpus.py

One list with every scenario: the 49 chat scenarios from corpus.py (development set) and the
16 email scenarios from email_corpus.py (held-out test set). corpus.py itself is NOT modified, so
run_evaluation.py keeps working exactly as before.

Every item has: id, category, domains, conversation, expected_risk, rationale,
                channel ("chat" | "email"), meta ({} for chat), split ("dev" | "test")
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from corpus import CORPUS as _CHAT
from email_corpus import EMAIL_CORPUS as _EMAIL

ALL_CORPUS = (
    [dict(s, channel="chat", meta={}, split="dev") for s in _CHAT]
    + [dict(s, split="test") for s in _EMAIL]
)

if __name__ == "__main__":
    from collections import Counter
    print(len(ALL_CORPUS), "scenarios;", dict(Counter(s["split"] for s in ALL_CORPUS)))