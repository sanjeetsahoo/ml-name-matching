# ML Name Matching - Partial Accept Triage Service

This repository now includes a lightweight post-processing service that reduces
ops tickets generated from strict ML `partial_accept` outputs for
`bank_name` vs `pan_name` matching.

## Why this exists

If your upstream ML model is conservative, too many cases land in
`partial_accept` and are escalated to ops. This service adds deterministic
guardrails and similarity rules to safely auto-resolve obvious cases:

- `auto_accept`: high-confidence same person/entity
- `auto_reject`: high-confidence mismatch
- `needs_ops_review`: ambiguous cases only

## How it works

The engine combines:

1. **Normalization**: remove punctuation/noise, drop honorifics/corporate
   suffixes, normalize aliases (`mohd` -> `mohammad`, `kr` -> `kumar`, etc.)
2. **Similarity features**:
   - sequence similarity
   - token-set overlap (jaccard/coverage)
   - first/last token similarity
   - initials compatibility
3. **Decision policy**:
   - safety-first hard reject guardrails on strong mismatches
   - deterministic auto-accept patterns for common true matches
   - blended confidence with optional upstream `ml_score`
   - fallback to ops only when still uncertain

## API

### `POST /triage`

Request:

```json
{
  "case_id": "abc-123",
  "bank_name": "Rahul K Singh",
  "pan_name": "Rahul Kumar Singh",
  "ml_score": 0.84
}
```

Response (example):

```json
{
  "case_id": "abc-123",
  "decision": "auto_accept",
  "confidence": 0.88,
  "reason_codes": ["INITIALS_EXPANSION_MATCH"],
  "normalized_bank_name": "rahul k singh",
  "normalized_pan_name": "rahul kumar singh",
  "features": {
    "deterministic_score": 0.81,
    "blended_score": 0.82
  }
}
```

### `POST /triage/batch`

Accepts a list of cases and returns individual decisions plus:

- `auto_accept` count
- `auto_reject` count
- `needs_ops_review` count
- `ticket_reduction_ratio`

This ratio estimates how many tickets can be removed from ops flow.

## Run locally

```bash
python -m pip install -r requirements.txt
uvicorn partial_accepts_api:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Run tests

```bash
pytest -q
```

## Files

- `name_triage_engine.py`: core rule engine + score blending + summary metrics
- `partial_accepts_api.py`: FastAPI service layer
- `test_name_triage_engine.py`: behavior tests
