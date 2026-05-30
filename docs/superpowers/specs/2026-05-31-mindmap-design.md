# Interactive MindMap — Design Spec

**Date:** 2026-05-31  
**Status:** Approved  
**Scope:** Chat page right panel — MindMap only (Studio panel future work)

---

## Overview

Add an interactive MindMap panel to the right side of the Chat page (`/knowledge/chat`). The MindMap is AI-generated from wiki pages, cached per scope, and rendered as a collapsible/expandable horizontal tree — matching the NotebookLM Studio MindMap pattern.

---

## User-Facing Behaviour

### Panel States

| State | Description |
|---|---|
| **Collapsed** | Thin strip on the right edge with a vertical "MINDMAP" label and `◀` toggle |
| **Open** | ~35% width side panel showing the tree alongside the chat |
| **Full screen** | `position:fixed inset-0 z-50` overlay with title, page count, regenerate + close buttons |

Transitions: `◀ / ▶` collapses/opens. `⤢` enters full screen. `⤡` exits full screen. `✕` closes from full screen.

### Scope Picker

The panel header contains a dropdown populated from existing `/api/departments` and `/api/projects` endpoints. Each option shows its wiki page count. Options:

- 🌐 **Global** — all wiki pages in the org
- 🏢 **Department** entries (e.g. Engineering, Marketing)
- 📁 **Project** entries

Switching scope immediately checks the cache. On cache miss → empty state with "Generate MindMap" button. Controls are disabled while generating.

### MindMap Generation (on demand)

1. User selects a scope and clicks **"Generate MindMap"**
2. Panel shows spinner + *"Analysing N wiki pages…"*
3. On success → tree renders, cache status shown in header (*"Cached · X pages · Generated N days ago"*)
4. **Regenerate** button (full-screen header only) → deletes cache then re-generates

### Tree Interaction

- Horizontal left-to-right layout (root on left, branches to right)
- Pill-shaped rectangular nodes, curved bracket-style edges
- `›` button on each node to expand/collapse children
- Scroll-wheel zoom + drag to pan
- `+` / `−` buttons for zoom (bottom-right corner)

---

## Architecture

### Backend

#### New DB Table: `wiki_mindmaps`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scope_type` | `ScopeType` enum | `"global"` / `"project"` / `"department"` (matches existing enum) |
| `scope_id` | UUID (nullable) | null for global |
| `title` | string | Root node label |
| `tree_json` | JSONB | Full tree in react-d3-tree format |
| `wiki_page_count` | int | Pages used for generation |
| `generated_at` | datetime | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

Unique constraint: `(scope_type, scope_id)`. Re-generating upserts the existing row.

#### Tree JSON Format

```json
{
  "name": "Knowledge Base",
  "children": [
    {
      "name": "Architecture",
      "children": [
        { "name": "RAG System", "children": [] },
        { "name": "Vector DB", "children": [] }
      ]
    },
    { "name": "Fallback System", "children": [] }
  ]
}
```

Depth is determined by the LLM based on content complexity — no hard cap.

#### New API Endpoints (`/api/mindmap`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/mindmap?scope_type=&scope_id=` | JWT | Return cached mindmap or 404 |
| `POST` | `/api/mindmap/generate` | JWT | Generate, store, return tree |
| `DELETE` | `/api/mindmap/{id}` | JWT | Delete cache to force regeneration |

#### Generation Logic (`app/services/mindmap_service.py`)

1. Fetch wiki pages for the requested scope from DB
2. **Adaptive payload strategy:**
   - `< 150 pages` → send `title + first 300 chars of content` per page
   - `≥ 150 pages` → send titles only
3. Call LiteLLM with prompt:
   > *"You are given a list of wiki page titles [and excerpts]. Group them into a meaningful topic hierarchy that reflects the knowledge structure. Return valid JSON matching `{name: string, children: [{name, children}]}`. Depth should match the natural complexity — do not impose a fixed level limit."*
4. Parse and validate JSON response
5. Upsert into `wiki_mindmaps` table
6. Return the saved record

#### New Files (backend)

| File | Purpose |
|---|---|
| `alembic/versions/029_add_wiki_mindmaps.py` | Migration |
| `app/database/models.py` | Add `WikiMindmap` ORM model |
| `app/services/mindmap_service.py` | Generation logic |
| `app/routers/mindmap.py` | 3 endpoints |
| `app/main.py` | Register router |

### Frontend

#### New Files

| File | Purpose |
|---|---|
| `frontend/src/components/chat/mindmap-panel.tsx` | Panel shell — states, header, scope picker, empty/loading/error states |
| `frontend/src/components/chat/mindmap-tree.tsx` | `react-d3-tree` renderer — custom node, edges, zoom |

#### Modified Files

| File | Change |
|---|---|
| `frontend/src/components/chat/chat-area.tsx` | Add `<MindMapPanel>` to layout |
| `frontend/package.json` | Add `react-d3-tree` dependency |

#### `mindmap-panel.tsx` responsibilities

- State machine: `collapsed` → `open` → `fullscreen`
- On mount: `GET /api/mindmap?scope_type=global&scope_id=` (default global)
- Scope change: re-fetch cache for new scope
- Delegates tree rendering to `<MindMapTree tree={treeJson} />`
- Full-screen uses `position:fixed inset-0 z-50` (no React portal needed)

#### `mindmap-tree.tsx` responsibilities

- Wraps `react-d3-tree` with:
  - `orientation="horizontal"`
  - `pathFunc="step"` (curved bracket edges)
  - Custom `renderCustomNodeElement` — pill shape via `<foreignObject>`, `›` expand button
  - `zoom`, `translate` state for pan/zoom controls
  - `+` / `−` buttons wired to `zoom` state

---

## Data Flow Summary

```
User clicks "Generate MindMap"
  → POST /api/mindmap/generate { scope_type, scope_id }
    → Fetch wiki pages for scope
    → Adaptive payload (titles+excerpts OR titles-only)
    → LiteLLM → JSON tree
    → Upsert wiki_mindmaps
  ← { id, tree_json, wiki_page_count, generated_at }
  → MindMapPanel stores tree_json in state
  → MindMapTree renders react-d3-tree
```

---

## Out of Scope (this iteration)

- Studio panel with multiple tools (summary, flashcards, etc.)
- Clicking a node to navigate to the wiki page
- Partial/incremental map updates from chat context
- Export as image/PDF
- Scoped MindMap on chat session (scope picker in panel covers this)
