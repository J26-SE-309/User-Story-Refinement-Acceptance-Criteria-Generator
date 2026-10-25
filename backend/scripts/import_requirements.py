"""Import reviewed requirements into the component-owned database.

Records are intentionally imported as pending_review. A reviewer must approve them
before they appear in the requirements API or can be refined.
"""

import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ValidatedRequirement


def _rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("XLSX import requires openpyxl; install it in the backend environment.") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.values)
        if not values:
            return []
        headers = [str(value).strip() if value is not None else "" for value in values[0]]
        return [dict(zip(headers, row, strict=False)) for row in values[1:]]
    raise ValueError("Input must be a .csv or .xlsx file.")


def import_requirements(path: Path, dry_run: bool = False) -> tuple[int, int, int]:
    imported = skipped = rejected = 0
    with SessionLocal() as session:
        for row_number, row in enumerate(_rows(path), start=2):
            requirement_id = str(row.get("requirement_id") or row.get("record_id") or f"REQ-{row_number:04d}").strip()
            text = str(row.get("validated_requirement") or row.get("requirement_text") or "").strip()
            if not requirement_id or not text:
                rejected += 1
                continue
            if session.scalar(select(ValidatedRequirement.id).where(ValidatedRequirement.id == requirement_id)):
                skipped += 1
                continue
            if not dry_run:
                session.add(
                    ValidatedRequirement(
                        id=requirement_id,
                        project_id=(str(row["project_id"]).strip() if row.get("project_id") else None),
                        domain=(str(row["domain"]).strip() if row.get("domain") else None),
                        text=text,
                        context_text=(str(row["context_text"] or row["project_context"]).strip()
                                      if row.get("context_text") or row.get("project_context") else None),
                        validation_status="pending_review",
                    )
                )
            imported += 1
        if not dry_run:
            session.commit()
    return imported, skipped, rejected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    imported, skipped, rejected = import_requirements(args.input, args.dry_run)
    mode = "Would import" if args.dry_run else "Imported"
    print(f"{mode}: {imported}; skipped duplicates: {skipped}; rejected missing fields: {rejected}")


if __name__ == "__main__":
    main()
