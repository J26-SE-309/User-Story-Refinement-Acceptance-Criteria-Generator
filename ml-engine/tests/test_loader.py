from pathlib import Path

import pandas as pd
import pytest

from story_ml.data.loader import DATASET_COLUMNS, load_dataset


def test_load_dataset_extracts_only_requested_columns(tmp_path: Path):
    path = tmp_path / "requirements.csv"
    pd.DataFrame(
        {
            "requirement_id": ["REQ-1"],
            "validated_requirement": ["A learner can book a tutor."],
            "context_text": ["Only available sessions can be booked."],
            "reference_user_story_synthetic": ["As a learner, I want to book a tutor."],
            "reference_acceptance_criteria_synthetic": ["Given a learner, when booking, then availability is checked."],
            "expected_quality_focus": ["Clarity"],
            "train_dev_test_split": ["train"],
        }
    ).to_csv(path, index=False)

    result = load_dataset(path)

    assert list(result.columns) == list(DATASET_COLUMNS)
    assert result.to_dict("records") == [
        {
            "validated_requirement": "A learner can book a tutor.",
            "context_text": "Only available sessions can be booked.",
            "reference_user_story_synthetic": "As a learner, I want to book a tutor.",
            "reference_acceptance_criteria_synthetic": "Given a learner, when booking, then availability is checked.",
            "expected_quality_focus": "Clarity",
        }
    ]


def test_load_dataset_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "requirements.csv"
    pd.DataFrame({"validated_requirement": ["A requirement"]}).to_csv(
        path, index=False
    )

    with pytest.raises(ValueError, match="missing required columns"):
        load_dataset(path)


def test_load_dataset_rejects_blank_values(tmp_path: Path):
    path = tmp_path / "requirements.csv"
    pd.DataFrame({column: [""] for column in DATASET_COLUMNS}).to_csv(
        path, index=False
    )

    with pytest.raises(ValueError, match="missing or blank values"):
        load_dataset(path)
