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
│   ├── config/           # safe-to-commit training configuration examples
│   └── src/story_ml/     # inference, retrieval, evaluation and optional LoRA training
├── scripts/              # dataset, training and evaluation command-line tools
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

The database settings are read from `DATABASE_URL`; copy `backend/.env.example` to
`backend/.env` and set the password through the environment rather than committing it.
The default local Compose service uses `story_db` on `localhost:5442` and the API listens
on `localhost:8002`. The current schema reuses the component-owned refinement history
tables: `refinement_runs` and its candidates preserve every generated result, while
`validated_requirements` stores the selectable source records. Dataset imports are never
approved automatically:

```powershell
cd backend
..\.venv\Scripts\python scripts\import_requirements.py `
  --input ..\..\Datasets\story-refinement\raw\Story_Refinement_Local_Optimization_500_Records.xlsx `
  --dry-run
..\.venv\Scripts\python scripts\import_requirements.py `
  --input ..\..\Datasets\story-refinement\processed\requirements.csv
```

Reviewers can approve imported rows by setting `validation_status` to `validated` in the
component database. Only those rows are returned by `GET /api/v1/requirements` and accepted
by `POST /api/v1/refine`. The refinement endpoint accepts
`{"requirement_id":"REQ-0001"}` and returns `404` for missing or unapproved records.
For example:

```powershell
curl http://localhost:8002/api/v1/requirements?project_id=PROJECT-1
curl -X POST http://localhost:8002/api/v1/refine `
  -H "Content-Type: application/json" `
  -d '{"requirement_id":"REQ-0001"}'
```

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

Additional backend endpoints include:

- `GET /api/v1/stories/{story_id}` and `PUT /api/v1/stories/{story_id}` for retrieval and editing.
- `POST /api/v1/story-refinement/{generation_id}/review` for approval, rejection, or change requests.
- `GET /api/v1/datasets/status` and `GET /api/v1/models/status` for operational status.
- `GET /api/v1/requirements` and `GET /api/v1/requirements/{requirement_id}` for validated
  requirement selection.

### Configuration and integration

Copy `backend/.env.example` to `backend/.env`. Set `CORS_ORIGINS` to the
Synapse-Web origin(s), `STORY_LLM_BASE_URL` and `STORY_LLM_MODEL` for Ollama,
`STORY_MODEL_PATH` to the local fine-tuned T5 artifact (by default
`models/story-refinement-model`), and `STORY_DATA_DIR` to the external
`AgilePlatform/Datasets/story-refinement/` folder. The model endpoint loads the
configured artifact once on first use, uses CPU when CUDA is unavailable, and
returns an explicit 503 when the artifact is missing or cannot be loaded.
No API keys are required by this service. The frontend should send the
validated requirement from Component 1, its `requirement_id`, `project_id`,
optional role, and context to `/api/v1/requirements/generate`.

### Dataset preparation

The dataset schema is: `record_id`, `requirement_text`, `project_context`,
`role`, `target_user_story`, `acceptance_criteria` (a list of `{id, given,
when, then}` objects), `assumptions`, `source_metadata`, and optional
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

The complete external layout is:

```text
Datasets/story-refinement/
├── raw/          # supplied workbooks, CSV and JSONL; never committed
├── processed/    # normalized records and quality reports
├── splits/       # train.jsonl, validation.jsonl and test.jsonl
├── models/       # final model or adapter artifacts
├── checkpoints/  # resumable training checkpoints
├── evaluation/   # experiment CSV results
└── logs/         # training and inference logs
```

### Optional fine-tuning

Fine-tuning is intentionally controlled and does not run from a public API
endpoint. Install the optional dependencies only when reviewed data and
suitable hardware are available:

```powershell
..\.venv\Scripts\python -m pip install -e "ml-engine[training]"
..\.venv\Scripts\python scripts/train_model.py `
  --config ml-engine/config/training.example.json --check-only
```

The readiness check blocks training when reviewed train/validation examples,
licence confirmation, or hardware configuration are missing. Review the
configuration and explicitly add `--confirm` before any training run:

```powershell
..\.venv\Scripts\python scripts/train_model.py `
  --config ml-engine/config/training.example.json --confirm
```

The default model is `google/flan-t5-small`, matching the backend's
encoder-decoder inference path. Training uses the requirement fields as the
input prompt and produces separate target labels in the exact API JSON
contract: `user_story`, `acceptance_criteria`, and
`unsupported_assumptions`. Verify the model licence and hardware suitability
before use. CPU training is disabled by default and, if enabled, is only
suitable for a small experiment. No model has been trained by this repository
yet.

### Research evaluation

Create a JSONL prediction file containing reference fields plus
`predicted_user_story`, `predicted_acceptance_criteria`, optional
`predicted_assumptions`, and optional `latency_ms`, then run:

```powershell
..\.venv\Scripts\python scripts/evaluate_generation.py `
  --input ..\Datasets\story-refinement\splits\test_predictions.jsonl `
  --output ..\Datasets\story-refinement\evaluation\structured-prompt.csv
```

The evaluator reports structural validity, criteria completeness,
unsupported-assumption count, human-review status, and latency where supplied.
Automatic metrics do not prove semantic faithfulness; compare the same held-out
reviewed examples across baseline, structured prompting, and fine-tuned runs,
then add human reviewer ratings.

### Frontend integration

The existing Synapse-Web refinement workspace remains the UI. It can use the
FastAPI service through the gateway by setting this in
`Synapse-Web/.env.local`:

```text
NEXT_PUBLIC_GATEWAY_URL=http://127.0.0.1:8000
NEXT_PUBLIC_STORY_REFINEMENT_API=true
```

With the flag enabled, the current workspace sends validated requirements to
`/api/v1/story-refinement/refine`, displays the returned story and criteria,
and retains the existing editing and review screens. The default remains
`false` so prototype tests and offline demonstrations are not disrupted.

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
