# User Story Refinement and Acceptance Criteria Generator

> A microservice of **Synapse**, an AI-assisted agile project platform built by research group **J26-SE-309**.

![Status](https://img.shields.io/badge/status-initial%20setup-orange)

## Overview

This service helps refine user stories and generates acceptance criteria for them, so backlog items are clear, complete and testable before they enter a sprint.

Scope, methodology, datasets and models will be documented here as the research progresses.

## Repository Layout

```
User-Story-Refinement-Acceptance-Criteria-Generator/
├── backend/             # FastAPI service the platform calls (port 8002)
│   ├── app/
│   │   ├── main.py      # app setup and /health
│   │   ├── config.py    # settings from environment variables or backend/.env
│   │   ├── db.py        # this component's own PostgreSQL database
│   │   ├── schemas.py   # request and response models (the API contract)
│   │   └── api/v1/      # endpoints
│   ├── tests/
│   └── Dockerfile
├── ml-engine/           # research code: datasets, training, evaluation (package `story_ml`)
└── docker-compose.yml   # this service and its database
```

## Getting Started

Requires Python 3.12, Docker Desktop and Git. Run these in PowerShell from the repository root after cloning.

1. Create a virtual environment and install the backend and ML engine with their test tools:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install -e "backend[dev]" -e "ml-engine[dev]"
   ```

2. Start this component's database, then run the API with auto-reload:

   ```powershell
   docker compose up -d story-db
   cd backend
   ..\.venv\Scripts\uvicorn app.main:app --reload --port 8002
   ```

   Open http://localhost:8002/docs for the interactive API documentation.

3. Run the tests and the linter (from `backend/`):

   ```powershell
   ..\.venv\Scripts\python -m pytest
   ..\.venv\Scripts\ruff check .
   ```

To run the service and its database together in Docker instead: `docker compose up --build`.

### Database

This component has its own PostgreSQL database and account. No other component connects to it.

| Setting | Local value |
|---|---|
| Host and port | `localhost:5442` |
| Database | `story_db` |
| User / password | `story_user` / `story-local` |

The backend owns additive refinement-storage tables managed by Alembic. Apply them only after
confirming the live `story_db` catalog is free of those table names:

```powershell
cd backend
..\.venv\Scripts\alembic upgrade head
```

The migration creates project context, validated requirement, existing-story, generation,
candidate, evaluation, context-reference, and review-decision tables. It does not drop or
alter existing tables or delete existing records. The migration intentionally stops if any
target table already exists outside Alembic so an existing database cannot be duplicated or
silently overwritten.

### API contract

The baseline endpoints are available under `/api/v1/requirements/generate` and
`/api/v1/requirements/validate`. The baseline is deterministic and marked
`model_version: "deterministic-baseline"`; it always requires human review.
`/api/v1/story-refinement/generate` runs the optional Ollama-backed local model
and persists ranked candidates. Model failures are returned as explicit API
errors rather than silently falling back to a fabricated result.

The shared JSON Schemas live in
[`Synapse-Web/contracts/story-refinement`](https://github.com/J26-SE-309/Synapse-Web/tree/main/contracts/story-refinement);
keep them in sync with `backend/app/schemas.py`.

### Configuration and integration

Copy `backend/.env.example` to `backend/.env`. Set `CORS_ORIGINS` to the
Synapse-Web origin(s), `STORY_LLM_BASE_URL` and `STORY_LLM_MODEL` for Ollama,
and `STORY_DATA_DIR` to the external `AgilePlatform/Datasets/story-refinement/` folder.
No API keys are required by this service. The frontend should send the
validated requirement from Component 1, its `requirement_id`, `project_id`,
optional role, and context to `/api/v1/requirements/generate`.

### Dataset preparation

The dataset schema is: `record_id`, `requirement_text`, `project_context`,
`role`, `target_user_story`, `acceptance_criteria` (a list of `{given, when,
then}` objects), `assumptions`, `source_metadata`, and optional
`annotation_status`. Use JSONL or CSV input:

```powershell
..\.venv\Scripts\python scripts/prepare_dataset.py `
  --input ..\Datasets\story-refinement\raw\Story_Refinement_Local_Optimization_500_Records.xlsx `
  --output-dir ..\Datasets\story-refinement\processed
```

The script writes `quality_report.json`, `provenance.json`, and
reviewed-only `train.jsonl`, `validation.jsonl`, and `test.jsonl`. The included
500-record workbook is synthetic and marked “Needs human review”; it is
processed for pipeline testing but excluded from training splits. It is not
research evidence or a sufficient training dataset. Add only legally usable
public or human-reviewed examples with source and consent/licensing metadata.

### Data and models

Datasets and trained models are never committed. Keep them in
`AgilePlatform/Datasets/story-refinement/`, next to the repositories (see
[`ml-engine/README.md`](ml-engine/README.md)).

## Synapse Platform Services

| Service | Repository | Type |
|---|---|---|
| Synapse Web | [Synapse-Web](https://github.com/J26-SE-309/Synapse-Web) | Frontend |
| Effort Estimation and Sprint Risk Predictor | [Effort-Estimation-and-Sprint-Risk-Predictor](https://github.com/J26-SE-309/Effort-Estimation-and-Sprint-Risk-Predictor) | Backend + ML engine |
| Requirement Quality and Ambiguity Analyzer | [Requirement-Quality-and-Ambiguity-Analyzer](https://github.com/J26-SE-309/Requirement-Quality-and-Ambiguity-Analyzer) | Backend + ML engine |
| Requirement Traceability Engine | [Requirement-Traceability-Engine](https://github.com/J26-SE-309/Requirement-Traceability-Engine) | Backend + ML engine |
| **User Story Refinement and Acceptance Criteria Generator** | [User-Story-Refinement-Acceptance-Criteria-Generator](https://github.com/J26-SE-309/User-Story-Refinement-Acceptance-Criteria-Generator) | Backend + ML engine |

## Project Lead

- [@Nikeshala22](https://github.com/Nikeshala22)
