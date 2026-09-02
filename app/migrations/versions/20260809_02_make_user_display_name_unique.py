"""Make user display names unique.

Revision ID: 20260809_02
Revises: 20260809_01
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_02"
down_revision: str | Sequence[str] | None = "20260809_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_users_display_name", "users", ["display_name"])


def downgrade() -> None:
    op.drop_constraint("uq_users_display_name", "users", type_="unique")
