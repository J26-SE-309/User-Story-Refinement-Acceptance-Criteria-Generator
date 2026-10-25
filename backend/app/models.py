"""SQLAlchemy models owned by the story-refinement component."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "refinement_projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    context_entries: Mapped[list["ProjectContextEntry"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    requirements: Mapped[list["ValidatedRequirement"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    existing_stories: Mapped[list["ExistingStory"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    refinement_runs: Mapped[list["RefinementRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectContextEntry(Base):
    __tablename__ = "project_context_entries"
    __table_args__ = (
        UniqueConstraint("project_id", "context_key", name="uq_context_project_key"),
        Index("ix_context_project_type", "project_id", "context_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("refinement_projects.id", ondelete="CASCADE"))
    context_key: Mapped[str] = mapped_column(String(200))
    context_type: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authoritative: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    project: Mapped[Project] = relationship(back_populates="context_entries")


class ValidatedRequirement(Base):
    __tablename__ = "validated_requirements"
    __table_args__ = (Index("ix_requirement_project_status", "project_id", "validation_status"),)

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("refinement_projects.id", ondelete="SET NULL"), nullable=True
    )
    domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), default="pending_review")
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    project: Mapped[Project | None] = relationship(back_populates="requirements")
    refinement_runs: Mapped[list["RefinementRun"]] = relationship(back_populates="requirement")

    @property
    def requirement_id(self) -> str:
        return self.id

    @property
    def validated_requirement(self) -> str:
        return self.text

    @property
    def status(self) -> str:
        return self.validation_status


class ExistingStory(Base):
    __tablename__ = "existing_stories"
    __table_args__ = (
        Index("ix_existing_story_project", "project_id"),
        UniqueConstraint("project_id", "story_id", name="uq_existing_story_project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("refinement_projects.id", ondelete="CASCADE"))
    story_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project: Mapped[Project] = relationship(back_populates="existing_stories")
    acceptance_criteria: Mapped[list["ExistingStoryAcceptanceCriterion"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


class ExistingStoryAcceptanceCriterion(Base):
    __tablename__ = "existing_story_acceptance_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("existing_stories.id", ondelete="CASCADE"))
    criterion_id: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    story: Mapped[ExistingStory] = relationship(back_populates="acceptance_criteria")


class RefinementRun(Base):
    __tablename__ = "refinement_runs"
    __table_args__ = (Index("ix_refinement_run_requirement_created", "requirement_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("validated_requirements.id", ondelete="RESTRICT"))
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("refinement_projects.id", ondelete="SET NULL"), nullable=True
    )
    context_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    selected_candidate_id: Mapped[int | None] = mapped_column(nullable=True)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    model_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    requirement: Mapped[ValidatedRequirement] = relationship(back_populates="refinement_runs")
    project: Mapped[Project | None] = relationship(back_populates="refinement_runs")
    context_references: Mapped[list["RefinementContextReference"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["StoryCandidate"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", foreign_keys="StoryCandidate.run_id"
    )
    reviews: Mapped[list["ReviewDecision"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RefinementContextReference(Base):
    __tablename__ = "refinement_context_references"
    __table_args__ = (Index("ix_refinement_context_run", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("refinement_runs.id", ondelete="CASCADE"))
    context_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_context_entries.id", ondelete="SET NULL"), nullable=True
    )
    source_reference: Mapped[str] = mapped_column(String(500))
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    run: Mapped[RefinementRun] = relationship(back_populates="context_references")


class StoryCandidate(Base):
    __tablename__ = "story_candidates"
    __table_args__ = (Index("ix_candidate_run_rank", "run_id", "rank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("refinement_runs.id", ondelete="CASCADE"))
    story_id: Mapped[str] = mapped_column(String(200))
    user_story: Mapped[str] = mapped_column(Text)
    original_user_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_acceptance_criteria: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rank: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    unsupported_assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    inconsistencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    run: Mapped[RefinementRun] = relationship(back_populates="candidates", foreign_keys=[run_id])
    acceptance_criteria: Mapped[list["CandidateAcceptanceCriterion"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    evaluation: Mapped["CandidateQualityEvaluation | None"] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", uselist=False
    )


class CandidateAcceptanceCriterion(Base):
    __tablename__ = "candidate_acceptance_criteria"
    __table_args__ = (UniqueConstraint("candidate_id", "criterion_id", name="uq_candidate_criterion_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("story_candidates.id", ondelete="CASCADE"))
    criterion_id: Mapped[str] = mapped_column(String(100))
    given: Mapped[str] = mapped_column(Text)
    when: Mapped[str] = mapped_column(Text)
    then: Mapped[str] = mapped_column(Text)
    candidate: Mapped[StoryCandidate] = relationship(back_populates="acceptance_criteria")


class CandidateQualityEvaluation(Base):
    __tablename__ = "candidate_quality_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("story_candidates.id", ondelete="CASCADE"), unique=True)
    scores: Mapped[dict] = mapped_column(JSON)
    explanations: Mapped[dict] = mapped_column(JSON, default=dict)
    candidate: Mapped[StoryCandidate] = relationship(back_populates="evaluation")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (Index("ix_review_run_created", "run_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("refinement_runs.id", ondelete="CASCADE"))
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_candidates.id", ondelete="SET NULL"), nullable=True
    )
    reviewer: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    run: Mapped[RefinementRun] = relationship(back_populates="reviews")
