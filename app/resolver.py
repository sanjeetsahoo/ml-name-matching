from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from app.config import settings
from app.normalize import is_initial, meaningful_tokens, normalized_string


@dataclass(frozen=True)
class ResolveResult:
    decision: str
    confidence: float
    reasons: list[str]
    bank_norm: str
    pan_norm: str
    features: dict


def _initials_compatible(a_tokens: list[str], b_tokens: list[str]) -> bool:
    """
    Allow matches like "RAVI KUMAR" vs "RAVI K" or "A K SHARMA" vs "ANIL K SHARMA".
    Strategy: for each initial token, check it matches the first letter of some
    non-initial token in the other side (order-insensitive).
    """
    a_non = [t for t in a_tokens if not is_initial(t)]
    b_non = [t for t in b_tokens if not is_initial(t)]
    a_inits = [t for t in a_tokens if is_initial(t)]
    b_inits = [t for t in b_tokens if is_initial(t)]

    def init_matches(init: str, pool: list[str]) -> bool:
        return any(p.startswith(init) for p in pool)

    return all(init_matches(i, b_non) for i in a_inits) and all(init_matches(i, a_non) for i in b_inits)


def resolve(bank_name: str, pan_name: str, *, entity_type: str = "unknown", ml_score: float | None = None) -> ResolveResult:
    bank_norm = normalized_string(bank_name, entity_type=entity_type)
    pan_norm = normalized_string(pan_name, entity_type=entity_type)

    bank_toks = meaningful_tokens(bank_name, entity_type=entity_type)
    pan_toks = meaningful_tokens(pan_name, entity_type=entity_type)

    reasons: list[str] = []
    features: dict = {
        "bank_tokens": bank_toks,
        "pan_tokens": pan_toks,
    }

    # Fast path
    if bank_norm == pan_norm and bank_norm:
        return ResolveResult(
            decision="auto_accept",
            confidence=max(1.0, ml_score or 0.0),
            reasons=["exact_normalized_match"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features={**features, "token_set_ratio": 100, "wratio": 100},
        )

    token_set_ratio = fuzz.token_set_ratio(bank_norm, pan_norm) if bank_norm and pan_norm else 0
    wratio = fuzz.WRatio(bank_norm, pan_norm) if bank_norm and pan_norm else 0
    features.update({"token_set_ratio": token_set_ratio, "wratio": wratio, "ml_score": ml_score})

    # Optional: respect high-confidence ML
    if ml_score is not None and ml_score >= settings.ml_score_auto_accept:
        return ResolveResult(
            decision="auto_accept",
            confidence=float(ml_score),
            reasons=["ml_score_high_override"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Optional: reject obviously poor matches (even if upstream called it partial)
    if ml_score is not None and ml_score <= settings.ml_score_auto_reject:
        return ResolveResult(
            decision="auto_reject",
            confidence=float(ml_score),
            reasons=["ml_score_low_override"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Require enough signal to avoid auto-accept on tiny names.
    if min(len(bank_toks), len(pan_toks)) < settings.min_meaningful_tokens:
        reasons.append("insufficient_tokens")
        return ResolveResult(
            decision="send_to_ops",
            confidence=max((ml_score or 0.0), wratio / 100.0, token_set_ratio / 100.0),
            reasons=reasons,
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Strong token overlap
    if token_set_ratio >= settings.token_set_ratio_auto_accept:
        return ResolveResult(
            decision="auto_accept",
            confidence=max((ml_score or 0.0), token_set_ratio / 100.0),
            reasons=["token_set_ratio_high"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Weighted ratio tends to work well for small reorderings and punctuation.
    if wratio >= settings.wratio_auto_accept:
        return ResolveResult(
            decision="auto_accept",
            confidence=max((ml_score or 0.0), wratio / 100.0),
            reasons=["wratio_high"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Subset containment (e.g., "RAHUL KUMAR" vs "RAHUL KUMAR SINGH")
    bank_set = set(bank_toks)
    pan_set = set(pan_toks)
    if bank_set.issubset(pan_set) or pan_set.issubset(bank_set):
        return ResolveResult(
            decision="auto_accept",
            confidence=max((ml_score or 0.0), token_set_ratio / 100.0),
            reasons=["token_subset_containment"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Initials compatibility
    if _initials_compatible(bank_toks, pan_toks):
        return ResolveResult(
            decision="auto_accept",
            confidence=max((ml_score or 0.0), wratio / 100.0, token_set_ratio / 100.0),
            reasons=["initials_compatible"],
            bank_norm=bank_norm,
            pan_norm=pan_norm,
            features=features,
        )

    # Otherwise: send to ops with explainability features.
    return ResolveResult(
        decision="send_to_ops",
        confidence=max((ml_score or 0.0), wratio / 100.0, token_set_ratio / 100.0),
        reasons=["no_safe_auto_resolution_rule_matched"],
        bank_norm=bank_norm,
        pan_norm=pan_norm,
        features=features,
    )
