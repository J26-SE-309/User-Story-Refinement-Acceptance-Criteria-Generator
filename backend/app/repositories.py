"""Transactional persistence operations for refinement requests."""

from sqlalchemy.orm import Session

from app.models import (
    CandidateAcceptanceCriterion,
    CandidateQualityEvaluation,
    Project,
    ProjectContextEntry,
    RefinementContextReference,
    RefinementRun,
    ReviewDecision,
    StoryCandidate,
    ValidatedRequirement,
)
from app.schemas import (
    ProjectContextCreate,
    ProjectCreate,
    RefinedStory,
    RefinementRequest,
    ReviewDecisionRequest,
)


def persist_refinement(session: Session, request: RefinementRequest, result: RefinedStory) -> RefinementRun:
    """Persist one complete refinement result in a single transaction."""
    with session.begin():
        project = None
        if request.project_id:
            project = session.get(Project, request.project_id)
            if project is None:
                project = Project(id=request.project_id, name=request.project_id)
                session.add(project)

        requirement = session.get(ValidatedRequirement, request.requirement_id)
        if requirement is None:
            requirement = ValidatedRequirement(
                id=request.requirement_id,
                project=project,
                text=request.validated_requirement,
            )
            session.add(requirement)
        else:
            requirement.text = request.validated_requirement
            if request.project_id and requirement.project_id is None:
                requirement.project = project

        run = RefinementRun(
            requirement=requirement,
            project=project,
            context_reference=request.context_reference,
            processing_time_ms=result.processing_time_ms,
            model_metadata=result.model_metadata,
            status="draft",
        )
        session.add(run)
        session.flush()

        candidate = StoryCandidate(
            run=run,
            story_id=result.story_id,
            user_story=result.user_story,
            rank=1,
            selected=True,
            unsupported_assumptions=result.unsupported_assumptions,
            inconsistencies=[],
        )
        session.add(candidate)
        session.flush()
        run.selected_candidate_id = candidate.id

        for criterion in result.acceptance_criteria:
            session.add(
                CandidateAcceptanceCriterion(
                    candidate_id=candidate.id,
                    criterion_id=criterion.id,
                    given=criterion.given,
                    when=criterion.when,
                    then=criterion.then,
                )
            )
        session.add(
            CandidateQualityEvaluation(
                candidate_id=candidate.id,
                scores=result.quality_scores.model_dump(),
                explanations={},
            )
        )
        if request.context_reference:
            session.add(
                RefinementContextReference(
                    run_id=run.id,
                    source_reference=request.context_reference,
                )
            )
    return run


def create_project(session: Session, request: ProjectCreate) -> Project:
    with session.begin():
        project = Project(**request.model_dump())
        session.add(project)
    return project


def add_context_entry(session: Session, project_id: str, request: ProjectContextCreate) -> ProjectContextEntry:
    with session.begin():
        project = session.get(Project, project_id)
        if project is None:
            raise LookupError(f"Project '{project_id}' does not exist.")
        entry = ProjectContextEntry(project_id=project_id, **request.model_dump())
        session.add(entry)
    return entry


def record_review(session: Session, run_id: int, request: ReviewDecisionRequest) -> ReviewDecision:
    with session.begin():
        run = session.get(RefinementRun, run_id)
        if run is None:
            raise LookupError(f"Refinement run '{run_id}' does not exist.")
        if request.candidate_id is not None:
            candidate = session.get(StoryCandidate, request.candidate_id)
            if candidate is None or candidate.run_id != run_id:
                raise ValueError("The selected candidate does not belong to this refinement run.")
        decision = ReviewDecision(run_id=run_id, **request.model_dump())
        session.add(decision)
        run.status = request.status
    return decision
