from __future__ import annotations

import re
import unicodedata

NOISE_TOKENS = {
    "MR",
    "MRS",
    "MS",
    "DR",
    "SHRI",
    "SMT",
    "KUMARI",
    "MISS",
}


def normalize_name(raw_name: str) -> str:
    """
    Normalize names for robust matching.

    Steps:
    - normalize unicode and strip accents
    - uppercase
    - drop punctuation/symbols
    - collapse extra spaces
    """

    text = unicodedata.normalize("NFKD", raw_name or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.upper()
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_name(normalized_name: str) -> list[str]:
    tokens = [token for token in normalized_name.split(" ") if token]
    return [token for token in tokens if token not in NOISE_TOKENS]


def is_token_equivalent(token_a: str, token_b: str) -> bool:
    """
    Two tokens are equivalent when exact, or one is an initial of the other.
    """

    if token_a == token_b:
        return True
    if len(token_a) == 1 and token_b.startswith(token_a):
        return True
    if len(token_b) == 1 and token_a.startswith(token_b):
        return True
    return False

