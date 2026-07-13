# Chat Bubble for Mindmap Viewer

**Date:** 2026-07-13
**Status:** Draft

## Problem

Chat and mindmap interaction is not seamless. Today, clicking a mindmap node to ask about it navigates the user away from the mindmap entirely (`window.location.href = /knowledge/chat?input=...`). The user loses visual context of the mindmap and has to navigate back to continue exploring.

## Goal

Add a floating chat bubble on the mindmap viewer page that lets users discuss mindmap concepts without leaving the view. The bubble provides a mini chat experience with conversation history, auto-passes scope context to the AI, and prefills questions from node clicks.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Session persistence | Welcome screen with history + "New Chat" | Mini chat app feel, not one-shot |
| Scope context | Auto-pass from mindmap | AI knows which documents to reference |
| Node click behavior | Open bubble + prefill "Explain about X" | Seamless explore → ask flow |
| Layout | Floating panel, bottom-right, 400×500px | Standard chat widget, mindmap stays visible |
| Approach | Self-contained ChatBubble component | Clean separation, reuses presentational components |

## Component Architecture

```
ChatBubble (floating container + toggle button)
├── BubbleToggle (round chat icon, fixed bottom-right)
└── BubblePanel (expanded floating panel)
    ├── BubbleHeader (title + minimize + close + "Open full page" link)
    ├── BubbleWelcome (scrollable session list + "New Chat" button)
    ├── MessageList (reused from chat/message-list.tsx)
    └── ChatInput (reused from chat/chat-input.tsx)
```

### Props (passed from MindmapViewer)

| Prop | Type | Description |
|------|------|-------------|
| `scopeType` | `string` | "global" \| "department" \| "project" |
| `scopeId` | `string \| null` | UUID or null for global |
| `prefillInput` | `string \| null` | Set when a node is clicked, cleared after first submit |

### Internal State

| State | Type | Description |
|-------|------|-------------|
| `isOpen` | `boolean` | Panel visible or collapsed to icon |
| `sessions` | `ChatSession[]` | Conversation history for this scope |
| `activeSessionId` | `string \| null` | Currently viewed session |
| `messages` | `UIMessage[]` | Messages for active session |
| `input` | `string` | Current input text |

## API Changes

### Database: Add scope fields to `chat_sessions`

New Alembic migration `037` adds two nullable columns to `chat_sessions`:
- `scope_type` — `String(20)`, nullable. "global", "department", or "project".
- `scope_id` — `UUID`, nullable. Null for global scope.

Both nullable so existing sessions (created without scope) remain valid.

### `POST /api/chat/sessions`

Add optional fields to request body:

```json
{
  "scope_type": "department",
  "scope_id": "uuid-here"
}
```

Backend stores `scope_type` + `scope_id` on the `ChatSession` row. Passes these to `create_session()` in `chat_service.py`.

### `GET /api/chat/sessions?scope_type=X&scope_id=Y`

Add optional query params to filter sessions by scope. Returns only sessions matching that scope, most recent first. Without params, returns all sessions (backward compatible). Updates `list_sessions()` in `chat_service.py` to accept optional scope filter.

### `POST /api/chat/sessions/{session_id}/stream` — Scope-aware AI

When `session.scope_type` is set, pass it to `stream_agent_response()` so the AI's tool searches (search_wiki, list_wiki_pages, etc.) are filtered to that scope instead of the employee's default scope. This ensures the AI answers in the context of the mindmap's documents.

## Visual Design

### Collapsed State (Bubble Icon)

- Fixed position: bottom-right, 16px from edges
- 56px round button with `chat` icon (Material Symbols)
- `bg-primary text-primary-foreground` with subtle shadow
- Hover: slight scale-up effect
- z-index: 40 (above mindmap, below modals)

### Expanded State (Panel)

- 400px wide, 500px tall
- Fixed position: bottom-right, 16px from edges
- Rounded corners (`rounded-xl`), shadow (`shadow-lg`), border
- Header: "Chat" + minimize button (→ collapses to icon) + close button
- "Open in full page" link/icon in header → `/knowledge/chat?session={sessionId}`

### Welcome Screen (No Active Session)

- "New Chat" button at top
- Scrollable list of previous sessions (title + timestamp)
- Click a session → loads messages
- Empty state: "Start a conversation about this mindmap"

### Active Session Screen

- Message area (scrollable, reuses `MessageList`)
- Input at bottom (reuses `ChatInput`)
- Back arrow in header → returns to welcome screen

### Responsive (Mobile < 768px)

- Panel takes full width at bottom (drawer style)
- Mindmap visible above

## Interaction Flow

### Node Click → Chat

1. User clicks a mindmap node (no wiki page link)
2. `handleAskInChat(name)` fires in MindmapViewer
3. Sets `prefillInput = 'Explain about "name"'`
4. ChatBubble opens, input is pre-filled, cursor ready
5. User hits Enter → new session created with scope context → message streams
6. `prefillInput` is cleared so reopening doesn't re-prefill

### Manual Open

1. User clicks the floating chat bubble icon
2. Welcome screen shows with session history
3. User clicks "New Chat" or selects an existing session

### Session Lifecycle

- Create: `POST /api/chat/sessions` with scope params
- List: `GET /api/chat/sessions?scope_type=X&scope_id=Y`
- Load messages: `GET /api/chat/sessions/{id}/messages`
- Send/stream: `POST /api/chat/sessions/{id}/stream` (existing useChat hook)
- Delete: `DELETE /api/chat/sessions/{id}`

## Files to Create/Modify

### New Files

- `frontend/src/components/chat/chat-bubble.tsx` — Main ChatBubble component
- `frontend/src/components/chat/bubble-toggle.tsx` — The floating round button
- `frontend/src/components/chat/bubble-panel.tsx` — The expanded panel container
- `frontend/src/components/chat/bubble-welcome.tsx` — Welcome screen with session list

### Modified Files

- `frontend/src/components/mindmap/mindmap-viewer.tsx` — Add ChatBubble integration, pass scope props, manage prefillInput state
- `app/routers/chat.py` — Add scope_type/scope_id params to session creation and listing
- `app/database/models.py` — Ensure ChatSession model has scope fields (or add if missing)

### Reused Components (No Changes)

- `frontend/src/components/chat/message-list.tsx`
- `frontend/src/components/chat/chat-input.tsx`
- `frontend/src/components/chat/message-bubble.tsx`

## Out of Scope (v1)

- Live sync between bubble and full chat page (acceptable to sync on next load)
- Unread message badge on bubble icon
- MindMapPanel sidebar updates on chat page (addressed separately)
- Typing indicators
- File attachments in bubble (can add later)

## Testing

- Open bubble → welcome screen loads with sessions
- Click "New Chat" → empty message area, input focused
- Click a mindmap node → bubble opens with pre-filled input
- Send message → streams response, session appears in history
- Reload page → previous sessions still in history
- Scope filtering → only shows sessions for current mindmap's scope
- "Open in full page" → navigates to `/knowledge/chat?session={id}`
- Mobile → panel is full-width drawer at bottom
