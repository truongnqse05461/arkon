"""Add translation columns to sources, wiki_pages, wiki_page_embeddings_*

Revision ID: 033
Revises: 032
Create Date: 2026-05-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_TABLES = (
    "wiki_page_embeddings_768",
    "wiki_page_embeddings_1024",
    "wiki_page_embeddings_1536",
    "wiki_page_embeddings_3072",
)


def upgrade() -> None:
    # --- sources ---
    op.add_column("sources", sa.Column("source_language", sa.String(8), nullable=True))
    op.add_column("sources", sa.Column("target_language", sa.String(8), nullable=True))

    # --- wiki_pages ---
    op.add_column("wiki_pages", sa.Column("source_language", sa.String(8), nullable=True))
    op.add_column("wiki_pages", sa.Column("target_language", sa.String(8), nullable=True))
    op.add_column("wiki_pages", sa.Column("title_translated", sa.String(500), nullable=True))
    op.add_column("wiki_pages", sa.Column("summary_translated", sa.Text, nullable=True))
    op.add_column("wiki_pages", sa.Column("content_md_translated", sa.Text, nullable=True))
    op.add_column(
        "wiki_pages",
        sa.Column(
            "translation_status",
            sa.String(20),
            nullable=False,
            server_default="skipped",
        ),
    )

    # --- wiki_page_embeddings_<dim>: add language column + extend PK ---
    for tbl in EMBED_TABLES:
        op.add_column(
            tbl,
            sa.Column(
                "language", sa.String(8), nullable=False, server_default="source"
            ),
        )
        op.drop_constraint(f"{tbl}_pkey", tbl, type_="primary")
        op.create_primary_key(
            f"{tbl}_pkey", tbl, ["page_id", "model_spec_id", "language"]
        )


def downgrade() -> None:
    for tbl in EMBED_TABLES:
        op.drop_constraint(f"{tbl}_pkey", tbl, type_="primary")
        op.create_primary_key(f"{tbl}_pkey", tbl, ["page_id", "model_spec_id"])
        op.drop_column(tbl, "language")

    op.drop_column("wiki_pages", "translation_status")
    op.drop_column("wiki_pages", "content_md_translated")
    op.drop_column("wiki_pages", "summary_translated")
    op.drop_column("wiki_pages", "title_translated")
    op.drop_column("wiki_pages", "target_language")
    op.drop_column("wiki_pages", "source_language")

    op.drop_column("sources", "target_language")
    op.drop_column("sources", "source_language")
