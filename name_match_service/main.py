from __future__ import annotations

from fastapi import FastAPI

from name_match_service.decision_engine import Decision, PartialAcceptTriageEngine
from name_match_service.schemas import (
    BatchDecisionRequest,
    BatchDecisionResponse,
    PartialAcceptDecisionResponse,
    PartialAcceptRequest,
)

app = FastAPI(
    title="Partial Accept Triage Service",
    description=(
        "Reduces ops tickets by auto-resolving high-confidence partial "
        "bank-name vs PAN-name matches."
    ),
    version="0.1.0",
)

engine = PartialAcceptTriageEngine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/partial-accepts/decision", response_model=PartialAcceptDecisionResponse)
def decide(request: PartialAcceptRequest) -> PartialAcceptDecisionResponse:
    result = engine.decide(
        bank_name=request.bank_name,
        pan_name=request.pan_name,
        ml_score=request.ml_score,
    )

    return PartialAcceptDecisionResponse(
        request_id=request.request_id,
        decision=result.decision,
        confidence=result.confidence,
        reason_codes=result.reason_codes,
        features=result.features.__dict__,
        ops_ticket_required=result.decision == Decision.SEND_TO_OPS,
    )


@app.post("/v1/partial-accepts/decision/batch", response_model=BatchDecisionResponse)
def decide_batch(request: BatchDecisionRequest) -> BatchDecisionResponse:
    decisions: list[PartialAcceptDecisionResponse] = []
    auto_accept_count = 0
    auto_reject_count = 0
    sent_to_ops_count = 0

    for item in request.items:
        result = engine.decide(
            bank_name=item.bank_name,
            pan_name=item.pan_name,
            ml_score=item.ml_score,
        )
        if result.decision == Decision.AUTO_ACCEPT:
            auto_accept_count += 1
        elif result.decision == Decision.AUTO_REJECT:
            auto_reject_count += 1
        else:
            sent_to_ops_count += 1

        decisions.append(
            PartialAcceptDecisionResponse(
                request_id=item.request_id,
                decision=result.decision,
                confidence=result.confidence,
                reason_codes=result.reason_codes,
                features=result.features.__dict__,
                ops_ticket_required=result.decision == Decision.SEND_TO_OPS,
            )
        )

    return BatchDecisionResponse(
        total_items=len(request.items),
        auto_accept_count=auto_accept_count,
        auto_reject_count=auto_reject_count,
        sent_to_ops_count=sent_to_ops_count,
        decisions=decisions,
    )

