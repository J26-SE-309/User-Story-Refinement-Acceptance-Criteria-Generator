from scripts.prepare_dataset import (
    _normalise_source_records,
    split_records,
    validate_records,
)


def _record(record_id: str, source_metadata: str = "human-reviewed") -> dict:
    return {
        "record_id": record_id,
        "requirement_text": "A learner can book a tutor.",
        "project_context": "Tutor service",
        "role": "learner",
        "target_user_story": "As a learner, I want to book a tutor, so that I can learn.",
        "acceptance_criteria": [{"given": "an available tutor", "when": "booking", "then": "it is created"}],
        "assumptions": [],
        "source_metadata": source_metadata,
        "annotation_status": "reviewed",
    }


def test_validate_records_reports_duplicates_and_missing_values():
    records = [_record("REQ-1"), _record("REQ-1")]
    records[1]["project_context"] = ""

    _, report = validate_records(records)

    assert report["invalid_record_count"] == 1
    assert report["duplicate_record_count"] == 1
    assert report["missing_value_count"] == 1


def test_split_records_excludes_synthetic_examples():
    splits = split_records([_record("REQ-1"), _record("SYN-1", "synthetic smoke test")])

    assert sum(len(records) for records in splits.values()) == 1
    assert all(record["record_id"] == "REQ-1" for records in splits.values() for record in records)


def test_normalise_records_maps_starter_workbook_fields():
    records = _normalise_source_records(
        [
            {
                "requirement_id": "REQ-1",
                "validated_requirement": "A learner can book a tutor.",
                "context_text": "Only available tutors can be booked.",
                "reference_user_story_synthetic": (
                    "As a learner, I want to book a tutor, so that I can learn."
                ),
                "reference_acceptance_criteria_synthetic": (
                    "1. Given an available tutor, when the learner books, then the booking is created."
                ),
                "source_type": "Synthetic illustrative record",
                "source_status": "Generated for prototype",
                "context_id": "CTX-1",
                "project_id": "PROJ-1",
                "annotation_status": "Needs human review",
            }
        ]
    )

    assert records[0]["requirement_text"] == "A learner can book a tutor."
    assert records[0]["role"] == "learner"
    assert records[0]["acceptance_criteria"][0]["given"] == "an available tutor"
