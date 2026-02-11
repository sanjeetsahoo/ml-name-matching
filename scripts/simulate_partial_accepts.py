import argparse
import json
from pathlib import Path
from typing import Any

from partial_accept_service.decision_engine import PartialAcceptDecisionEngine
from partial_accept_service.schemas import DecisionAction, PartialAcceptCase


LABEL_KEYS = ("is_match", "label", "ground_truth_match", "actual_match")


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "match", "accepted"}:
            return True
        if lowered in {"0", "false", "no", "mismatch", "rejected"}:
            return False
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as infile:
        for line_number, raw_line in enumerate(infile, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Line {line_number} is not a JSON object.")
            records.append(item)
    return records


def _extract_label(record: dict[str, Any]) -> bool | None:
    for key in LABEL_KEYS:
        if key in record:
            return _to_bool(record[key])
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate partial-accept automation and estimate Ops ticket reduction.",
    )
    parser.add_argument("--input", required=True, help="Path to JSONL file with partial-accept cases.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSONL path containing model decisions.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    records = _read_jsonl(input_path)
    if not records:
        raise ValueError("No records found in input JSONL.")

    engine = PartialAcceptDecisionEngine()

    total = 0
    action_counts = {action.value: 0 for action in DecisionAction}
    false_accepts = 0
    false_rejects = 0
    evaluated_with_labels = 0
    output_rows: list[dict[str, Any]] = []

    for record in records:
        total += 1
        case = PartialAcceptCase(
            case_id=str(record.get("case_id", total)),
            bank_name=str(record["bank_name"]),
            pan_name=str(record["pan_name"]),
            ml_score=float(record["ml_score"]),
            model_version=record.get("model_version"),
            metadata=record.get("metadata", {}),
        )
        decision = engine.decide(case)
        action_counts[decision.action.value] += 1

        label = _extract_label(record)
        if label is not None:
            evaluated_with_labels += 1
            if decision.action == DecisionAction.AUTO_ACCEPT and label is False:
                false_accepts += 1
            if decision.action == DecisionAction.AUTO_REJECT and label is True:
                false_rejects += 1

        output_rows.append(
            {
                "case_id": decision.case_id,
                "bank_name": record["bank_name"],
                "pan_name": record["pan_name"],
                "ml_score": record["ml_score"],
                "action": decision.action.value,
                "decision_score": decision.decision_score,
                "ops_ticket_required": decision.ops_ticket_required,
                "reasons": decision.reasons,
                "features": decision.features.model_dump(),
            }
        )

    ops_before = total
    ops_after = action_counts[DecisionAction.SEND_TO_OPS.value]
    reduction = (ops_before - ops_after) / ops_before

    print(f"Total partial accepts processed: {total}")
    print(f"AUTO_ACCEPT: {action_counts[DecisionAction.AUTO_ACCEPT.value]}")
    print(f"AUTO_REJECT: {action_counts[DecisionAction.AUTO_REJECT.value]}")
    print(f"SEND_TO_OPS: {action_counts[DecisionAction.SEND_TO_OPS.value]}")
    print(f"Estimated Ops ticket reduction: {reduction:.2%}")

    if evaluated_with_labels > 0:
        print(f"Records with labels: {evaluated_with_labels}")
        print(f"False accepts (auto-accepted but actually mismatch): {false_accepts}")
        print(f"False rejects (auto-rejected but actually match): {false_rejects}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as outfile:
            for row in output_rows:
                outfile.write(json.dumps(row) + "\n")
        print(f"Saved decisions to: {output_path}")


if __name__ == "__main__":
    main()
