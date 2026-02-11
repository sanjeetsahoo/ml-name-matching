# ml-name-matching

This repo contains a small service to **auto-resolve "partial accept" name matches** (bank name vs PAN name) using deterministic normalization + fuzzy matching heuristics, reducing the number of Ops tickets.

## Run locally

```bash
make install
make run
```

Service will start on `http://localhost:8000` (OpenAPI docs at `/docs`).

## API

### Resolve one

```bash
curl -s http://localhost:8000/v1/resolve \
  -H 'content-type: application/json' \
  -d '{
    "bank_name": "XYZ PVT LTD",
    "pan_name": "XYZ PRIVATE LIMITED",
    "entity_type": "company",
    "ml_score": 0.78
  }' | jq
```

### Resolve bulk

```bash
curl -s http://localhost:8000/v1/resolve/bulk \
  -H 'content-type: application/json' \
  -d '[
    {"bank_name":"RAVI KUMAR","pan_name":"RAVI K","ml_score":0.71},
    {"bank_name":"A","pan_name":"A","ml_score":0.71}
  ]' | jq
```

## How to use it in your pipeline

- Send only **partial accepts** from your ML model to this service.
- If response `decision == "auto_accept"`, skip creating an Ops ticket.
- If `decision == "send_to_ops"`, create a ticket and include `reasons` + `features` so Ops can decide faster.
- If `decision == "auto_reject"`, you can optionally auto-reject (or still route to Ops based on your risk appetite).
