from __future__ import annotations

from pydantic import BaseModel


class Settings(BaseModel):
    # Fuzzy thresholds
    token_set_ratio_auto_accept: int = 95
    wratio_auto_accept: int = 93

    # Optional ML score overrides (if provided by caller)
    ml_score_auto_accept: float = 0.92
    ml_score_auto_reject: float = 0.50

    # Safety: require at least this many meaningful tokens on both sides
    min_meaningful_tokens: int = 2


settings = Settings()
