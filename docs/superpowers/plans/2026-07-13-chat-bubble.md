# Chat Bubble Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floating chat bubble on the mindmap viewer page so users can discuss mindmap concepts without leaving the view.

**Architecture:** Self-contained `ChatBubble` component with its own session management, rendered as a fixed-position floating panel. Reuses existing `MessageList` and `ChatInput` components. Backend gains scope fields on `chat_sessions` for context-aware AI responses.

**Tech Stack:** Next.js App Router, React, Vercel AI SDK (`useChat`), FastAPI, SQLAlchemy, Alembic, PostgreSQL

## Global Constraints

- Follow existing Material Symbols icon pattern used throughout the app
- Use `api()` from `@/lib/api` for all API calls (not raw fetch)
- Use `useChat` from `ai/react` for streaming (same pattern as `chat-area.tsx`)
- All new frontend files use `"use client"` directive
- Tailwind CSS for styling; use existing design tokens (`bg-primary`, `text-muted-foreground`, etc.)
- Python tests use `pytest` + `unittest.mock` (same pattern as `tests/test_chat_service.py`)
- Alembic migration ID: `037` (zero-padded, sequential after `036`)

---

### Task 1: Add scope fields to ChatSession model + migration

**Files:**
- Create: `alembic/versions/037_add_chat_session_scope.py`
- Modify: `app/database/models.py` (ChatSession class around line 1327)

**Interfaces:**
- Produces: `ChatSession.scope_type: Mapped[Optional[str]]` and `ChatSession.scope_id: Mapped[Optional[uuid.UUID]]`

- [ ] **Step 1: Add columns to ChatSession model**

In `app/database/models.py`, find the `ChatSession` class (line ~1327). Add two new columns after the `updated_at` field:

```python
scope_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
```

Ensure `Optional` is imported from `typing` and `String` is from `sqlalchemy`.

- [ ] **Step 2: Create Alembic migration**

Create `alembic/versions/037_add_chat_session_scope.py`:

```python
"""Add scope fields to chat_sessions

Revision ID: 037
Revises: 036
Create Date: 2026-07-13 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("scope_type", sa.String(20), nullable=True))
    op.add_column("chat_sessions", sa.Column("scope_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "scope_id")
    op.drop_column("chat_sessions", "scope_type")
```

- [ ] **Step 3: Verify migration applies**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m alembic upgrade head`
Expected: migration applies successfully.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/037_add_chat_session_scope.py app/database/models.py
git commit -m "feat(chat): add scope_type and scope_id columns to chat_sessions"
```

---

### Task 2: Update chat_service.py to support scope

**Files:**
- Modify: `app/services/chat_service.py`
- Modify: `tests/test_chat_service.py`

**Interfaces:**
- Produces: `create_session(db, employee_id, scope_type=None, scope_id=None) -> ChatSession`
- Produces: `list_sessions(db, employee_id, limit=100, scope_type=None, scope_id=None) -> list[ChatSession]`

- [ ] **Step 1: Add test for create_session with scope**

In `tests/test_chat_service.py`, add:

```python
@pytest.mark.asyncio
async def test_create_session_with_scope():
    from app.services.chat_service import create_session
    db = AsyncMock()
    employee_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    with patch("app.services.chat_service.ChatSession") as MockSession:
        mock_instance = MagicMock()
        MockSession.return_value = mock_instance
        result = await create_session(db, employee_id, scope_type="department", scope_id=scope_id)
        MockSession.assert_called_once_with(
            employee_id=employee_id, scope_type="department", scope_id=scope_id
        )
        db.add.assert_called_once_with(mock_instance)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_service.py::test_create_session_with_scope -v`
Expected: FAIL — `create_session` doesn't accept scope params yet.

- [ ] **Step 3: Update create_session to accept scope**

In `app/services/chat_service.py`, update `create_session`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_service.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Add test for list_sessions with scope filter**

In `tests/test_chat_service.py`, add:

```python
@pytest.mark.asyncio
async def test_list_sessions_filters_by_scope():
    from app.services.chat_service import list_sessions
    db = AsyncMock()
    employee_id = uuid.uuid4()
    # Mock the delete (pruning) and select queries
    db.execute = AsyncMock()
    # First call returns empty for pruning, second returns sessions
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result
    result = await list_sessions(db, employee_id, scope_type="department", scope_id=uuid.uuid4())
    assert isinstance(result, list)
```

- [ ] **Step 6: Update list_sessions to accept scope filter**

In `app/services/chat_service.py`, update `list_sessions`:

```python
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
```

- [ ] **Step 7: Run all chat service tests**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_service.py -v`
Expected: ALL PASS.

- [ ] **Step 8: Commit**

```bash
git add app/services/chat_service.py tests/test_chat_service.py
git commit -m "feat(chat): add scope params to create_session and list_sessions"
```

---

### Task 3: Update chat router endpoints for scope

**Files:**
- Modify: `app/routers/chat.py`
- Modify: `tests/test_chat_router.py`

**Interfaces:**
- Consumes: `create_session(db, employee_id, scope_type, scope_id)` from Task 2
- Consumes: `list_sessions(db, employee_id, limit, scope_type, scope_id)` from Task 2
- Produces: `POST /api/chat/sessions` accepts `scope_type` + `scope_id` in body
- Produces: `GET /api/chat/sessions` accepts `scope_type` + `scope_id` as query params

- [ ] **Step 1: Add test for create session with scope**

In `tests/test_chat_router.py`, add a test (check existing patterns in the file first):

```python
@pytest.mark.asyncio
async def test_create_session_with_scope():
    from app.routers.chat import create_chat_session
    # Verify the endpoint accepts scope params
    # This is an integration-level check; adjust based on existing test patterns
```

Check the existing test patterns in `test_chat_router.py` first and follow the same style.

- [ ] **Step 2: Update POST /api/chat/sessions endpoint**

In `app/routers/chat.py`, add a request body schema and update the create endpoint:

```python
class CreateSessionRequest(BaseModel):
    scope_type: Optional[str] = None
    scope_id: Optional[uuid.UUID] = None
```

Update the endpoint:

```python
@router.post("/chat/sessions", response_model=CreateSessionResponse)
async def create_chat_session(
    req: Optional[CreateSessionRequest] = None,
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    scope_type = req.scope_type if req else None
    scope_id = req.scope_id if req else None
    session = await create_session(db, user.id, scope_type=scope_type, scope_id=scope_id)
    await db.commit()
    return CreateSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat(),
    )
```

- [ ] **Step 3: Update GET /api/chat/sessions endpoint**

```python
@router.get("/chat/sessions", response_model=list[SessionResponse])
async def list_chat_sessions(
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    sessions = await list_sessions(db, user.id, scope_type=scope_type, scope_id=scope_id)
    # ... rest stays the same
```

- [ ] **Step 4: Run existing chat router tests**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_router.py -v`
Expected: ALL PASS (backward compatible — no scope = returns all).

- [ ] **Step 5: Commit**

```bash
git add app/routers/chat.py tests/test_chat_router.py
git commit -m "feat(chat): add scope query params to session list and create endpoints"
```

---

### Task 4: Make chat agent scope-aware

**Files:**
- Modify: `app/services/chat_agent.py` (stream_agent_response function, line ~515)
- Modify: `app/routers/chat.py` (stream_chat endpoint, line ~174)

**Interfaces:**
- Consumes: `ChatSession.scope_type`, `ChatSession.scope_id` from Task 1
- Produces: `stream_agent_response(..., scope_override: dict | None = None)` — when provided, uses this scope instead of employee's default

- [ ] **Step 1: Update stream_agent_response signature**

In `app/services/chat_agent.py`, update the function signature and scope resolution:

```python
async def stream_agent_response(
    db: AsyncSession,
    employee: Employee,
    history: list[dict],
    user_message: str,
    attachments: list[dict],
    max_steps: int = 8,
    scope_override: dict | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run the agentic loop and yield Vercel AI SDK data stream protocol lines.
    History is the existing session messages in neutral format (role/content dicts).
    If scope_override is provided, use it instead of deriving from employee.
    """
    registry = ProviderRegistry(db)
    llm = await registry.get_llm()

    scope = scope_override if scope_override else await _get_scope(db, employee)
    # ... rest stays the same
```

- [ ] **Step 2: Build scope override in stream_chat endpoint**

In `app/routers/chat.py`, in the `stream_chat` endpoint's `generate()` function, build a scope override from the session:

```python
async def generate():
    async with async_session_factory() as stream_db:
        from sqlalchemy.orm import selectinload
        emp = (await stream_db.execute(
            select(Employee).where(Employee.id == user.id)
            .options(selectinload(Employee.custom_role), selectinload(Employee.department))
        )).scalar_one_or_none()

        if emp is None:
            yield '3:"Employee not found"\n'
            return

        # Build scope override from session if set
        scope_override = None
        if session.scope_type:
            from app.services.chat_agent import _get_scope
            base_scope = await _get_scope(stream_db, emp)
            if session.scope_type == "global":
                base_scope["department_id"] = None
                base_scope["project_ids"] = []
            elif session.scope_type == "department" and session.scope_id:
                base_scope["department_id"] = str(session.scope_id)
                base_scope["project_ids"] = []
            elif session.scope_type == "project" and session.scope_id:
                base_scope["department_id"] = None
                base_scope["project_ids"] = [str(session.scope_id)]
            scope_override = base_scope

        # ... pass scope_override to stream_agent_response
        async for chunk in stream_agent_response(
            db=stream_db,
            employee=emp,
            history=history,
            user_message=req.message,
            attachments=attachments,
            scope_override=scope_override,
        ):
```

- [ ] **Step 3: Run chat scope tests**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_scope.py -v`
Expected: existing tests still pass (scope_override is optional, defaults to None).

- [ ] **Step 4: Run all chat tests**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_service.py tests/test_chat_router.py tests/test_chat_agent.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/chat_agent.py app/routers/chat.py
git commit -m "feat(chat): pass session scope to agent for context-aware responses"
```

---

### Task 5: Create BubbleToggle component

**Files:**
- Create: `frontend/src/components/chat/bubble-toggle.tsx`

**Interfaces:**
- Produces: `BubbleToggle({ onClick, isOpen })` — floating round button, bottom-right

- [ ] **Step 1: Create BubbleToggle component**

Create `frontend/src/components/chat/bubble-toggle.tsx`:

```tsx
"use client";

type BubbleToggleProps = {
  onClick: () => void;
  isOpen: boolean;
};

export function BubbleToggle({ onClick, isOpen }: BubbleToggleProps) {
  if (isOpen) return null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="fixed bottom-4 right-4 z-40 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl hover:scale-105 transition-all flex items-center justify-center"
      title="Open chat"
    >
      <span
        className="material-symbols-outlined text-[24px]"
        style={{ fontVariationSettings: "'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24" }}
      >
        chat
      </span>
    </button>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /d/workspace/src/truongnqse05461/arkon/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/bubble-toggle.tsx
git commit -m "feat(chat): add BubbleToggle floating button component"
```

---

### Task 6: Create BubbleWelcome component

**Files:**
- Create: `frontend/src/components/chat/bubble-welcome.tsx`

**Interfaces:**
- Consumes: `ChatSession` type from `session-panel.tsx` (reuse: `{ id, title, created_at, updated_at, message_count }`)
- Produces: `BubbleWelcome({ sessions, onSelectSession, onNewSession, onDeleteSession })` — scrollable session list + "New Chat" button

- [ ] **Step 1: Create BubbleWelcome component**

Create `frontend/src/components/chat/bubble-welcome.tsx`:

```tsx
"use client";

import type { ChatSession } from "./session-panel";

type BubbleWelcomeProps = {
  sessions: ChatSession[];
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
};

function relativeTime(isoString: string): string {
  const now = Date.now();
  const ts = new Date(isoString).getTime();
  const diff = Math.floor((now - ts) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(isoString).toLocaleDateString();
}

export function BubbleWelcome({
  sessions,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}: BubbleWelcomeProps) {
  return (
    <div className="flex flex-col h-full">
      {/* New Chat button */}
      <div className="px-4 pt-4 pb-2 shrink-0">
        <button
          type="button"
          onClick={onNewSession}
          className="w-full px-4 py-2.5 bg-foreground text-background rounded-lg text-sm font-medium hover:bg-foreground/90 transition-colors flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground/50 text-center py-8">
            Start a conversation about this mindmap.
          </p>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="group flex items-start gap-1 rounded-md px-2 py-1.5 cursor-pointer hover:bg-black/[0.03] transition-colors"
                onClick={() => onSelectSession(s.id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] truncate text-muted-foreground">
                    {s.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground/60">
                    {relativeTime(s.updated_at)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(s.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-muted-foreground/40 hover:text-destructive transition-all shrink-0 mt-0.5"
                >
                  <span
                    className="material-symbols-outlined text-[13px]"
                    style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 14" }}
                  >
                    close
                  </span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /d/workspace/src/truongnqse05461/arkon/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/bubble-welcome.tsx
git commit -m "feat(chat): add BubbleWelcome session list component"
```

---

### Task 7: Create ChatBubble main component

**Files:**
- Create: `frontend/src/components/chat/chat-bubble.tsx`

**Interfaces:**
- Consumes: `BubbleToggle` from Task 5, `BubbleWelcome` from Task 6
- Consumes: `MessageList` from `chat/message-list.tsx`, `ChatInput` from `chat/chat-input.tsx`
- Consumes: `ChatSession` type from `session-panel.tsx`
- Consumes: `api()` from `@/lib/api`, `useChat` from `ai/react`
- Produces: `ChatBubble({ scopeType, scopeId, prefillInput, onPrefillConsumed })`

- [ ] **Step 1: Create ChatBubble component**

Create `frontend/src/components/chat/chat-bubble.tsx`:

```tsx
"use client";

import { useState, useCallback, useEffect } from "react";
import { useChat } from "ai/react";
import type { UIMessage, Message } from "ai";
import { api } from "@/lib/api";
import { BubbleToggle } from "./bubble-toggle";
import { BubbleWelcome } from "./bubble-welcome";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import type { ChatSession } from "./session-panel";
import type { Attachment } from "./attachment-picker";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5055";

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("arkon_token") ?? "";
}

type ChatBubbleProps = {
  scopeType: string;
  scopeId: string | null;
  prefillInput: string | null;
  onPrefillConsumed: () => void;
};

export function ChatBubble({
  scopeType,
  scopeId,
  prefillInput,
  onPrefillConsumed,
}: ChatBubbleProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [initialMessages, setInitialMessages] = useState<UIMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState("");
  const [attachments] = useState<Attachment[]>([]);

  // Fetch sessions when bubble opens
  const fetchSessions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("scope_type", scopeType);
      if (scopeId) params.set("scope_id", scopeId);
      const data = await api<ChatSession[]>(`/api/chat/sessions?${params.toString()}`);
      setSessions(Array.isArray(data) ? data : []);
    } catch {
      setSessions([]);
    }
  }, [scopeType, scopeId]);

  useEffect(() => {
    if (isOpen) fetchSessions();
  }, [isOpen, fetchSessions]);

  // Handle prefill: open bubble and set input
  useEffect(() => {
    if (prefillInput) {
      setIsOpen(true);
      setInput(prefillInput);
      onPrefillConsumed();
    }
  }, [prefillInput, onPrefillConsumed]);

  // useChat hook for active session
  const { messages, handleSubmit, isLoading } = useChat({
    api: activeSessionId
      ? `${API_BASE}/api/chat/sessions/${activeSessionId}/stream`
      : `${API_BASE}/api/chat/sessions/placeholder/stream`,
    headers: { Authorization: `Bearer ${getToken()}` },
    body: { attachments: attachments.map(({ label: _label, ...rest }) => rest) },
    initialMessages: initialMessages as unknown as Message[],
    onFinish: () => {
      fetchSessions();
    },
  });

  const handleNewSession = useCallback(async () => {
    try {
      const s = await api<ChatSession>("/api/chat/sessions", {
        method: "POST",
        body: { scope_type: scopeType, scope_id: scopeId },
      });
      setSessions((prev) => [s, ...prev]);
      setActiveSessionId(s.id);
      setInitialMessages([]);
      setInput("");
    } catch {
      // ignore
    }
  }, [scopeType, scopeId]);

  const handleSelectSession = useCallback(async (id: string) => {
    setActiveSessionId(id);
    setLoadingMessages(true);
    try {
      const msgs = await api<{
        id: string;
        role: string;
        content: string | null;
        created_at: string;
      }[]>(`/api/chat/sessions/${id}/messages`);
      const uiMessages: UIMessage[] = msgs
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content ?? "",
          parts: [{ type: "text" as const, text: m.content ?? "" }],
          createdAt: new Date(m.created_at),
        }));
      setInitialMessages(uiMessages);
    } catch {
      setInitialMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await api(`/api/chat/sessions/${id}`, { method: "DELETE" });
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeSessionId === id) {
          setActiveSessionId(null);
          setInitialMessages([]);
        }
      } catch {
        // ignore
      }
    },
    [activeSessionId]
  );

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return;
    // If no active session, create one first
    if (!activeSessionId) {
      handleNewSession().then(() => {
        // handleSubmit will be called after session is created
        // The next render will have activeSessionId set
      });
      return;
    }
    handleSubmit({});
  }, [input, isLoading, activeSessionId, handleSubmit, handleNewSession]);

  // Auto-submit after session creation when prefill triggered new session
  useEffect(() => {
    if (activeSessionId && input.trim() && !isLoading && messages.length === 0) {
      handleSubmit({});
    }
  }, [activeSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBack = useCallback(() => {
    setActiveSessionId(null);
    setInitialMessages([]);
    setInput("");
  }, []);

  return (
    <>
      <BubbleToggle onClick={() => setIsOpen(true)} isOpen={isOpen} />

      {isOpen && (
        <div className="fixed bottom-4 right-4 z-40 w-[400px] h-[500px] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-2rem)] bg-background border border-border rounded-xl shadow-lg flex flex-col overflow-hidden md:w-[400px] md:h-[500px]">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border flex items-center gap-2 shrink-0">
            {activeSessionId && (
              <button
                type="button"
                onClick={handleBack}
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="Back to conversations"
              >
                <span className="material-symbols-outlined text-[20px]">arrow_back</span>
              </button>
            )}
            <span className="text-sm font-semibold flex-1 truncate">
              {activeSessionId
                ? sessions.find((s) => s.id === activeSessionId)?.title ?? "Chat"
                : "Chat"}
            </span>
            {activeSessionId && (
              <a
                href={`/knowledge/chat?session=${activeSessionId}`}
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="Open in full page"
              >
                <span className="material-symbols-outlined text-[18px]">open_in_new</span>
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setActiveSessionId(null);
                setInitialMessages([]);
                setInput("");
              }}
              className="text-muted-foreground hover:text-foreground transition-colors"
              title="Close"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>

          {/* Body */}
          {!activeSessionId ? (
            <BubbleWelcome
              sessions={sessions}
              onSelectSession={handleSelectSession}
              onNewSession={handleNewSession}
              onDeleteSession={handleDeleteSession}
            />
          ) : loadingMessages ? (
            <div className="flex-1 flex items-center justify-center">
              <span className="material-symbols-outlined text-2xl text-muted-foreground animate-spin">
                progress_activity
              </span>
            </div>
          ) : (
            <>
              <MessageList
                messages={messages as UIMessage[]}
                isLoading={isLoading}
                onCitationClick={() => {}}
              />
              <ChatInput
                input={input}
                onInputChange={setInput}
                onSubmit={handleSend}
                attachments={attachments}
                onAddAttachment={() => {}}
                onRemoveAttachment={() => {}}
                isLoading={isLoading}
              />
            </>
          )}
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /d/workspace/src/truongnqse05461/arkon/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/chat-bubble.tsx
git commit -m "feat(chat): add ChatBubble main component with session management"
```

---

### Task 8: Integrate ChatBubble into MindmapViewer

**Files:**
- Modify: `frontend/src/components/mindmap/mindmap-viewer.tsx`

**Interfaces:**
- Consumes: `ChatBubble` from Task 7
- Consumes: `MindmapViewer` already has `mindmap.scope_type`, `mindmap.scope_id`, `mindmap.title`

- [ ] **Step 1: Add ChatBubble to MindmapViewer**

In `frontend/src/components/mindmap/mindmap-viewer.tsx`, add:

```tsx
import { useState, useCallback } from "react";
import { ChatBubble } from "@/components/chat/chat-bubble";
```

Add state and update the component:

```tsx
export function MindmapViewer({ mindmap, onBack, onRegenerate, onDelete }: MindmapViewerProps) {
  const [prefillInput, setPrefillInput] = useState<string | null>(null);

  const handleAskInChat = useCallback((name: string) => {
    setPrefillInput(`Explain about "${name}"`);
  }, []);

  // ... existing handleAskInChat is replaced by the above

  return (
    <div className="flex flex-col h-full">
      {/* ... existing header and MindMapTree ... */}

      <ChatBubble
        scopeType={mindmap.scope_type}
        scopeId={mindmap.scope_id}
        prefillInput={prefillInput}
        onPrefillConsumed={() => setPrefillInput(null)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Remove old window.location.href navigation**

The old `handleAskInChat` did `window.location.href = /knowledge/chat?input=...`. Replace it entirely with the new `setPrefillInput` approach. The `handleNodeClick` callback stays the same but calls the new `handleAskInChat`.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /d/workspace/src/truongnqse05461/arkon/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Run frontend build**

Run: `cd /d/workspace/src/truongnqse05461/arkon/frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/mindmap/mindmap-viewer.tsx
git commit -m "feat(mindmap): integrate ChatBubble for in-page chat"
```

---

### Task 9: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_chat_service.py tests/test_chat_router.py tests/test_chat_agent.py tests/test_chat_scope.py -v`
Expected: ALL PASS.

- [ ] **Step 2: Run frontend type check**

Run: `cd /d/workspace/src/truongnqse05461/arkon/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Run mindmap tests**

Run: `cd /d/workspace/src/truongnqse05461/arkon && python -m pytest tests/test_mindmap_service.py -v`
Expected: ALL PASS.

- [ ] **Step 4: Manual smoke test checklist**

1. Open mindmap viewer → floating chat bubble icon visible (bottom-right)
2. Click bubble icon → panel opens with "New Chat" button
3. Click "New Chat" → session created, input focused
4. Type a message → streams response
5. Click a mindmap node (no wiki link) → bubble opens with pre-filled "Explain about X"
6. Send pre-filled message → streams response
7. Close and reopen bubble → previous session in history
8. "Open in full page" link → navigates to `/knowledge/chat?session={id}`
