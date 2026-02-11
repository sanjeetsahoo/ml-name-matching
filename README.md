# ml-name-matching

Service to reduce manual ops tickets for **partial-accept** bank-name vs PAN-name matches.

## Why this service exists

Your ML matcher already classifies some name pairs as strong accepts/rejects. The difficult middle bucket (partial accepts) gets sent to ops, where manual review can become too strict or too expensive.

This service adds a second-stage triage for partial accepts:

- `auto_accept` for high-confidence matches
- `auto_reject` for high-confidence mismatches
- `send_to_ops` for ambiguous cases

This keeps the risky cases with ops while reducing total ticket volume.

## How it works

For each pair (`bank_name`, `pan_name`) the service computes:

- normalization (case, punctuation, noise-title removal)
- fuzzy lexical scores (`token_set_ratio`, `token_sort_ratio`, `jaro_winkler`)
- soft token coverage (including initial matching, e.g. `R` == `RAKESH`)
- conflict signals (first-name conflict, surname match)
- optional original model score (`ml_score` in `[0,1]` or `[0,100]`)

It combines these signals into a blended score and applies conservative thresholds.

## API

### Health

```bash
curl -s http://localhost:8000/health
```

### Single decision

```bash
curl -s -X POST http://localhost:8000/v1/partial-accepts/decision \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "txn-123",
    "bank_name": "Rakesh Kumar Sharma",
    "pan_name": "Rakesh K Sharma",
    "ml_score": 0.91
  }'
```

### Batch decision

```bash
curl -s -X POST http://localhost:8000/v1/partial-accepts/decision/batch \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "request_id": "1",
        "bank_name": "Rakesh Kumar Sharma",
        "pan_name": "Rakesh Kumar Sharma",
        "ml_score": 0.96
      },
      {
        "request_id": "2",
        "bank_name": "Priya Gupta",
        "pan_name": "Mohit Sharma",
        "ml_score": 0.11
      }
    ]
  }'
```

## Local setup

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run service

```bash
uvicorn name_match_service.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run tests

```bash
pytest
```

## Threshold tuning

You can tune behavior through environment variables:

- `AUTO_ACCEPT_THRESHOLD` (default: `88.0`)
- `AUTO_ACCEPT_MIN_COVERAGE` (default: `0.70`)
- `AUTO_REJECT_THRESHOLD` (default: `52.0`)
- `AUTO_REJECT_CONFLICT_CEILING` (default: `72.0`)
- `HARD_REJECT_MIN_COVERAGE` (default: `0.35`)
- `ML_SCORE_WEIGHT` (default: `0.30`)

Higher `AUTO_ACCEPT_THRESHOLD` means fewer automated accepts and more ops tickets. Lowering it increases reduction but adds risk. Start conservatively and calibrate using historical ops outcomes.
