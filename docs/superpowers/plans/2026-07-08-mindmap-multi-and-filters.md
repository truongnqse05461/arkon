# Mindmap Multi-Per-Scope, Titles, and Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow multiple mindmaps per scope, add LLM-generated titles, add scope filter to list page, and fix metadata display bugs.

**Architecture:** Remove DB unique constraints to allow multiple mindmaps per scope. Add title generation to the LLM prompt. Add scope filter dropdown to the frontend list page. Extract shared utility. Fix pluralization in viewer.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic (PostgreSQL), Next.js, React

## Global Constraints

- Follow existing migration pattern: 3-digit zero-padded revision IDs (`"036"`)
- Follow existing router pattern: `Depends(get_db)`, `Depends(get_current_user)`
- Use existing `api<T>()` helper from `@/lib/api` for frontend API calls
- Use existing `material-symbols-outlined` for icons
- All new code must pass `rtk tsc` and `rtk lint`

---

### Task 1: Drop Unique Indexes (DB Migration)

**Files:**
- Create: `alembic/versions/036_drop_mindmap_unique_indexes.py`

**Interfaces:**
- Produces: DB table `wiki_mindmaps` no longer has `uq_wiki_mindmaps_global` or `uq_wiki_mindmaps_scoped` indexes

- [ ] **Step 1: Create migration file**

```python
"""Drop mindmap unique indexes to allow multiple per scope.

Revision ID: 036
Revises: 035
Create Date: 2026-07-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_wiki_mindmaps_global", table_name="wiki_mindmaps")
    op.drop_index("uq_wiki_mindmaps_scoped", table_name="wiki_mindmaps")


def downgrade() -> None:
    from sqlalchemy import text

    op.create_index(
        "uq_wiki_mindmaps_global",
        "wiki_mindmaps",
        ["scope_type"],
        unique=True,
        postgresql_where=text("scope_id IS NULL"),
    )
    op.create_index(
        "uq_wiki_mindmaps_scoped",
        "wiki_mindmaps",
        ["scope_type", "scope_id"],
        unique=True,
        postgresql_where=text("scope_id IS NOT NULL"),
    )
```

- [ ] **Step 2: Run migration**

Run: `cd D:/workspace/src/truongnqse05461/arkon && uv run alembic upgrade head`
Expected: `Running upgrade 035 -> 036`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/036_drop_mindmap_unique_indexes.py
git commit -m "feat(mindmap): drop unique indexes to allow multiple per scope"
```

---

### Task 2: Remove Upsert Logic + Add Scope Filter to List Endpoint (Backend)

**Files:**
- Modify: `app/services/mindmap_service.py:370-374` (list_mindmaps)
- Modify: `app/services/mindmap_service.py:471-498` (generate_mindmap upsert → insert-only)
- Modify: `app/routers/mindmap.py:65-71` (list_mindmaps_endpoint)
- Modify: `app/database/models.py:1385` (docstring update)

**Interfaces:**
- Consumes: `mindmap_service.list_mindmaps(db, scope_type?, scope_id?)` — new optional params
- Produces: `list_mindmaps()` always returns list; `generate_mindmap()` always inserts new row

- [ ] **Step 1: Update `list_mindmaps` to accept scope filter params**

In `app/services/mindmap_service.py`, replace lines 370-374:

```python
async def list_mindmaps(
    db: AsyncSession,
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
) -> list[WikiMindmap]:
    """List all mindmaps, optionally filtered by scope."""
    stmt = select(WikiMindmap)
    if scope_type:
        stmt = stmt.where(WikiMindmap.scope_type == scope_type)
    if scope_id:
        stmt = stmt.where(WikiMindmap.scope_id == scope_id)
    stmt = stmt.order_by(WikiMindmap.generated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

- [ ] **Step 2: Remove upsert logic from `generate_mindmap`**

In `app/services/mindmap_service.py`, replace lines 471-498 (the section starting with `title = str(tree.get("name", "Knowledge Base"))` through the end of the function):

```python
    title = str(tree.get("name", "Knowledge Base"))

    mindmap = WikiMindmap(
        scope_type=scope_type,
        scope_id=scope_id,
        title=title,
        tree_json=tree,
        wiki_page_count=page_count,
        source_type=source_type,
        source_ids=[str(sid) for sid in source_ids] if source_ids else None,
        instruction=instruction,
    )
    db.add(mindmap)
    await db.flush()
    await db.refresh(mindmap)
    return mindmap
```

- [ ] **Step 3: Add scope query params to list endpoint**

In `app/routers/mindmap.py`, replace lines 65-71:

```python
@router.get("/mindmaps", response_model=list[MindmapSummaryResponse])
async def list_mindmaps_endpoint(
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    mindmaps = await mindmap_service.list_mindmaps(db, scope_type=scope_type, scope_id=scope_id)
    return mindmaps
```

- [ ] **Step 4: Update model docstring**

In `app/database/models.py`, line 1385, change:
```python
"""Cached AI-generated MindMap tree for a wiki scope. Multiple rows per scope allowed."""
```

- [ ] **Step 5: Run backend tests**

Run: `cd D:/workspace/src/truongnqse05461/arkon && uv run pytest tests/test_mindmap.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add app/services/mindmap_service.py app/routers/mindmap.py app/database/models.py
git commit -m "feat(mindmap): remove upsert, add scope filter to list endpoint"
```

---

### Task 3: LLM-Generated Title (Backend)

**Files:**
- Modify: `app/services/mindmap_service.py:23-58` (system prompt + template)
- Modify: `app/services/mindmap_service.py:441-457` (JSON parsing)

**Interfaces:**
- Produces: `generate_mindmap()` stores LLM-generated title in `WikiMindmap.title` column
- Fallback: `"Untitled Mindmap"` if LLM doesn't return a title

- [ ] **Step 1: Update system prompt to request title**

In `app/services/mindmap_service.py`, replace `_SYSTEM` (line 23):

```python
_SYSTEM = (
    "You are a knowledge architect. Return ONLY valid JSON - no markdown, no explanation. "
    'Return an object with "title" (string, 3-8 words) and "tree" (the concept map object).'
)
```

- [ ] **Step 2: Update prompt template to instruct title generation**

In `app/services/mindmap_service.py`, replace `_PROMPT_TEMPLATE` (lines 25-58). Add the title instruction to the schema section:

```python
_PROMPT_TEMPLATE = """\
You are given wiki knowledge pages from an organization's knowledge base.
Create a learner-facing concept map that helps a user understand the actual
knowledge content.

Do not mirror wiki navigation or maintenance structure. Ignore administrative,
index, log, changelog, navigation, and metadata pages if they appear in the
input. Prefer concepts, processes, systems, entities, policies, decisions,
relationships, and dependencies.

Return valid JSON matching this schema exactly:
{{
  "title": "<short descriptive title - 3-8 words>",
  "tree": {{
    "name": "<root topic name - 2-4 words summarising the whole KB>",
    "children": [
      {{
        "name": "<subtopic>",
        "children": [
          {{"name": "<leaf>", "children": []}}
        ]
      }}
    ]
  }}
}}

Rules:
- "title" should be a concise, descriptive name for this mindmap.
- Depth should match the natural complexity - no fixed level limit.
- Every node must have a "children" key (empty array for leaves).
- Node names must be concise, user-facing concepts.
- Avoid node names like "Wiki Index", "Wiki Log", "Administrative Pages", "Metadata", or "Source List".
- Do not include duplicate sibling names.
- Return ONLY the JSON object, nothing else.

Wiki knowledge pages:
{pages}
"""
```

- [ ] **Step 3: Update JSON parsing to extract title and tree**

In `app/services/mindmap_service.py`, replace the JSON parsing block (lines 441-457). The LLM now returns `{"title": "...", "tree": {...}}` instead of just `{...}`:

```python
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"LLM returned unexpected JSON shape: {type(parsed).__name__}")

    # Extract title and tree from wrapped response
    title = str(parsed.get("title", "")).strip() or "Untitled Mindmap"
    tree = parsed.get("tree", parsed)
    if not isinstance(tree, dict) or "name" not in tree:
        # Fallback: maybe LLM returned tree directly without wrapper
        tree = parsed
        title = str(tree.get("name", "Untitled Mindmap"))
```

- [ ] **Step 4: Remove old title extraction**

In `app/services/mindmap_service.py`, remove line 471 (`title = str(tree.get("name", "Knowledge Base"))`) since title is now extracted above.

- [ ] **Step 5: Run backend tests**

Run: `cd D:/workspace/src/truongnqse05461/arkon && uv run pytest tests/test_mindmap.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add app/services/mindmap_service.py
git commit -m "feat(mindmap): generate descriptive titles via LLM prompt"
```

---

### Task 4: Extract Shared `formatAge` Utility (Frontend)

**Files:**
- Create: `frontend/src/lib/format-age.ts`
- Modify: `frontend/src/components/mindmap/mindmap-list.tsx:30-36` (remove local formatAge)
- Modify: `frontend/src/components/mindmap/mindmap-viewer.tsx:24-30` (remove local formatAge)

**Interfaces:**
- Produces: `formatAge(iso: string): string` in `@/lib/format-age`
- Consumed by: `mindmap-list.tsx`, `mindmap-viewer.tsx`

- [ ] **Step 1: Create shared utility**

Create `frontend/src/lib/format-age.ts`:

```typescript
export function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}
```

- [ ] **Step 2: Update mindmap-list.tsx to use shared utility**

In `frontend/src/components/mindmap/mindmap-list.tsx`:

1. Add import at line 2 (after existing imports):
```typescript
import { formatAge } from "@/lib/format-age";
```

2. Delete lines 30-36 (the local `formatAge` function).

- [ ] **Step 3: Update mindmap-viewer.tsx to use shared utility**

In `frontend/src/components/mindmap/mindmap-viewer.tsx`:

1. Add import at line 2 (after existing imports):
```typescript
import { formatAge } from "@/lib/format-age";
```

2. Delete lines 24-30 (the local `formatAge` function).

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd D:/workspace/src/truongnqse05461/arkon/frontend && rtk pnpm tsc`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/format-age.ts frontend/src/components/mindmap/mindmap-list.tsx frontend/src/components/mindmap/mindmap-viewer.tsx
git commit -m "refactor(frontend): extract shared formatAge utility"
```

---

### Task 5: Add Title Column + Scope Filter to Mindmap List (Frontend)

**Files:**
- Modify: `frontend/src/components/mindmap/mindmap-list.tsx` (full rewrite)

**Interfaces:**
- Consumes: `GET /api/mindmaps?scope_type=...&scope_id=...` (from Task 2)
- Consumes: `formatAge` from `@/lib/format-age` (from Task 4)
- Produces: List table with 6 columns: Title, Scope, Source, Pages, Generated, Actions
- Produces: Scope filter dropdown above table

- [ ] **Step 1: Rewrite mindmap-list.tsx**

Replace the full content of `frontend/src/components/mindmap/mindmap-list.tsx`:

```typescript
"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { formatAge } from "@/lib/format-age";

type MindmapSummary = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

type Scope = {
  type: string;
  id: string | null;
  name: string;
};

type MindmapListProps = {
  onView: (mindmap: MindmapSummary) => void;
  onRegenerate: (mindmap: MindmapSummary) => void;
  onDelete: (mindmap: MindmapSummary) => void;
  refreshKey: number;
  onDataLoaded: (hasItems: boolean) => void;
};

export function MindmapList({ onView, onRegenerate, onDelete, refreshKey, onDataLoaded }: MindmapListProps) {
  const [mindmaps, setMindmaps] = useState<MindmapSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [scopeFilter, setScopeFilter] = useState<string>("");

  // Load scope names for display
  useEffect(() => {
    async function loadScopes() {
      try {
        const [depts, projects] = await Promise.all([
          api<{ id: string; name: string }[]>("/api/departments"),
          api<{ id: string; name: string }[]>("/api/projects"),
        ]);
        const allScopes: Scope[] = [
          { type: "global", id: null, name: "Global" },
          ...depts.map((d) => ({ type: "department", id: d.id, name: d.name })),
          ...projects.map((p) => ({ type: "project", id: p.id, name: p.name })),
        ];
        setScopes(allScopes);
      } catch {
        setScopes([{ type: "global", id: null, name: "Global" }]);
      }
    }
    loadScopes();
  }, []);

  const fetchMindmaps = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (scopeFilter) {
        const [type, id] = scopeFilter.split(":");
        params.set("scope_type", type);
        if (id) params.set("scope_id", id);
      }
      const qs = params.toString();
      const data = await api<MindmapSummary[]>(`/api/mindmaps${qs ? `?${qs}` : ""}`);
      const items = Array.isArray(data) ? data : [];
      setMindmaps(items);
      onDataLoaded(items.length > 0);
    } catch {
      setMindmaps([]);
      onDataLoaded(false);
    } finally {
      setLoading(false);
    }
  }, [onDataLoaded, scopeFilter]);

  useEffect(() => {
    fetchMindmaps();
  }, [fetchMindmaps, refreshKey]);

  // Derive scope options from loaded scopes
  const scopeOptions = useMemo(() => {
    return scopes.map((s) => ({
      key: s.type === "global" ? "global" : `${s.type}:${s.id}`,
      label: s.type === "global" ? "🌐 Global" : `${s.type === "department" ? "🏢" : "📁"} ${s.name}`,
    }));
  }, [scopes]);

  const getScopeLabel = (scopeType: string, scopeId: string | null): string => {
    const scope = scopes.find((s) => s.type === scopeType && (s.id ?? null) === (scopeId ?? null));
    if (scope) {
      const icon = scopeType === "global" ? "🌐" : scopeType === "department" ? "🏢" : "📁";
      return `${icon} ${scope.name}`;
    }
    if (scopeType === "global") return "🌐 Global";
    if (scopeType === "department") return "🏢 Department";
    if (scopeType === "project") return "📁 Project";
    return scopeType;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="material-symbols-outlined text-3xl text-muted-foreground animate-spin">
          progress_activity
        </span>
      </div>
    );
  }

  if (mindmaps.length === 0 && !scopeFilter) {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* Scope filter */}
      {scopeOptions.length > 1 && (
        <div className="flex items-center gap-2">
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:border-ring"
            title="Filter by scope"
          >
            <option value="">All scopes</option>
            {scopeOptions.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Table */}
      {mindmaps.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">No mindmaps found for this scope.</p>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/50 border-b border-border">
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Title</th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Scope</th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Source</th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Pages</th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Generated</th>
                <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {mindmaps.map((mm) => (
                <tr key={mm.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    <span className="font-medium truncate block max-w-[200px]" title={mm.title}>
                      {mm.title}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-muted-foreground">{getScopeLabel(mm.scope_type, mm.scope_id)}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted">
                      {mm.source_type === "source_docs" ? "Source Doc" : "Wiki"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{mm.wiki_page_count}</td>
                  <td className="px-4 py-3 text-muted-foreground">{formatAge(mm.generated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => onView(mm)}
                        title="View"
                        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px]">visibility</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onRegenerate(mm)}
                        title="Regenerate"
                        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px]">refresh</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(mm)}
                        title="Delete"
                        className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px]">delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd D:/workspace/src/truongnqse05461/arkon/frontend && rtk pnpm tsc`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/mindmap/mindmap-list.tsx
git commit -m "feat(mindmap): add title column and scope filter to list page"
```

---

### Task 6: Fix Preview Metadata Pluralization (Frontend)

**Files:**
- Modify: `frontend/src/components/mindmap/mindmap-viewer.tsx:56-58`

**Interfaces:**
- Consumes: `formatAge` from `@/lib/format-age` (from Task 4)
- Produces: Correct pluralization: `"1 page"` vs `"2 pages"`

- [ ] **Step 1: Fix pluralization in viewer**

In `frontend/src/components/mindmap/mindmap-viewer.tsx`, replace lines 56-58:

```tsx
          <p className="text-xs text-muted-foreground">
            {mindmap.wiki_page_count} {mindmap.wiki_page_count === 1 ? "page" : "pages"} · {mindmap.source_type === "source_docs" ? "Source Docs" : "Wiki"} · {formatAge(mindmap.generated_at)}
          </p>
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd D:/workspace/src/truongnqse05461/arkon/frontend && rtk pnpm tsc`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/mindmap/mindmap-viewer.tsx
git commit -m "fix(mindmap): correct pluralization in preview metadata"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd D:/workspace/src/truongnqse05461/arkon && uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend type check**

Run: `cd D:/workspace/src/truongnqse05461/arkon/frontend && rtk pnpm tsc`
Expected: No errors

- [ ] **Step 3: Run frontend lint**

Run: `cd D:/workspace/src/truongnqse05461/arkon/frontend && rtk pnpm lint`
Expected: No errors

- [ ] **Step 4: Push all changes**

```bash
cd D:/workspace/src/truongnqse05461/arkon && git push
```
