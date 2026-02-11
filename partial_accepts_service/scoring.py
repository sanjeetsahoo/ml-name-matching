"""Similarity feature engineering for name-matching decisions."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from partial_accepts_service.normalization import initials, normalize_tokens


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        curr_row = [i]
        for j, char_b in enumerate(b, start=1):
            insertion = curr_row[j - 1] + 1
            deletion = prev_row[j] + 1
            substitution = prev_row[j - 1] + (char_a != char_b)
            curr_row.append(min(insertion, deletion, substitution))
        prev_row = curr_row
    return prev_row[-1]


def _token_jaccard(tokens_a: list[str], tokens_b: list[str]) -> float:
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _token_overlap(tokens_a: list[str], tokens_b: list[str]) -> float:
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / max(len(set_a), len(set_b))


def _is_abbreviation_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    if not tokens_a or not tokens_b:
        return False

    short, long = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    short_has_initials = all(len(token) == 1 for token in short[:-1])
    if not short_has_initials:
        return False
    if short[-1] != long[-1]:
        return False
    for idx, token in enumerate(short[:-1]):
        if idx >= len(long) - 1:
            return False
        if token != long[idx][0]:
            return False
    return True


@dataclass(frozen=True)
class SimilarityFeatures:
    bank_tokens: list[str]
    pan_tokens: list[str]
    sequence_ratio: float
    levenshtein_ratio: float
    token_jaccard: float
    token_overlap: float
    initials_match: bool
    abbreviation_match: bool
    first_token_match: bool
    last_token_match: bool
    heuristic_score: float

    @property
    def bank_normalized(self) -> str:
        return " ".join(self.bank_tokens)

    @property
    def pan_normalized(self) -> str:
        return " ".join(self.pan_tokens)

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "sequence_ratio": round(self.sequence_ratio, 4),
            "levenshtein_ratio": round(self.levenshtein_ratio, 4),
            "token_jaccard": round(self.token_jaccard, 4),
            "token_overlap": round(self.token_overlap, 4),
            "initials_match": self.initials_match,
            "abbreviation_match": self.abbreviation_match,
            "first_token_match": self.first_token_match,
            "last_token_match": self.last_token_match,
            "heuristic_score": round(self.heuristic_score, 4),
        }


def build_similarity_features(bank_name: str, pan_name: str) -> SimilarityFeatures:
    bank_tokens = normalize_tokens(bank_name)
    pan_tokens = normalize_tokens(pan_name)

    bank_normalized = " ".join(bank_tokens)
    pan_normalized = " ".join(pan_tokens)

    sequence_ratio = SequenceMatcher(None, bank_normalized, pan_normalized).ratio()
    max_len = max(len(bank_normalized), len(pan_normalized))
    levenshtein_ratio = 1.0 if max_len == 0 else 1 - (_levenshtein_distance(bank_normalized, pan_normalized) / max_len)
    token_jaccard = _token_jaccard(bank_tokens, pan_tokens)
    token_overlap = _token_overlap(bank_tokens, pan_tokens)
    initials_match = bool(bank_tokens and pan_tokens and initials(bank_tokens) == initials(pan_tokens))
    abbreviation_match = _is_abbreviation_match(bank_tokens, pan_tokens)
    first_token_match = bool(bank_tokens and pan_tokens and bank_tokens[0] == pan_tokens[0])
    last_token_match = bool(bank_tokens and pan_tokens and bank_tokens[-1] == pan_tokens[-1])

    score = (
        (0.32 * sequence_ratio)
        + (0.28 * levenshtein_ratio)
        + (0.22 * token_jaccard)
        + (0.18 * token_overlap)
    )
    if initials_match:
        score += 0.05
    if abbreviation_match:
        score += 0.08
    if first_token_match and last_token_match:
        score += 0.05
    heuristic_score = min(1.0, max(0.0, score))

    return SimilarityFeatures(
        bank_tokens=bank_tokens,
        pan_tokens=pan_tokens,
        sequence_ratio=sequence_ratio,
        levenshtein_ratio=levenshtein_ratio,
        token_jaccard=token_jaccard,
        token_overlap=token_overlap,
        initials_match=initials_match,
        abbreviation_match=abbreviation_match,
        first_token_match=first_token_match,
        last_token_match=last_token_match,
        heuristic_score=heuristic_score,
    )
