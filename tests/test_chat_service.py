# tests/test_chat_service.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_session(employee_id=None):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.employee_id = employee_id or uuid.uuid4()
    s.title = "(New conversation)"
    s.messages = []
    return s


@pytest.mark.asyncio
async def test_create_session():
    from app.services.chat_service import create_session
    db = AsyncMock()
    employee_id = uuid.uuid4()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    with patch("app.services.chat_service.ChatSession") as MockSession:
        mock_instance = MagicMock()
        MockSession.return_value = mock_instance
        result = await create_session(db, employee_id)
        db.add.assert_called_once_with(mock_instance)
        db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_set_title_truncates_at_60_chars():
    from app.services.chat_service import _make_title
    long_msg = "a" * 100
    result = _make_title(long_msg)
    assert len(result) <= 60


@pytest.mark.asyncio
async def test_set_title_short_message():
    from app.services.chat_service import _make_title
    result = _make_title("What is the leave policy?")
    assert result == "What is the leave policy?"
