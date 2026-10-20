"""Preserve the generated candidate before human edits."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_original_candidate_versions"
down_revision: str | None = "0001_refinement_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("story_candidates", sa.Column("original_user_story", sa.Text(), nullable=True))
    op.add_column("story_candidates", sa.Column("original_acceptance_criteria", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("story_candidates", "original_acceptance_criteria")
    op.drop_column("story_candidates", "original_user_story")
