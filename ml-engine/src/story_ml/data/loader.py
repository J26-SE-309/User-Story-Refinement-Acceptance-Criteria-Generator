"""Load the labelled story-refinement dataset."""

from pathlib import Path

import pandas as pd


DATASET_COLUMNS = (
    "validated_requirement",
    "context_text",
    "reference_user_story_synthetic",
    "reference_acceptance_criteria_synthetic",
    "expected_quality_focus",
)
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls"}


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load and validate the fields used by the refinement training pipeline.

    The source may be a processed CSV or the original Excel workbook.  Only
    the labelled fields consumed by the pipeline are returned; source columns
    such as identifiers and split metadata are intentionally not included.
    """

    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    suffix = dataset_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(
            f"Unsupported dataset format '{dataset_path.suffix}'. "
            f"Expected one of: {supported}."
        )

    if suffix == ".csv":
        frame = pd.read_csv(dataset_path)
    else:
        frame = pd.read_excel(dataset_path)

    missing_columns = [
        column for column in DATASET_COLUMNS if column not in frame.columns
    ]
    if missing_columns:
        raise ValueError(
            "Dataset is missing required columns: "
            + ", ".join(missing_columns)
        )

    selected = frame.loc[:, DATASET_COLUMNS].copy()
    blank_values = selected.isna() | selected.astype("string").apply(
        lambda column: column.str.strip().eq("")
    )
    if blank_values.any().any():
        invalid_columns = [
            column for column in DATASET_COLUMNS if blank_values[column].any()
        ]
        raise ValueError(
            "Dataset contains missing or blank values in: "
            + ", ".join(invalid_columns)
        )

    return selected