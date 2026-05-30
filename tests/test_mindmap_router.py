import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_mindmap(scope_type="global", scope_id=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.scope_type = scope_type
    m.scope_id = scope_id
    m.title = "Knowledge Base"
    m.tree_json = {"name": "Knowledge Base", "children": []}
    m.wiki_page_count = 5
    m.generated_at = "2026-05-31T00:00:00+00:00"
    return m


@pytest.mark.asyncio
async def test_get_mindmap_returns_404_when_missing():
    from app.routers.mindmap import get_mindmap_endpoint
    from fastapi import HTTPException
    db = AsyncMock()
    user = MagicMock()
    with patch("app.routers.mindmap.mindmap_service.get_mindmap", return_value=None):
        with pytest.raises(HTTPException) as exc:
            await get_mindmap_endpoint("global", None, db, user)
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_mindmap_returns_record_when_found():
    from app.routers.mindmap import get_mindmap_endpoint
    db = AsyncMock()
    user = MagicMock()
    mm = make_mindmap()
    with patch("app.routers.mindmap.mindmap_service.get_mindmap", return_value=mm):
        result = await get_mindmap_endpoint("global", None, db, user)
        assert result == mm


@pytest.mark.asyncio
async def test_generate_mindmap_returns_422_when_no_pages():
    from app.routers.mindmap import generate_mindmap_endpoint, GenerateRequest
    from fastapi import HTTPException
    db = AsyncMock()
    user = MagicMock()
    body = GenerateRequest(scope_type="global", scope_id=None)
    with patch("app.routers.mindmap.mindmap_service.generate_mindmap",
               side_effect=ValueError("No wiki pages")):
        with pytest.raises(HTTPException) as exc:
            await generate_mindmap_endpoint(body, db, user)
        assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_mindmap_returns_404_when_missing():
    from app.routers.mindmap import delete_mindmap_endpoint
    from fastapi import HTTPException
    db = AsyncMock()
    user = MagicMock()
    mid = uuid.uuid4()
    with patch("app.routers.mindmap.mindmap_service.delete_mindmap", return_value=False):
        with pytest.raises(HTTPException) as exc:
            await delete_mindmap_endpoint(mid, db, user)
        assert exc.value.status_code == 404
