"""
app.py

The Streamlit web interface for the conversational risk assessment framework.
Lets a user paste a conversation into a text box and see the full analysis
(risk level, indicators, explanation, recommendation) displayed visually,
instead of reading raw JSON in a terminal.

UPDATED (hybrid extension): same page and flow as before, now powered by the hybrid framework
(Gemini + lexical + technical email checks + escalation rules). New: an "Email" mode with
header/link fields, technical signals, the escalation rules that fired, Gemini's own rating
next to the framework's rating, and a view of exactly what is sent to Gemini (after masking).

Usage:
    streamlit run interface/app.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "framework"))

import streamlit as st
from pipeline import run_hybrid
from hybrid import CFG

st.set_page_config(page_title="Conversation Risk Assessment", page_icon="🛡️", layout="centered")

st.title("🛡️ Conversation Risk Assessment")
st.write(
    "Check a chat, SMS or email for signs of social engineering, digital manipulation, or fraud. "
    "Nothing is analysed until you press the Analyze button."
)

# ----------------------------------------------------------------------------- ready-made examples
CHAT_EXAMPLES = {
    "None — I'll paste my own below": "",
    "Example: Suspicious bank message":
    (
        "Bank: Your account will be suspended in 10 minutes due to suspicious activity.\n"
        "Bank: Please confirm your OTP immediately to prevent permanent account closure."
    ),
    "Example: Normal everyday chat":
    (
        "Riya: Hey, are we still on for dinner tonight?\n"
        "Aman: Yeah! 8pm works for me, same place as last time?"
    ),
}

# Demo emails written for the interface (they are NOT the held-out evaluation emails).
EMAIL_EXAMPLES = {
    "None — I'll paste my own below": {},
    "Example: Fake bank verification email": {
        "from": "NovaBank Security <alerts@novabank-secure.top>",
        "reply_to": "support@novabank-help.xyz",
        "subject": "URGENT: Verify your account within 24 hours",
        "auth": "spf=fail dkim=fail dmarc=fail",
        "attachments": "verify_account.html",
        "links": "https://novabank.com/verify | https://secure-novabank-verify.top/login",
        "body": (
            "Dear customer,\n\n"
            "We detected unusual activity on your NovaBank account. Your account will be suspended "
            "within 24 hours unless you verify your identity.\n\n"
            "Please confirm your net banking password and the OTP sent to your phone to avoid permanent closure.\n\n"
            "Verify now: https://secure-novabank-verify.top/login\n\n"
            "NovaBank Security Team"
        ),
    },
    "Example: Genuine library reminder": {
        "from": "Campus Library <library@riverside-college.edu>",
        "reply_to": "",
        "subject": "Reminder: books due on Friday",
        "auth": "spf=pass dkim=pass dmarc=pass",
        "attachments": "",
        "links": "https://library.riverside-college.edu/account | https://library.riverside-college.edu/account",
        "body": (
            "Hello,\n\n"
            "This is a friendly reminder that two of your borrowed books are due on Friday. "
            "You can renew them online from your library account.\n\n"
            "Thank you,\nCampus Library"
        ),
    },
    "Example: Polite email with a hidden link": {
        "from": "HR Team <hr@globaltech-careers.com>",
        "reply_to": "",
        "subject": "Updated holiday calendar",
        "auth": "spf=softfail dkim=pass dmarc=fail",
        "attachments": "",
        "links": "https://docs.google.com/holiday-calendar | http://bit.ly/3xYz9",
        "body": (
            "Hi all,\n\n"
            "Please find the updated holiday calendar for next year using the link below. "
            "Let us know if you have any questions.\n\n"
            "Regards,\nHR Team"
        ),
    },
    "Example: Job offer asking for a fee": {
        "from": "Careers <jobs@careerbridge-hr.com>",
        "reply_to": "",
        "subject": "Congratulations! You are selected",
        "auth": "",
        "attachments": "",
        "links": "",
        "body": (
            "Congratulations! You have been selected for the Data Entry Executive role (salary Rs 60,000 per month).\n\n"
            "To confirm your joining, please pay a one-time registration fee of Rs 4,500 today. "
            "Seats are limited and your offer will be cancelled if payment is not received by evening. "
            "We do not want you to lose this life-changing opportunity.\n\n"
            "Reply with your bank account number and Aadhaar details to receive the payment link."
        ),
    },
}

FORM_KEYS = ["conversation_text", "f_from", "f_reply_to", "f_subject", "f_auth", "f_attach", "f_links"]
for k in FORM_KEYS:
    st.session_state.setdefault(k, "")
NONE_CHOICE = "None — I'll paste my own below"


def reset_form():
    """Called when the user switches between Chat and Email: start from a clean form."""
    for k in FORM_KEYS:
        st.session_state[k] = ""
    st.session_state["chat_example"] = NONE_CHOICE
    st.session_state["email_example"] = NONE_CHOICE


def load_chat_example():
    st.session_state.conversation_text = CHAT_EXAMPLES[st.session_state.chat_example]


def load_email_example():
    ex = EMAIL_EXAMPLES[st.session_state.email_example]
    st.session_state.f_from = ex.get("from", "")
    st.session_state.f_reply_to = ex.get("reply_to", "")
    st.session_state.f_subject = ex.get("subject", "")
    st.session_state.f_auth = ex.get("auth", "")
    st.session_state.f_attach = ex.get("attachments", "")
    st.session_state.f_links = ex.get("links", "")
    st.session_state.conversation_text = ex.get("body", "")


# ----------------------------------------------------------------------------- step 1: type
st.write("**Step 1: What do you want to check?**")
channel_label = st.radio("Type of message", ["Chat / SMS", "Email"], horizontal=True,
                         key="channel_label", on_change=reset_form, label_visibility="collapsed")
channel = "email" if channel_label == "Email" else "chat"

# ----------------------------------------------------------------------------- step 2: examples
st.write("**Step 2 (optional): Load a ready-made example**")
if channel == "chat":
    st.selectbox("Chat examples", options=list(CHAT_EXAMPLES.keys()), key="chat_example",
                 on_change=load_chat_example, label_visibility="collapsed")
else:
    st.selectbox("Email examples", options=list(EMAIL_EXAMPLES.keys()), key="email_example",
                 on_change=load_email_example, label_visibility="collapsed")
st.caption("An example fills the boxes below. You can edit it, clear it, or skip this and paste your own.")

# ----------------------------------------------------------------------------- step 3: email details
meta = {}
if channel == "email":
    st.write("**Step 3 (optional): Email details**")
    st.caption("All of these are optional. They let the framework check the sender, links and attachments; "
               "without them only the message text is analysed.")
    with st.container(border=True):
        meta["from"] = st.text_input("From (optional)", key="f_from",
                                     placeholder="Name <address@domain.com>")
        meta["reply_to"] = st.text_input("Reply-To (optional, only if different from sender)", key="f_reply_to")
        meta["subject"] = st.text_input("Subject (optional)", key="f_subject")
        meta["auth"] = st.text_input("Authentication-Results (optional)", key="f_auth",
                                     help="In Gmail: open the email, click the three dots, choose 'Show original', "
                                          "and copy the line starting with Authentication-Results.",
                                     placeholder="spf=pass dkim=pass dmarc=pass")
        attachments = st.text_input("Attachment file names (optional, separated by commas)", key="f_attach",
                                    placeholder="invoice.pdf, update.zip")
        meta["attachments"] = [a.strip() for a in attachments.split(",") if a.strip()]
        links_text = st.text_area("Links (optional, one per line as:  visible text | real address)", height=80,
                                  key="f_links", placeholder="https://docs.google.com/x | https://evil-site.top/login")
        meta["links"] = []
        for line in links_text.splitlines():
            if "|" in line:
                shown, href = [p.strip() for p in line.split("|", 1)]
                meta["links"].append({"text": shown, "href": href})

# ----------------------------------------------------------------------------- final step: the text
step_no = "4" if channel == "email" else "3"
st.write(f"**Step {step_no} (required): {'Email body' if channel == 'email' else 'Conversation text'}**")
conversation_input = st.text_area(
    "Message text (required)",
    key="conversation_text",
    height=180,
    placeholder="Paste the email body here..." if channel == "email" else "Paste the conversation here...",
    label_visibility="collapsed",
)

analyze_clicked = st.button("Analyze", type="primary")

if analyze_clicked:
    if not conversation_input.strip():
        st.warning("Please paste the message text first (the only required field).")
    else:
        with st.spinner("Analyzing..."):
            try:
                result = run_hybrid(conversation_input, meta, channel)
                analysis = result["analysis"]
                hybrid = result["hybrid"]
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                analysis = None

        if analysis:
            risk = hybrid["risk_level"]
            risk_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            risk_icon = risk_colors.get(risk, "⚪")

            st.subheader(f"{risk_icon} Overall Risk: {risk.upper()}  ({hybrid['risk_score']:.0f}/100)")

            context = analysis.get("context", {})
            domain = context.get("domain", "unknown")
            confidence = context.get("confidence", "unknown")
            st.caption(
                f"Detected context: **{domain}** (confidence: {confidence})  |  "
                f"Gemini's own rating on its own: **{hybrid['llm_overall_risk'] or 'n/a'}**"
            )

            st.write("**Explanation:**")
            st.text(hybrid["explanation"])

            st.write("**Recommended Action:**")
            st.info(hybrid["recommended_action"])

            if hybrid["technical_flags"]:
                with st.expander(f"Technical signals ({len(hybrid['technical_flags'])})", expanded=True):
                    for f in hybrid["technical_flags"]:
                        st.write(f"⚠️ **{f['label']}**")
                        st.caption(f["detail"])
            elif channel == "email":
                st.caption("No sender, link or attachment warning signs were found in the details provided.")

            with st.expander("See detailed indicator breakdown"):
                level_icons = {"high": "🔴", "medium": "🟡", "low": "🟢", "none": "⚪"}
                for name, d in hybrid["indicators"].items():
                    icon = level_icons.get(d["level"], "⚪")
                    display_name = CFG["labels"][name]
                    st.write(f"{icon} **{display_name}**: {d['level']}  "
                             f"(Gemini {d['llm']}/3, keywords {d['lex']}/3, weighted contribution {d['contribution']:.1f})")
                    if d["evidence"] and d["evidence"].lower() != "none":
                        st.caption(f"Evidence: {d['evidence']}")

            with st.expander("Gemini's own reasoning (free text, not verified by the framework)"):
                st.write(analysis.get("explanation", "No explanation available."))

            with st.expander("Exactly what was sent to Gemini (after privacy masking)"):
                st.code(result["llm_input_text"])

st.divider()
st.caption(
    "This tool provides decision support, not a guaranteed fraud determination. "
    "Always independently verify suspicious requests through official channels."
)