"""Add requirement metadata used by the validated-requirement API."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_requirement_metadata"
down_revision: str | None = "0003_requirement_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("validated_requirements", sa.Column("domain", sa.String(200), nullable=True))
    op.add_column("validated_requirements", sa.Column("context_text", sa.Text(), nullable=True))
    op.alter_column(
        "validated_requirements",
        "validation_status",
        server_default=sa.text("'pending_review'"),
    )


def downgrade() -> None:
    op.alter_column(
        "validated_requirements",
        "validation_status",
        server_default=sa.text("'validated'"),
    )
    op.drop_column("validated_requirements", "context_text")
    op.drop_column("validated_requirements", "domain")
