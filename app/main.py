from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.policy import triage_cases
from app.schemas import TriageRequest, TriageResponse

app = FastAPI(
    title="Partial Accept Triage Service",
    description=(
        "Second-pass service to reduce manual ops load for bank-name vs PAN-name "
        "partial accepts."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/partial-accepts/triage", response_model=TriageResponse)
def triage_partial_accepts(request: TriageRequest) -> TriageResponse:
    try:
        return triage_cases(
            cases=request.cases,
            policy=request.policy,
            include_features=request.include_features,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

