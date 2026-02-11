# ml-name-matching

Service to reduce ops tickets from bank-name vs PAN-name **partial accepts**.

## What this does

Your upstream ML model already classifies name matches and sends ambiguous ("partial accept") cases to ops.
This service is a second-pass triage layer that:

- auto-approves high-confidence partial accepts
- auto-rejects clear mismatches
- sends only ambiguous cases to ops

Decision output per case:

- `AUTO_APPROVE`
- `AUTO_REJECT`
- `REVIEW_OPS`

## Decision logic (high level)

For every partial case (`bank_name`, `pan_name`, `model_score`), the service computes:

- normalized and tokenized names
- fuzzy matching scores (`token_sort`, `token_set`, `partial_ratio`)
- string distance scores (`Jaro-Winkler`, normalized Levenshtein)
- token overlap, initials alignment, surname checks, subset containment
- risk flags (surname mismatch, low overlap, first-token mismatch, etc.)

Then it produces a composite score and applies policy thresholds:

- strong + safe match => `AUTO_APPROVE`
- clear mismatch => `AUTO_REJECT`
- otherwise => `REVIEW_OPS`

## API

### Health

`GET /health`

### Triage endpoint

`POST /v1/partial-accepts/triage`

Request:

```json
{
  "cases": [
    {
      "case_id": "txn-001",
      "bank_name": "R K Sharma",
      "pan_name": "Rahul Kumar Sharma",
      "model_score": 0.68,
      "metadata": {
        "account_id": "A-991"
      }
    }
  ],
  "policy": {
    "auto_approve_threshold": 0.86,
    "auto_reject_threshold": 0.45,
    "high_model_score_threshold": 0.75,
    "low_model_score_threshold": 0.4
  },
  "include_features": true
}
```

Response (shape):

```json
{
  "summary": {
    "total_cases": 1,
    "auto_approved": 1,
    "auto_rejected": 0,
    "sent_to_ops": 0,
    "ops_reduction_ratio": 1.0
  },
  "decisions": [
    {
      "case_id": "txn-001",
      "decision": "AUTO_APPROVE",
      "confidence": 0.71,
      "ops_ticket_required": false,
      "reasons": [
        "High composite similarity with strong token alignment."
      ],
      "features": {
        "...": "..."
      },
      "metadata": {
        "account_id": "A-991"
      }
    }
  ]
}
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run tests

```bash
pytest -q
```

## How to integrate in your pipeline

1. Keep your current ML model and thresholds.
2. Send only **partial-accept** cases to this service.
3. Use result:
   - `AUTO_APPROVE` => finalize automatically
   - `AUTO_REJECT` => reject automatically
   - `REVIEW_OPS` => create ops ticket
4. Log downstream decisions and periodically tune policy thresholds using actual outcomes.
