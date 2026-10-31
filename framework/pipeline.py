"""
pipeline.py
Connecting Pre-processing and LLM Analysis into one end-to-end pipeline.

Usage:
    from pipeline import run_pipeline
    result = run_pipeline(raw_text)

ADDED (hybrid extension):
    run_hybrid(raw_text, meta=None, channel="chat", run=0)
        -> same Gemini analysis, PLUS technical email checks, fusion, escalation rules and a
           traceable explanation (see hybrid.py). `run_pipeline` below is unchanged.
"""

from preprocessing import preprocess_conversation
from llm_client import analyze_conversation


def build_llm_input(turns: list[dict]) -> str:
    """
    Rebuilds a clean, consistently-formatted "Speaker: message" string from the
    structured turns produced by preprocessing.py. This is what actually gets
    sent to Gemini — not the raw pasted text — so the AI always receives
    predictable, normalized input regardless of how messy the original paste was.
    """
    lines = [f"{turn['speaker']}: {turn['message']}" for turn in turns]
    return "\n".join(lines)


def run_pipeline(raw_text: str) -> dict:
    """
    Runs the full pipeline on a raw pasted conversation:
        1. Pre-processes and structures the text
        2. Rebuilds a clean version for the AI
        3. Sends it to Gemini for manipulation-risk analysis

    Returns a dict containing both the pre-processing details and the final
    analysis, so nothing is lost along the way (useful for debugging and later
    for the evaluation matrix).
    """
    preprocessed = preprocess_conversation(raw_text)
    llm_input_text = build_llm_input(preprocessed["turns"])
    analysis = analyze_conversation(llm_input_text)

    return {
        "preprocessing": preprocessed,
        "llm_input_text": llm_input_text,
        "analysis": analysis,
    }


# ----------------------------------------------------------------- hybrid extension
def build_email_input(meta: dict, body: str) -> str:
    """Email text for the LLM. Chat 'Speaker:' parsing is deliberately NOT used for email
    (a line like 'Note: ...' would be mistaken for a speaker). Mailbox names and long numbers
    are masked first (privacy by design); the sender DOMAIN is kept because it is evidence."""
    from hybrid import redact, CFG
    parts = ["[Email]"]
    if meta.get("from"):
        parts.append("From: " + redact(meta["from"]))
    if meta.get("subject"):
        parts.append("Subject: " + meta["subject"])
    text = "\n".join(parts) + "\n\n" + (body or "").strip()
    return redact(text)[: CFG["max_chars"]]


def prepare_input(raw_text: str, meta: dict = None, channel: str = "chat") -> str:
    """The exact text sent to Gemini and analysed locally (one function so that the
    evaluation, the Streamlit app and the cache all agree on it)."""
    if channel == "email":
        return build_email_input(meta or {}, raw_text)
    return build_llm_input(preprocess_conversation(raw_text)["turns"])


def run_hybrid(raw_text: str, meta: dict = None, channel: str = "chat", run: int = 0,
               cached: bool = True) -> dict:
    """
    Full framework run:
        prepare_input -> Gemini analysis (disk-cached) -> hybrid_assess
    `meta` (optional, email): from, reply_to, auth, subject, attachments[], links[{text, href}]
    """
    from hybrid import hybrid_assess, grounding
    from llm_client import analyze_cached

    meta = meta or {}
    llm_input_text = prepare_input(raw_text, meta, channel)
    if cached:
        analysis, from_cache = analyze_cached(llm_input_text, run=run)
    else:
        analysis, from_cache = analyze_conversation(llm_input_text), False
    result = hybrid_assess(llm_input_text, meta, analysis)
    quoted, verified = grounding(analysis, llm_input_text)
    return {
        "llm_input_text": llm_input_text,
        "analysis": analysis,
        "hybrid": result,
        "from_cache": from_cache,
        "evidence_quotes": quoted,
        "evidence_quotes_verified": verified,
    }


if __name__ == "__main__":
    import json

    # Test 1: the same malicious banking example used in earlier milestones,
    # but this time typed messily on purpose to prove the full pipeline
    # (cleaning + structuring + analysis) works together, not just each piece alone.
    malicious_sample = """

    Bank:   Your account will be suspended in 10 minutes due to suspicious activity.


    Bank: Please confirm your OTP immediately to prevent permanent account closure.
    """

    # Test 2: an ordinary, benign conversation — no manipulation at all.
    # Important per the Companion's dataset strategy (Milestone 1.10, §1.10.8):
    # the framework must also correctly recognize SAFE conversations, not just
    # flag everything as risky.
    benign_sample = """
    Riya: Hey, are we still on for dinner tonight?
    Aman: Yeah! 8pm works for me, same place as last time?
    Riya: Perfect, see you then.
    """

    print("=== Test 1: malicious banking scenario ===")
    result_1 = run_pipeline(malicious_sample)
    print(json.dumps(result_1["analysis"], indent=2))

    print("\n=== Test 2: benign conversation ===")
    result_2 = run_pipeline(benign_sample)
    print(json.dumps(result_2["analysis"], indent=2))