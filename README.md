# Explainable Human-Centered Conversational Risk Assessment Framework

Source code for the M.Tech Software Engineering (BITS Pilani WILP) dissertation
**"Design and Development of an Explainable Human-Centered Conversational Risk Assessment Framework for Social Engineering, Digital Manipulation, and AI-Assisted Fraud"**
by Dishani Basak (BITS ID 2024TM93676), course SEZG628T Dissertation.

> This is a research prototype. It supports a user's own decision and does **not** guarantee fraud detection.

## What it does

Given a chat message or an email, the framework returns a **risk level** (Low, Medium or High), a breakdown of **six manipulation indicators** (authority claims, urgency, fear or threat, sensitive-information requests, emotional pressure, financial pressure), **quoted evidence**, a plain-language **explanation** and a **recommended action**.

## How it works

Three analysis layers feed one explainable result:

1. **LLM layer** (Gemini, JSON output): rates the six indicators and quotes evidence.
2. **Lexical layer**: predefined keyword lists per indicator.
3. **Technical layer** (email only): ten checks on sender, links and attachments.

They are combined as follows:

- **Fusion** per indicator: 0.7 x LLM + 0.3 x lexical (none 0, low 1, medium 2, high 3), weighted into a 0 to 100 content score. For emails, 0.4 x technical points are added.
- **Levels**: Low below 20, Medium 20 to 39, High 40 or above.
- **Escalation rules R1 to R4** raise the level for dangerous combinations, for example a request for sensitive information together with urgency.
- **LLM safety floor**: the final level is never lower than the LLM's own overall rating.

Weights, thresholds, keyword lists, brand list and recommended actions are all in `framework/risk_config.json`. They are set by design, not learned from data.

## Repository layout

| Path | Purpose |
|---|---|
| `framework/hybrid.py` | Privacy masking, lexical indicators, technical email checks, fusion, rules R1 to R4, explanation |
| `framework/llm_client.py` | Gemini client: prompt, disk cache, retry on rate limits |
| `framework/pipeline.py` | Pipeline entry points (`run_pipeline`, `run_hybrid`) |
| `framework/preprocessing.py` | Input preprocessing |
| `framework/risk_config.json` | Single source of truth for weights, thresholds and word lists |
| `interface/app.py` | Streamlit app with chat mode and email mode |
| `gmail_addon/` | Gmail add-on in Google Apps Script: `Core.gs`, `Code.gs`, `Config.gs` (generated), `appsscript.json` |
| `evaluation/` | Scenarios (`corpus.py` chat, `email_corpus.py` email, `full_corpus.py` both), runners, saved results and Excel matrices |
| `tools/` | `build_addon.py` and the test scripts |

## Setup

Requires Python 3 (and Node.js for two of the tests) and a Gemini API key.

```bash
python3 -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a file named `.env` in the project root (the same folder as this README):

```
GEMINI_API_KEY=your_own_key_here
```

`.env` is listed in `.gitignore` and is never committed. The default model is `gemini-3.1-flash-lite`; to use another, set `GEMINI_MODEL` in `.env`. Free-tier keys have daily and per-minute limits.

All commands below are run from the project root with the virtual environment active.

## Run the Streamlit app

```bash
streamlit run interface/app.py
```

Choose chat mode or email mode, paste the text and press **Analyze**. Nothing is sent to Gemini until you press the button. Before sending, the part of an email address before the @ and long digit strings are masked, and the app shows what was sent.

## Tests (no API key needed)

```bash
python3 tools/smoke_test_offline.py      # plumbing check with a fake model
python3 tools/test_parity.py             # Python logic equals Gmail add-on logic (needs Node.js)
node tools/test_addon_ui.js              # add-on code paths with stand-in Google services
python3 tools/test_app.py                # Streamlit page renders with a fake model
python3 evaluation/offline_replay.py     # fusion and rules on the saved chat results
```

The parity test compares the Python and Apps Script versions across 65 scenarios and 5 configurations (325 comparisons, all matching).

## Evaluation

65 scenarios: 49 chat (development set) and 16 email (held-out test set). Seven configurations: B0 basic prompt, B1 rules only, B2 Gemini overall rating, B3 full hybrid, and ablations A1 (no technical layer), A2 (no escalation rules), A3 (no LLM safety floor).

```bash
python3 evaluation/run_comparison.py --dry-run                 # how many API calls are needed
python3 evaluation/run_comparison.py --source email --repeats 1 --naive-repeats 1   # smallest useful run
python3 evaluation/run_comparison.py --repeats 3               # all 65 scenarios, 3 runs each
python3 evaluation/run_comparison.py --max-calls 100           # stop after 100 real API calls and resume later
```

Useful options: `--source chat|email|all`, `--ids <scenario ids>`, `--sleep <seconds>` between API calls, `--report-only` to rebuild the report from cached results.

Results are cached in `.llm_cache/` (not included in the repository), so a re-run is free and an interrupted run resumes. Output is written to `evaluation/Framework_Comparison.xlsx`, `evaluation/comparison_summary.md` and `evaluation/comparison_summary.json`. The original 49-scenario chat evaluation is `python3 evaluation/run_evaluation.py`, with raw results in `evaluation/checkpoint_results.json`.

Headline results from the dissertation (accuracy): the full hybrid scores 0.94 on the email set and 0.98 on the chat set, 63 of 65 overall (0.97), against 0.92 for Gemini's overall rating alone. Gemini runs are repeated three times and combined by majority vote. The scenarios are synthetic and mostly written with AI assistance, and there was no user study. See the dissertation for the full analysis and limitations.

## Gmail add-on

The add-on is a Google Apps Script project run as a test deployment (not published on the Google Workspace Marketplace). It runs only when the user presses a button, analyses up to the latest 5 messages of a thread, notes when risk rises by 20 points or more, and caches results for one hour.

1. If you change the prompt or `framework/risk_config.json`, regenerate the config: `python3 tools/build_addon.py`. Do not edit `gmail_addon/Config.gs` by hand.
2. Go to https://script.google.com and create a new project. In Project Settings, tick "Show appsscript.json manifest file".
3. Create `Config.gs`, `Core.gs` and `Code.gs` and paste in the three files from `gmail_addon/`. Replace the manifest with `appsscript.json`.
4. In Project Settings, Script properties, add `GEMINI_API_KEY`. The key is stored there, never in the code.
5. Deploy, Test deployments, Install, and approve the permissions.
6. Open an email in Gmail. The side panel shows the add-on. Press **Analyze this email**.

## Privacy and ethics

- Analysis runs only on user action.
- Basic masking is applied before text goes to the LLM. Masking is not complete anonymisation.
- The evaluation scenarios are synthetic and contain no real personal data. Free-tier prompts may be used by Google to improve its products, so only synthetic or test text should be analysed.
- The tool does not block, delete or report anything. The user makes the final decision.

## Known limitations

English only; 65 synthetic scenarios, which is small; weights and rules set by design, not learned; Gemini output varies slightly between runs (temperature 0.2); small keyword and brand lists; domain parsing uses a simple heuristic; the add-on needs a user press, so it is not real-time interception.

## Generative AI use

Generative AI tools were used as disclosed in the Declaration and Generative AI Disclosure of the dissertation. Gemini is a component of the framework under evaluation, not a writing aid.

## Academic context

Dissertation work carried out at HSBC Software Development (India) Private Limited, Hyderabad, as a personal project, in partial fulfilment of the M.Tech Software Engineering programme at Birla Institute of Technology and Science, Pilani. Supervisor: Elisha Samuel Lella.