"""Transactional persistence operations for refinement requests."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CandidateAcceptanceCriterion,
    CandidateQualityEvaluation,
    ExistingStory,
    ExistingStoryAcceptanceCriterion,
    Project,
    ProjectContextEntry,
    RefinementContextReference,
    RefinementRun,
    ReviewDecision,
    StoryCandidate,
    ValidatedRequirement,
)
from app.schemas import (
    AcceptanceCriterion,
    ExistingStoryCreate,
    ExistingStoryUpdate,
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


def get_refinement(session: Session, run_id: int) -> RefinementRun | None:
    return session.scalar(
        select(RefinementRun)
        .options(
            selectinload(RefinementRun.candidates).selectinload(StoryCandidate.acceptance_criteria),
            selectinload(RefinementRun.candidates).selectinload(StoryCandidate.evaluation),
            selectinload(RefinementRun.context_references),
        )
        .where(RefinementRun.id == run_id)
    )


def get_candidate_by_story_id(session: Session, story_id: str) -> StoryCandidate | None:
    return session.scalar(
        select(StoryCandidate)
        .options(
            selectinload(StoryCandidate.acceptance_criteria),
            selectinload(StoryCandidate.evaluation),
            selectinload(StoryCandidate.run),
        )
        .where(StoryCandidate.story_id == story_id)
    )


def update_candidate(
        session: Session,
        candidate: StoryCandidate,
        user_story: str,
        acceptance_criteria: list[AcceptanceCriterion],
) -> StoryCandidate:
    session.rollback()
    with session.begin():
        if candidate.original_user_story is None:
            candidate.original_user_story = candidate.user_story
            candidate.original_acceptance_criteria = [
                {
                    "id": item.criterion_id,
                    "given": item.given,
                    "when": item.when,
                    "then": item.then,
                }
                for item in candidate.acceptance_criteria
            ]
        candidate.user_story = user_story
        for criterion in list(candidate.acceptance_criteria):
            session.delete(criterion)
        candidate.acceptance_criteria = []
        session.flush()
        candidate.acceptance_criteria.extend(
            CandidateAcceptanceCriterion(
                criterion_id=item.id,
                given=item.given,
                when=item.when,
                then=item.then,
            )
            for item in acceptance_criteria
        )
        candidate.run.status = "edited"
        session.add(candidate)
    return candidate


def list_context_entries(session: Session, project_id: str) -> list[ProjectContextEntry]:
    return list(
        session.scalars(
            select(ProjectContextEntry)
            .where(ProjectContextEntry.project_id == project_id)
            .order_by(ProjectContextEntry.id)
        )
    )


def get_context_entry(session: Session, project_id: str, entry_id: int) -> ProjectContextEntry | None:
    return session.scalar(
        select(ProjectContextEntry).where(
            ProjectContextEntry.project_id == project_id,
            ProjectContextEntry.id == entry_id,
        )
    )


def update_context_entry(session: Session, entry: ProjectContextEntry, changes: dict) -> ProjectContextEntry:
    with session.begin():
        for key, value in changes.items():
            if value is not None:
                setattr(entry, key, value)
        session.add(entry)
    return entry


def create_existing_story(session: Session, project_id: str, request: ExistingStoryCreate) -> ExistingStory:
    with session.begin():
        if session.scalar(select(Project.id).where(Project.id == project_id)) is None:
            raise LookupError(f"Project '{project_id}' does not exist.")
        story = ExistingStory(
            project_id=project_id,
            story_id=request.story_id,
            title=request.title,
            description=request.description,
            source_reference=request.source_reference,
        )
        story.acceptance_criteria = [
            ExistingStoryAcceptanceCriterion(criterion_id=f"AC{index}", text=text)
            for index, text in enumerate(request.acceptance_criteria, start=1)
        ]
        session.add(story)
        session.flush()
    return story


def list_existing_stories(session: Session, project_id: str) -> list[ExistingStory]:
    return list(
        session.scalars(
            select(ExistingStory)
            .options(selectinload(ExistingStory.acceptance_criteria))
            .where(ExistingStory.project_id == project_id)
            .order_by(ExistingStory.id)
        )
    )


def get_existing_story(session: Session, project_id: str, story_pk: int) -> ExistingStory | None:
    return session.scalar(
        select(ExistingStory)
        .options(selectinload(ExistingStory.acceptance_criteria))
        .where(ExistingStory.project_id == project_id, ExistingStory.id == story_pk)
    )


def update_existing_story(session: Session, story: ExistingStory, request: ExistingStoryUpdate) -> ExistingStory:
    with session.begin():
        values = request.model_dump(exclude_unset=True, exclude={"acceptance_criteria"})
        for key, value in values.items():
            setattr(story, key, value)
        if request.acceptance_criteria is not None:
            story.acceptance_criteria.clear()
            story.acceptance_criteria.extend(
                ExistingStoryAcceptanceCriterion(criterion_id=f"AC{index}", text=text)
                for index, text in enumerate(request.acceptance_criteria, start=1)
            )
        session.add(story)
    return story


def persist_engine_result(
    session: Session,
    project_id: str,
    requirement_id: str,
    requirement_text: str,
    context_reference: str | None,
    engine_result,
) -> RefinementRun:
    """Persist the complete engine result after inference has finished."""
    with session.begin():
        project = session.get(Project, project_id)
        if project is None:
            raise LookupError(f"Project '{project_id}' does not exist.")
        requirement = session.get(ValidatedRequirement, requirement_id)
        if requirement is None:
            requirement = ValidatedRequirement(
                id=requirement_id,
                project_id=project_id,
                text=requirement_text,
            )
            session.add(requirement)
            session.flush()
        else:
            requirement.text = requirement_text
            requirement.project_id = project_id

        run = RefinementRun(
            requirement_id=requirement_id,
            project_id=project_id,
            context_reference=context_reference,
            status=engine_result.status,
            processing_time_ms=0,
            model_metadata={str(key): str(value) for key, value in engine_result.metadata.items()},
        )
        session.add(run)
        session.flush()
        for item in engine_result.retrieved_context:
            context_entry = session.scalar(
                select(ProjectContextEntry).where(
                    ProjectContextEntry.project_id == project_id,
                    ProjectContextEntry.source_reference == item.document.source_reference,
                )
            )
            session.add(
                RefinementContextReference(
                    run_id=run.id,
                    context_entry_id=context_entry.id if context_entry else None,
                    source_reference=item.document.source_reference,
                    relevance_score=item.score,
                )
            )
        for item in engine_result.candidates:
            candidate = StoryCandidate(
                run_id=run.id,
                story_id=item.candidate.story_id,
                user_story=item.candidate.user_story,
                rank=item.rank,
                selected=engine_result.best_candidate is item,
                unsupported_assumptions=[
                    finding.statement for finding in item.evaluation.findings if finding.kind == "unsupported_claim"
                ],
                inconsistencies=[
                    finding.statement for finding in item.evaluation.findings if finding.kind == "contradiction"
                ],
            )
            session.add(candidate)
            session.flush()
            for criterion in item.candidate.acceptance_criteria:
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
                    scores={**item.evaluation.scores, "invest": item.evaluation.invest},
                    explanations=item.evaluation.explanations,
                )
            )
            if engine_result.best_candidate is item:
                run.selected_candidate_id = candidate.id
    return run
