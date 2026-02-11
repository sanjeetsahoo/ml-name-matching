from __future__ import annotations

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler, Levenshtein

from app.normalization import normalize_name, token_equivalent, tokenize_name
from app.schemas import SimilarityFeatures


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _greedy_token_matches(tokens_a: list[str], tokens_b: list[str]) -> int:
    used_b: set[int] = set()
    matches = 0
    for token_a in tokens_a:
        for index_b, token_b in enumerate(tokens_b):
            if index_b in used_b:
                continue
            if token_equivalent(token_a, token_b):
                used_b.add(index_b)
                matches += 1
                break
    return matches


def _initial_alignment(tokens_a: list[str], tokens_b: list[str]) -> float:
    initials_a = [token for token in tokens_a if len(token) == 1]
    initials_b = [token for token in tokens_b if len(token) == 1]

    if not initials_a and not initials_b:
        return 1.0

    first_chars_a = {token[0] for token in tokens_a}
    first_chars_b = {token[0] for token in tokens_b}

    total_checks = 0
    matched = 0

    for initial in initials_a:
        total_checks += 1
        if initial in first_chars_b:
            matched += 1

    for initial in initials_b:
        total_checks += 1
        if initial in first_chars_a:
            matched += 1

    if total_checks == 0:
        return 1.0
    return matched / total_checks


def _subset_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    if not tokens_a or not tokens_b:
        return False

    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    used_longer: set[int] = set()

    for token in shorter:
        found = False
        for idx, candidate in enumerate(longer):
            if idx in used_longer:
                continue
            if token_equivalent(token, candidate):
                used_longer.add(idx)
                found = True
                break
        if not found:
            return False
    return True


def extract_similarity_features(
    bank_name: str,
    pan_name: str,
    model_score: float,
) -> SimilarityFeatures:
    normalized_bank_name = normalize_name(bank_name)
    normalized_pan_name = normalize_name(pan_name)
    bank_tokens = tokenize_name(bank_name)
    pan_tokens = tokenize_name(pan_name)

    token_sort_ratio = fuzz.token_sort_ratio(normalized_bank_name, normalized_pan_name) / 100.0
    token_set_ratio = fuzz.token_set_ratio(normalized_bank_name, normalized_pan_name) / 100.0
    partial_ratio = fuzz.partial_ratio(normalized_bank_name, normalized_pan_name) / 100.0
    jaro_winkler = JaroWinkler.similarity(normalized_bank_name, normalized_pan_name)
    levenshtein_similarity = Levenshtein.normalized_similarity(
        normalized_bank_name, normalized_pan_name
    )

    if bank_tokens and pan_tokens:
        matched_tokens = _greedy_token_matches(bank_tokens, pan_tokens)
        token_overlap_shorter = matched_tokens / min(len(bank_tokens), len(pan_tokens))
        token_overlap_overall = matched_tokens / max(len(bank_tokens), len(pan_tokens))
        first_token_match = token_equivalent(bank_tokens[0], pan_tokens[0])
        surname_match = token_equivalent(bank_tokens[-1], pan_tokens[-1])
    else:
        token_overlap_shorter = 0.0
        token_overlap_overall = 0.0
        first_token_match = False
        surname_match = False

    initial_alignment = _initial_alignment(bank_tokens, pan_tokens)
    subset_match = _subset_match(bank_tokens, pan_tokens)

    risk_flags: list[str] = []
    if bank_tokens and pan_tokens and len(bank_tokens) >= 2 and len(pan_tokens) >= 2 and not surname_match:
        risk_flags.append("surname_mismatch")
    if bank_tokens and pan_tokens and not first_token_match and token_overlap_shorter < 0.75:
        risk_flags.append("first_token_mismatch")
    if token_overlap_shorter < 0.50:
        risk_flags.append("low_token_overlap")
    if abs(len(normalized_bank_name) - len(normalized_pan_name)) > 12:
        risk_flags.append("large_length_gap")
    if min(len(bank_tokens) if bank_tokens else 0, len(pan_tokens) if pan_tokens else 0) <= 1:
        risk_flags.append("single_token_profile")

    combined_score = (
        0.22 * token_sort_ratio
        + 0.22 * token_set_ratio
        + 0.18 * jaro_winkler
        + 0.12 * levenshtein_similarity
        + 0.12 * token_overlap_shorter
        + 0.08 * initial_alignment
        + 0.06 * model_score
    )
    if surname_match:
        combined_score += 0.04
    if subset_match:
        combined_score += 0.04
    if "surname_mismatch" in risk_flags:
        combined_score -= 0.08
    if "first_token_mismatch" in risk_flags:
        combined_score -= 0.05

    combined_score = _clamp(combined_score)

    return SimilarityFeatures(
        normalized_bank_name=normalized_bank_name,
        normalized_pan_name=normalized_pan_name,
        token_sort_ratio=_clamp(token_sort_ratio),
        token_set_ratio=_clamp(token_set_ratio),
        jaro_winkler=_clamp(jaro_winkler),
        levenshtein_similarity=_clamp(levenshtein_similarity),
        partial_ratio=_clamp(partial_ratio),
        token_overlap_shorter=_clamp(token_overlap_shorter),
        token_overlap_overall=_clamp(token_overlap_overall),
        initial_alignment=_clamp(initial_alignment),
        surname_match=surname_match,
        first_token_match=first_token_match,
        subset_match=subset_match,
        model_score=_clamp(model_score),
        combined_score=combined_score,
        risk_flags=risk_flags,
    )

