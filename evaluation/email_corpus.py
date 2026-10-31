"""
email_corpus.py

Email extension of the Conversation Evaluation Corpus (Milestone 1.10).
Same fields as corpus.py (id, category, domains, conversation, expected_risk, rationale)
PLUS:
    channel : "email"
    meta    : from, reply_to, auth, subject, attachments, links[{text, href}]
              (the header / link information a real mail client has, and a pasted chat does not)

HOW THIS SET IS USED (say this in the report):
  * corpus.py (49 chat scenarios) = DEVELOPMENT set: used while designing the fusion and rules.
  * this file (16 email scenarios) = HELD-OUT TEST set: expected risks were fixed here, at design
    time, BEFORE any model output for them was seen, and no framework parameter was tuned on it.

All scenarios are synthetic (expert-designed, AI-drafted, then reviewed by the researcher).
Brands are either fictional (NovaBank) or used only as awareness-training examples; the .example
and look-alike domains are invented. No personal data.

>>> REVIEW EVERY SCENARIO YOURSELF before running. Edit text or expected_risk if you disagree,
>>> and record that you reviewed them (BITS Gen-AI policy: disclose AI-drafted material). <<<
"""

EMAIL_CORPUS = [
    # ---------------- HIGH: text-driven phishing ----------------
    {
        "id": "EML-01", "category": "Banking impersonation", "domains": ["Social Engineering"],
        "channel": "email",
        "meta": {"from": "NovaBank Security <alerts@novabank-secure.co>", "reply_to": "support@novabank-help.co",
                 "auth": "spf=fail dkim=none dmarc=fail", "subject": "URGENT: Your NovaBank account will be suspended",
                 "attachments": [], "links": []},
        "conversation": "Dear Customer,\n\nOur Security Team has detected unauthorized activity on your account. Your account will be suspended within 2 hours unless you verify your identity immediately.\n\nClick http://novabank-secure.co/verify and enter your net banking password and the OTP sent to your phone.\n\nFailure to comply will result in permanent account closure.\n\nNovaBank Fraud Department",
        "expected_risk": "high",
        "rationale": "Credential phishing: authority + deadline + threat + OTP/password request, look-alike domain, failed authentication.",
    },
    {
        "id": "EML-02", "category": "Fake job recruitment", "domains": ["Digital Manipulation"],
        "channel": "email",
        "meta": {"from": "HR Recruitment <careers.globaltech.hr@gmail.com>", "reply_to": "", "auth": "",
                 "subject": "Work From Home Offer - You are Selected!", "attachments": [], "links": []},
        "conversation": "Congratulations! You have been selected for a Data Entry position at GlobalTech with a salary of Rs 45,000 per month, no interview required.\n\nTo confirm your seat, pay a refundable registration fee of Rs 2,500 via UPI today and send a copy of your Aadhaar and bank account details. Only 3 seats remain.",
        "expected_risk": "high",
        "rationale": "Advance-fee job scam plus identity-document harvesting.",
    },
    {
        "id": "EML-03", "category": "Technical support scam", "domains": ["Social Engineering"],
        "channel": "email",
        "meta": {"from": "Microsoft Support <support@microsoft-helpdesk.xyz>", "reply_to": "alerts@ms-care-desk.top",
                 "auth": "spf=fail dmarc=fail", "subject": "Virus detected on your computer",
                 "attachments": [], "links": []},
        "conversation": "Microsoft Technical Support: A virus has been detected and your computer is compromised. Call +1 (800) 555 0147 immediately to avoid permanent data loss. Our technician will need remote access using AnyDesk to remove the threat.",
        "expected_risk": "high",
        "rationale": "Fake tech-support alert with a remote-access request and a spoofed brand sender.",
    },
    {
        "id": "EML-04", "category": "Delivery scam", "domains": ["Digital Manipulation"],
        "channel": "email",
        "meta": {"from": "FedEx Delivery <tracking@fedex-parcel-notice.top>", "reply_to": "", "auth": "spf=softfail",
                 "subject": "Delivery attempt failed", "attachments": [],
                 "links": [{"text": "Pay now", "href": "https://fedex-parcel-notice.top/pay"}]},
        "conversation": "We could not deliver your parcel. Confirm your address and pay the customs fee of Rs 1,200 within 24 hours or your package will be returned.",
        "expected_risk": "high",
        "rationale": "Brand-spoofed delivery notice with a fee demand and a look-alike domain.",
    },
    {
        "id": "EML-05", "category": "Government impersonation", "domains": ["Social Engineering"],
        "channel": "email",
        "meta": {"from": "Income Tax Department <refund@incometax-refund.in>", "reply_to": "", "auth": "spf=softfail dmarc=fail",
                 "subject": "Income tax refund approved", "attachments": [],
                 "links": [{"text": "Claim refund", "href": "http://incometax-refund.in/claim"}]},
        "conversation": "Dear Taxpayer, a refund of Rs 38,540 has been approved by the Income Tax Department. To receive it within 24 hours, verify your PAN, Aadhaar and net banking details using the link below. Refund requests not claimed will be cancelled.",
        "expected_risk": "high",
        "rationale": "Refund-lure phishing impersonating a tax authority.",
    },
    {
        "id": "EML-06", "category": "Government impersonation", "domains": ["Social Engineering"],
        "channel": "email",
        "meta": {"from": "Customs Clearance <clearance@customs-gov-delivery.org>", "reply_to": "", "auth": "",
                 "subject": "Gift parcel held at customs", "attachments": [], "links": []},
        "conversation": "A gift parcel sent from abroad is held at customs. As per customs regulations, pay the clearance duty of Rs 8,900 within 48 hours, otherwise the parcel will be destroyed. Reply with your full name, address and mobile number.",
        "expected_risk": "high",
        "rationale": "Customs-duty advance-fee scam with urgency and a threat.",
    },

    # ---------------- MEDIUM: pressure without credential theft ----------------
    {
        "id": "EML-07", "category": "Investment scam", "domains": ["Digital Manipulation"],
        "channel": "email",
        "meta": {"from": "Wealth Insights <offers@wealthinsights-mail.com>", "reply_to": "", "auth": "",
                 "subject": "Exclusive pre-IPO allocation - limited slots", "attachments": [], "links": []},
        "conversation": "Dear investor, double your money in 30 days with our exclusive pre-IPO allocation. Only 20 slots are left and registration closes on Friday. Invest a minimum of Rs 25,000 to reserve your slot.",
        "expected_risk": "medium",
        "rationale": "Unrealistic returns plus scarcity, but no credential request or threat.",
    },
    {
        "id": "EML-08", "category": "Borderline / ambiguous", "domains": ["Digital Manipulation"],
        "channel": "email",
        "meta": {"from": "ShopZone <deals@shopzone-store.com>", "reply_to": "", "auth": "",
                 "subject": "Last chance! 60% off ends tonight", "attachments": [], "links": []},
        "conversation": "Only 2 left in stock! Your cart will expire in 10 minutes. 60% off ends tonight at midnight - don't miss out. Pay now to keep your discount.",
        "expected_risk": "medium",
        "rationale": "Dark-pattern scarcity and urgency in marketing; manipulative but not a credential-theft attempt.",
    },

    # ---------------- HIGH: the text looks harmless, the headers/links are not ----------------
    # These test the value of the technical layer: Gemini only reads the text.
    {
        "id": "EML-09", "category": "Technical-only deception", "domains": ["Human-Centered Cybersecurity"],
        "channel": "email",
        "meta": {"from": "Anil Mehta <anil.mehta@acmecorp.example>", "reply_to": "", "auth": "",
                 "subject": "Revised vendor contract", "attachments": [],
                 "links": [{"text": "https://docs.google.com/document/d/1xYz-contract",
                            "href": "https://contract-review.filesharing.top/login"}]},
        "conversation": "Hi, sharing the revised vendor contract for your review. Please open it here: https://docs.google.com/document/d/1xYz-contract and sign in with your work account to view it. Thanks, Anil",
        "expected_risk": "high",
        "rationale": "Polite text, but the visible link points to Google while the real target is an unrelated .top domain: credential-harvest link.",
    },
    {
        "id": "EML-10", "category": "Technical-only deception", "domains": ["Human-Centered Cybersecurity"],
        "channel": "email",
        "meta": {"from": "Accounts <billing@acme-supplies.example>", "reply_to": "payments@acme-supplies-pay.example",
                 "auth": "", "subject": "Invoice 4471 - updated bank details",
                 "attachments": ["Invoice_4471.html"], "links": []},
        "conversation": "Hello, please find attached invoice 4471 for last month's order. Our bank details have changed, the new details are inside the attachment. Kindly arrange payment at the earliest.",
        "expected_risk": "high",
        "rationale": "Business-email-compromise pattern: changed bank details, Reply-To on a different domain, and an .html attachment.",
    },
    {
        "id": "EML-11", "category": "Technical-only deception", "domains": ["Human-Centered Cybersecurity"],
        "channel": "email",
        "meta": {"from": "NovaBank Statements <statements@novabank-online.com>", "reply_to": "", "auth": "spf=fail",
                 "subject": "Your monthly statement is ready", "attachments": [],
                 "links": [{"text": "View statement", "href": "https://novabank-online.com/statement"}]},
        "conversation": "Dear customer, your monthly statement is ready. Please sign in securely to view it using the link below. Thank you for banking with NovaBank.",
        "expected_risk": "high",
        "rationale": "Calm wording, but look-alike sender and link domain, a failed SPF check and a brand-in-display-name mismatch.",
    },

    # ---------------- LOW: genuine messages (false-positive tests) ----------------
    {
        "id": "EML-12", "category": "Safe / benign", "domains": ["Explainable AI"],
        "channel": "email",
        "meta": {"from": "Priya Nair <priya.nair@acmecorp.example>", "reply_to": "", "auth": "spf=pass dkim=pass",
                 "subject": "Q3 sales deck", "attachments": [], "links": []},
        "conversation": "Hi Sam, can you share the Q3 sales deck by 5 pm today? It is urgent as the client call has moved up. Thanks, Priya",
        "expected_risk": "low",
        "rationale": "Ordinary workplace deadline: the urgency is legitimate, not manipulative.",
    },
    {
        "id": "EML-13", "category": "Safe / benign", "domains": ["Explainable AI"],
        "channel": "email",
        "meta": {"from": "NovaBank <alerts@novabank.com>", "reply_to": "", "auth": "spf=pass dkim=pass dmarc=pass",
                 "subject": "OTP for your payment", "attachments": [], "links": []},
        "conversation": "482913 is your one-time password for the Rs 1,200 payment to Metro Cafe. Do not share this OTP with anyone. NovaBank will never ask for your OTP or PIN. If you did not make this payment, call the number on the back of your card.",
        "expected_risk": "low",
        "rationale": "Genuine OTP message that warns AGAINST sharing it: a keyword false-positive trap (otp, pin, payment).",
    },
    {
        "id": "EML-14", "category": "Safe / benign", "domains": ["Explainable AI"],
        "channel": "email",
        "meta": {"from": "Google <no-reply@accounts.google.com>", "reply_to": "", "auth": "spf=pass dkim=pass dmarc=pass",
                 "subject": "Reset your password", "attachments": [],
                 "links": [{"text": "Reset password", "href": "https://accounts.google.com/signin/recovery"}]},
        "conversation": "You recently asked to reset your Google account password. Use the button below to choose a new one. The link expires in one hour. If you didn't request this, you can ignore this email.",
        "expected_risk": "low",
        "rationale": "User-initiated password reset on the real domain with a matching link: tests that the technical layer does not over-fire.",
    },
    {
        "id": "EML-15", "category": "Safe / benign", "domains": ["Explainable AI"],
        "channel": "email",
        "meta": {"from": "Amazon.in <shipment-tracking@amazon.in>", "reply_to": "", "auth": "spf=pass dkim=pass dmarc=pass",
                 "subject": "Your order has shipped", "attachments": [],
                 "links": [{"text": "Track your package", "href": "https://www.amazon.in/gp/your-account/order-details"}]},
        "conversation": "Your order #402-1234567-8901234 has shipped and is expected to arrive on 28 Oct. Track your package using the link below. Thank you for shopping with us.",
        "expected_risk": "low",
        "rationale": "Genuine shipment notice on the real brand domain.",
    },
    {
        "id": "EML-16", "category": "Safe / benign", "domains": ["Explainable AI"],
        "channel": "email",
        "meta": {"from": "Neha Sharma <neha.sharma@brightlabs.example>", "reply_to": "", "auth": "spf=pass",
                 "subject": "Interview scheduling", "attachments": [], "links": []},
        "conversation": "Hi, thank you for applying for the Backend Engineer role. We would like to schedule a 30-minute interview on Tuesday or Wednesday this week. Please reply with your preferred time. There is no fee at any stage of our hiring process.",
        "expected_risk": "low",
        "rationale": "Genuine recruiter message, explicitly states no fee.",
    },
]

if __name__ == "__main__":
    from collections import Counter
    print(len(EMAIL_CORPUS), "email scenarios:", dict(Counter(s["expected_risk"] for s in EMAIL_CORPUS)))