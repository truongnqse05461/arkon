"""Unit tests for the language-aware embedding storage helpers.

These test the pure function `embedding_input_text`/`compute_content_hash`
behavior with language tagging — DB-level tests are covered by integration.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.ai.embedding_catalog import EmbeddingModelSpec
from app.services.embedding_storage import (
    compute_content_hash,
    embedding_input_text,
    upsert_page_embedding,
)


def test_compute_content_hash_includes_inputs():
    h1 = compute_content_hash("T", "S", "C")
    h2 = compute_content_hash("T", "S", "D")
    assert h1 != h2


def test_embedding_input_text_truncates_to_8000():
    out = embedding_input_text("t", "s", "x" * 20000)
    assert len(out) == 8000


@pytest.mark.asyncio
async def test_upsert_page_embedding_passes_language():
    """The `language` kwarg must reach the INSERT statement so per-language
    rows are stored distinctly (source vs. vi vs. en …)."""
    session = AsyncMock()
    spec = EmbeddingModelSpec(
        id="openai/text-embedding-3-small",
        provider="openai",
        model_id="text-embedding-3-small",
        dimension=1536,
        max_input_tokens=8191,
        label="test",
        cost_per_1m_tokens=0.02,
    )
    await upsert_page_embedding(
        session=session,
        page_id=uuid.uuid4(),
        spec=spec,
        vector=[0.0] * 1536,
        content_hash="abc",
        language="vi",
    )

    # The first call's first positional arg is the compiled insert statement.
    stmt = session.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "'vi'" in compiled
