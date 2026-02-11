from __future__ import annotations

import re

TITLE_TOKENS = {
    "MR",
    "MRS",
    "MS",
    "MISS",
    "DR",
    "SHRI",
    "SHREE",
    "SMT",
    "SRI",
}

NON_ALPHA = re.compile(r"[^A-Z\s]")
MULTI_SPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Normalize noisy name strings before fuzzy matching."""
    cleaned = NON_ALPHA.sub(" ", name.upper())
    cleaned = MULTI_SPACE.sub(" ", cleaned).strip()
    tokens = [token for token in cleaned.split(" ") if token and token not in TITLE_TOKENS]
    return " ".join(tokens)


def tokenize_name(name: str) -> list[str]:
    normalized = normalize_name(name)
    return normalized.split(" ") if normalized else []


def token_equivalent(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) == 1 and right.startswith(left):
        return True
    if len(right) == 1 and left.startswith(right):
        return True
    return False

