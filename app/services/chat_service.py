"""Chat Service — session and message CRUD."""

import uuid
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChatMessage, ChatSession


def _make_title(text: str) -> str:
    return text.strip()[:60]


async def create_session(
    db: AsyncSession,
    employee_id: uuid.UUID,
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
) -> ChatSession:
    session = ChatSession(
        employee_id=employee_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def list_sessions(
    db: AsyncSession,
    employee_id: uuid.UUID,
    limit: int = 100,
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
) -> list[ChatSession]:
    # Prune empty sessions (no messages) before listing.
    empty_ids = (
        select(ChatSession.id)
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.employee_id == employee_id)
        .group_by(ChatSession.id)
        .having(func.count(ChatMessage.id) == 0)
    )
    await db.execute(delete(ChatSession).where(ChatSession.id.in_(empty_ids)))

    stmt = (
        select(ChatSession)
        .where(ChatSession.employee_id == employee_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    if scope_type is not None:
        stmt = stmt.where(ChatSession.scope_type == scope_type)
    if scope_id is not None:
        stmt = stmt.where(ChatSession.scope_id == scope_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession, session_id: uuid.UUID, employee_id: uuid.UUID
) -> Optional[ChatSession]:
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.employee_id == employee_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_session(
    db: AsyncSession, session_id: uuid.UUID, employee_id: uuid.UUID
) -> bool:
    session = await get_session(db, session_id, employee_id)
    if not session:
        return False
    await db.delete(session)
    return True


async def get_messages(
    db: AsyncSession, session_id: uuid.UUID
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def add_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    tool_input: Optional[dict] = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_input=tool_input,
    )
    db.add(msg)
    await db.flush()
    return msg


async def set_session_title(
    db: AsyncSession, session: ChatSession, first_user_message: str
) -> None:
    session.title = _make_title(first_user_message)
    await db.flush()
