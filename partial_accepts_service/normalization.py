"""Name normalization helpers for bank/PAN comparison."""

from __future__ import annotations

import re
from typing import Iterable

_PUNCTUATION_RE = re.compile(r"[^A-Z0-9\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")

_STOPWORDS = {
    "MR",
    "MRS",
    "MS",
    "DR",
    "SHRI",
    "SMT",
    "MISS",
    "M/S",
    "PRIVATE",
    "PVT",
    "LIMITED",
    "LTD",
    "LLP",
    "LLC",
    "INC",
    "CORP",
    "CORPORATION",
    "COMPANY",
    "CO",
}


def _cleanup(name: str) -> str:
    cleaned = name.strip().upper().replace("&", " AND ")
    cleaned = _PUNCTUATION_RE.sub(" ", cleaned)
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()


def normalize_tokens(name: str) -> list[str]:
    """Return canonical tokens while removing common legal/honorific noise."""
    cleaned = _cleanup(name)
    if not cleaned:
        return []
    return [token for token in cleaned.split(" ") if token and token not in _STOPWORDS]


def normalize_name(name: str) -> str:
    return " ".join(normalize_tokens(name))


def initials(tokens: Iterable[str]) -> str:
    token_list = [token for token in tokens if token]
    return "".join(token[0] for token in token_list)
