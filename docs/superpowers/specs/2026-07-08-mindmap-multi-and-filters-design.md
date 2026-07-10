# Mindmap Multi-Per-Scope, Titles, and Filter Design

**Date:** 2026-07-08
**Status:** Approved

## Problem

1. Mindmap table enforces uniqueness by `(scope_type, scope_id)` — only one mindmap per scope. Users want to generate multiple mindmaps (e.g. wiki + source_docs, or different source doc sets) for the same scope.
2. The `title` column exists in DB (default `"Knowledge Base"`) but is never shown in the list UI. List only shows Scope, Source, Pages, Generated, Actions.
3. No filter controls on the mindmap list page. Hard to find mindmaps when the list grows.
4. Preview metadata shows `"1 pages"` (grammar: should be singular when count = 1).

## Changes

### 1. Remove Unique Constraints (DB + Service)

**Migration:** Drop both partial unique indexes:
```sql
DROP INDEX IF EXISTS uq_wiki_mindmaps_global;
DROP INDEX IF EXISTS uq_wiki_mindmaps_scoped;
```

**Service (`mindmap_service.py`):**
- `generate_mindmap()`: Remove upsert logic. Always insert a new `WikiMindmap` row.
- `get_mindmap()` by scope: Rename to `list_mindmaps()`, return `list[WikiMindmap]` ordered by `generated_at DESC`.
- `get_mindmap_by_id()`: Keep as-is.

**Router (`mindmap.py`):**
- `GET /api/mindmaps`: Add optional `scope_type` and `scope_id` query params for filtering. Returns list ordered by `generated_at DESC`.
- `POST /api/mindmap/generate`: No longer upserts — always creates new.
- `GET /api/mindmap?scope_type=...&scope_id=...&source_type=...`: Keep for backward compat, returns most recent match.

### 2. LLM-Generated Title

**Service (`mindmap_service.py`):**
- In the system prompt, add: `"Also provide a short descriptive title (3-8 words) for this mindmap. Return the title in a "title" field alongside the tree."`
- Parse `title` from LLM response. Store in existing `title` column.
- Fallback: `"Untitled Mindmap"` if LLM doesn't return one.

**Pydantic (`MindmapResponse`, `MindmapSummaryResponse`):** Already include `title` field.

### 3. Scope Filter Dropdown (Frontend)

**List page (`mindmap-list.tsx`):**
- Add `<Select>` dropdown above the table (same pattern as Wiki page filter).
- Options: "All Scopes" (default), "🌐 Global", departments (🏢 prefix), projects (📁 prefix).
- On change, pass `scope_type` + `scope_id` as query params to `GET /api/mindmaps`.
- Scopes loaded from `/api/departments` and `/api/projects` (reuse existing logic).

### 4. List Table Columns

| # | Column | Source | Notes |
|---|--------|--------|-------|
| 1 | Title | `mm.title` | **New.** Bold text, truncated with tooltip. |
| 2 | Scope | `getScopeLabel()` | Existing. Icon + name. |
| 3 | Source | `mm.source_type` | Existing. Badge pill. |
| 4 | Pages | `mm.wiki_page_count` | Existing. |
| 5 | Generated | `mm.generated_at` | Existing. Relative age. |
| 6 | Actions | — | Existing. View / Refresh / Delete. |

### 5. Preview Metadata Fix

**Viewer (`mindmap-viewer.tsx`):**
- Fix pluralization: `{count} page` when count = 1, `{count} pages` otherwise.
- Source type display already correct (shows "Source Docs" when `source_type === "source_docs"`).
- Deduplicate `formatAge` — extract to `frontend/src/lib/format-age.ts`.

## Files Changed

| File | Change |
|------|--------|
| `alembic/versions/xxx_drop_mindmap_unique.py` | New migration: drop unique indexes |
| `app/services/mindmap_service.py` | Remove upsert, add title parsing, rename get → list |
| `app/routers/mindmap.py` | Add scope params to list endpoint |
| `frontend/src/lib/format-age.ts` | New: shared `formatAge` utility |
| `frontend/src/components/mindmap/mindmap-list.tsx` | Add scope filter, title column, use shared formatAge |
| `frontend/src/components/mindmap/mindmap-viewer.tsx` | Fix pluralization, use shared formatAge |

## Testing

- Generate 2+ mindmaps for the same scope (different source types) — both should exist independently.
- Verify title appears in list and viewer.
- Filter by scope — only matching mindmaps shown.
- Verify `"1 page"` (singular) in preview metadata.
