# ML engine: User Story Refinement and Acceptance Criteria Generator

Research code for this component: preparing datasets, training and evaluating models.
The API in [`../backend`](../backend) loads the trained models to serve results to the platform.

## Implemented engine

- **Project-context retrieval:** project-scoped TF-IDF/cosine retrieval over supplied stories, criteria, glossary entries, business rules and requirements.
- **Generation:** an Ollama-compatible local HTTP client generates structured JSON candidates.
- **Quality optimisation:** deterministic INVEST, clarity, completeness, testability, consistency, context relevance and acceptance-criteria coverage heuristics rank valid candidates.
- **Unsupported-assumption detection:** generated story/criterion outcomes are compared with explicit requirement/context evidence; lexical similarity is not treated as proof.
- **Evaluation:** compare against baseline LLM prompting with automated measures and expert ratings.

The engine does not call cloud services. `STORY_LLM_BASE_URL`, `STORY_LLM_MODEL`,
`STORY_LLM_TIMEOUT_SECONDS`, and `STORY_CANDIDATE_COUNT` configure the local provider.
Model failures and malformed JSON raise explicit errors; no placeholder or cloud fallback is used.
Quality scores are documented heuristics and require research validation against expert ratings.

The main entry point is `story_ml.pipeline.refine_requirement`. It returns a structured
`RefinementResult` with retrieved source references, ranked candidates, the best candidate
when one passes validation, risks, and model metadata.

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
