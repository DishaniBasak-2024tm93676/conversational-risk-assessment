"""
llm_client.py

Wraps the Google Gemini API call for analysis step
(context classification, manipulation indicator assessment, multi-dimensional
risk, and plain-language explanation) in one structured JSON response.

Setup:
    pip install -r requirements.txt
    Add GEMINI_API_KEY=your-key-here to a .env file in the Code/ root.

Usage:
    from llm_client import analyze_conversation
    result = analyze_conversation(conversation_text)

ADDED (Oct 2026, hybrid extension) - everything above still works exactly as before:
    analyze_cached(text, run=0)  -> (result, from_cache)   same analysis, saved to disk by input
    naive_verdict(text, run=0)   -> (result, from_cache)   the "is this spam?" baseline prompt
  Why cache: free-tier daily quota is small. With the cache, re-running an evaluation never pays
  twice for the same (model, prompt, text, run) and a quota cut-off simply resumes next day.
  The cache lives in Code/.llm_cache/ (delete the folder to force fresh calls).
"""

import os
import json
import time
import hashlib
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

# Model retired: gemini-2.5-flash (no longer available to new API keys as of Aug 2026)
# Switched from gemini-3.6-flash to gemini-3.1-flash-lite (Sep 2026): the Flash
# tier's free daily quota was found to be only 20 requests/day (discovered via
# a live 429 RESOURCE_EXHAUSTED error during bulk evaluation testing) — far too
# low for running dozens of scenarios. Flash-Lite models carry a higher free
# daily quota, needed specifically for the bulk Conversation Evaluation Corpus
# runs. If this model's quota also proves insufficient, the
# fallback is gemini-2.5-flash-lite (confirmed available to this API key via
# check_models.py).
# (Can be overridden without editing code:  export GEMINI_MODEL=gemini-2.5-flash-lite)
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
TEMPERATURE = 0.2

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".llm_cache")

SYSTEM_PROMPT = """You are an analysis component inside a decision-support tool that helps \
ordinary users assess whether a digital conversation (chat, SMS, or email) shows signs of \
social engineering, digital manipulation, or AI-assisted fraud.

Your role is strictly limited to ANALYSIS. You do not decide anything on the user's behalf, \
you do not take action, and you must not claim certainty. You support human judgement — you \
do not replace it.

Assess the conversation against exactly these six manipulation indicators. Do not invent \
additional indicators:
1. authority_claims — sender claims to represent a bank, government body, employer, or other authority
2. urgency — pressure to act immediately, artificial deadlines
3. fear_threat — threats of loss, account suspension, legal trouble, harm
4. sensitive_info_requests — requests for passwords, OTPs, bank details, personal identifiers
5. emotional_pressure — guilt, sympathy, excitement, flattery used to influence a decision
6. financial_pressure — requests for money, payment, investment, or financial action

For each indicator, ground your judgement in a short quote or close paraphrase from the \
conversation itself — do not assert a level without evidence from the text.

If the conversation is ordinary and benign (e.g. friends chatting, routine scheduling, normal \
customer support), say so plainly — do not manufacture risk where none exists.

Return ONLY valid JSON matching this exact schema, with no extra commentary:

{
  "context": {"domain": "banking|job_offer|delivery|investment|government|tech_support|other|benign", "confidence": "low|medium|high"},
  "indicators": {
    "authority_claims": {"level": "none|low|medium|high", "evidence": "string"},
    "urgency": {"level": "none|low|medium|high", "evidence": "string"},
    "fear_threat": {"level": "none|low|medium|high", "evidence": "string"},
    "sensitive_info_requests": {"level": "none|low|medium|high", "evidence": "string"},
    "emotional_pressure": {"level": "none|low|medium|high", "evidence": "string"},
    "financial_pressure": {"level": "none|low|medium|high", "evidence": "string"}
  },
  "overall_risk": "low|medium|high",
  "explanation": "string",
  "recommended_action": "string"
}
"""

# Baseline B0 for the evaluation: the single-prompt "is this spam?" approach, with no framework.
NAIVE_PROMPT = (
    "You are an email and chat security assistant. Decide whether the message is spam or a "
    "cybersecurity threat. Return ONLY valid JSON: {\"verdict\": \"safe|spam|threat\"}"
)


def _generate(contents: str, system_prompt: str, temperature: float = TEMPERATURE) -> dict:
    """One Gemini call with retry, returning the parsed JSON dict."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey "
            "and put it in a .env file: GEMINI_API_KEY=your-key-here"
        )

    client = genai.Client(api_key=api_key)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=temperature,
                ),
            )
            break  # success — exit the retry loop
        except Exception as e:
            is_last_attempt = (attempt == max_retries)
            msg = str(e)
            is_overloaded = "503" in msg or "UNAVAILABLE" in msg
            # A PER-MINUTE 429 clears after a short wait, so it is retried. A PER-DAY 429
            # (message contains "PerDay") will not clear today, so it is raised straight away.
            is_minute_limit = "RESOURCE_EXHAUSTED" in msg and "PerDay" not in msg
            if (is_overloaded or is_minute_limit) and not is_last_attempt:
                wait_seconds = (5 if is_overloaded else 20) * attempt
                print(f"  {'Server overloaded (503)' if is_overloaded else 'Per-minute rate limit (429)'}, "
                      f"retrying in {wait_seconds}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait_seconds)
                continue
            raise  # not retryable, or out of retries — let the caller handle it

    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, AttributeError) as e:
        raise RuntimeError(f"Model did not return valid JSON: {e}\nRaw response: {response.text}")


def analyze_conversation(conversation_text: str) -> dict:
    """
    Sends a conversation to the Gemini API and returns the structured
    manipulation-risk assessment as a Python dict, matching the schema
    designed.

    Automatically retries up to 3 times on a 503 (server overloaded) error or on a
    per-minute 429, since these are transient. Does NOT retry a per-day 429 (daily quota
    exhausted), since retrying that immediately would not help.

    Raises:
        RuntimeError: if the API key is missing or the response isn't valid JSON.
    """
    return _generate(conversation_text, SYSTEM_PROMPT)


# ----------------------------------------------------------------- cached variants
def _cache_path(kind: str, system_prompt: str, text: str, run: int) -> str:
    key = hashlib.sha256(json.dumps([kind, MODEL_NAME, TEMPERATURE, system_prompt, text, run],
                                    sort_keys=True).encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, key + ".json")


def _cached_call(kind: str, system_prompt: str, text: str, run: int):
    path = _cache_path(kind, system_prompt, text, run)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), True
    result = _generate(text, system_prompt)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f)
    return result, False


def is_cached(kind: str, text: str, run: int = 0) -> bool:
    """True if this (kind, text, run) is already on disk, i.e. running it costs no API call."""
    prompt = SYSTEM_PROMPT if kind == "analysis" else NAIVE_PROMPT
    return os.path.exists(_cache_path(kind, prompt, text, run))


def analyze_cached(text: str, run: int = 0):
    """Same as analyze_conversation, but cached on disk. `run` = repeat number (0, 1, 2...):
    each run is a separate cached sample, which is what the consistency measurement needs.
    Returns (result_dict, from_cache)."""
    return _cached_call("analysis", SYSTEM_PROMPT, text, run)


def naive_verdict(text: str, run: int = 0):
    """Baseline B0: ask Gemini only 'spam / threat / safe?'. Returns (dict with verdict and
    risk_level low|high, from_cache)."""
    raw, cached = _cached_call("naive", NAIVE_PROMPT, text, run)
    verdict = str(raw.get("verdict", "safe")).lower()
    return {"verdict": verdict, "risk_level": "low" if verdict == "safe" else "high"}, cached


if __name__ == "__main__":
    # Quick manual smoke test — replace with a real scenario from the
    # Conversation Evaluation Corpus once built.
    sample = """
    Bank: Your account will be suspended in 10 minutes due to suspicious activity.
    Bank: Please confirm your OTP immediately to prevent permanent account closure.
    """
    result = analyze_conversation(sample)
    print(json.dumps(result, indent=2))