"""Import dataset requirements without approving them.

The workbook's synthetic reference outputs are intentionally not stored on
ValidatedRequirement. They are training/evaluation data, not approval evidence.
"""

from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db import SessionLocal
from app.models import Project, ValidatedRequirement

LOGGER = logging.getLogger(__name__)
DEFAULT_INPUT = (
    Path(__file__).resolve().parents[3]
    / "Datasets"
    / "story-refinement"
    / "raw"
    / "Story_Refinement_Local_Optimization_500_Records.xlsx"
)
REQUIREMENTS_SHEET = "Requirements_500"


@dataclass
class ImportSummary:
    imported: int = 0
    skipped: int = 0
    duplicates: int = 0
    invalid: int = 0
    reasons: list[str] = field(default_factory=list)


def _value(row: dict[str, Any], name: str) -> str | None:
    value = row.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none"} else None


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("XLSX import requires openpyxl; install the backend dependencies.") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        if REQUIREMENTS_SHEET not in workbook.sheetnames:
            raise ValueError(f"Workbook does not contain the required '{REQUIREMENTS_SHEET}' sheet.")
        values = workbook[REQUIREMENTS_SHEET].iter_rows(values_only=True)
        headers = [str(value).strip() if value is not None else "" for value in next(values, ())]
        if not headers or any(not header for header in headers):
            raise ValueError(f"'{REQUIREMENTS_SHEET}' must have a non-empty header row.")
        return [dict(zip(headers, row, strict=False)) for row in values]
    raise ValueError("Input must be a .csv or .xlsx file.")


def import_requirements(
    path: Path,
    dry_run: bool = False,
    session_factory: sessionmaker[Session] = SessionLocal,
) -> ImportSummary:
    summary = ImportSummary()
    rows = _rows(path)
    with session_factory() as session:
        existing_ids = set(session.scalars(select(ValidatedRequirement.id)))
        seen_ids: set[str] = set()
        project_ids = set(session.scalars(select(Project.id)))

        for row_number, row in enumerate(rows, start=2):
            requirement_id = _value(row, "requirement_id")
            text = _value(row, "validated_requirement") or _value(row, "requirement_text")
            if not requirement_id:
                summary.invalid += 1
                summary.reasons.append(f"row {row_number}: missing requirement_id")
                continue
            if not text:
                summary.invalid += 1
                summary.reasons.append(f"{requirement_id}: missing validated_requirement")
                continue
            if requirement_id in seen_ids:
                summary.duplicates += 1
                summary.reasons.append(f"{requirement_id}: duplicate in input")
                continue
            seen_ids.add(requirement_id)
            if requirement_id in existing_ids:
                summary.skipped += 1
                summary.reasons.append(f"{requirement_id}: already exists; status and text preserved")
                continue

            project_id = _value(row, "project_id")
            if not dry_run and project_id and project_id not in project_ids:
                session.add(Project(id=project_id, name=project_id))
                project_ids.add(project_id)

            if not dry_run:
                session.add(
                    ValidatedRequirement(
                        id=requirement_id,
                        project_id=project_id,
                        domain=_value(row, "domain"),
                        text=text,
                        context_text=_value(row, "context_text"),
                        source_reference=_value(row, "context_id"),
                        validation_status="pending_review",
                    )
                )
            summary.imported += 1

        if not dry_run:
            session.commit()
        else:
            session.rollback()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import requirements as pending review.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to .xlsx or .csv input.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing to the database.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not args.input.is_file():
        parser.error(f"Input file does not exist: {args.input}")
    try:
        summary = import_requirements(args.input, dry_run=args.dry_run)
    except SQLAlchemyError as exc:
        parser.exit(1, f"Database operation failed; no import was completed: {exc}\n")
    mode = "Would import" if args.dry_run else "Imported"
    print(
        f"{mode}: {summary.imported}; skipped: {summary.skipped}; "
        f"duplicates: {summary.duplicates}; invalid: {summary.invalid}"
    )
    for reason in summary.reasons:
        LOGGER.info(reason)


if __name__ == "__main__":
    main()
