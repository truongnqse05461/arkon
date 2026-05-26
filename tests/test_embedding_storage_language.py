"""Unit tests for the language-aware embedding storage helpers.

These test the pure function `embedding_input_text`/`compute_content_hash`
behavior with language tagging — DB-level tests are covered by integration.
"""

from app.services.embedding_storage import (
    compute_content_hash,
    embedding_input_text,
)


def test_compute_content_hash_includes_inputs():
    h1 = compute_content_hash("T", "S", "C")
    h2 = compute_content_hash("T", "S", "D")
    assert h1 != h2


def test_embedding_input_text_truncates_to_8000():
    out = embedding_input_text("t", "s", "x" * 20000)
    assert len(out) == 8000
