"""Validate and split reviewed story-refinement examples.

Synthetic examples are useful for smoke tests only. They must not be presented
as research evidence or used as a sufficient training set.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_FIELDS = (
    "requirement_text",
    "project_context",
    "role",
    "target_user_story",
    "acceptance_criteria",
    "assumptions",
    "source_metadata",
)
SPLITS = ("train", "validation", "test")


def default_data_dir() -> Path:
    return Path(
        os.environ.get(
            "STORY_DATA_DIR",
            Path(__file__).resolve().parents[2] / "Datasets" / "story-refinement",
        )
    )


def _read_records(input_path: Path) -> list[dict[str, Any]]:
    if input_path.suffix.lower() == ".jsonl":
        with input_path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    if input_path.suffix.lower() == ".csv":
        return pd.read_csv(input_path).to_dict(orient="records")
    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(input_path).to_dict(orient="records")
    raise ValueError("Input must be JSONL, CSV, or XLSX.")


def _parse_acceptance_criteria(value: Any) -> list[dict[str, str]]:
    if _is_missing(value):
        return []
    criteria: list[dict[str, str]] = []
    for line in str(value).splitlines():
        text = line.strip()
        match = pd.Series([text]).str.extract(
            r"^\s*\d+\.\s*Given\s+(.+?),\s*when\s+(.+?),\s*then\s+(.+?)(?:\.)?\s*$",
            expand=False,
        ).iloc[0]
        if not match.isna().any():
            criteria.append(
                {
                    "id": f"AC{len(criteria) + 1}",
                    "given": match.iloc[0].strip(),
                    "when": match.iloc[1].strip(),
                    "then": match.iloc[2].strip(),
                }
            )
    return criteria


def _extract_role(story: Any) -> str:
    match = pd.Series([str(story)]).str.extract(
        r"^\s*As a\s+(.+?),\s*I want\b", expand=False
    ).iloc[0]
    return "" if pd.isna(match) else str(match).strip()


def _normalise_source_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map the supplied starter workbook/CSV schema to the canonical schema."""
    normalised = []
    for record in records:
        if "requirement_text" in record:
            normalised.append(record)
            continue
        normalised.append(
            {
                "record_id": record.get("requirement_id"),
                "requirement_text": record.get("validated_requirement"),
                "project_context": record.get("context_text"),
                "role": _extract_role(record.get("reference_user_story_synthetic", "")),
                "target_user_story": record.get("reference_user_story_synthetic"),
                "acceptance_criteria": _parse_acceptance_criteria(
                    record.get("reference_acceptance_criteria_synthetic")
                ),
                "assumptions": [record.get("ambiguity_notes", "")]
                if not _is_missing(record.get("ambiguity_notes"))
                else [],
                "source_metadata": {
                    "source_type": record.get("source_type"),
                    "source_status": record.get("source_status"),
                    "context_id": record.get("context_id"),
                    "project_id": record.get("project_id"),
                },
                "annotation_status": record.get("annotation_status"),
            }
        )
    return normalised


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    return []


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return isinstance(value, str) and not value.strip()


def validate_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    normalised: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(records, start=1):
        record = dict(raw)
        record_id = str(record.get("record_id") or f"row-{index}")
        record["record_id"] = record_id
        row_errors: list[str] = []
        missing = [field for field in REQUIRED_FIELDS if _is_missing(record.get(field))]
        if missing:
            row_errors.append(f"missing fields: {', '.join(missing)}")
        if record_id in seen:
            row_errors.append("duplicate record_id")
        seen.add(record_id)
        criteria = _as_list(record.get("acceptance_criteria"))
        if not criteria and not _is_missing(record.get("acceptance_criteria")):
            row_errors.append("acceptance_criteria must be a JSON list")
        for criterion in criteria:
            if not isinstance(criterion, dict) or any(
                _is_missing(criterion.get(field)) for field in ("given", "when", "then")
            ):
                row_errors.append("acceptance criteria must contain non-empty given, when, and then fields")
                break
        record["acceptance_criteria"] = criteria
        record["assumptions"] = _as_list(record.get("assumptions"))
        if row_errors:
            errors.append({"record_id": record_id, "row": index, "errors": row_errors})
        normalised.append(record)
    report = {
        "record_count": len(records),
        "valid_record_count": len(records) - len(errors),
        "invalid_record_count": len(errors),
        "duplicate_record_count": sum("duplicate record_id" in item["errors"] for item in errors),
        "missing_value_count": sum(any(error.startswith("missing fields") for error in item["errors"]) for item in errors),
        "errors": errors,
    }
    return normalised, report


def split_records(records: list[dict[str, Any]], seed: int = 42) -> dict[str, list[dict[str, Any]]]:
    reviewed = [
        record for record in records
        if str(record.get("source_metadata", "")).lower().find("synthetic") < 0
        and str(record.get("annotation_status", "reviewed")).lower() in {"reviewed", "approved"}
    ]
    if not reviewed:
        return {split: [] for split in SPLITS}
    frame = pd.DataFrame(reviewed).sample(frac=1, random_state=seed).reset_index(drop=True)
    total = len(frame)
    train_end = round(total * 0.8)
    validation_end = train_end + round(total * 0.1)
    return {
        "train": frame.iloc[:train_end].to_dict(orient="records"),
        "validation": frame.iloc[train_end:validation_end].to_dict(orient="records"),
        "test": frame.iloc[validation_end:].to_dict(orient="records"),
    }


def prepare_dataset(
    input_path: Path,
    output_dir: Path,
    seed: int = 42,
    splits_dir: Path | None = None,
) -> dict[str, Any]:
    records = _normalise_source_records(_read_records(input_path))
    normalised, report = validate_records(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    provenance = {
        "input": str(input_path),
        "prepared_at": datetime.now(UTC).isoformat(),
        "split_seed": seed,
        "split_ratios": {"train": 0.8, "validation": 0.1, "test": 0.1},
        "synthetic_records_are_not_research_evidence": True,
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    valid = [record for record in normalised if record["record_id"] not in {item["record_id"] for item in report["errors"]}]
    splits_dir = splits_dir or output_dir.parent / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)
    for split, split_records_data in split_records(valid, seed).items():
        with (splits_dir / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
            for record in split_records_data:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=default_data_dir() / "raw" / "Story_Refinement_Local_Optimization_500_Records.xlsx",
        help="JSONL, CSV, or XLSX input file",
    )
    parser.add_argument("--output-dir", type=Path, default=default_data_dir() / "processed")
    parser.add_argument("--splits-dir", type=Path, default=default_data_dir() / "splits")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = prepare_dataset(args.input, args.output_dir, args.seed, args.splits_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
