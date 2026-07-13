"""Add scope fields to chat_sessions

Revision ID: 037
Revises: 036
Create Date: 2026-07-13 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("scope_type", sa.String(20), nullable=True))
    op.add_column("chat_sessions", sa.Column("scope_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "scope_id")
    op.drop_column("chat_sessions", "scope_type")
