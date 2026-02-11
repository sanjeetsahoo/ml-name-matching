# ml-name-matching

Service for reducing Ops tickets from partial name matches (Bank name vs PAN name).

## Problem

Your first-stage ML model produces a match score. Cases in a partial-accept band are usually sent to Ops.  
This service adds a second-stage decision layer to auto-resolve safe partial accepts and only escalate uncertain cases.

## What this service does

Input: `bank_name`, `pan_name`, and `ml_score` from the existing model.

The service computes explainable features:
- name normalization (punctuation/titles removed)
- token overlap (`jaccard`, containment)
- order-insensitive similarity
- initials compatibility (for formats like `R K SHARMA`)
- hard mismatch guardrails

Output action:
- `AUTO_ACCEPT`
- `AUTO_REJECT`
- `SEND_TO_OPS`

Every decision includes:
- `decision_score` (0 to 1)
- human-readable reasons
- feature values for auditability

## Project structure

```
partial_accept_service/
  api.py                 # FastAPI endpoints
  config.py              # Thresholds + scoring weights (env-configurable)
  decision_engine.py     # Core orchestration and action logic
  features.py            # Feature computation from names
  normalization.py       # Name normalization/tokenization helpers
  schemas.py             # Request/response models
scripts/
  simulate_partial_accepts.py  # Offline backtest on historical JSONL
tests/
  test_decision_engine.py
```

## Quick start

### 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2) Run API

```bash
python -m partial_accept_service
```

Server runs on `http://0.0.0.0:8000`

### 3) Try single decision

```bash
curl -X POST "http://localhost:8000/v1/partial-accept/decide" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "C-1001",
    "bank_name": "SACHIN R TENDULKAR",
    "pan_name": "SACHIN TENDULKAR",
    "ml_score": 0.94
  }'
```

## Batch endpoint

`POST /v1/partial-accept/decide-batch`

```json
{
  "cases": [
    {
      "case_id": "C-1001",
      "bank_name": "RAHUL KUMAR",
      "pan_name": "RAHUL KUMAR",
      "ml_score": 0.80
    },
    {
      "case_id": "C-1002",
      "bank_name": "ANIL KUMAR",
      "pan_name": "ANIL KUMARI",
      "ml_score": 0.62
    }
  ]
}
```

## Configurable thresholds

Tune with environment variables (prefix `PA_`):

- `PA_AUTO_ACCEPT_THRESHOLD` (default `0.86`)
- `PA_AUTO_REJECT_THRESHOLD` (default `0.33`)
- `PA_MAX_ML_SCORE_FOR_AUTO_REJECT` (default `0.56`)
- `PA_STRONG_MODEL_ACCEPT_THRESHOLD` (default `0.91`)

Example:

```bash
export PA_AUTO_ACCEPT_THRESHOLD=0.84
export PA_AUTO_REJECT_THRESHOLD=0.30
```

## Backtesting to estimate ticket reduction

Input JSONL (one case per line), minimum keys:
- `bank_name`
- `pan_name`
- `ml_score`

Optional ground-truth keys:
- `is_match` / `label` / `ground_truth_match` / `actual_match`

Run:

```bash
python scripts/simulate_partial_accepts.py --input historical_partial_accepts.jsonl
```

The script prints:
- action distribution
- estimated Ops ticket reduction (`SEND_TO_OPS` after automation)
- false accepts/rejects (if labels provided)

## Recommended rollout

1. Run simulator on 1-3 months of historical partial accepts.
2. Start in **shadow mode** (log decisions, keep Ops in control).
3. Validate false accept rate and false reject rate.
4. Gradually enable auto-actions for high-confidence slices.
5. Re-tune thresholds monthly using fresh outcomes.
