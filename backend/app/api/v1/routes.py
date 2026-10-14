"""Version 1 of the refinement API.

Until the local LLM, context retrieval and candidate optimisation are plugged in, the
endpoint returns a placeholder story (model_version "stub") so the gateway and frontend
can be built against the real contract.
"""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import db
from app.repositories import add_context_entry, create_project, persist_refinement, record_review
from app.schemas import (
    AcceptanceCriterion,
    InvestFlags,
    ProjectContextCreate,
    ProjectContextResponse,
    ProjectCreate,
    ProjectResponse,
    QualityScores,
    RefinedStory,
    RefinementRequest,
    ReviewDecisionRequest,
)

router = APIRouter(tags=["user story refinement"])


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_route(
    request: ProjectCreate,
    session: Annotated[Session, Depends(db.get_session)],
) -> ProjectResponse:
    try:
        return create_project(session, request)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The project already exists.") from exc


@router.post(
    "/projects/{project_id}/context",
    response_model=ProjectContextResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_context_route(
    project_id: str,
    request: ProjectContextCreate,
    session: Annotated[Session, Depends(db.get_session)],
) -> ProjectContextResponse:
    try:
        return add_context_entry(session, project_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The project already has a context entry with this key.",
        ) from exc


@router.post("/refine", response_model=RefinedStory)
def refine(request: RefinementRequest, session: Annotated[Session, Depends(db.get_session)]) -> RefinedStory:
    """Turn one validated requirement into a user story with acceptance criteria and quality scores."""
    started = time.perf_counter()
    no_flags = InvestFlags(
        independent=False, negotiable=False, valuable=False, estimable=False, small=False, testable=False
    )
    result = RefinedStory(
        requirement_id=request.requirement_id,
        story_id=f"{request.requirement_id}-S1",
        user_story=f"Placeholder story for: {request.validated_requirement}",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC1", given="(placeholder)", when="(placeholder)", then="(placeholder)")
        ],
        quality_scores=QualityScores(
            invest=no_flags,
            invest_score=0,
            completeness=0,
            clarity=0,
            testability=0,
            consistency=0,
            context_relevance=0,
        ),
        processing_time_ms=int((time.perf_counter() - started) * 1000),
        model_metadata={"model_version": "stub"},
    )
    try:
        run = persist_refinement(session, request, result)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The refinement result could not be persisted.",
        ) from exc
    return result.model_copy(update={"refinement_id": run.id})


@router.post("/refinements/{run_id}/review", response_model=ReviewDecisionRequest)
def review(
    run_id: int,
    request: ReviewDecisionRequest,
    session: Annotated[Session, Depends(db.get_session)],
) -> ReviewDecisionRequest:
    """Record a human decision and update the refinement run status."""
    try:
        record_review(session, run_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The review decision could not be persisted.",
        ) from exc
    return request
