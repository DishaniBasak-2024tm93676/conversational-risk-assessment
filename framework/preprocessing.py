"""
preprocessing.py

Takes raw, possibly messy conversation text (pasted by a user) and turns it into a
clean, structured form: individual speaker turns, in order, ready to be sent to the
LLM analysis step (llm_client.py).
 
Handles messages that wrap across multiple lines, and speaker labels that end up
run together in one paragraph with no line breaks between them.
 
Usage:
    from preprocessing import preprocess_conversation
    result = preprocess_conversation(raw_text)
"""

import re

# A line counts as a new "speaker turn" if it starts with a short label followed by
# a colon, e.g. "Bank:", "Mom:", "Unknown Sender:". This regex captures that pattern.
# ^                -> start of the line
# ([A-Za-z0-9 _-]{1,30})  -> the speaker name: letters/numbers/spaces/dashes, 1-30 characters
# :\s*             -> a colon, followed by optional spaces
# (.+)$            -> the rest of the line is the actual message
SPEAKER_PATTERN = re.compile(r"^([A-Za-z0-9 _-]{1,30}):\s*(.+)$")


# Used by clean_text(): finds a candidate speaker label anywhere in the text.
# The position is only accepted if _is_valid_label_boundary() confirms it sits
# in a sensible starting spot. A plain Python check is used here instead of a
# single regex with a lookbehind, because Python's re module only allows
# FIXED-WIDTH lookbehinds — it cannot handle "zero, one, or several spaces"
# after punctuation, which real pasted text frequently has.
LABEL_PATTERN = re.compile(r"([A-Z][A-Za-z0-9 _-]{0,29}):\s*")


def _is_valid_label_boundary(text: str, pos: int) -> bool:
    """
    Checks whether position `pos` in `text` is a sensible place for a new
    speaker label to start: the very beginning of the text, right after a
    line break, or right after a sentence-ending punctuation mark (. ! or ?)
    — regardless of how much whitespace, including none at all, sits between
    the punctuation and the label.
    """
    prefix = text[:pos]
    core = prefix.rstrip()  # prefix with ALL trailing whitespace removed, however much there is
    trailing_whitespace = prefix[len(core):]
 
    if core == "":
        return True  # nothing but whitespace (or nothing at all) before this point
    if "\n" in trailing_whitespace:
        return True  # a line break occurred somewhere before this label
    return core[-1] in ".!?"


def validate_input(raw_text: str) -> None:
    """
    Checks that the input is usable before we try to process it.
    Raises ValueError with a clear message if not.
    """
    if raw_text is None:
        raise ValueError("No conversation text was provided (received None).")
    if not raw_text.strip():
        raise ValueError("The conversation text is empty. Please paste a conversation.")
    if len(raw_text.strip()) < 10:
        raise ValueError(
            "The conversation text looks too short to be a real conversation "
            "(less than 10 characters). Please check what was pasted."
        )


def _insert_line_breaks_before_inline_labels(text: str) -> str:
    """
    Helper for clean_text(). Scans the text for speaker labels that appear
    mid-paragraph (not already at the start of their own line) and inserts a
    line break right before each one, so every speaker ends up starting a new
    line — turning a paste error like:
        "Bank: ...OTP. Mom: Are you okay? Bank: Yes, act now."
    into properly line-separated text before parse_turns() ever sees it.
    """
    matches = [m for m in LABEL_PATTERN.finditer(text) if _is_valid_label_boundary(text, m.start())]
    if not matches:
        return text
 
    pieces = []
    last_end = 0
    for match in matches:
        start = match.start()
        pieces.append(text[last_end:start])
        # Only insert a break if this label isn't already at the very start of
        # the text and isn't already immediately preceded by a line break.
        if start > 0 and text[start - 1] != "\n":
            pieces.append("\n")
        last_end = start
 
    pieces.append(text[last_end:])
    return "".join(pieces)
 

def clean_text(raw_text: str) -> str:
    """
    Cleans raw text into a well-formed, line-separated conversation so it's ready to split into turns:
      1. Trims whitespace and inserts line breaks before mid-paragraph speaker labels.
      2. If a line has extra spaces in the middle, shrink them to one space.
      3. Trims each line and collapses repeated blank lines.
    """
    text = raw_text.strip()
    text = _insert_line_breaks_before_inline_labels(text)

    lines = text.splitlines()
    cleaned_lines = [re.sub(r" {2,}", " ", line).strip() for line in lines]
 
    result_lines = []
    previous_was_blank = False
    for line in cleaned_lines:
        is_blank = (line == "")
        if is_blank and previous_was_blank:
            continue # skip repeated blank lines
        result_lines.append(line)
        previous_was_blank = is_blank
 
    return "\n".join(result_lines).strip()


def parse_turns(cleaned_text: str) -> list[dict]:
    """
    Splits cleaned text into a list of speaker turns.

    If lines follow the "Speaker: message" pattern, each match starts a new turn,
    and any following line WITHOUT that pattern is treated as a continuation of the
    previous speaker's message (handles messages that wrap across multiple lines).

    If NO lines match the pattern at all (e.g. a single block of text with no
    speaker labels), the whole thing is returned as one turn from "Unknown".
    """
    turns = []

    for line in cleaned_text.splitlines():
        if not line.strip():
            continue  # skip blank lines

        match = SPEAKER_PATTERN.match(line)
        if match:
            speaker = match.group(1).strip()
            message = match.group(2).strip()
            turns.append({"speaker": speaker, "message": message})
        else:
            if turns:
                # No speaker label on this line — treat it as a continuation of the previous turn's message
                # (e.g. a message that wrapped onto a second line).
                turns[-1]["message"] += " " + line.strip()
            else:
                # First line has no speaker label at all — start an "Unknown" turn.
                turns.append({"speaker": "Unknown", "message": line.strip()})

    return turns


def preprocess_conversation(raw_text: str) -> dict:
    """
    Main entry point. Validates, cleans, and parses raw conversation text into a structured result.

    Returns a dict with:
        - "cleaned_text": the cleaned, ready-to-send version of the conversation
        - "turns": list of {"speaker": ..., "message": ...} dicts, in order
        - "turn_count": number of turns found
        - "has_speaker_labels": True if at least one real speaker label was found
    """
    validate_input(raw_text)
    cleaned = clean_text(raw_text)
    turns = parse_turns(cleaned)

    has_labels = any(turn["speaker"] != "Unknown" for turn in turns)

    return {
        "cleaned_text": cleaned,
        "turns": turns,
        "turn_count": len(turns),
        "has_speaker_labels": has_labels,
    }


if __name__ == "__main__":
    # Test 1: a well-formatted conversation with clear speaker labels
    sample_1 = """

    Bank:   Your account will be suspended in 10 minutes due to suspicious activity.





    Bank: Please confirm your OTP immediately to prevent permanent account closure.
    """

    # Test 2: a messier example — a message that wraps across two lines, and
    # extra blank lines, to prove the continuation-handling works
    sample_2 = """
    Recruiter: Congratulations! You have been selected for a work-from-home job.
    We just need your bank details
    to process your first advance payment today.
    """

    # Test 3 : multiple speakers run together in ONE paragraph, no line
    # breaks at all — the exact paste-error scenario this fix addresses.
    sample_3 = (
        "Bank: Your account will be suspended in 10 minutes. Please confirm your OTP. " 
        "Mom: Wait, is this legit? Bank: Yes, act now or lose access permanently."
    )

    # Test 4: irregular spacing case 1 — zero spaces between a sentence-ending
    # punctuation mark and the next label.
    sample_4 = (
        "Bank: Your account will be suspended in 10 minutes.  Please confirm your OTP."
        "Mom: Wait, is this legit? Bank: Yes, act now or lose access permanently."
    )
 
    # Test 5: irregular spacing case 2 — a DOUBLE space directly between a
    # sentence-ending punctuation mark and the next label (Test 4 only tested
    # a double space mid-sentence, not right before a label — this closes
    # that gap properly).
    sample_5 = "Bank: Your account will be suspended.  Mom: Wait, what?"


    print("=== Test 1: clean, well-labeled conversation ===")
    result_1 = preprocess_conversation(sample_1)
    print(result_1)

    print("\n=== Test 2: message wrapping across lines ===")
    result_2 = preprocess_conversation(sample_2)
    print(result_2)
 
    print("\n=== Test 3: multiple speakers in one paragraph, no line breaks ===")
    result_3 = preprocess_conversation(sample_3)
    print(result_3)

    print("\n=== Test 4: irregular spacing (double space, then zero space) ===")
    print(preprocess_conversation(sample_4))

    print("\n=== Test 5: double space directly before the next label ===")
    print(preprocess_conversation(sample_5))