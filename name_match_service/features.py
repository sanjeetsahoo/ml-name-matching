from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

from name_match_service.normalization import (
    is_token_equivalent,
    normalize_name,
    tokenize_name,
)


@dataclass(frozen=True)
class NameFeatures:
    bank_normalized: str
    pan_normalized: str
    bank_tokens: list[str]
    pan_tokens: list[str]
    token_set_score: float
    token_sort_score: float
    jaro_winkler_score: float
    lexical_score: float
    ml_score: float
    blended_score: float
    soft_coverage: float
    first_token_conflict: bool
    first_token_match: bool
    surname_match: bool
    exact_match: bool
    unmatched_pan_tokens: list[str]
    unmatched_bank_tokens: list[str]


def normalize_ml_score(raw_ml_score: float | None) -> float:
    """
    Accept model score in [0,1] or [0,100] and return [0,100].
    """

    if raw_ml_score is None:
        return 0.0
    value = max(0.0, float(raw_ml_score))
    if value <= 1.0:
        return value * 100.0
    return min(value, 100.0)


def _sorted_join(tokens: list[str]) -> str:
    return " ".join(sorted(tokens))


def _soft_match(
    source_tokens: list[str], target_tokens: list[str]
) -> tuple[list[str], list[str], int]:
    """
    Greedy one-to-one matching with token-equivalence checks.
    """

    remaining_target = target_tokens.copy()
    matched = 0
    unmatched_source: list[str] = []
    for source in source_tokens:
        found_idx = next(
            (
                idx
                for idx, candidate in enumerate(remaining_target)
                if is_token_equivalent(source, candidate)
            ),
            None,
        )
        if found_idx is None:
            unmatched_source.append(source)
            continue
        matched += 1
        remaining_target.pop(found_idx)
    return unmatched_source, remaining_target, matched


def extract_name_features(
    bank_name: str, pan_name: str, ml_score: float | None
) -> NameFeatures:
    bank_normalized = normalize_name(bank_name)
    pan_normalized = normalize_name(pan_name)

    bank_tokens = tokenize_name(bank_normalized)
    pan_tokens = tokenize_name(pan_normalized)

    bank_joined = _sorted_join(bank_tokens)
    pan_joined = _sorted_join(pan_tokens)

    token_set_score = fuzz.token_set_ratio(bank_joined, pan_joined)
    token_sort_score = fuzz.token_sort_ratio(bank_joined, pan_joined)
    jaro_winkler_score = JaroWinkler.similarity(bank_joined, pan_joined) * 100.0

    lexical_score = (
        (0.45 * token_set_score) + (0.35 * token_sort_score) + (0.20 * jaro_winkler_score)
    )
    ml_score_normalized = normalize_ml_score(ml_score)
    blended_score = (0.70 * lexical_score) + (0.30 * ml_score_normalized)

    unmatched_pan_tokens, unmatched_bank_tokens, matched_count = _soft_match(
        pan_tokens, bank_tokens
    )
    denominator = max(len(pan_tokens), len(bank_tokens), 1)
    soft_coverage = matched_count / denominator

    first_pan = pan_tokens[0] if pan_tokens else ""
    first_bank = bank_tokens[0] if bank_tokens else ""
    first_token_match = bool(first_pan and first_bank and is_token_equivalent(first_pan, first_bank))
    first_token_conflict = bool(
        first_pan
        and first_bank
        and not first_token_match
        and len(first_pan) > 1
        and len(first_bank) > 1
    )

    surname_pan = pan_tokens[-1] if pan_tokens else ""
    surname_bank = bank_tokens[-1] if bank_tokens else ""
    surname_match = bool(
        surname_pan and surname_bank and is_token_equivalent(surname_pan, surname_bank)
    )

    exact_match = bank_joined == pan_joined and bank_joined != ""

    return NameFeatures(
        bank_normalized=bank_normalized,
        pan_normalized=pan_normalized,
        bank_tokens=bank_tokens,
        pan_tokens=pan_tokens,
        token_set_score=round(token_set_score, 2),
        token_sort_score=round(token_sort_score, 2),
        jaro_winkler_score=round(jaro_winkler_score, 2),
        lexical_score=round(lexical_score, 2),
        ml_score=round(ml_score_normalized, 2),
        blended_score=round(blended_score, 2),
        soft_coverage=round(soft_coverage, 3),
        first_token_conflict=first_token_conflict,
        first_token_match=first_token_match,
        surname_match=surname_match,
        exact_match=exact_match,
        unmatched_pan_tokens=unmatched_pan_tokens,
        unmatched_bank_tokens=unmatched_bank_tokens,
    )

