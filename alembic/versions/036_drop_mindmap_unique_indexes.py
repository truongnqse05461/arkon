"""Drop mindmap unique indexes to allow multiple per scope.

Revision ID: 036
Revises: 035
Create Date: 2026-07-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_wiki_mindmaps_global", table_name="wiki_mindmaps")
    op.drop_index("uq_wiki_mindmaps_scoped", table_name="wiki_mindmaps")


def downgrade() -> None:
    from sqlalchemy import text

    op.create_index(
        "uq_wiki_mindmaps_global",
        "wiki_mindmaps",
        ["scope_type"],
        unique=True,
        postgresql_where=text("scope_id IS NULL"),
    )
    op.create_index(
        "uq_wiki_mindmaps_scoped",
        "wiki_mindmaps",
        ["scope_type", "scope_id"],
        unique=True,
        postgresql_where=text("scope_id IS NOT NULL"),
    )
