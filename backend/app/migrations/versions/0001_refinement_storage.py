"""Add refinement storage tables.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    targets = {
        "refinement_projects",
        "project_context_entries",
        "validated_requirements",
        "existing_stories",
        "existing_story_acceptance_criteria",
        "refinement_runs",
        "refinement_context_references",
        "story_candidates",
        "candidate_acceptance_criteria",
        "candidate_quality_evaluations",
        "review_decisions",
    }
    conflicts = sorted(existing & targets)
    if conflicts:
        raise RuntimeError(
            "Refinement migration stopped because target tables already exist outside Alembic: " + ", ".join(conflicts)
        )

    op.create_table(
        "refinement_projects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_context_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id", sa.String(64), sa.ForeignKey("refinement_projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("context_key", sa.String(200), nullable=False),
        sa.Column("context_type", sa.String(40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("authoritative", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "context_key", name="uq_context_project_key"),
    )
    op.create_index("ix_context_project_type", "project_context_entries", ["project_id", "context_type"])
    op.create_table(
        "validated_requirements",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column(
            "project_id", sa.String(64), sa.ForeignKey("refinement_projects.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False, server_default="validated"),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_requirement_project_status", "validated_requirements", ["project_id", "validation_status"])
    op.create_table(
        "existing_stories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id", sa.String(64), sa.ForeignKey("refinement_projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("story_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.UniqueConstraint("project_id", "story_id", name="uq_existing_story_project_id"),
    )
    op.create_index("ix_existing_story_project", "existing_stories", ["project_id"])
    op.create_table(
        "existing_story_acceptance_criteria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("story_id", sa.Integer(), sa.ForeignKey("existing_stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion_id", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_table(
        "refinement_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.String(200),
            sa.ForeignKey("validated_requirements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.String(64), sa.ForeignKey("refinement_projects.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("context_reference", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("selected_candidate_id", sa.Integer(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refinement_run_requirement_created", "refinement_runs", ["requirement_id", "created_at"])
    op.create_table(
        "refinement_context_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("refinement_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_entry_id",
            sa.Integer(),
            sa.ForeignKey("project_context_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_refinement_context_run", "refinement_context_references", ["run_id"])
    op.create_table(
        "story_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("refinement_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", sa.String(200), nullable=False),
        sa.Column("user_story", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unsupported_assumptions", sa.JSON(), nullable=False),
        sa.Column("inconsistencies", sa.JSON(), nullable=False),
    )
    op.create_index("ix_candidate_run_rank", "story_candidates", ["run_id", "rank"])
    op.create_table(
        "candidate_acceptance_criteria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id", sa.Integer(), sa.ForeignKey("story_candidates.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("criterion_id", sa.String(100), nullable=False),
        sa.Column("given", sa.Text(), nullable=False),
        sa.Column("when", sa.Text(), nullable=False),
        sa.Column("then", sa.Text(), nullable=False),
        sa.UniqueConstraint("candidate_id", "criterion_id", name="uq_candidate_criterion_id"),
    )
    op.create_table(
        "candidate_quality_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("story_candidates.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("explanations", sa.JSON(), nullable=False),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("refinement_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "candidate_id", sa.Integer(), sa.ForeignKey("story_candidates.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_run_created", "review_decisions", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_review_run_created", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_table("candidate_quality_evaluations")
    op.drop_table("candidate_acceptance_criteria")
    op.drop_index("ix_candidate_run_rank", table_name="story_candidates")
    op.drop_table("story_candidates")
    op.drop_index("ix_refinement_context_run", table_name="refinement_context_references")
    op.drop_table("refinement_context_references")
    op.drop_index("ix_refinement_run_requirement_created", table_name="refinement_runs")
    op.drop_table("refinement_runs")
    op.drop_table("existing_story_acceptance_criteria")
    op.drop_index("ix_existing_story_project", table_name="existing_stories")
    op.drop_table("existing_stories")
    op.drop_index("ix_requirement_project_status", table_name="validated_requirements")
    op.drop_table("validated_requirements")
    op.drop_index("ix_context_project_type", table_name="project_context_entries")
    op.drop_table("project_context_entries")
    op.drop_table("refinement_projects")
