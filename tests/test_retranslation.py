"""Decision-table tests for the per-page re-translation helper.

`retranslate_page` mutates a WikiPage in place and returns an outcome string.
We patch the translator + embedding helpers so these stay pure unit tests
(no LLM, no DB).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.database.models import WikiPage
from app.ai.mrp.translator import TranslationOutput
from app.services.retranslation import retranslate_page


def _page(**kw) -> WikiPage:
    defaults = dict(
        id=uuid.uuid4(),
        slug="concept/x",
        title="T",
        page_type="concept",
        content_md="some body content",
        summary="sum",
        source_language=None,
        target_language=None,
        translation_status="skipped",
        title_translated=None,
        summary_translated=None,
        content_md_translated=None,
    )
    defaults.update(kw)
    return WikiPage(**defaults)


@pytest.mark.asyncio
async def test_add_translates_and_embeds():
    page = _page(source_language="zh")
    out = TranslationOutput(title="Bình", summary="cong cu", content_md="Bình chữa cháy ...")
    embedder = AsyncMock()
    embedder.embed.return_value = [0.1] * 8
    spec = object()  # truthy active_spec
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=out)), \
         patch("app.services.retranslation.upsert_page_embedding", AsyncMock()) as up, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), embedder, spec)

    assert outcome == "done"
    assert page.target_language == "vi"
    assert page.source_language == "zh"
    assert page.content_md_translated == "Bình chữa cháy ..."
    assert page.translation_status == "done"
    up.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_overwrites_without_delete():
    page = _page(source_language="zh", target_language="en",
                 translation_status="done", content_md_translated="old english")
    out = TranslationOutput(title="t", summary="s", content_md="bản dịch mới")
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=out)), \
         patch("app.services.retranslation.upsert_page_embedding", AsyncMock()), \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()) as dp:
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), None, None)

    assert outcome == "done"
    assert page.target_language == "vi"
    assert page.content_md_translated == "bản dịch mới"
    dp.assert_not_awaited()  # in-place overwrite — no explicit delete


@pytest.mark.asyncio
async def test_remove_clears_fields_and_deletes_embedding():
    page = _page(source_language="zh", target_language="vi", translation_status="done",
                 title_translated="x", summary_translated="y", content_md_translated="z")
    with patch("app.services.retranslation.translate_page", AsyncMock()) as tp, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()) as dp:
        outcome = await retranslate_page(AsyncMock(), page, None, None, AsyncMock(), None, None)

    assert outcome == "removed"
    assert page.target_language is None
    assert page.content_md_translated is None
    assert page.translation_status == "skipped"
    dp.assert_awaited_once()
    tp.assert_not_awaited()  # never calls the LLM


@pytest.mark.asyncio
async def test_skip_when_source_equals_target():
    page = _page(source_language="vi")
    with patch("app.services.retranslation.translate_page", AsyncMock()) as tp, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), None, None)

    assert outcome == "skipped"
    assert page.target_language == "vi"
    assert page.translation_status == "skipped"
    tp.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_when_source_undetectable():
    page = _page(source_language=None)
    with patch("app.services.retranslation.detect_language", return_value=("en", 0.0)), \
         patch("app.services.retranslation.translate_page", AsyncMock()) as tp, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), None, None)

    assert outcome == "skipped"
    tp.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_marks_failed_and_clears_stale():
    page = _page(source_language="zh", target_language="vi", content_md_translated="old")
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=None)), \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()) as dp:
        outcome = await retranslate_page(AsyncMock(), page, "en", None, AsyncMock(), None, None)

    assert outcome == "failed"
    assert page.translation_status == "failed"
    assert page.content_md_translated is None
    assert page.target_language == "en"
    dp.assert_awaited_once()


@pytest.mark.asyncio
async def test_source_override_propagates_to_page():
    page = _page(source_language=None)
    out = TranslationOutput(title="t", summary="s", content_md="dich")
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=out)), \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", "zh", AsyncMock(), None, None)

    assert outcome == "done"
    assert page.source_language == "zh"
