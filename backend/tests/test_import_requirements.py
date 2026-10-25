from pathlib import Path

from app.models import ValidatedRequirement
from scripts.import_requirements import import_requirements


def _input_file(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "requirements.csv"
    headers = ["requirement_id", "project_id", "domain", "validated_requirement", "context_id", "context_text"]
    path.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(row.get(header, "") for header in headers) for row in rows),
        encoding="utf-8",
    )
    return path


def test_imports_valid_rows_as_pending_review(tmp_path, test_session_factory):
    path = _input_file(
        tmp_path,
        [
            {
                "requirement_id": "REQ-IMPORT-1",
                "project_id": "PROJECT-IMPORT",
                "domain": "Education",
                "validated_requirement": "A learner can search tutors.",
                "context_id": "CTX-1",
                "context_text": "Tutor profiles are searchable.",
            }
        ],
    )

    summary = import_requirements(path, session_factory=test_session_factory)

    assert summary.imported == 1
    with test_session_factory() as session:
        requirement = session.get(ValidatedRequirement, "REQ-IMPORT-1")
        assert requirement.validation_status == "pending_review"
        assert requirement.text == "A learner can search tutors."
        assert requirement.source_reference == "CTX-1"


def test_invalid_and_duplicate_rows_are_reported(tmp_path, test_session_factory):
    path = _input_file(
        tmp_path,
        [
            {"requirement_id": "REQ-IMPORT-2", "validated_requirement": ""},
            {"requirement_id": "", "validated_requirement": "Missing ID"},
            {"requirement_id": "REQ-IMPORT-3", "validated_requirement": "Valid"},
            {"requirement_id": "REQ-IMPORT-3", "validated_requirement": "Duplicate"},
        ],
    )

    summary = import_requirements(path, session_factory=test_session_factory)

    assert summary.imported == 1
    assert summary.duplicates == 1
    assert summary.invalid == 2


def test_dry_run_and_rerun_do_not_change_existing_records(tmp_path, test_session_factory):
    path = _input_file(
        tmp_path,
        [{"requirement_id": "REQ-IMPORT-4", "validated_requirement": "Imported text"}],
    )

    dry_run = import_requirements(path, dry_run=True, session_factory=test_session_factory)
    assert dry_run.imported == 1
    with test_session_factory() as session:
        assert session.get(ValidatedRequirement, "REQ-IMPORT-4") is None

    first = import_requirements(path, session_factory=test_session_factory)
    assert first.imported == 1
    with test_session_factory() as session:
        requirement = session.get(ValidatedRequirement, "REQ-IMPORT-4")
        requirement.validation_status = "validated"
        requirement.text = "Human-reviewed text"
        session.commit()

    second = import_requirements(path, session_factory=test_session_factory)
    assert second.skipped == 1
    with test_session_factory() as session:
        requirement = session.get(ValidatedRequirement, "REQ-IMPORT-4")
        assert requirement.validation_status == "validated"
        assert requirement.text == "Human-reviewed text"
