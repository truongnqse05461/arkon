import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_page(title: str, content: str = "content", scope_type: str = "global", scope_id=None):
    p = MagicMock()
    p.title = title
    p.content_md = content
    p.scope_type = scope_type
    p.scope_id = scope_id
    p.orphaned = False
    return p


@pytest.mark.asyncio
async def test_build_payload_uses_excerpts_for_small_wiki():
    from app.services.mindmap_service import _build_payload
    pages = [make_page(f"Page {i}", "x" * 400) for i in range(10)]
    result = _build_payload(pages)
    assert "Page 0" in result
    # With excerpts: each line has content (the "x" * 300 excerpt)
    assert "x" in result


@pytest.mark.asyncio
async def test_build_payload_titles_only_for_large_wiki():
    from app.services.mindmap_service import _build_payload
    pages = [make_page(f"Page {i}") for i in range(150)]
    result = _build_payload(pages)
    lines = result.splitlines()
    assert len(lines) == 150
    # Titles-only lines are shorter (just "- Page N")
    for line in lines:
        assert len(line) < 20


@pytest.mark.asyncio
async def test_generate_mindmap_calls_llm_and_upserts():
    from app.services.mindmap_service import generate_mindmap
    db = AsyncMock()
    pages = [make_page("Architecture"), make_page("Deployment")]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": [{"name": "Architecture", "children": []}]}
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=json.dumps(tree))

    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            result = await generate_mindmap(db, "global", None)
            db.add.assert_called_once()
            db.flush.assert_called()


@pytest.mark.asyncio
async def test_generate_mindmap_raises_when_no_pages():
    from app.services.mindmap_service import generate_mindmap
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValueError, match="No wiki pages"):
        await generate_mindmap(db, "global", None)


@pytest.mark.asyncio
async def test_generate_mindmap_strips_markdown_fences():
    from app.services.mindmap_service import generate_mindmap
    db = AsyncMock()
    pages = [make_page("Arch")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": []}
    raw = f"```json\n{json.dumps(tree)}\n```"
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=raw)
    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            result = await generate_mindmap(db, "global", None)
            assert result is not None
