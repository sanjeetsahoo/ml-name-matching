"""FastAPI wrapper for partial accept triage service."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from name_triage_engine import (
    Decision,
    PartialAcceptTriageService,
    TriageInput,
    TriageResult,
    summarize_results,
)


class TriageRequest(BaseModel):
    bank_name: str = Field(..., min_length=1, description="Name from bank source")
    pan_name: str = Field(..., min_length=1, description="Name from PAN source")
    ml_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional score from existing ML model",
    )
    case_id: str | None = Field(default=None, description="External identifier")


class TriageResponse(BaseModel):
    case_id: str | None = None
    decision: Decision
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_codes: list[str]
    normalized_bank_name: str
    normalized_pan_name: str
    features: dict[str, float]

    @classmethod
    def from_result(cls, result: TriageResult) -> "TriageResponse":
        return cls(
            case_id=result.case_id,
            decision=result.decision,
            confidence=result.confidence,
            reason_codes=result.reason_codes,
            normalized_bank_name=result.normalized_bank_name,
            normalized_pan_name=result.normalized_pan_name,
            features=result.features,
        )


class BatchTriageRequest(BaseModel):
    cases: list[TriageRequest] = Field(..., min_length=1)


class BatchTriageResponse(BaseModel):
    summary: dict[str, float | int]
    decisions: list[TriageResponse]


app = FastAPI(
    title="Partial Accepts Triage Service",
    description=(
        "Post-processes ML partial accepts for bank-name vs PAN-name matching to "
        "reduce ops workload."
    ),
    version="0.1.0",
)

triage_service = PartialAcceptTriageService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
def triage_case(request: TriageRequest) -> TriageResponse:
    result = triage_service.evaluate(
        TriageInput(
            bank_name=request.bank_name,
            pan_name=request.pan_name,
            ml_score=request.ml_score,
            case_id=request.case_id,
        )
    )
    return TriageResponse.from_result(result)


@app.post("/triage/batch", response_model=BatchTriageResponse)
def triage_batch(request: BatchTriageRequest) -> BatchTriageResponse:
    results: list[TriageResult] = []
    for item in request.cases:
        result = triage_service.evaluate(
            TriageInput(
                bank_name=item.bank_name,
                pan_name=item.pan_name,
                ml_score=item.ml_score,
                case_id=item.case_id,
            )
        )
        results.append(result)

    return BatchTriageResponse(
        summary=summarize_results(results),
        decisions=[TriageResponse.from_result(result) for result in results],
    )
