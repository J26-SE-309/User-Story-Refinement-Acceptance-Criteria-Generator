# ML engine: User Story Refinement and Acceptance Criteria Generator

Research code for this component: preparing datasets, training and evaluating models.
The API in [`../backend`](../backend) loads the trained models to serve results to the platform.

## Planned work (from the proposal)

- **Project-context retrieval:** semantic retrieval of existing stories, terminology and business rules.
- **Generation:** a locally deployed LLM generates several user-story and acceptance-criteria candidates.
- **Quality optimisation:** score candidates on INVEST, completeness, clarity, testability, consistency and context relevance, then rank and select.
- **Unsupported-assumption detection:** check generated claims against the requirement and context.
- **Evaluation:** compare against baseline LLM prompting with automated measures and expert ratings.

## Layout

```
ml-engine/
├── src/story_ml/   # reusable code: data loading, features, models, evaluation
├── notebooks/        # exploration only; move anything reusable into src/
└── tests/
```

## Data and models

Never commit datasets or trained models. Keep them in `AgilePlatform/Datasets/story-refinement/`, next to the
repositories; `story_ml.config.DATA_DIR` points there (override it with the `STORY_DATA_DIR` environment variable).

## Adding libraries

Add what you need (for example `transformers`, `sentence-transformers`, `torch`) to `dependencies` in
`ml-engine/pyproject.toml`, then reinstall from the repository root:

```powershell
.venv\Scripts\python -m pip install -e "ml-engine[dev]"
```
