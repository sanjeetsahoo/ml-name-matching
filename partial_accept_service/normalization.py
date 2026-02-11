import re


SEPARATOR_PATTERN = re.compile(r"[^A-Za-z0-9]+")
WHITESPACE_PATTERN = re.compile(r"\s+")

NOISE_TOKENS = {
    "MR",
    "MRS",
    "MS",
    "MISS",
    "DR",
    "SHRI",
    "SMT",
    "KUMARI",
}


def normalize_name(name: str) -> str:
    cleaned = SEPARATOR_PATTERN.sub(" ", name.upper())
    cleaned = WHITESPACE_PATTERN.sub(" ", cleaned).strip()
    filtered = [token for token in cleaned.split(" ") if token and token not in NOISE_TOKENS]
    return " ".join(filtered)


def tokenize_name(name: str) -> list[str]:
    normalized = normalize_name(name)
    if not normalized:
        return []
    return normalized.split(" ")


def is_initial(token: str) -> bool:
    return len(token) == 1 and token.isalpha()


def initials_signature(tokens: list[str]) -> str:
    return "".join(token[0] for token in tokens if token)
