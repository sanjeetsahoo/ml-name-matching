"""Decision engine for reducing ops tickets from ML partial accepts.

This module is intentionally framework-agnostic so it can be reused from an
API service, a batch job, or an event consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
import re
import unicodedata


_HONORIFICS = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "prof",
    "sir",
    "smt",
    "shri",
    "kumari",
}

_CORPORATE_SUFFIXES = {
    "pvt",
    "private",
    "ltd",
    "limited",
    "llp",
    "co",
    "company",
    "inc",
    "corp",
    "corporation",
    "enterprises",
}

_TOKEN_ALIASES = {
    "md": "mohammad",
    "mohd": "mohammad",
    "mohammed": "mohammad",
    "muhammad": "mohammad",
    "kr": "kumar",
    "kmr": "kumar",
    "rajkumar": "raj kumar",
}


class Decision(str, Enum):
    AUTO_ACCEPT = "auto_accept"
    NEEDS_OPS_REVIEW = "needs_ops_review"
    AUTO_REJECT = "auto_reject"


@dataclass(frozen=True)
class TriageInput:
    bank_name: str
    pan_name: str
    ml_score: float | None = None
    case_id: str | None = None


@dataclass(frozen=True)
class TriageResult:
    decision: Decision
    confidence: float
    reason_codes: list[str]
    normalized_bank_name: str
    normalized_pan_name: str
    features: dict[str, float]
    case_id: str | None = None


@dataclass(frozen=True)
class TriageConfig:
    auto_accept_threshold: float = 0.90
    auto_reject_threshold: float = 0.35
    ml_weight: float = 0.30
    surname_guardrail: float = 0.65


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _normalize_ascii(raw: str) -> str:
    text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name(raw_name: str) -> list[str]:
    normalized = _normalize_ascii(raw_name)
    if not normalized:
        return []

    expanded: list[str] = []
    for token in normalized.split():
        alias = _TOKEN_ALIASES.get(token, token)
        expanded.extend(alias.split())

    filtered: list[str] = []
    for token in expanded:
        if token in _HONORIFICS or token in _CORPORATE_SUFFIXES:
            continue
        filtered.append(token)

    return filtered


def _ratio(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _token_jaccard(left_tokens: list[str], right_tokens: list[str]) -> float:
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _token_coverage(left_tokens: list[str], right_tokens: list[str]) -> float:
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / min(len(left_set), len(right_set))


def _first_token_similarity(left_tokens: list[str], right_tokens: list[str]) -> float:
    if not left_tokens or not right_tokens:
        return 0.0
    return _ratio(left_tokens[0], right_tokens[0])


def _last_token_similarity(left_tokens: list[str], right_tokens: list[str]) -> float:
    if not left_tokens or not right_tokens:
        return 0.0
    return _ratio(left_tokens[-1], right_tokens[-1])


def _initials(tokens: list[str]) -> str:
    return "".join(token[0] for token in tokens if token)


def _initials_compatible(left_tokens: list[str], right_tokens: list[str]) -> bool:
    left_initials = _initials(left_tokens)
    right_initials = _initials(right_tokens)
    if not left_initials or not right_initials:
        return False
    return left_initials == right_initials or left_initials in right_initials or right_initials in left_initials


class PartialAcceptTriageService:
    """Rule-based post-processor for ML partial accepts.

    Goal: auto-resolve clear positive/negative cases and route only uncertain
    cases to operations review.
    """

    def __init__(self, config: TriageConfig | None = None) -> None:
        self.config = config or TriageConfig()

    def evaluate(self, triage_input: TriageInput) -> TriageResult:
        bank_tokens = normalize_name(triage_input.bank_name)
        pan_tokens = normalize_name(triage_input.pan_name)
        normalized_bank = " ".join(bank_tokens)
        normalized_pan = " ".join(pan_tokens)

        if not normalized_bank or not normalized_pan:
            return TriageResult(
                decision=Decision.NEEDS_OPS_REVIEW,
                confidence=0.50,
                reason_codes=["EMPTY_AFTER_NORMALIZATION"],
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features={"deterministic_score": 0.0, "blended_score": 0.0},
                case_id=triage_input.case_id,
            )

        if normalized_bank == normalized_pan:
            return TriageResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=0.99,
                reason_codes=["EXACT_NORMALIZED_MATCH"],
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features={"deterministic_score": 1.0, "blended_score": 1.0},
                case_id=triage_input.case_id,
            )

        sequence_score = _ratio(normalized_bank, normalized_pan)
        sorted_sequence_score = _ratio(" ".join(sorted(bank_tokens)), " ".join(sorted(pan_tokens)))
        token_jaccard = _token_jaccard(bank_tokens, pan_tokens)
        token_coverage = _token_coverage(bank_tokens, pan_tokens)
        first_similarity = _first_token_similarity(bank_tokens, pan_tokens)
        last_similarity = _last_token_similarity(bank_tokens, pan_tokens)
        initials_match = 1.0 if _initials_compatible(bank_tokens, pan_tokens) else 0.0

        deterministic_score = (
            0.30 * sequence_score
            + 0.20 * sorted_sequence_score
            + 0.20 * token_jaccard
            + 0.20 * token_coverage
            + 0.10 * initials_match
        )

        if first_similarity >= 0.90 and last_similarity >= 0.90:
            deterministic_score += 0.05

        deterministic_score = _clamp(deterministic_score)

        blended_score = deterministic_score
        ml_score = None
        if triage_input.ml_score is not None:
            ml_score = _clamp(triage_input.ml_score)
            blended_score = _clamp(
                deterministic_score * (1.0 - self.config.ml_weight)
                + ml_score * self.config.ml_weight
            )

        features = {
            "deterministic_score": deterministic_score,
            "blended_score": blended_score,
            "sequence_score": sequence_score,
            "sorted_sequence_score": sorted_sequence_score,
            "token_jaccard": token_jaccard,
            "token_coverage": token_coverage,
            "first_token_similarity": first_similarity,
            "last_token_similarity": last_similarity,
            "initials_match": initials_match,
        }
        if ml_score is not None:
            features["ml_score"] = ml_score

        reason_codes: list[str] = []

        # Hard mismatch guardrail: both leading and trailing identity disagree.
        if (
            len(bank_tokens) >= 2
            and len(pan_tokens) >= 2
            and first_similarity < 0.45
            and last_similarity < 0.45
            and token_jaccard < 0.20
        ):
            reason_codes.append("HARD_FIRST_LAST_MISMATCH")
            return TriageResult(
                decision=Decision.AUTO_REJECT,
                confidence=max(0.80, 1.0 - blended_score),
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        if token_jaccard == 1.0 and min(len(bank_tokens), len(pan_tokens)) >= 2:
            reason_codes.append("TOKEN_SET_MATCH")
            return TriageResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=max(0.95, blended_score),
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        if (
            token_coverage >= 0.80
            and last_similarity >= 0.90
            and sequence_score >= 0.80
            and (ml_score is None or ml_score >= 0.65)
        ):
            reason_codes.append("HIGH_COVERAGE_SURNAME_MATCH")
            return TriageResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=max(0.90, blended_score),
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        if (
            first_similarity >= 0.90
            and last_similarity >= 0.90
            and initials_match == 1.0
            and (ml_score is None or ml_score >= 0.75)
        ):
            reason_codes.append("INITIALS_EXPANSION_MATCH")
            return TriageResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=max(0.88, blended_score),
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        if (
            sequence_score >= 0.90
            and sorted_sequence_score >= 0.90
            and first_similarity >= 0.75
            and last_similarity >= 0.90
            and (ml_score is None or ml_score >= 0.80)
        ):
            reason_codes.append("MINOR_TYPO_STRONG_MATCH")
            return TriageResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=max(0.88, blended_score),
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        if (
            blended_score >= self.config.auto_accept_threshold
            and last_similarity >= self.config.surname_guardrail
        ):
            reason_codes.append("BLENDED_SCORE_HIGH")
            return TriageResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=blended_score,
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        if blended_score <= self.config.auto_reject_threshold and token_jaccard < 0.20:
            reason_codes.append("BLENDED_SCORE_LOW")
            return TriageResult(
                decision=Decision.AUTO_REJECT,
                confidence=max(0.75, 1.0 - blended_score),
                reason_codes=reason_codes,
                normalized_bank_name=normalized_bank,
                normalized_pan_name=normalized_pan,
                features=features,
                case_id=triage_input.case_id,
            )

        reason_codes.append("REQUIRES_HUMAN_REVIEW")
        return TriageResult(
            decision=Decision.NEEDS_OPS_REVIEW,
            confidence=abs(blended_score - 0.50),
            reason_codes=reason_codes,
            normalized_bank_name=normalized_bank,
            normalized_pan_name=normalized_pan,
            features=features,
            case_id=triage_input.case_id,
        )


def summarize_results(results: list[TriageResult]) -> dict[str, float | int]:
    total = len(results)
    auto_accept = sum(1 for item in results if item.decision == Decision.AUTO_ACCEPT)
    auto_reject = sum(1 for item in results if item.decision == Decision.AUTO_REJECT)
    needs_review = total - auto_accept - auto_reject

    if total == 0:
        return {
            "total": 0,
            "auto_accept": 0,
            "auto_reject": 0,
            "needs_ops_review": 0,
            "ticket_reduction_ratio": 0.0,
        }

    return {
        "total": total,
        "auto_accept": auto_accept,
        "auto_reject": auto_reject,
        "needs_ops_review": needs_review,
        "ticket_reduction_ratio": (auto_accept + auto_reject) / total,
    }
