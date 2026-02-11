from __future__ import annotations

from fastapi import FastAPI

from app.models import ResolveRequest, ResolveResponse
from app.resolver import resolve


app = FastAPI(title="Partial Accept Resolver", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/v1/resolve", response_model=ResolveResponse)
def resolve_one(req: ResolveRequest) -> ResolveResponse:
    res = resolve(req.bank_name, req.pan_name, entity_type=req.entity_type, ml_score=req.ml_score)
    return ResolveResponse(
        decision=res.decision,
        confidence=res.confidence,
        reasons=res.reasons,
        bank_normalized=res.bank_norm,
        pan_normalized=res.pan_norm,
        features=res.features,
    )


@app.post("/v1/resolve/bulk", response_model=list[ResolveResponse])
def resolve_bulk(reqs: list[ResolveRequest]) -> list[ResolveResponse]:
    out: list[ResolveResponse] = []
    for r in reqs:
        res = resolve(r.bank_name, r.pan_name, entity_type=r.entity_type, ml_score=r.ml_score)
        out.append(
            ResolveResponse(
                decision=res.decision,
                confidence=res.confidence,
                reasons=res.reasons,
                bank_normalized=res.bank_norm,
                pan_normalized=res.pan_norm,
                features=res.features,
            )
        )
    return out

