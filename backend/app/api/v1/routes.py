"""Version 1 of the refinement API."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import db
from app.config import get_settings
from app.models import ExistingStory, Project
from app.quality import validate_story_quality
from app.repositories import (
    add_context_entry,
    create_existing_story,
    create_project,
    get_candidate_by_story_id,
    get_context_entry,
    get_existing_story,
    get_refinement,
    get_validated_requirement,
    list_context_entries,
    list_existing_stories,
    list_validated_requirements,
    persist_engine_result,
    persist_refinement,
    record_review,
    update_candidate,
    update_context_entry,
    update_existing_story,
)
from app.schemas import (
    AcceptanceCriterion,
    CandidateResponse,
    ExistingStoryCreate,
    ExistingStoryResponse,
    ExistingStoryUpdate,
    ProjectContextCreate,
    ProjectContextResponse,
    ProjectContextUpdate,
    ProjectCreate,
    ProjectResponse,
    QualityValidationRequest,
    QualityValidationResponse,
    RefinedStory,
    RefinementRequest,
    RetrievedContextResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    StoryRefinementGenerateRequest,
    StoryRefinementGenerateResponse,
    StoryStatusResponse,
    StoryUpdateRequest,
    ValidatedRequirementResponse,
)
from app.services.generation import generate_baseline
from app.services.story_model import (
    InvalidModelOutputError,
    ModelUnavailableError,
    generate_refinement,
)

router = APIRouter(tags=["user story refinement"])


def _validated_requirement_response(requirement) -> ValidatedRequirementResponse:
    return ValidatedRequirementResponse(
        requirement_id=requirement.id,
        project_id=requirement.project_id,
        domain=requirement.domain,
        validated_requirement=requirement.text,
        context_text=requirement.context_text,
        created_at=requirement.created_at.isoformat(),
    )


@router.get("/requirements", response_model=list[ValidatedRequirementResponse])
def list_requirements(
    session: Annotated[Session, Depends(db.get_session)],
    project_id: str | None = None,
) -> list[ValidatedRequirementResponse]:
    try:
        return [
            _validated_requirement_response(requirement)
            for requirement in list_validated_requirements(session, project_id)
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Requirements are temporarily unavailable.",
        ) from exc


@router.get("/requirements/{requirement_id}", response_model=ValidatedRequirementResponse)
def get_requirement(
    requirement_id: str,
    session: Annotated[Session, Depends(db.get_session)],
) -> ValidatedRequirementResponse:
    try:
        requirement = get_validated_requirement(session, requirement_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Requirement lookup failed.",
        ) from exc
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validated requirement not found.")
    return _validated_requirement_response(requirement)


@router.get("/datasets/status", response_model=StoryStatusResponse)
def dataset_status() -> StoryStatusResponse:
    data_dir = Path(get_settings().story_data_dir).resolve()
    files = [item for item in data_dir.rglob("*") if item.is_file()] if data_dir.exists() else []
    return StoryStatusResponse(
        story_id="dataset",
        available=data_dir.exists(),
        message="Dataset directory is available." if data_dir.exists() else "Dataset directory is not available.",
        details={
            "data_dir": str(data_dir),
            "file_count": len(files),
            "split_files": [
                item.name for item in files if item.name in {"train.jsonl", "validation.jsonl", "test.jsonl"}
            ],
        },
    )


@router.get("/models/status", response_model=StoryStatusResponse)
def model_status() -> StoryStatusResponse:
    from app.services.story_model import status

    available, message, details = status()
    return StoryStatusResponse(
        story_id="model",
        available=available,
        message=message,
        details={**details, "generation_mode": get_settings().story_generation_mode},
    )


@router.post("/requirements/validate", response_model=QualityValidationResponse)
def validate_requirement_output(request: QualityValidationRequest) -> QualityValidationResponse:
    """Run structural checks; semantic correctness still requires human review."""
    return validate_story_quality(
        request.user_story,
        request.acceptance_criteria,
        request.requirement_text,
        request.assumptions,
    )


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


@router.get("/projects/{project_id}/context", response_model=list[ProjectContextResponse])
def list_context_route(
    project_id: str,
    session: Annotated[Session, Depends(db.get_session)],
) -> list[ProjectContextResponse]:
    return list_context_entries(session, project_id)


@router.get("/projects/{project_id}/context/{entry_id}", response_model=ProjectContextResponse)
def get_context_route(
    project_id: str,
    entry_id: int,
    session: Annotated[Session, Depends(db.get_session)],
) -> ProjectContextResponse:
    entry = get_context_entry(session, project_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context entry not found.")
    return entry


@router.patch("/projects/{project_id}/context/{entry_id}", response_model=ProjectContextResponse)
def update_context_route(
    project_id: str,
    entry_id: int,
    request: ProjectContextUpdate,
    session: Annotated[Session, Depends(db.get_session)],
) -> ProjectContextResponse:
    entry = get_context_entry(session, project_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context entry not found.")
    try:
        return update_context_entry(session, entry, request.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Context key already exists.") from exc


@router.post("/projects/{project_id}/stories", response_model=ExistingStoryResponse, status_code=201)
def create_existing_story_route(
    project_id: str,
    request: ExistingStoryCreate,
    session: Annotated[Session, Depends(db.get_session)],
) -> ExistingStoryResponse:
    try:
        story = create_existing_story(session, project_id, request)
        return _existing_story_response(story)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The story already exists.") from exc


@router.get("/projects/{project_id}/stories", response_model=list[ExistingStoryResponse])
def list_existing_stories_route(
    project_id: str,
    session: Annotated[Session, Depends(db.get_session)],
) -> list[ExistingStoryResponse]:
    return [_existing_story_response(story) for story in list_existing_stories(session, project_id)]


@router.get("/projects/{project_id}/stories/{story_pk}", response_model=ExistingStoryResponse)
def get_existing_story_route(
    project_id: str,
    story_pk: int,
    session: Annotated[Session, Depends(db.get_session)],
) -> ExistingStoryResponse:
    story = get_existing_story(session, project_id, story_pk)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Existing story not found.")
    return _existing_story_response(story)


@router.patch("/projects/{project_id}/stories/{story_pk}", response_model=ExistingStoryResponse)
def update_existing_story_route(
    project_id: str,
    story_pk: int,
    request: ExistingStoryUpdate,
    session: Annotated[Session, Depends(db.get_session)],
) -> ExistingStoryResponse:
    story = get_existing_story(session, project_id, story_pk)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Existing story not found.")
    try:
        return _existing_story_response(update_existing_story(session, story, request))
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story update failed.") from exc


def _existing_story_response(story: ExistingStory) -> ExistingStoryResponse:
    return ExistingStoryResponse(
        id=story.id,
        project_id=story.project_id,
        story_id=story.story_id,
        title=story.title,
        description=story.description,
        source_reference=story.source_reference,
        acceptance_criteria=[item.text for item in story.acceptance_criteria],
    )


def _candidate_response(item, candidate_id: int | None = None) -> CandidateResponse:
    evaluation = item.evaluation
    scores = evaluation.scores if evaluation else {}
    invest = scores.get("invest", {}) if isinstance(scores.get("invest"), dict) else {}
    return CandidateResponse(
        id=candidate_id,
        story_id=item.story_id,
        user_story=item.user_story,
        acceptance_criteria=[
            AcceptanceCriterion(
                id=criterion.criterion_id, given=criterion.given, when=criterion.when, then=criterion.then
            )
            for criterion in item.acceptance_criteria
        ],
        rank=item.rank,
        selected=item.selected,
        quality_scores={key: value for key, value in scores.items() if isinstance(value, (int, float))},
        invest=invest,
        explanations=evaluation.explanations if evaluation else {},
        unsupported_assumptions=item.unsupported_assumptions,
        risks=[{"statement": value, "kind": "contradiction"} for value in item.inconsistencies],
        ranking_rationale="Persisted candidate ranking from the local refinement engine.",
    )


@router.post("/story-refinement/generate", response_model=StoryRefinementGenerateResponse, status_code=201)
def generate_story_refinement(
    request: StoryRefinementGenerateRequest,
    session: Annotated[Session, Depends(db.get_session)],
) -> StoryRefinementGenerateResponse:
    """Run local inference first, then persist the complete result transactionally."""
    try:
        context_entries = list_context_entries(session, request.project_id)
        existing_stories = list_existing_stories(session, request.project_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Context lookup failed.") from exc
    if not context_entries and not existing_stories:
        project_exists = session.get(Project, request.project_id)
        if project_exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    try:
        from story_ml.config import LLMSettings
        from story_ml.llm import LLMResponseError, LLMUnavailable
        from story_ml.pipeline import refine_requirement
        from story_ml.types import ContextDocument

        documents = [
            ContextDocument(
                project_id=request.project_id,
                source_id=str(entry.id),
                source_type=entry.context_type,
                text=entry.content,
                source_reference=entry.source_reference or f"context:{entry.id}",
            )
            for entry in context_entries
        ]
        for story in existing_stories:
            documents.append(
                ContextDocument(
                    project_id=request.project_id,
                    source_id=str(story.id),
                    source_type="existing_story",
                    text=story.title
                    + " "
                    + story.description
                    + " "
                    + " ".join(item.text for item in story.acceptance_criteria),
                    source_reference=story.source_reference or f"story:{story.id}",
                )
            )
        for index, entry in enumerate(request.context, start=1):
            documents.append(
                ContextDocument(
                    project_id=request.project_id,
                    source_id=f"request-{index}",
                    source_type=entry.context_type,
                    text=entry.content,
                    source_reference=entry.source_reference or f"request-context:{index}",
                )
            )
        session.rollback()
        result = refine_requirement(
            request.validated_requirement,
            request.project_id,
            documents,
            llm_settings=LLMSettings(candidate_count=request.options.candidate_count),
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Local ML engine unavailable."
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Local model timed out.") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid generation input."
        ) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Local model unavailable.") from exc
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Local model returned invalid output."
        ) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Local model unavailable.") from exc
    try:
        run = persist_engine_result(
            session,
            request.project_id,
            request.requirement_id,
            request.validated_requirement,
            None,
            result,
        )
        persisted = get_refinement(session, run.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.") from exc
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Generation persistence failed."
        ) from exc
    candidates = [_candidate_response(item, item.id) for item in persisted.candidates]
    selected = next((item for item in candidates if item.selected), None)
    return StoryRefinementGenerateResponse(
        generation_id=run.id,
        requirement_id=request.requirement_id,
        project_id=request.project_id,
        status=run.status,
        candidates=candidates,
        selected_candidate=selected,
        context_references=[
            RetrievedContextResponse(
                source_id=reference.source_reference,
                source_type="context",
                source_reference=reference.source_reference,
                text="",
                score=reference.relevance_score or 0,
            )
            for reference in persisted.context_references
        ],
        risks=[],
        metadata=run.model_metadata,
    )


@router.get("/story-refinement/{generation_id}", response_model=StoryRefinementGenerateResponse)
def get_story_refinement(
    generation_id: int,
    session: Annotated[Session, Depends(db.get_session)],
) -> StoryRefinementGenerateResponse:
    run = get_refinement(session, generation_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found.")
    candidates = [_candidate_response(item, item.id) for item in run.candidates]
    return StoryRefinementGenerateResponse(
        generation_id=run.id,
        requirement_id=run.requirement_id,
        project_id=run.project_id or "",
        status=run.status,
        candidates=candidates,
        selected_candidate=next((item for item in candidates if item.selected), None),
        context_references=[
            RetrievedContextResponse(
                source_id=item.source_reference,
                source_type="context",
                source_reference=item.source_reference,
                text="",
                score=item.relevance_score or 0,
            )
            for item in run.context_references
        ],
        risks=[],
        metadata=run.model_metadata,
    )


@router.get("/stories/{story_id}", response_model=CandidateResponse)
def get_story(story_id: str, session: Annotated[Session, Depends(db.get_session)]) -> CandidateResponse:
    candidate = get_candidate_by_story_id(session, story_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")
    return _candidate_response(candidate, candidate.id)


@router.put("/stories/{story_id}", response_model=CandidateResponse)
def edit_story(
    story_id: str,
    request: StoryUpdateRequest,
    session: Annotated[Session, Depends(db.get_session)],
) -> CandidateResponse:
    candidate = get_candidate_by_story_id(session, story_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")
    quality = validate_story_quality(request.user_story, request.acceptance_criteria)
    if not quality.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Edited story failed structural validation.", "validation": quality.model_dump()},
        )
    try:
        updated = update_candidate(session, candidate, request.user_story, request.acceptance_criteria)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story update failed.") from exc
    return _candidate_response(updated, updated.id)


@router.post(
    "/story-refinement/{generation_id}/review",
    response_model=ReviewDecisionResponse,
)
def review_story_refinement(
    generation_id: int,
    request: ReviewDecisionRequest,
    session: Annotated[Session, Depends(db.get_session)],
) -> ReviewDecisionResponse:
    try:
        decision = record_review(session, generation_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Review persistence failed."
        ) from exc
    return ReviewDecisionResponse(
        **request.model_dump(),
        id=decision.id,
        generation_id=generation_id,
        created_at=decision.created_at.isoformat(),
    )


@router.post("/requirements/generate", response_model=RefinedStory)
def generate_requirement(
    request: RefinementRequest,
    session: Annotated[Session, Depends(db.get_session)],
) -> RefinedStory:
    """Turn one validated requirement into a reviewable baseline story."""
    result = generate_baseline(request)
    try:
        run = persist_refinement(session, request, result)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The refinement result could not be persisted.",
        ) from exc
    return result.model_copy(update={"refinement_id": run.id})


@router.post("/refine", response_model=RefinedStory)
def refine(
    request: RefinementRequest,
    session: Annotated[Session, Depends(db.get_session)],
) -> RefinedStory:
    """Generate and persist a refinement using the configured fine-tuned model."""
    try:
        requirement = get_validated_requirement(session, request.requirement_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Requirement lookup failed.",
        ) from exc
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validated requirement not found.")
    request = request.model_copy(
        update={
            "project_id": requirement.project_id,
            "validated_requirement": requirement.text,
            "project_context": requirement.context_text,
        }
    )
    session.rollback()
    try:
        result = generate_refinement(request)
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except InvalidModelOutputError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The refinement request or model configuration is invalid.",
        ) from exc
    except (RuntimeError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model inference failed: {exc}",
        ) from exc

    try:
        run = persist_refinement(session, request, result)
        return result.model_copy(update={"refinement_id": run.id})
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refinement persistence failed.",
        ) from exc


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
