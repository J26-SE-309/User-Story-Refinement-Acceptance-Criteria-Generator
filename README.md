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

### API contract

Until the models are in place, the endpoints return placeholder results marked `model_version: "stub"`, so the
gateway and frontend can already be built against the real request and response shapes. The shared JSON
Schemas live in [`Synapse-Web/contracts/story-refinement`](https://github.com/J26-SE-309/Synapse-Web/tree/main/contracts/story-refinement);
keep them in sync with `backend/app/schemas.py`.

### Data and models

Datasets and trained models are never committed. Keep them in `AgilePlatform/Datasets/story-refinement/`, next to the
repositories (see [`ml-engine/README.md`](ml-engine/README.md)).

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
