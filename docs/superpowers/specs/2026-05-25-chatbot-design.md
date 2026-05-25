# Chatbot Page — Design Spec
Date: 2026-05-25

## Overview

Add an agentic chatbot page inside the **Org Knowledge** navigation section. The chatbot answers employee questions by querying the scoped knowledge base in real time using existing Tier 1 MCP tools. Conversation history is persisted in the database. The UI streams responses with full tool call visibility using the Vercel AI SDK.

---

## Scope

| Capability | Included |
|---|---|
| Read-only KB queries (wiki, sources) | Yes |
| Write actions (propose/edit wiki) | No |
| DB-persisted conversation history | Yes |
| Real-time SSE streaming | Yes |
| Tool call visibility in UI | Yes |
| Markdown response rendering | Yes |
| Doc/wiki attachment to input | Yes |
| Permission-scoped responses | Yes |

---

## Architecture

### Agent Framework

**Native tool-use loop** via LiteLLM (already installed). The backend manages the entire agentic loop — no LangChain or LangGraph dependency.

Loop per turn:
1. Load session history from DB
2. Build scoped system prompt (department, workspace, knowledge type scope from JWT)
3. If attachments present → inject pinned context, call `read_wiki_page`/`get_source` upfront
4. `LiteLLM.completion(stream=True, tools=[...])` → stream text tokens immediately
5. On tool call detection → execute tool → stream tool result → continue
6. Repeat until no more tool calls (max 8 steps per turn)
7. Persist all new messages to DB

### Streaming Protocol

FastAPI `StreamingResponse` with `text/event-stream`. Output conforms to the **Vercel AI SDK data stream protocol**:

```
0:"token"                          ← text chunk (streamed as generated)
9:{toolCallId, toolName, args}     ← tool call start
b:{toolCallId, result}             ← tool result
d:{finishReason, usage}            ← stream complete
3:"error message"                  ← error (closes stream)
```

The frontend `useChat` hook consumes this natively.

### Permission Scoping

Identical to the existing REST pattern. JWT resolves to:
- `department_id` — for `own_dept`-scoped wiki/source access
- `project_ids` — for workspace-scoped pages
- `allowed_knowledge_types` — KT filter on every tool call

The same `apply_scope_filter` and `_scope_filter_for_identity` helpers used by the MCP server are reused directly. No new permission surface.

---

## Tools Available to the Chatbot

All 10 existing Tier 1 MCP tools — read-only, no new tools added:

| Tool | Purpose |
|---|---|
| `search_wiki` | Semantic search over scoped wiki pages |
| `read_wiki_page` | Read a specific wiki page by slug |
| `read_wiki_index` | Browse full wiki catalog |
| `list_wiki_pages` | Paginated wiki list with filters |
| `list_sources` | List raw source documents |
| `get_source` | Metadata for a specific source |
| `get_source_outline` | Heading-based outline of a source |
| `get_source_pages` | Raw text of specific source pages |
| `list_knowledge_types` | List accessible knowledge type categories |
| `get_knowledge_type_docs` | Documents for a specific knowledge type |

---

## Data Model

Two new tables (new Alembic migration):

### `chat_sessions`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `employee_id` | `UUID FK → employees.id` | owner, cascade delete |
| `title` | `VARCHAR(200)` | auto-set from first user message (60 chars); fallback: "(New conversation)" |
| `created_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | bumped on each new message |

### `chat_messages`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | |
| `session_id` | `UUID FK → chat_sessions.id` | cascade delete |
| `role` | `VARCHAR(20)` | `user` / `assistant` / `tool` |
| `content` | `TEXT` | text content or tool result text |
| `tool_name` | `VARCHAR(100)` | nullable — for `role=tool` |
| `tool_call_id` | `VARCHAR(100)` | nullable — links tool result to tool call |
| `tool_input` | `JSONB` | nullable — args passed to tool |
| `created_at` | `TIMESTAMPTZ` | |

Attachments are **not persisted** — they are per-request inputs reflected in the system prompt, not stored entities.

---

## API Contract

New router: `app/routers/chat.py`. All endpoints require JWT auth and are scoped to `current_user`.

### `GET /api/chat/sessions`
Returns the current user's sessions ordered by `updated_at DESC`. Max 100. Empty sessions (no messages) are pruned on this call.

Response: `[{id, title, created_at, updated_at, message_count}]`

### `POST /api/chat/sessions`
Creates a new empty session. Title defaults to `"(New conversation)"` until first message.

Response: `{id, title, created_at}`

### `DELETE /api/chat/sessions/{id}`
Deletes session and all its messages. Returns `403` if not owner.

### `GET /api/chat/sessions/{id}/messages`
Returns full message history for restoring on session load.

Response: `[{id, role, content, tool_name, tool_call_id, tool_input, created_at}]`

### `POST /api/chat/sessions/{id}/stream`

```json
{
  "message": "What is the leave policy?",
  "attachments": [
    {"type": "wiki", "slug": "hr/leave-policy"},
    {"type": "source", "id": "uuid"}
  ]
}
```

Returns `StreamingResponse` (`text/event-stream`) in Vercel AI SDK data stream format. Returns `403` if session doesn't belong to `current_user`. Auto-sets session title on first message.

---

## Frontend Architecture

**New route:** `frontend/src/app/(portal)/knowledge/chat/page.tsx`

**New dependency:** `ai` (Vercel AI SDK) — only new package.

### Component Structure

```
frontend/src/components/chat/
├── chat-page.tsx          ← root; owns session list state, selected session
├── session-panel.tsx      ← collapsible left panel, sessions grouped by date
├── session-item.tsx       ← session row: title + timestamp + delete button
├── chat-area.tsx          ← useChat hook owner; renders message list + input
├── message-list.tsx       ← auto-scroll message history
├── message-bubble.tsx     ← user bubble (dark) / assistant bubble (light)
├── tool-call-row.tsx      ← collapsible row: tool name + monospace args + result
├── chat-input.tsx         ← textarea + attach 📎 + send ↑ buttons
└── attachment-picker.tsx  ← popover: wiki page search + source doc search tabs
```

### `useChat` Wiring (`chat-area.tsx`)

```ts
const { messages, input, handleSubmit, isLoading, setInput } = useChat({
  api: `${API_BASE}/api/chat/sessions/${sessionId}/stream`,
  headers: { Authorization: `Bearer ${token}` },
  body: { attachments },
  initialMessages: loadedHistory,
  onFinish: () => refetchSessions(),
})
```

### Tool Call Rendering

Vercel AI SDK exposes tool calls as `ToolCallPart` and results as `ToolResultPart` inside `message.parts`. `message-bubble.tsx` maps over parts:
- `text` → `<ReactMarkdown>` with `remark-gfm` (already installed)
- `tool-call` → `<ToolCallRow>` (collapsible, monospace args)
- `tool-result` → appended inside the same `<ToolCallRow>`

### Attachment Picker

The 📎 button opens a popover with two tabs:
- **Wiki pages** — searches `GET /api/wiki/pages?search=...` (scoped). `GET /api/wiki/pages` needs a `search` query param added (title/slug text filter) — minor addition to the existing endpoint.
- **Documents** — searches `GET /api/sources?search=...` (scoped, already supported).

Selected items appear as dismissible chips above the input. Attachments are cleared from state after each message is sent (they apply to one turn only). The picker only surfaces items the user already has access to — no extra permission layer.

### Sidebar Entry

Added to the `org-knowledge` section in `sidebar.tsx`:

```ts
{ label: "Chat", href: "/knowledge/chat", icon: "chat",
  requiredPermissions: ["wiki:read:own_dept", "wiki:read:all"] }
```

---

## UI Layout

**Split-panel page** at `/knowledge/chat`:

- **Left panel (220px, collapsible):** session list grouped by date (Today / Yesterday / Older). Header has New Chat `+` and collapse `◀` buttons. Collapsed state shows a 36px stub with `▶` and `+` icons only.
- **Right panel (flex):** chat header (session title + delete), scrollable message list, input area.
- **Message list:** user messages right-aligned (dark bubble), assistant messages left-aligned (light bubble) with tool call rows above the text.
- **Input area:** attachment chips row (when populated) + textarea + 📎 attach + ↑ send. Scope disclaimer footer: "Answers are scoped to your department and workspace access."

---

## Error Handling

| Scenario | Handling |
|---|---|
| LLM API error mid-stream | Write `3:"..."` error event; `useChat.onError` shows toast |
| Max 8 tool calls reached | LLM instructed to answer with available context |
| Out-of-scope KB results | Existing `search_wiki` hint surfaced naturally in assistant response |
| Session not found / wrong owner | `403` → frontend clears selection, shows empty state |
| Empty session (no messages sent) | Pruned on next `GET /api/chat/sessions` call |
| Attachment not accessible | Picker only shows accessible items; no server-side bypass possible |

---

## Files to Create

### Backend
- `app/routers/chat.py` — REST + streaming endpoints
- `app/services/chat_service.py` — session/message CRUD
- `app/services/chat_agent.py` — agentic loop, tool definitions, SSE encoder
- `alembic/versions/<next>_add_chat_tables.py` — migration for `chat_sessions` + `chat_messages` (number assigned by Alembic at generation time)

### Frontend
- `frontend/src/app/(portal)/knowledge/chat/page.tsx`
- `frontend/src/components/chat/chat-page.tsx`
- `frontend/src/components/chat/session-panel.tsx`
- `frontend/src/components/chat/session-item.tsx`
- `frontend/src/components/chat/chat-area.tsx`
- `frontend/src/components/chat/message-list.tsx`
- `frontend/src/components/chat/message-bubble.tsx`
- `frontend/src/components/chat/tool-call-row.tsx`
- `frontend/src/components/chat/chat-input.tsx`
- `frontend/src/components/chat/attachment-picker.tsx`

### Modified
- `app/main.py` — register `chat` router
- `app/routers/wiki.py` — add `?search=` query param to `GET /api/wiki/pages`
- `frontend/src/components/layout/sidebar.tsx` — add Chat nav item
- `frontend/package.json` — add `ai` dependency
