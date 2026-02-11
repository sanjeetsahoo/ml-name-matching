from __future__ import annotations

import re
import unicodedata


_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9 ]+")

# Common salutations/honorifics in India + generic.
_HONORIFICS = {
    "MR",
    "MRS",
    "MS",
    "MISS",
    "DR",
    "SHRI",
    "SHREE",
    "SMT",
    "KUMARI",
    "KUM",
    "SRI",
    "LT",
    "COL",
    "CAPT",
}

# Common noise tokens.
_NOISE = {"THE", "AND", "OR", "OF"}

# Company suffix normalization map (aggressive but useful when entity_type=company/unknown).
_COMPANY_CANON = {
    "PVT": "PRIVATE",
    "PVT.": "PRIVATE",
    "PTE": "PRIVATE",
    "PVTLTD": "PRIVATE LIMITED",
    "LTD": "LIMITED",
    "LTD.": "LIMITED",
    "LIMITED": "LIMITED",
    "PRIVATE": "PRIVATE",
    "PVT LTD": "PRIVATE LIMITED",
    "PVT. LTD": "PRIVATE LIMITED",
    "PVT. LIMITED": "PRIVATE LIMITED",
    "PVT LIMITED": "PRIVATE LIMITED",
    "CO": "COMPANY",
    "CO.": "COMPANY",
    "COMP": "COMPANY",
    "LLP": "LLP",
    "INC": "INC",
    "INC.": "INC",
}


def _strip_accents(s: str) -> str:
    # Keep ASCII; PAN/bank names are typically ascii-ish but this helps with accidental unicode.
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def basic_normalize(s: str) -> str:
    s = _strip_accents(s)
    s = s.upper()
    s = s.replace("&", " AND ")
    s = s.replace("/", " ")
    s = _NON_ALNUM_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def tokenize(s: str) -> list[str]:
    s = basic_normalize(s)
    if not s:
        return []
    return [t for t in s.split(" ") if t]


def normalize_tokens(tokens: list[str], *, entity_type: str = "unknown") -> list[str]:
    out: list[str] = []
    for t in tokens:
        if t in _HONORIFICS or t in _NOISE:
            continue
        out.append(t)

    # Company canonicalization: join, replace known suffix patterns, split again.
    if entity_type in {"company", "unknown"}:
        joined = " ".join(out)
        for k, v in _COMPANY_CANON.items():
            joined = joined.replace(k, v)
        joined = _WS_RE.sub(" ", joined).strip()
        out = [t for t in joined.split(" ") if t]

    # Drop duplicate adjacent tokens (e.g., "LIMITED LIMITED")
    dedup: list[str] = []
    for t in out:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    return dedup


def normalized_string(name: str, *, entity_type: str = "unknown") -> str:
    toks = normalize_tokens(tokenize(name), entity_type=entity_type)
    return " ".join(toks)


def meaningful_tokens(name: str, *, entity_type: str = "unknown") -> list[str]:
    return normalize_tokens(tokenize(name), entity_type=entity_type)


def is_initial(token: str) -> bool:
    return len(token) == 1 and token.isalpha()
