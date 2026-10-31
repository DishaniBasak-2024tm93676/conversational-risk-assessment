"""
test_app.py - drives the Streamlit app headlessly with a FAKE Gemini (no key needed) to prove the
page renders for a chat paste and an email paste.   python3 tools/test_app.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "framework")]
import llm_client
from hybrid import lexical_scores, INDICATORS
from streamlit.testing.v1 import AppTest

LEVEL = ["none", "low", "medium", "high"]


def fake(contents, system_prompt, temperature=0.2):
    lex = lexical_scores(contents)
    t = sum(v["score"] for v in lex.values())
    return {"context": {"domain": "banking", "confidence": "high"},
            "indicators": {i: {"level": LEVEL[lex[i]["score"]], "evidence": "'" + (lex[i]["hits"][0] if lex[i]["hits"] else "n/a") + "'"} for i in INDICATORS},
            "overall_risk": "high" if t >= 6 else "medium" if t >= 3 else "low", "explanation": "fake", "recommended_action": "x"}


llm_client._generate = fake
llm_client.CACHE_DIR = tempfile.mkdtemp()

at = AppTest.from_file(os.path.join(ROOT, "interface", "app.py"), default_timeout=30).run()
assert not at.exception, at.exception

# --- chat mode: only chat examples are offered, no email fields
assert at.radio(key="channel_label").value == "Chat / SMS"
assert [s.key for s in at.selectbox] == ["chat_example"], [s.key for s in at.selectbox]
assert len(at.text_input) == 0, "email fields must be hidden in chat mode"
at.selectbox(key="chat_example").select("Example: Suspicious bank message").run()
assert "suspended" in at.text_area(key="conversation_text").value
at.button[0].click().run()
assert not at.exception, at.exception
assert any("Overall Risk" in s.value for s in at.subheader), "chat result not shown"
print("chat mode ok:", [s.value for s in at.subheader])

# --- switch to email: form is cleared, email examples + optional fields appear
at.radio(key="channel_label").set_value("Email").run()
assert not at.exception, at.exception
assert [s.key for s in at.selectbox] == ["email_example"], [s.key for s in at.selectbox]
assert at.text_area(key="conversation_text").value == "", "form must be cleared when switching type"
assert len(at.text_input) == 5, len(at.text_input)
assert all("optional" in t.label.lower() for t in at.text_input), [t.label for t in at.text_input]

# every email example loads into all fields and can be analysed
import importlib.util, re
src = open(os.path.join(ROOT, "interface", "app.py")).read()
names = re.findall(r'"(Example: [^"]+)": \{\n\s+"from"', src)
assert len(names) == 4, names
for n in names:
    at.selectbox(key="email_example").select(n).run()
    assert not at.exception, at.exception
    assert at.text_area(key="conversation_text").value.strip(), n
    at.button[0].click().run()
    assert not at.exception, (n, at.exception)
    print("email example ok:", n, "->", [s.value for s in at.subheader])

# phishing example must raise technical flags and come out HIGH with the fake LLM
at.selectbox(key="email_example").select("Example: Fake bank verification email").run()
assert at.text_input(key="f_from").value.startswith("NovaBank")
assert at.text_area(key="f_links").value
at.button[0].click().run()
assert any("Overall Risk: HIGH" in s.value for s in at.subheader), [s.value for s in at.subheader]

# switching back to chat clears the email form
at.radio(key="channel_label").set_value("Chat / SMS").run()
assert [s.key for s in at.selectbox] == ["chat_example"]
assert at.text_area(key="conversation_text").value == ""
print("APP TEST PASSED")