# ml-name-matching

Service to reduce manual ops tickets for **partial-accept** name matches between:
- `bank_name` (name from bank/KYC side)
- `pan_name` (name from PAN source)

The service acts as a **second-stage decision layer** after your ML model and returns:
- `auto_approve` for high-confidence matches
- `auto_reject` for strong mismatches
- `route_to_ops` only for truly ambiguous cases

It also includes **duplicate suppression** for recent escalations so repeated partial-accept pairs do not create multiple ops tickets.

## How this reduces ops load

1. Takes your model's borderline cases (`partial accepts`).
2. Re-scores with deterministic features:
   - normalized name equality
   - sequence similarity
   - edit-distance similarity
   - token overlap/jaccard
   - initials/abbreviation consistency
3. Applies decision policy thresholds to auto-resolve safe cases.
4. Uses a TTL cache to suppress duplicate ops escalations (`ticket_action=skip_duplicate`).

## API

### Health

`GET /health`

Response:

```json
{"status":"ok"}
```

### Review a single partial-accept

`POST /v1/partial-accepts/review`

Request:

```json
{
  "request_id": "req-123",
  "bank_name": "Ravi Kumar Sharma",
  "pan_name": "Ravi Sharma",
  "model_score": 0.73
}
```

Response (example):

```json
{
  "request_id": "req-123",
  "bank_name": "Ravi Kumar Sharma",
  "pan_name": "Ravi Sharma",
  "normalized_bank_name": "RAVI KUMAR SHARMA",
  "normalized_pan_name": "RAVI SHARMA",
  "decision": "route_to_ops",
  "confidence": 0.79,
  "reasons": ["borderline_case_route_to_ops"],
  "model_score_used": 0.73,
  "features": {
    "sequence_ratio": 0.81,
    "levenshtein_ratio": 0.69,
    "token_jaccard": 0.66,
    "token_overlap": 0.66,
    "initials_match": false,
    "abbreviation_match": false,
    "first_token_match": true,
    "last_token_match": true,
    "heuristic_score": 0.81
  },
  "source": "computed",
  "should_create_ops_ticket": true,
  "ticket_action": "create",
  "cache_ttl_seconds_remaining": 0
}
```

### Review batch

`POST /v1/partial-accepts/review-batch`

Request:

```json
{
  "requests": [
    {
      "request_id": "req-a",
      "bank_name": "Mr. Rakesh Kumar Pvt Ltd.",
      "pan_name": "Rakesh Kumar",
      "model_score": 0.65
    },
    {
      "request_id": "req-b",
      "bank_name": "Ravi Kumar Sharma",
      "pan_name": "Ravi Sharma",
      "model_score": 0.73
    }
  ]
}
```

Response includes `decision_counts` and `ticket_action_counts` for quick monitoring.

## Configuration

Environment variables:

- `APPROVE_THRESHOLD` (default `0.86`)
- `MANUAL_REVIEW_FLOOR` (default `0.46`)
- `REJECT_THRESHOLD` (default `0.28`)
- `MODEL_WEIGHT` (default `0.35`)
- `OPS_DEDUPE_TTL_SECONDS` (default `86400`)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Run tests

```bash
python -m pytest
```
