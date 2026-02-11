from fastapi import FastAPI

from partial_accept_service.decision_engine import PartialAcceptDecisionEngine
from partial_accept_service.schemas import (
    BatchDecisionRequest,
    BatchDecisionResponse,
    DecisionResponse,
    PartialAcceptCase,
)

app = FastAPI(
    title="Partial Accept Ops Automation Service",
    description="Auto-resolve safe partial name matches to reduce Ops tickets.",
    version="0.1.0",
)
engine = PartialAcceptDecisionEngine()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/partial-accept/decide", response_model=DecisionResponse)
def decide_partial_accept(payload: PartialAcceptCase) -> DecisionResponse:
    return engine.decide(payload)


@app.post("/v1/partial-accept/decide-batch", response_model=BatchDecisionResponse)
def decide_partial_accept_batch(payload: BatchDecisionRequest) -> BatchDecisionResponse:
    return BatchDecisionResponse(decisions=[engine.decide(item) for item in payload.cases])
