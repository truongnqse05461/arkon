"""Add wiki_mindmaps table

Revision ID: 030
Revises: 029
Create Date: 2026-05-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "030"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wiki_mindmaps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False, server_default="Knowledge Base"),
        sa.Column("tree_json", JSONB, nullable=False),
        sa.Column("wiki_page_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_wiki_mindmaps_global", "wiki_mindmaps", ["scope_type"],
        unique=True, postgresql_where=sa.text("scope_id IS NULL"),
    )
    op.create_index(
        "uq_wiki_mindmaps_scoped", "wiki_mindmaps", ["scope_type", "scope_id"],
        unique=True, postgresql_where=sa.text("scope_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_wiki_mindmaps_scoped", table_name="wiki_mindmaps")
    op.drop_index("uq_wiki_mindmaps_global", table_name="wiki_mindmaps")
    op.drop_table("wiki_mindmaps")
