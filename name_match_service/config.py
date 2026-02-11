from __future__ import annotations

import os
from dataclasses import dataclass


def _float_from_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class DecisionConfig:
    """
    Thresholds for deciding whether a partial accept can be auto-resolved.

    Values are intentionally conservative by default:
    - only high-confidence matches auto-accept
    - only clear mismatches auto-reject
    - ambiguous cases still go to ops
    """

    auto_accept_threshold: float = 88.0
    auto_accept_min_coverage: float = 0.70
    auto_reject_threshold: float = 52.0
    auto_reject_conflict_ceiling: float = 72.0
    hard_reject_min_coverage: float = 0.35
    ml_score_weight: float = 0.30

    @classmethod
    def from_env(cls) -> "DecisionConfig":
        return cls(
            auto_accept_threshold=_float_from_env(
                "AUTO_ACCEPT_THRESHOLD", cls.auto_accept_threshold
            ),
            auto_accept_min_coverage=_float_from_env(
                "AUTO_ACCEPT_MIN_COVERAGE", cls.auto_accept_min_coverage
            ),
            auto_reject_threshold=_float_from_env(
                "AUTO_REJECT_THRESHOLD", cls.auto_reject_threshold
            ),
            auto_reject_conflict_ceiling=_float_from_env(
                "AUTO_REJECT_CONFLICT_CEILING", cls.auto_reject_conflict_ceiling
            ),
            hard_reject_min_coverage=_float_from_env(
                "HARD_REJECT_MIN_COVERAGE", cls.hard_reject_min_coverage
            ),
            ml_score_weight=_float_from_env("ML_SCORE_WEIGHT", cls.ml_score_weight),
        )

