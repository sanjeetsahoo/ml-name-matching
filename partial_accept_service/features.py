from dataclasses import asdict, dataclass

from rapidfuzz import fuzz

from partial_accept_service.normalization import (
    initials_signature,
    is_initial,
    normalize_name,
    tokenize_name,
)


@dataclass
class NameMatchFeatures:
    normalized_bank_name: str
    normalized_pan_name: str
    normalized_equal: bool
    token_jaccard: float
    token_containment: float
    raw_similarity: float
    token_sort_similarity: float
    initials_compatible: bool
    first_token_conflict: bool
    hard_mismatch: bool

    def asdict(self) -> dict[str, float | bool | str]:
        return asdict(self)


def _jaccard_similarity(left_tokens: list[str], right_tokens: list[str]) -> float:
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    intersection = len(left_set.intersection(right_set))
    union = len(left_set.union(right_set))
    return intersection / union


def _containment_similarity(left_tokens: list[str], right_tokens: list[str]) -> float:
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if not left_set or not right_set:
        return 0.0
    denominator = min(len(left_set), len(right_set))
    if denominator == 0:
        return 0.0
    return len(left_set.intersection(right_set)) / denominator


def _initials_compatible(left_tokens: list[str], right_tokens: list[str]) -> bool:
    if not left_tokens or not right_tokens:
        return False

    compare_len = min(len(left_tokens), len(right_tokens))
    ordered_matches = 0
    for idx in range(compare_len):
        left = left_tokens[idx]
        right = right_tokens[idx]
        if left == right:
            ordered_matches += 1
            continue
        if is_initial(left) and right.startswith(left):
            ordered_matches += 1
            continue
        if is_initial(right) and left.startswith(right):
            ordered_matches += 1

    if compare_len > 0 and (ordered_matches / compare_len) >= 0.8 and abs(len(left_tokens) - len(right_tokens)) <= 1:
        return True

    return initials_signature(left_tokens) == initials_signature(right_tokens)


def _first_token_conflict(left_tokens: list[str], right_tokens: list[str]) -> bool:
    if not left_tokens or not right_tokens:
        return False

    left_first = left_tokens[0]
    right_first = right_tokens[0]
    if is_initial(left_first) or is_initial(right_first):
        return False
    return left_first[0] != right_first[0]


def _hard_mismatch(
    *,
    token_jaccard: float,
    token_containment: float,
    raw_similarity: float,
    token_sort_similarity: float,
    initials_compatible: bool,
    first_token_conflict: bool,
) -> bool:
    if initials_compatible:
        return False

    low_overlap = token_jaccard <= 0.15 and token_sort_similarity < 58.0
    very_low_similarity = token_containment < 0.34 and raw_similarity < 50.0
    conflicting_primary_token = first_token_conflict and token_jaccard < 0.4
    return low_overlap or very_low_similarity or conflicting_primary_token


def calculate_name_match_features(bank_name: str, pan_name: str) -> NameMatchFeatures:
    normalized_bank_name = normalize_name(bank_name)
    normalized_pan_name = normalize_name(pan_name)
    bank_tokens = tokenize_name(bank_name)
    pan_tokens = tokenize_name(pan_name)

    token_jaccard = _jaccard_similarity(bank_tokens, pan_tokens)
    token_containment = _containment_similarity(bank_tokens, pan_tokens)
    raw_similarity = float(fuzz.ratio(normalized_bank_name, normalized_pan_name))
    token_sort_similarity = float(fuzz.token_sort_ratio(normalized_bank_name, normalized_pan_name))
    initials_compatible = _initials_compatible(bank_tokens, pan_tokens)
    first_token_conflict = _first_token_conflict(bank_tokens, pan_tokens)
    normalized_equal = normalized_bank_name == normalized_pan_name
    hard_mismatch = _hard_mismatch(
        token_jaccard=token_jaccard,
        token_containment=token_containment,
        raw_similarity=raw_similarity,
        token_sort_similarity=token_sort_similarity,
        initials_compatible=initials_compatible,
        first_token_conflict=first_token_conflict,
    )

    return NameMatchFeatures(
        normalized_bank_name=normalized_bank_name,
        normalized_pan_name=normalized_pan_name,
        normalized_equal=normalized_equal,
        token_jaccard=round(token_jaccard, 4),
        token_containment=round(token_containment, 4),
        raw_similarity=round(raw_similarity, 2),
        token_sort_similarity=round(token_sort_similarity, 2),
        initials_compatible=initials_compatible,
        first_token_conflict=first_token_conflict,
        hard_mismatch=hard_mismatch,
    )
