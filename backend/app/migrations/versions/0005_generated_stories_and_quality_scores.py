"""Add generated story and quality score storage.

The existing refinement schema uses integer run IDs, so the new tables retain
that relationship while using UUID IDs for generated stories and scores.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_generated_stories_and_quality_scores"
down_revision: str | None = "0004_requirement_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("refinement_runs", sa.Column("input_requirement_snapshot", sa.Text(), nullable=True))
    op.add_column("refinement_runs", sa.Column("model_name", sa.String(150), nullable=True))
    op.add_column("refinement_runs", sa.Column("model_version", sa.String(150), nullable=True))
    op.add_column("refinement_runs", sa.Column("prompt_version", sa.String(50), nullable=True))
    op.add_column("refinement_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("refinement_runs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "idx_refinement_runs_requirement",
        "refinement_runs",
        ["requirement_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "generated_stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("refinement_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_number", sa.Integer(), nullable=False),
        sa.Column("user_story", sa.Text(), nullable=False),
        sa.Column(
            "acceptance_criteria",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "quality_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generated_story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invest_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("clarity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("testability_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("consistency_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("context_relevance_score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "unsupported_assumptions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("evaluation_version", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("quality_scores")
    op.drop_table("generated_stories")
    op.drop_index("idx_refinement_runs_requirement", table_name="refinement_runs")
    op.drop_column("refinement_runs", "completed_at")
    op.drop_column("refinement_runs", "error_message")
    op.drop_column("refinement_runs", "prompt_version")
    op.drop_column("refinement_runs", "model_version")
    op.drop_column("refinement_runs", "model_name")
    op.drop_column("refinement_runs", "input_requirement_snapshot")
