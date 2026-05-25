# tests/test_chat_agent.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_tool_executor_unknown_tool():
    from app.services.chat_agent import execute_tool
    result = await execute_tool("nonexistent_tool", {}, employee=None, db=None)
    assert "unknown tool" in result.lower() or "error" in result.lower()
