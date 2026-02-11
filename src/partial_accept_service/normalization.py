"""Name normalization and similarity helpers for PAN/bank matching."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

NON_ALNUM_PATTERN = re.compile(r"[^A-Z0-9 ]+")
MULTI_SPACE_PATTERN = re.compile(r"\s+")

# Common words that usually do not help identify the entity.
STOP_WORDS = {
    "MR",
    "MRS",
    "MS",
    "MISS",
    "DR",
    "SHRI",
    "SMT",
    "KUMARI",
    "KU",
    "LATE",
    "M",
    "S",
    "O",
    "D",
    "W",
    "MS",
    "M/S",
    "AND",
    "THE",
}

# Conservative normalization for common variations.
TOKEN_SYNONYMS = {
    "MOHD": "MOHAMMED",
    "MOHAMMAD": "MOHAMMED",
    "MUHAMMAD": "MOHAMMED",
    "AHMED": "AHMAD",
    "SINGHJI": "SINGH",
}


def _clean_text(name: str) -> str:
    text = name.upper().strip()
    text = text.replace("&", " AND ")
    text = NON_ALNUM_PATTERN.sub(" ", text)
    return MULTI_SPACE_PATTERN.sub(" ", text).strip()


def normalize_name(name: str) -> str:
    """
    Normalize a raw name into a canonical comparison form.

    Steps:
    1) Uppercase and remove punctuation/noise
    2) Remove non-informative tokens
    3) Canonicalize a few frequent spelling variants
    """
    cleaned = _clean_text(name)
    if not cleaned:
        return ""

    tokens: list[str] = []
    for token in cleaned.split():
        if token in STOP_WORDS:
            continue
        token = TOKEN_SYNONYMS.get(token, token)
        tokens.append(token)
    return " ".join(tokens)


def tokenize(name: str) -> tuple[str, ...]:
    """Split a normalized name to immutable token tuple."""
    normalized = normalize_name(name)
    if not normalized:
        return tuple()
    return tuple(normalized.split())


def sequence_similarity(left: str, right: str) -> float:
    """Character-level similarity using difflib ratio."""
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=normalize_name(left), b=normalize_name(right)).ratio()


def _as_set(tokens: Iterable[str]) -> set[str]:
    return {token for token in tokens if token}


def token_jaccard(left_tokens: Iterable[str], right_tokens: Iterable[str]) -> float:
    """Jaccard similarity on token sets."""
    left_set = _as_set(left_tokens)
    right_set = _as_set(right_tokens)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def token_coverage(reference_tokens: Iterable[str], observed_tokens: Iterable[str]) -> float:
    """
    Return the share of reference tokens present in observed tokens.

    Example:
      reference=PAN tokens, observed=bank tokens
      => "How much of PAN name appears in bank name?"
    """
    ref_set = _as_set(reference_tokens)
    observed_set = _as_set(observed_tokens)
    if not ref_set:
        return 0.0
    return len(ref_set & observed_set) / len(ref_set)


def _is_initial(token: str) -> bool:
    return len(token) == 1 and token.isalpha()


def initials_compatible(left_tokens: tuple[str, ...], right_tokens: tuple[str, ...]) -> bool:
    """
    Check if two token sequences are compatible considering initials.

    This allows:
      "R K SHARMA" <-> "RAJ KUMAR SHARMA"
      "A B C" <-> "ANIL BHARAT CHOUDHARY"
    """
    if not left_tokens or not right_tokens:
        return False

    # Greedy match shorter sequence against longer sequence.
    if len(left_tokens) <= len(right_tokens):
        shorter, longer = left_tokens, right_tokens
    else:
        shorter, longer = right_tokens, left_tokens

    s_idx = 0
    l_idx = 0
    while s_idx < len(shorter) and l_idx < len(longer):
        s_token = shorter[s_idx]
        l_token = longer[l_idx]

        if s_token == l_token:
            s_idx += 1
            l_idx += 1
            continue

        if _is_initial(s_token) and l_token.startswith(s_token):
            s_idx += 1
            l_idx += 1
            continue

        if _is_initial(l_token) and s_token.startswith(l_token):
            s_idx += 1
            l_idx += 1
            continue

        # Allow skipped middle tokens in the longer name.
        l_idx += 1

    return s_idx == len(shorter)


def surnames_match(left_tokens: tuple[str, ...], right_tokens: tuple[str, ...]) -> bool:
    """Conservative surname check on final tokens."""
    if not left_tokens or not right_tokens:
        return False

    left_last = left_tokens[-1]
    right_last = right_tokens[-1]
    if left_last == right_last:
        return True

    if _is_initial(left_last) and right_last.startswith(left_last):
        return True
    if _is_initial(right_last) and left_last.startswith(right_last):
        return True
    return False
