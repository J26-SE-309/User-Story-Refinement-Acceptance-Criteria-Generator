"""Evaluate saved JSONL predictions against reviewed references without inventing scores."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def validate_output(user_story: str, criteria: list[dict]) -> tuple[bool, bool]:
    story_valid = bool(
        re.match(r"^As a .+, I want .+, so that .+\.$", user_story.strip(), re.IGNORECASE)
    )
    criteria_valid = bool(criteria) and all(
        all(isinstance(item.get(field), str) and item[field].strip() for field in ("given", "when", "then"))
        for item in criteria
        if isinstance(item, dict)
    )
    return story_valid and criteria_valid, True


def evaluate(input_path: Path, output_path: Path) -> list[dict[str, object]]:
    rows = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        criteria = record.get("predicted_acceptance_criteria", [])
        format_valid, requires_human_review = validate_output(record.get("predicted_user_story", ""), criteria)
        reference = record.get("acceptance_criteria", [])
        rows.append(
            {
                "record_id": record.get("record_id"),
                "format_valid": format_valid,
                "acceptance_criteria_present": bool(criteria),
                "acceptance_criteria_completeness": len(criteria) / max(len(reference), 1),
                "unsupported_assumption_count": len(record.get("predicted_assumptions", [])),
                "requires_human_review": requires_human_review,
                "latency_ms": record.get("latency_ms"),
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["record_id"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"evaluated": len(evaluate(args.input, args.output)), "output": str(args.output)}))


if __name__ == "__main__":
    main()
