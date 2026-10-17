
from pathlib import Path

import pandas as pd


# Change this to the location of your original Excel workbook.
INPUT_FILE = Path(
    r"D:\AgilePlatform\Datasets\story-refinement\raw\Story_Refinement_Local_Optimization_500_Records.xlsx"
)

OUTPUT_DIR = Path(
    r"D:\AgilePlatform\Datasets\story-refinement\processed"
)

REQUIRED_COLUMNS = [
    "requirement_id",
    "domain",
    "project_id",
    "validated_requirement",
    "context_id",
    "context_text",
    "train_dev_test_split",
    "source_type",
    "annotation_status",
]

ALLOWED_SPLITS = {"train", "dev", "test"}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    requirements = pd.read_excel(
        INPUT_FILE,
        sheet_name="Requirements_500",
    )

    contexts = pd.read_excel(
        INPUT_FILE,
        sheet_name="Project_Context_500",
    )

    # Preserve all original rows for audit and review.
    requirements.to_csv(
        OUTPUT_DIR / "requirements_imported.csv",
        index=False,
    )

    # The 500 main records are marked as synthetic illustrative records.
    # Keep the extra examples separately for review.
    main_mask = requirements["source_type"].eq(
        "Synthetic illustrative record"
    )

    main = requirements.loc[main_mask].copy()
    extras = requirements.loc[~main_mask].copy()

    # Validate main-record count and uniqueness.
    if len(main) != 500:
        raise ValueError(
            f"Expected 500 main records, found {len(main)}."
        )

    if main["requirement_id"].duplicated().any():
        raise ValueError("Duplicate requirement IDs detected.")

    # Validate required columns.
    missing_columns = set(REQUIRED_COLUMNS) - set(main.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns: {sorted(missing_columns)}"
        )

    # Validate required text and identifier fields.
    for col in [
        "requirement_id",
        "project_id",
        "validated_requirement",
        "context_id",
        "context_text",
    ]:
        invalid = (
            main[col].isna()
            | main[col].astype(str).str.strip().eq("")
        )
        if invalid.any():
            raise ValueError(
                f"{col}: {int(invalid.sum())} missing/empty values."
            )

    # Validate the provisional split labels.
    bad_splits = ~main["train_dev_test_split"].isin(ALLOWED_SPLITS)
    if bad_splits.any():
        raise ValueError(
            "Invalid split labels:\n"
            + main.loc[
                bad_splits,
                ["requirement_id", "train_dev_test_split"],
            ].to_string(index=False)
        )

    # Check context references.
   
    # Clean completely empty rows from the context sheet.
    contexts = contexts.dropna(how="all").copy()

    # Validate context IDs.
    contexts["context_id"] = (
        contexts["context_id"].astype("string").str.strip()
    )

    invalid_context_ids = (
        contexts["context_id"].isna()
        | contexts["context_id"].eq("")
    )

    if invalid_context_ids.any():
        print("Rows with missing context IDs:")
        print(
            contexts.loc[invalid_context_ids].to_string(index=False)
        )
        raise ValueError(
            "Context records contain missing or empty context IDs."
        )

    # Check duplicates only after handling missing IDs.
    duplicate_contexts = contexts[
        contexts["context_id"].duplicated(keep=False)
    ]

    if not duplicate_contexts.empty:
        print("Duplicate context records:")
        print(
            duplicate_contexts.to_string(index=False)
        )
        raise ValueError("Duplicate context IDs detected.")


    # Check context references.
    context_ids = set(contexts["context_id"])
    missing_contexts = ~main["context_id"].astype("string").str.strip().isin(
        context_ids
    )

    if missing_contexts.any():
        raise ValueError(
            "Requirements have missing context references:\n"
            + main.loc[
                missing_contexts,
                ["requirement_id", "context_id"],
            ].to_string(index=False)
        )


    context_ids = set(contexts["context_id"].dropna())
    missing_contexts = ~main["context_id"].isin(context_ids)

    if missing_contexts.any():
        raise ValueError(
            "Requirements have missing context references:\n"
            + main.loc[
                missing_contexts,
                ["requirement_id", "context_id"],
            ].to_string(index=False)
        )

    # Export validated inputs. Keep synthetic reference columns.
 
    # Export the processed datasets
    main.to_csv(
        OUTPUT_DIR / "requirements.csv",
        index=False,
    )

    contexts.to_csv(
        OUTPUT_DIR / "project_context.csv",
        index=False,
    )

    extras.to_csv(
        OUTPUT_DIR / "extra_examples_for_review.csv",
        index=False,
    )

    print("Dataset preparation completed.")
    print(f"Main requirements: {len(main)}")
    print(f"Context rows: {len(contexts)}")
    print(f"Extra rows saved for review: {len(extras)}")
    print("\nSplit counts:")
    print(main["train_dev_test_split"].value_counts())
    print(f"\nOutput directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
