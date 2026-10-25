"""Reserve the requirement-context migration revision.

The context fields are added by the following migration so this repair remains
non-destructive for databases that already recorded revision 0003.
"""

from collections.abc import Sequence

revision: str = "0003_requirement_context"
down_revision: str | None = "0002_original_candidate_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass