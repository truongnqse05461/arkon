"""Verify TRANSLATE phase is invoked when target_language is set, skipped otherwise.

Mocks the LLM so this is a unit-level integration test (no real API calls).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.mrp.writer import PageWriteResult


@pytest.mark.asyncio
async def test_translate_phase_skipped_when_no_target_language():
    from app.ai.mrp.pipeline import _maybe_run_translate_phase

    pages = [
        PageWriteResult(slug="concept/x", title="X", page_type="concept",
                        action="CREATE", content_md="body", summary="sum")
    ]
    llm = AsyncMock()

    out = await _maybe_run_translate_phase(
        pages=pages, source_language="zh", target_language=None, llm=llm,
    )
    assert out == pages
    assert all(p.title_translated is None for p in out)
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_phase_skipped_when_languages_equal():
    from app.ai.mrp.pipeline import _maybe_run_translate_phase

    pages = [
        PageWriteResult(slug="concept/x", title="X", page_type="concept",
                        action="CREATE", content_md="body", summary="sum")
    ]
    llm = AsyncMock()

    out = await _maybe_run_translate_phase(
        pages=pages, source_language="vi", target_language="vi", llm=llm,
    )
    assert out == pages
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_phase_populates_translated_fields_on_success():
    from app.ai.mrp.pipeline import _maybe_run_translate_phase

    pages = [
        PageWriteResult(
            slug="concept/x", title="灭火器", page_type="concept", action="CREATE",
            content_md="灭火器是工具。" * 10, summary="工具",
        )
    ]
    llm = AsyncMock()
    llm.generate.return_value = (
        '{"title": "Bình chữa cháy",'
        ' "summary": "công cụ",'
        ' "content_md": "Bình chữa cháy là công cụ. ' + "x" * 60 + '"}'
    )

    out = await _maybe_run_translate_phase(
        pages=pages, source_language="zh", target_language="vi", llm=llm,
    )
    assert out[0].title_translated == "Bình chữa cháy"
    assert out[0].translation_status == "done"
