# ML Name Matching - Partial Accept Ops Automation

Service to reduce ops load from *partial-accept* PAN vs bank-name matches.

## What this does

Your primary ML model marks some matches as `PARTIAL_ACCEPT`.  
Instead of sending all of them to ops, this service adds a second triage layer:

- `AUTO_ACCEPT`: safe, high-confidence cases (no ops ticket).
- `AUTO_REJECT`: clear mismatches (no ops ticket).
- `SEND_TO_OPS`: ambiguous/high-risk cases (ops ticket required).

The engine combines:

1. Model confidence (`ml_score`)
2. Name normalization
3. Token overlap
4. Sequence similarity
5. Initials compatibility (`R K SHARMA` vs `RAJ KUMAR SHARMA`)
6. Surname stability
7. Risk guardrails (e.g. sanctions/fraud flags always go to ops)

---

## Repository layout

```text
src/partial_accept_service/
  __main__.py          # server entrypoint
  api.py               # HTTP routes
  config.py            # configurable thresholds
  engine.py            # triage decision engine
  models.py            # input/output models
  normalization.py     # name normalization + similarity helpers
tests/
  test_engine.py
  test_api.py
run_service.py         # convenient local runner
```

---

## Run the service

```bash
python3 run_service.py
```

Defaults:

- host: `0.0.0.0`
- port: `8080`
- auto-accept threshold: `0.82`
- auto-reject threshold: `0.35`

Optional environment variables:

- `SERVICE_HOST`
- `SERVICE_PORT`
- `AUTO_ACCEPT_THRESHOLD`
- `AUTO_REJECT_THRESHOLD`

Example:

```bash
SERVICE_PORT=9090 AUTO_ACCEPT_THRESHOLD=0.84 python3 run_service.py
```

---

## API

### Health

`GET /health`

```json
{"status":"ok"}
```

### Single triage

`POST /triage`

Request:

```json
{
  "case_id": "case-123",
  "bank_name": "R K Sharma",
  "pan_name": "Raj Kumar Sharma",
  "ml_score": 0.66,
  "risk_flags": [],
  "metadata": {"source": "onboarding"}
}
```

Response:

```json
{
  "case_id": "case-123",
  "decision": "AUTO_ACCEPT",
  "decision_score": 0.88,
  "should_create_ops_ticket": false,
  "reasons": ["initial-based abbreviation is consistent with PAN name"],
  "features": {
    "bank_name_normalized": "R K SHARMA",
    "pan_name_normalized": "RAJ KUMAR SHARMA",
    "ml_score": 0.66,
    "sequence_similarity": 0.8,
    "token_jaccard": 0.2,
    "pan_token_coverage": 0.3333,
    "bank_token_coverage": 0.3333,
    "initials_compatible": true,
    "surname_match": true,
    "exact_match": false
  }
}
```

### Batch triage

`POST /triage/batch`

Request can be either:

- a raw list of cases, or
- an object: `{"cases": [ ... ]}`

Response includes `decision_counts` and per-case results.

---

## Integration pattern (recommended)

1. Existing model emits `PARTIAL_ACCEPT`.
2. Call this service with the same pair + model score.
3. Create ops ticket only when `decision == SEND_TO_OPS`.
4. Store triage result + reason for audit and threshold tuning.

---

## Run tests

```bash
python -m unittest discover -s tests -v
```
