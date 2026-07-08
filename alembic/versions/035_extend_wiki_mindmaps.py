"""Extend wiki_mindmaps with source_type, source_ids, instruction

Revision ID: 035
Revises: 034
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wiki_mindmaps",
        sa.Column("source_type", sa.String(20), nullable=False, server_default="wiki"),
    )
    op.add_column(
        "wiki_mindmaps",
        sa.Column("source_ids", JSONB, nullable=True),
    )
    op.add_column(
        "wiki_mindmaps",
        sa.Column("instruction", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wiki_mindmaps", "instruction")
    op.drop_column("wiki_mindmaps", "source_ids")
    op.drop_column("wiki_mindmaps", "source_type")
