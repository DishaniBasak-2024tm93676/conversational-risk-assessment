"""
corpus.py

The Conversation Evaluation Corpus: a structured set of test scenarios covering
all categories defined in the Companion's dataset strategy (banking, job
recruitment, investment, tech support, delivery, government impersonation, and
benign), plus borderline/ambiguous cases.

Each scenario is tagged with:
  - category: which scam/conversation type it represents
  - domains: which of the 5 academic research domains it best demonstrates
             (HCC = Human-Centered Cybersecurity, SE = Social Engineering,
              DM = Digital Manipulation, CAI = Conversational AI, XAI = Explainable AI)
  - expected_risk: the risk level a correct analysis should produce
  - rationale: why this scenario belongs in the corpus

This corpus is imported by run_evaluation.py, which sends every scenario
through the pipeline and builds the Framework Evaluation Matrix from the
results.
"""

CORPUS = [
    # ---------------- BANKING IMPERSONATION ----------------
    {
        "id": "BANK-01",
        "category": "Banking impersonation",
        "domains": ["Social Engineering"],
        "conversation": """
        Bank: Your account will be suspended in 10 minutes due to suspicious activity.
        Bank: Please confirm your OTP immediately to prevent permanent account closure.
        """,
        "expected_risk": "high",
        "rationale": "Classic authority + urgency + fear + sensitive-info-request combination.",
    },
    {
        "id": "BANK-02",
        "category": "Banking impersonation",
        "domains": ["Social Engineering"],
        "conversation": """
        SBI Alert: We noticed a login attempt from a new device in Mumbai.
        SBI Alert: If this wasn't you, verify your identity now by sharing the OTP sent to your phone.
        """,
        "expected_risk": "high",
        "rationale": "Different wording, same mechanism - tests generalization beyond one exact phrasing.",
    },
    {
        "id": "BANK-03",
        "category": "Banking impersonation",
        "domains": ["Social Engineering", "Conversational AI"],
        "conversation": """
        Bank: Hi, this is a routine reminder that your monthly account statement is now available in the app.
        Bank: No action is needed from your end.
        """,
        "expected_risk": "low",
        "rationale": "Same domain (banking) but genuinely benign - tests false-positive avoidance within a high-risk category.",
    },

    # ---------------- JOB RECRUITMENT SCAM ----------------
    {
        "id": "JOB-01",
        "category": "Fake job recruitment",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Recruiter: Congratulations! You've been selected for a work-from-home data entry role.
        Recruiter: To finalize your onboarding, please pay a refundable registration fee of Rs. 2000 today.
        """,
        "expected_risk": "high",
        "rationale": "Upfront-fee employment scam - financial pressure disguised as opportunity.",
    },
    {
        "id": "JOB-02",
        "category": "Fake job recruitment",
        "domains": ["Digital Manipulation"],
        "conversation": """
        HR Team: We reviewed your resume and would like to offer you a part-time social media role.
        HR Team: Please share your bank account number so we can set up your first payment in advance.
        """,
        "expected_risk": "high",
        "rationale": "Different bait (advance payment request instead of fee) - tests indicator combination beyond one script.",
    },
    {
        "id": "JOB-03",
        "category": "Fake job recruitment",
        "domains": ["Conversational AI"],
        "conversation": """
        Recruiter: Thank you for applying. We'd like to schedule a formal interview next Tuesday at 3pm.
        Recruiter: Please confirm your availability by replying to this message.
        """,
        "expected_risk": "low",
        "rationale": "Ordinary, legitimate recruitment message - tests the framework doesn't flag all recruiter messages as risky.",
    },

    # ---------------- INVESTMENT SCAM ----------------
    {
        "id": "INV-01",
        "category": "Investment scam",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Advisor: I have an exclusive crypto investment opportunity with guaranteed 40% monthly returns.
        Advisor: Only 3 slots left today - transfer funds now to secure your spot before it closes.
        """,
        "expected_risk": "high",
        "rationale": "Guaranteed-returns + scarcity + urgency - classic dark-pattern manipulation mechanism.",
    },
    {
        "id": "INV-02",
        "category": "Investment scam",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Trader: My private trading group has a 95% win rate. Join now and I'll personally manage your funds.
        Trader: Send your investment today to start seeing profits by next week.
        """,
        "expected_risk": "high",
        "rationale": "Different framing (personal management claim) testing indicator generalization.",
    },
    {
        "id": "INV-03",
        "category": "Investment scam",
        "domains": ["Explainable AI"],
        "conversation": """
        Friend: I put some money into an index fund through my bank's app last month, seems decent so far.
        Friend: Not promising anything, just sharing in case you're curious.
        """,
        "expected_risk": "low",
        "rationale": "Ordinary, honest personal finance conversation with explicit disclaimers - tests explanation nuance on a topic-adjacent but non-manipulative case.",
    },

    # ---------------- TECH SUPPORT SCAM ----------------
    {
        "id": "TECH-01",
        "category": "Technical support scam",
        "domains": ["Social Engineering"],
        "conversation": """
        Support: We detected a virus on your computer that is stealing your banking data right now.
        Support: Please install our remote access tool immediately so we can fix this before it spreads.
        """,
        "expected_risk": "high",
        "rationale": "Fear + urgency + remote-access request - highest-invasiveness scam category.",
    },
    {
        "id": "TECH-02",
        "category": "Technical support scam",
        "domains": ["Social Engineering"],
        "conversation": """
        Microsoft Support: Your Windows license has expired and your device is at risk.
        Microsoft Support: Call this number immediately and provide your license key to avoid data loss.
        """,
        "expected_risk": "high",
        "rationale": "Brand-impersonation variant - tests generalization beyond 'Support' as the only sender label.",
    },
    {
        "id": "TECH-03",
        "category": "Technical support scam",
        "domains": ["Conversational AI"],
        "conversation": """
        IT Helpdesk: Your password reset request has been completed successfully.
        IT Helpdesk: If you did not request this, please contact IT directly using the internal extension.
        """,
        "expected_risk": "low",
        "rationale": "Legitimate IT notification - directs to internal official channel rather than an external link, correctly non-manipulative.",
    },

    # ---------------- DELIVERY SCAM ----------------
    {
        "id": "DEL-01",
        "category": "Delivery scam",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Delivery: Your package could not be delivered due to an unpaid customs fee of Rs. 150.
        Delivery: Click the link below within 24 hours to pay, or the package will be returned.
        """,
        "expected_risk": "high",
        "rationale": "Small-fee + deadline + threat combination - classic delivery phishing pattern.",
    },
    {
        "id": "DEL-02",
        "category": "Delivery scam",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Courier: We attempted delivery but no one was home. A re-delivery fee of Rs. 99 is required.
        Courier: Pay now via the secure link to reschedule, limited to the next 12 hours.
        """,
        "expected_risk": "high",
        "rationale": "Different fee/deadline framing - tests generalization within the same category.",
    },
    {
        "id": "DEL-03",
        "category": "Delivery scam",
        "domains": ["Conversational AI"],
        "conversation": """
        Amazon: Your order #4471 has been shipped and is expected to arrive Thursday.
        Amazon: Track your package anytime from the Orders section of the app.
        """,
        "expected_risk": "low",
        "rationale": "Standard, legitimate delivery notification with no payment request or deadline.",
    },

    # ---------------- GOVERNMENT IMPERSONATION ----------------
    {
        "id": "GOV-01",
        "category": "Government impersonation",
        "domains": ["Social Engineering"],
        "conversation": """
        Officer: This is an urgent notice from the Income Tax Department regarding a pending case against you.
        Officer: To avoid arrest, you must settle the outstanding amount immediately via the link provided.
        """,
        "expected_risk": "high",
        "rationale": "Highest-authority impersonation combined with an arrest threat - strongest fear indicator expected.",
    },
    {
        "id": "GOV-02",
        "category": "Government impersonation",
        "domains": ["Social Engineering"],
        "conversation": """
        Police Dept: Your Aadhaar number has been linked to an illegal parcel seizure at customs.
        Police Dept: Verify your identity now on this portal to avoid a warrant being issued in your name.
        """,
        "expected_risk": "high",
        "rationale": "Different agency (police) and different sensitive-info type (Aadhaar) - tests generalization across government sub-types.",
    },
    {
        "id": "GOV-03",
        "category": "Government impersonation",
        "domains": ["Human-Centered Cybersecurity"],
        "conversation": """
        Election Commission: Reminder that voter list verification camps are open in your area this week.
        Election Commission: Visit your nearest designated center at your convenience to verify your details.
        """,
        "expected_risk": "low",
        "rationale": "Legitimate government communication with no urgency, threat, or payment request - tests decision support stays calibrated even for a government sender.",
    },

    # ---------------- BENIGN / SAFE ----------------
    {
        "id": "SAFE-01",
        "category": "Safe / benign",
        "domains": ["Conversational AI", "Human-Centered Cybersecurity"],
        "conversation": """
        Riya: Hey, are we still on for dinner tonight?
        Aman: Yeah! 8pm works for me, same place as last time?
        Riya: Perfect, see you then.
        """,
        "expected_risk": "low",
        "rationale": "Baseline ordinary conversation with zero manipulation indicators.",
    },
    {
        "id": "SAFE-02",
        "category": "Safe / benign",
        "domains": ["Conversational AI", "Human-Centered Cybersecurity"],
        "conversation": """
        Airline: Reminder: your flight AI202 is now boarding at Gate 14. Final boarding call in 10 minutes.
        Airline: Please proceed to the gate immediately with your boarding pass and ID.
        """,
        "expected_risk": "low",
        "rationale": "Genuinely urgent but non-manipulative - tests the framework distinguishes urgency from manipulation.",
    },
    {
        "id": "SAFE-03",
        "category": "Safe / benign",
        "domains": ["Human-Centered Cybersecurity"],
        "conversation": """
        Mom: Don't forget to pick up milk on your way home.
        Son: Got it, will do!
        """,
        "expected_risk": "low",
        "rationale": "Second, unrelated baseline benign example to confirm SAFE-01 wasn't a lucky one-off.",
    },

    # ---------------- BORDERLINE / AMBIGUOUS ----------------
    {
        "id": "BORD-01",
        "category": "Borderline / ambiguous",
        "domains": ["Explainable AI", "Human-Centered Cybersecurity"],
        "conversation": """
        Rohan: Hey, sorry to ask but I'm a bit short this month, could you send me 2000 rupees?
        Rohan: I'll pay you back next week when my salary comes in, promise.
        """,
        "expected_risk": "low",
        "rationale": "Genuinely ambiguous - could be real or a compromised-contact scam. Tests decision-support framing (verify, don't refuse) rather than a binary verdict.",
    },
    {
        "id": "BORD-02",
        "category": "Borderline / ambiguous",
        "domains": ["Explainable AI"],
        "conversation": """
        Contest: You've been randomly selected as a winner in our monthly customer draw!
        Contest: Reply with your full name and address so we can arrange delivery of your prize.
        """,
        "expected_risk": "medium",
        "rationale": "Mild phishing shape with no threats/urgency - tests whether the framework needs fear/urgency to flag risk, and whether it can produce a genuine medium rating.",
    },
    {
        "id": "BANK-04",
        "category": "Banking impersonation",
        "domains": ["Social Engineering"],
        "conversation": """
        HDFC Alert: Your debit card has been temporarily blocked due to 3 failed KYC verification attempts.
        HDFC Alert: Complete your KYC update within 2 hours using the link below to reactivate your card.
        """,
        "expected_risk": "high",
        "rationale": "KYC-update phishing variant, a very common real-world pattern - tests generalization to a different pretext (KYC vs. suspicious activity).",
    },
    {
        "id": "BANK-05",
        "category": "Banking impersonation",
        "domains": ["Social Engineering", "Digital Manipulation"],
        "conversation": """
        Bank: We attempted to credit a refund of Rs. 4,500 to your account but it failed due to incorrect details.
        Bank: Please share your UPI PIN so we can process the refund immediately.
        """,
        "expected_risk": "high",
        "rationale": "Reverse-psychology variant (offering money, not threatening loss) requesting a UPI PIN - tests whether the framework requires a threat to flag sensitive-info requests.",
    },
    {
        "id": "BANK-06",
        "category": "Banking impersonation",
        "domains": ["Conversational AI"],
        "conversation": """
        Bank: Your salary of Rs. 45,000 has been credited to your account ending 4521.
        Bank: Available balance: Rs. 62,340.
        """,
        "expected_risk": "low",
        "rationale": "Second legitimate banking example (routine credit alert) to confirm BANK-03 wasn't a one-off, using a different message type entirely.",
    },

    {
        "id": "JOB-04",
        "category": "Fake job recruitment",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Recruiter: We loved your profile! This part-time online task job pays Rs. 3000/day just for liking videos.
        Recruiter: Join our Telegram group now to start today, limited seats available.
        """,
        "expected_risk": "high",
        "rationale": "Task-based/Telegram-redirect job scam, a very common current pattern distinct from the fee-based scams already in the corpus.",
    },
    {
        "id": "JOB-05",
        "category": "Fake job recruitment",
        "domains": ["Social Engineering", "Digital Manipulation"],
        "conversation": """
        HR: Your final offer letter is ready. To process it today, we need your Aadhaar and PAN details right away.
        HR: Delay may result in the offer being given to another candidate.
        """,
        "expected_risk": "high",
        "rationale": "Combines authority (HR/offer letter) with urgency and a sensitive-document request - a more escalated variant than JOB-01/02.",
    },
    {
        "id": "JOB-06",
        "category": "Fake job recruitment",
        "domains": ["Conversational AI"],
        "conversation": """
        Recruiter: Thanks for attending the interview. We'll share feedback within 5 working days as per our process.
        Recruiter: Feel free to reach out if you have any questions in the meantime.
        """,
        "expected_risk": "low",
        "rationale": "Second legitimate recruitment example, ordinary post-interview follow-up with no requests at all.",
    },

    {
        "id": "INV-04",
        "category": "Investment scam",
        "domains": ["Digital Manipulation"],
        "conversation": """
        Group Admin: Our AI trading bot has a proven 98% success rate this month. Screenshots attached in the group.
        Group Admin: Deposit today before the bot's license renewal doubles the entry fee tomorrow.
        """,
        "expected_risk": "high",
        "rationale": "AI-trading-bot framing, a newer scam angle, combined with artificial price-increase urgency.",
    },
    {
        "id": "INV-05",
        "category": "Investment scam",
        "domains": ["Social Engineering", "Digital Manipulation"],
        "conversation": """
        Advisor: I work with a SEBI-registered firm and can help you double your money in gold trading.
        Advisor: Just need your bank login to set up the auto-trading account on your behalf.
        """,
        "expected_risk": "high",
        "rationale": "False regulatory-authority claim (SEBI) combined with a direct credential request - a more severe indicator combination than INV-01/02.",
    },
    {
        "id": "INV-06",
        "category": "Investment scam",
        "domains": ["Conversational AI"],
        "conversation": """
        Colleague: I've been putting a small fixed amount into a SIP every month, nothing fancy, just discipline.
        Colleague: Might be worth looking into if you're starting out with investing.
        """,
        "expected_risk": "low",
        "rationale": "Second legitimate, low-key personal finance conversation with no pressure or promises.",
    },

    {
        "id": "TECH-04",
        "category": "Technical support scam",
        "domains": ["Social Engineering"],
        "conversation": """
        Apple Support: Your iCloud account has been accessed from an unrecognized device in Russia.
        Apple Support: Verify your Apple ID password now on this page to secure your account immediately.
        """,
        "expected_risk": "high",
        "rationale": "Different brand impersonation (Apple/iCloud) - tests generalization beyond Microsoft/generic 'Support'.",
    },
    {
        "id": "TECH-05",
        "category": "Technical support scam",
        "domains": ["Social Engineering", "Digital Manipulation"],
        "conversation": """
        Support: Your antivirus subscription has auto-renewed for Rs. 12,999. Call now within 30 minutes to cancel and get a refund.
        Support: If you miss this window, the charge cannot be reversed.
        """,
        "expected_risk": "high",
        "rationale": "Refund-scam variant (fake overcharge) rather than virus-detection framing - tests generalization to a different fear trigger.",
    },
    {
        "id": "TECH-06",
        "category": "Technical support scam",
        "domains": ["Conversational AI"],
        "conversation": """
        IT Helpdesk: Scheduled maintenance on the company VPN is planned for Saturday 10pm-12am.
        IT Helpdesk: No action is needed; access will resume automatically after maintenance.
        """,
        "expected_risk": "low",
        "rationale": "Second legitimate IT communication, purely informational with explicitly no action required.",
    },

    {
        "id": "DEL-04",
        "category": "Delivery scam",
        "domains": ["Digital Manipulation"],
        "conversation": """
        FedEx: Your package is on hold due to an incorrect address. Update your address within 6 hours to avoid return.
        FedEx: A small verification fee of Rs. 49 applies to confirm the updated address.
        """,
        "expected_risk": "high",
        "rationale": "Different brand (FedEx) and a different pretext (address issue vs. customs fee) - tests generalization within the category.",
    },
    {
        "id": "DEL-05",
        "category": "Delivery scam",
        "domains": ["Social Engineering", "Digital Manipulation"],
        "conversation": """
        Delivery Agent: I'm outside your building with your order but the OTP on the app isn't matching, can you read it to me directly?
        Delivery Agent: I have other deliveries waiting, please hurry.
        """,
        "expected_risk": "high",
        "rationale": "OTP-fraud-via-delivery-agent pretext, a distinct and very common real-world variant, combining a direct sensitive-info request with time pressure.",
    },
    {
        "id": "DEL-06",
        "category": "Delivery scam",
        "domains": ["Conversational AI"],
        "conversation": """
        Zomato: Your order has been picked up and is on the way. Estimated arrival: 25 minutes.
        Zomato: Track your delivery live from the app.
        """,
        "expected_risk": "low",
        "rationale": "Second legitimate delivery notification, food delivery rather than package delivery, for category variety.",
    },

    {
        "id": "GOV-04",
        "category": "Government impersonation",
        "domains": ["Social Engineering"],
        "conversation": """
        RTO Notice: A traffic e-challan of Rs. 2,500 is pending against your vehicle registration.
        RTO Notice: Pay within 24 hours via the link below to avoid your license being suspended.
        """,
        "expected_risk": "high",
        "rationale": "Traffic/RTO impersonation, a different government body than Income Tax or Police, testing generalization across agency types.",
    },
    {
        "id": "GOV-05",
        "category": "Government impersonation",
        "domains": ["Social Engineering", "Digital Manipulation"],
        "conversation": """
        Passport Seva: Your passport application has a discrepancy that requires immediate verification.
        Passport Seva: Share your Aadhaar-linked mobile OTP now to avoid application rejection.
        """,
        "expected_risk": "high",
        "rationale": "Passport-authority impersonation combined with a direct OTP request - a different sensitive-info vector than earlier government scenarios.",
    },
    {
        "id": "GOV-06",
        "category": "Government impersonation",
        "domains": ["Conversational AI"],
        "conversation": """
        Municipal Corporation: Water supply in your area will be temporarily interrupted tomorrow 9am-1pm for pipeline work.
        Municipal Corporation: We apologize for the inconvenience.
        """,
        "expected_risk": "low",
        "rationale": "Second legitimate government communication, a routine civic notice with no request or urgency at all.",
    },

    {
        "id": "SAFE-04",
        "category": "Safe / benign",
        "domains": ["Conversational AI", "Human-Centered Cybersecurity"],
        "conversation": """
        Teacher: Reminder that tomorrow's class has been moved to Room 204 instead of the usual room.
        Student: Thanks for letting us know!
        """,
        "expected_risk": "low",
        "rationale": "Third baseline benign example, an academic/institutional context distinct from personal or commercial ones already covered.",
    },
    {
        "id": "SAFE-05",
        "category": "Safe / benign",
        "domains": ["Conversational AI", "Human-Centered Cybersecurity"],
        "conversation": """
        Landlord: Just a reminder that rent is due on the 5th as usual, no changes this month.
        Tenant: Got it, will transfer it by then.
        """,
        "expected_risk": "low",
        "rationale": "Financial topic (rent) but entirely routine and expected - tests that 'money is mentioned' alone doesn't trigger financial_pressure incorrectly.",
    },

    {
        "id": "BORD-03",
        "category": "Borderline / ambiguous",
        "domains": ["Digital Manipulation", "Explainable AI"],
        "conversation": """
        Store: Hi! Your cart has an item still waiting - our 20% discount code ends tonight at midnight.
        Store: Use code SAVE20 at checkout before it expires, no rush if you're not interested.
        """,
        "expected_risk": "low",
        "rationale": "Real commercial urgency pattern, self-softened - tests against over-flagging ordinary marketing.",
    },
    {
        "id": "BORD-04",
        "category": "Borderline / ambiguous",
        "domains": ["Human-Centered Cybersecurity", "Explainable AI"],
        "conversation": """
        HR: As part of this month's payroll update, please confirm your bank account number for salary processing.
        HR: This is a standard yearly verification requested by finance.
        """,
        "expected_risk": "medium",
        "rationale": "Genuinely difficult case: legitimate-sounding HR authority requesting sensitive bank details - a real scenario where even genuine requests warrant independent verification. Tests whether the framework can flag caution without assuming malice.",
    },
    {
        "id": "BORD-05",
        "category": "Borderline / ambiguous",
        "domains": ["Explainable AI"],
        "conversation": """
        Unknown: Hi, I think you messaged the wrong number but I saw you're into stock trading - I run a small advisory circle, interested?
        Unknown: No pressure at all, just thought I'd mention it.
        """,
        "expected_risk": "medium",
        "rationale": "Soft-approach investment solicitation from an unknown contact with no pressure tactics - tests medium-risk reasoning on a socially-engineered opening move rather than a fully developed scam.",
    },
    {
        "id": "BORD-06",
        "category": "Borderline / ambiguous",
        "domains": ["Digital Manipulation", "Explainable AI"],
        "conversation": """
        Newsletter: Last chance! Our annual sale ends in 3 hours - up to 70% off sitewide.
        Newsletter: This email was sent because you subscribed to our updates.
        """,
        "expected_risk": "low",
        "rationale": "Aggressive marketing urgency with transparent unsubscribe context - tests against over-flagging legitimate but high-pressure retail email marketing.",
    },
    {
        "id": "BORD-07",
        "category": "Borderline / ambiguous",
        "domains": ["Human-Centered Cybersecurity", "Explainable AI"],
        "conversation": """
        Cousin: Hey I'm stuck at the hospital with an emergency, can you send 5000 rupees right now? I'll explain later.
        Cousin: Please hurry, I really need it now.
        """,
        "expected_risk": "medium",
        "rationale": "Classic 'emergency relative' social engineering opening, but plausible as genuine - tests medium-risk, verification-first reasoning on a high-emotion, high-ambiguity case rather than a false accusation of fraud.",
    },
    {
        "id": "BORD-08",
        "category": "Borderline / ambiguous",
        "domains": ["Explainable AI"],
        "conversation": """
        Landlord: I need to raise the rent by 10% starting next month due to increased maintenance costs.
        Landlord: Let me know if you'd like to discuss this before it takes effect.
        """,
        "expected_risk": "low",
        "rationale": "Financial change with advance notice and an open invitation to discuss - tests that unwelcome-but-legitimate financial news isn't scored as manipulative.",
    },
]