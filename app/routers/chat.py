"""Chat router — session management and streaming endpoint."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.models import ChatMessage, ChatSession, Employee
from app.services.auth_service import get_current_user
from app.services.chat_service import (
    add_message,
    create_session,
    delete_session,
    get_messages,
    get_session,
    list_sessions,
    set_session_title,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

    model_config = {"from_attributes": True}


class CreateSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: Optional[str]
    tool_name: Optional[str]
    tool_call_id: Optional[str]
    tool_input: Optional[dict]
    created_at: str

    model_config = {"from_attributes": True}


class Attachment(BaseModel):
    type: str   # "wiki" | "source"
    slug: Optional[str] = None
    id: Optional[str] = None


class StreamRequest(BaseModel):
    # Direct format: { message: "...", attachments: [...] }
    message: Optional[str] = None
    # Vercel AI SDK format: { messages: [...], id: "...", attachments: [...] }
    messages: Optional[list[dict]] = None

    attachments: list[Attachment] = []

    @model_validator(mode="after")
    def resolve_message(self) -> "StreamRequest":
        if not self.message and self.messages:
            for msg in reversed(self.messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        self.message = content
                    elif isinstance(content, list):
                        texts = [p["text"] for p in content if p.get("type") == "text" and p.get("text")]
                        self.message = " ".join(texts)
                    break
        return self


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/chat/sessions", response_model=list[SessionResponse])
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    sessions = await list_sessions(db, user.id)
    await db.commit()

    if not sessions:
        return []

    count_stmt = (
        select(ChatMessage.session_id, func.count(ChatMessage.id).label("cnt"))
        .where(ChatMessage.session_id.in_([s.id for s in sessions]))
        .group_by(ChatMessage.session_id)
    )
    counts = {row.session_id: row.cnt for row in (await db.execute(count_stmt)).all()}

    return [
        SessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            message_count=counts.get(s.id, 0),
        )
        for s in sessions
    ]


@router.post("/chat/sessions", response_model=CreateSessionResponse)
async def create_chat_session(
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    session = await create_session(db, user.id)
    await db.commit()
    return CreateSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat(),
    )


@router.delete("/chat/sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    deleted = await delete_session(db, session_id, user.id)
    if not deleted:
        raise HTTPException(403, "Session not found or access denied")
    await db.commit()


@router.get("/chat/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_chat_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    session = await get_session(db, session_id, user.id)
    if not session:
        raise HTTPException(403, "Session not found or access denied")
    messages = await get_messages(db, session_id)
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            tool_name=m.tool_name,
            tool_call_id=m.tool_call_id,
            tool_input=m.tool_input,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/chat/sessions/{session_id}/stream")
async def stream_chat(
    session_id: uuid.UUID,
    req: StreamRequest,
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    if not req.message:
        raise HTTPException(422, "No user message found in request")

    session = await get_session(db, session_id, user.id)
    if not session:
        raise HTTPException(403, "Session not found or access denied")

    existing_messages = await get_messages(db, session_id)
    history = _messages_to_neutral(existing_messages)

    is_first_message = not existing_messages
    if is_first_message:
        await set_session_title(db, session, req.message)
        await db.commit()

    await add_message(db, session_id, role="user", content=req.message)
    await db.commit()

    attachments = [a.model_dump() for a in req.attachments]

    from app.database import async_session_factory
    from app.services.chat_agent import stream_agent_response

    async def generate():
        async with async_session_factory() as stream_db:
            from sqlalchemy.orm import selectinload
            emp = (await stream_db.execute(
                select(Employee).where(Employee.id == user.id)
                .options(selectinload(Employee.custom_role), selectinload(Employee.employee_departments))
            )).scalar_one_or_none()

            if emp is None:
                yield '3:"Employee not found"\n'
                return

            accumulated_assistant_text: list[str] = []
            tool_calls_made: list[dict] = []

            async for chunk in stream_agent_response(
                db=stream_db,
                employee=emp,
                history=history,
                user_message=req.message,
                attachments=attachments,
            ):
                if chunk.startswith("0:"):
                    try:
                        accumulated_assistant_text.append(json.loads(chunk[2:]))
                    except Exception:
                        pass
                elif chunk.startswith("9:"):
                    try:
                        tool_calls_made.append(json.loads(chunk[2:]))
                    except Exception:
                        pass
                yield chunk

            assistant_text = "".join(accumulated_assistant_text) or None
            await add_message(stream_db, session_id, role="assistant", content=assistant_text)
            for tc in tool_calls_made:
                await add_message(
                    stream_db, session_id,
                    role="tool",
                    tool_name=tc.get("toolName"),
                    tool_call_id=tc.get("toolCallId"),
                    tool_input=tc.get("args"),
                )
            await stream_db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


def _messages_to_neutral(messages: list) -> list[dict]:
    """Convert ChatMessage rows to neutral format for the agent loop."""
    result = []
    pending_assistant: dict | None = None
    pending_tool_calls: list = []

    for m in messages:
        if m.role == "user":
            if pending_assistant:
                result.append(pending_assistant)
                if pending_tool_calls:
                    from app.ai.agent_protocol import tool_results_message
                    result.append(tool_results_message(pending_tool_calls))
                pending_assistant = None
                pending_tool_calls = []
            result.append({"role": "user", "content": m.content or ""})

        elif m.role == "assistant":
            pending_assistant = {"role": "assistant", "content": m.content, "tool_calls": []}
            pending_tool_calls = []

        elif m.role == "tool":
            if pending_assistant is not None:
                from app.ai.agent_protocol import ToolCall as TC
                tc = TC(
                    id=m.tool_call_id or "",
                    name=m.tool_name or "",
                    arguments=m.tool_input or {},
                )
                pending_assistant["tool_calls"].append(tc)
                pending_tool_calls.append((m.tool_call_id or "", m.tool_name or "", m.content or ""))

    if pending_assistant:
        result.append(pending_assistant)
        if pending_tool_calls:
            from app.ai.agent_protocol import tool_results_message
            result.append(tool_results_message(pending_tool_calls))

    return result
