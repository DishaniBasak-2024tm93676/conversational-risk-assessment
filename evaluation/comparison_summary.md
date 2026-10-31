# Framework comparison

Model gemini-3.1-flash-lite; scenarios 65; repeats 3; calls still missing: 0 (complete)

## ALL

| Config | n | accuracy | ordinal MAE | precision | recall | F1 | benign FP rate | FN | consistency |
|---|---|---|---|---|---|---|---|---|---|
| B0 naive | 65 | 0.89 | 0.12 | 0.97 | 1.00 | 0.99 | 0.04 | 0 | - |
| B1 rules-only | 65 | 0.46 | 0.78 | 0.94 | 0.44 | 0.60 | 0.04 | 22 | - |
| B2 LLM-only | 65 | 0.92 | 0.08 | 1.00 | 0.97 | 0.99 | 0.00 | 1 | 0.99 |
| B3 hybrid | 65 | 0.97 | 0.03 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A1 no-technical | 65 | 0.94 | 0.06 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 0.99 |
| A2 no-rules | 65 | 0.95 | 0.05 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A3 score-only | 65 | 0.89 | 0.11 | 1.00 | 0.97 | 0.99 | 0.00 | 1 | 1.00 |

## dev (chat)

| Config | n | accuracy | ordinal MAE | precision | recall | F1 | benign FP rate | FN | consistency |
|---|---|---|---|---|---|---|---|---|---|
| B0 naive | 49 | 0.90 | 0.12 | 0.97 | 1.00 | 0.98 | 0.05 | 0 | - |
| B1 rules-only | 49 | 0.45 | 0.86 | 1.00 | 0.32 | 0.49 | 0.00 | 19 | - |
| B2 LLM-only | 49 | 0.98 | 0.02 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| B3 hybrid | 49 | 0.98 | 0.02 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A1 no-technical | 49 | 0.98 | 0.02 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A2 no-rules | 49 | 0.98 | 0.02 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A3 score-only | 49 | 0.86 | 0.14 | 1.00 | 0.96 | 0.98 | 0.00 | 1 | 1.00 |

## test (email)

| Config | n | accuracy | ordinal MAE | precision | recall | F1 | benign FP rate | FN | consistency |
|---|---|---|---|---|---|---|---|---|---|
| B0 naive | 16 | 0.88 | 0.12 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | - |
| B1 rules-only | 16 | 0.50 | 0.56 | 0.89 | 0.73 | 0.80 | 0.20 | 3 | - |
| B2 LLM-only | 16 | 0.75 | 0.25 | 1.00 | 0.91 | 0.95 | 0.00 | 1 | 0.98 |
| B3 hybrid | 16 | 0.94 | 0.06 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A1 no-technical | 16 | 0.81 | 0.19 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 0.98 |
| A2 no-rules | 16 | 0.88 | 0.12 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |
| A3 score-only | 16 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0 | 1.00 |

Evidence grounding (B3): 430 quoted spans, 0.97 verified present in the input
Hybrid agrees with Gemini's own rating: 0.95

Notes: metrics use the majority prediction per scenario across runs (ties -> higher risk). 'consistency' = share of runs agreeing with the majority. dev = used while designing the framework; test = held out (email). Positive class for precision/recall = medium or high.
