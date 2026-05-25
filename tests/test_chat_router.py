# tests/test_chat_router.py
import pytest
from unittest.mock import AsyncMock, MagicMock
import uuid


@pytest.mark.asyncio
async def test_session_belongs_to_user():
    """get_session returns None for wrong owner — router should 403."""
    from app.services.chat_service import get_session

    db = AsyncMock()
    # Simulate DB returning no row (wrong owner)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_session(db, uuid.uuid4(), uuid.uuid4())
    assert result is None
