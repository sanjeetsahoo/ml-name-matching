"""Runtime configuration for triage thresholds."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value


@dataclass(frozen=True)
class TriageConfig:
    """Thresholds used by the decision engine."""

    auto_accept_threshold: float = 0.82
    auto_reject_threshold: float = 0.35

    @classmethod
    def from_env(cls) -> "TriageConfig":
        auto_accept = _float_env("AUTO_ACCEPT_THRESHOLD", cls.auto_accept_threshold)
        auto_reject = _float_env("AUTO_REJECT_THRESHOLD", cls.auto_reject_threshold)

        # Keep thresholds in a safe and monotonic range.
        auto_accept = max(0.5, min(1.0, auto_accept))
        auto_reject = max(0.0, min(0.5, auto_reject))
        if auto_reject >= auto_accept:
            auto_reject = min(0.45, auto_accept - 0.1)

        return cls(
            auto_accept_threshold=auto_accept,
            auto_reject_threshold=auto_reject,
        )
