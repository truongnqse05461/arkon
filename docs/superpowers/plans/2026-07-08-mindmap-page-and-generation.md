# Mindmap Page & Generation Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Mindmap management page with multi-source generation (Wiki + Source Documents), LLM-generated node summaries, and Chat ↔ Mindmap navigation.

**Architecture:** Extend existing `WikiMindmap` model with `source_type`, `source_ids`, `instruction` fields. New `/mindmap` route with list view, generation dialog, and full-screen viewer. Backend gains source doc support and LLM summary generation. Chat page reads prefilled input from URL params.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Next.js (App Router), React, Tailwind CSS, react-d3-tree

## Global Constraints

- Python 3.11+, FastAPI async patterns
- Next.js App Router with `"use client"` components
- Tailwind CSS for styling, Material Symbols for icons
- Existing `api()` helper from `@/lib/api` for frontend API calls
- Existing `MindMapTree` component reused as-is
- Backward compatible: existing mindmaps work without migration data

---

## File Structure

### Backend (Python)

| File | Responsibility |
|------|---------------|
| `alembic/versions/031_extend_wiki_mindmaps.py` | DB migration: add `source_type`, `source_ids`, `instruction` columns |
| `app/database/models.py` | Add 3 new fields to `WikiMindmap` model |
| `app/routers/mindmap.py` | Add `GET /api/mindmaps`, update `GenerateRequest` schema |
| `app/services/mindmap_service.py` | Add source doc support, LLM summary generation, list function |

### Frontend (TypeScript/React)

| File | Responsibility |
|------|---------------|
| `frontend/src/app/(portal)/mindmap/page.tsx` | Mindmap page route with list view |
| `frontend/src/components/mindmap/mindmap-list.tsx` | Table component showing all mindmaps |
| `frontend/src/components/mindmap/generation-dialog.tsx` | Modal for scope/source/instruction selection |
| `frontend/src/components/mindmap/mindmap-viewer.tsx` | Full-screen mindmap viewer |
| `frontend/src/components/chat/chat-area.tsx` | Read prefilled input from URL (minor edit) |

---

## Task 1: Database Migration — Extend WikiMindmap

**Files:**
- Create: `alembic/versions/031_extend_wiki_mindmaps.py`
- Modify: `app/database/models.py:1384-1400`

**Interfaces:**
- Produces: `WikiMindmap.source_type`, `WikiMindmap.source_ids`, `WikiMindmap.instruction` columns

- [ ] **Step 1: Write the migration file**

```python
# alembic/versions/031_extend_wiki_mindmaps.py
"""Extend wiki_mindmaps with source_type, source_ids, instruction

Revision ID: 031
Revises: 030
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wiki_mindmaps",
        sa.Column("source_type", sa.String(20), nullable=False, server_default="wiki"),
    )
    op.add_column(
        "wiki_mindmaps",
        sa.Column("source_ids", JSONB, nullable=True),
    )
    op.add_column(
        "wiki_mindmaps",
        sa.Column("instruction", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wiki_mindmaps", "instruction")
    op.drop_column("wiki_mindmaps", "source_ids")
    op.drop_column("wiki_mindmaps", "source_type")
```

- [ ] **Step 2: Update the WikiMindmap model**

In `app/database/models.py`, find the `WikiMindmap` class and add after the `wiki_page_count` field:

```python
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="wiki",
        comment="'wiki' or 'source_docs'",
    )
    source_ids: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment="UUIDs of source documents. NULL for wiki mode.",
    )
    instruction: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="User instruction appended to system prompt.",
    )
```

- [ ] **Step 3: Run migration**

```bash
cd D:\workspace\src\truongnqse05461\arkon
alembic upgrade head
```

Expected: Migration applies successfully, 3 new columns added to `wiki_mindmaps`.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/031_extend_wiki_mindmaps.py app/database/models.py
git commit -m "feat(mindmap): extend WikiMindmap with source_type, source_ids, instruction"
```

---

## Task 2: Backend — List Mindmaps API

**Files:**
- Modify: `app/routers/mindmap.py`
- Modify: `app/services/mindmap_service.py`

**Interfaces:**
- Produces: `GET /api/mindmaps` → `list[MindmapSummaryResponse]`
- Produces: `list_mindmaps(db, user)` → `list[WikiMindmap]`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_mindmap_service.py

@pytest.mark.asyncio
async def test_list_mindmaps_returns_all():
    from app.services.mindmap_service import list_mindmaps
    db = make_db()
    mindmaps = [MagicMock(), MagicMock()]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mindmaps
    db.execute = AsyncMock(return_value=mock_result)

    result = await list_mindmaps(db)
    assert len(result) == 2
    db.execute.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:\workspace\src\truongnqse05461\arkon
uv run pytest tests/test_mindmap_service.py::test_list_mindmaps_returns_all -v
```

Expected: FAIL with `ImportError: cannot import name 'list_mindmaps'`

- [ ] **Step 3: Implement list_mindmaps in service**

Add to `app/services/mindmap_service.py`:

```python
async def list_mindmaps(db: AsyncSession) -> list[WikiMindmap]:
    """List all mindmaps ordered by most recent first."""
    stmt = select(WikiMindmap).order_by(WikiMindmap.generated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_mindmap_service.py::test_list_mindmaps_returns_all -v
```

Expected: PASS

- [ ] **Step 5: Add MindmapSummaryResponse schema and GET endpoint**

In `app/routers/mindmap.py`, add the response model and endpoint:

```python
class MindmapSummaryResponse(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_id: Optional[uuid.UUID]
    title: str
    source_type: str
    wiki_page_count: int
    generated_at: datetime

    model_config = {"from_attributes": True}


@router.get("/mindmaps", response_model=list[MindmapSummaryResponse])
async def list_mindmaps_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    mindmaps = await mindmap_service.list_mindmaps(db)
    return mindmaps
```

- [ ] **Step 6: Commit**

```bash
git add app/routers/mindmap.py app/services/mindmap_service.py tests/test_mindmap_service.py
git commit -m "feat(mindmap): add GET /api/mindmaps list endpoint"
```

---

## Task 3: Backend — Enhanced Generation Request Schema

**Files:**
- Modify: `app/routers/mindmap.py`
- Modify: `app/services/mindmap_service.py`

**Interfaces:**
- Modifies: `GenerateRequest` schema with `source_type`, `source_ids`, `instruction`
- Modifies: `generate_mindmap()` signature to accept new parameters

- [ ] **Step 1: Update GenerateRequest schema**

In `app/routers/mindmap.py`, update the `GenerateRequest` class:

```python
class GenerateRequest(BaseModel):
    scope_type: Literal["global", "department", "project"]
    scope_id: Optional[uuid.UUID] = None
    source_type: Literal["wiki", "source_docs"] = "wiki"
    source_ids: Optional[list[uuid.UUID]] = None
    instruction: Optional[str] = None

    @validator("instruction")
    def validate_instruction(cls, v):
        if v is not None and len(v) > 500:
            raise ValueError("Instruction must be 500 characters or less")
        return v

    @validator("source_ids")
    def validate_source_ids(cls, v, values):
        if values.get("source_type") == "source_docs" and not v:
            raise ValueError("source_ids required when source_type is 'source_docs'")
        return v
```

- [ ] **Step 2: Update generate_mindmap_endpoint**

In `app/routers/mindmap.py`, update the endpoint to pass new params:

```python
@router.post("/mindmap/generate", response_model=MindmapResponse)
async def generate_mindmap_endpoint(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    try:
        mindmap = await mindmap_service.generate_mindmap(
            db,
            body.scope_type,
            body.scope_id,
            source_type=body.source_type,
            source_ids=body.source_ids,
            instruction=body.instruction,
        )
        await db.commit()
        return mindmap
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

- [ ] **Step 3: Update generate_mindmap signature**

In `app/services/mindmap_service.py`, update the function signature:

```python
async def generate_mindmap(
    db: AsyncSession,
    scope_type: str,
    scope_id: Optional[uuid.UUID],
    source_type: str = "wiki",
    source_ids: Optional[list[uuid.UUID]] = None,
    instruction: Optional[str] = None,
) -> WikiMindmap:
```

- [ ] **Step 4: Add import for validator**

At the top of `app/routers/mindmap.py`, add:

```python
from pydantic import BaseModel, validator
```

- [ ] **Step 5: Commit**

```bash
git add app/routers/mindmap.py app/services/mindmap_service.py
git commit -m "feat(mindmap): extend GenerateRequest with source_type, source_ids, instruction"
```

---

## Task 4: Backend — Source Document Support

**Files:**
- Modify: `app/services/mindmap_service.py`

**Interfaces:**
- Produces: `_build_source_doc_payload(sources)` → `str`
- Produces: `_enrich_tree_nodes_from_sources(tree, sources)` → `dict`
- Modifies: `generate_mindmap()` to handle `source_type="source_docs"`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_mindmap_service.py

def make_source(title: str, full_text: str = "content " * 100, source_type: str = "file"):
    src = MagicMock()
    src.id = uuid.uuid4()
    src.title = title
    src.full_text = full_text
    src.source_type = source_type
    return src


def test_build_source_doc_payload_basic():
    from app.services.mindmap_service import _build_source_doc_payload
    sources = [make_source("Doc A", "Content A " * 100), make_source("Doc B", "Content B " * 100)]
    result = _build_source_doc_payload(sources)
    assert "Doc A" in result
    assert "Doc B" in result
    assert "Content A" in result


def test_build_source_doc_payload_truncates_large_text():
    from app.services.mindmap_service import _build_source_doc_payload
    sources = [make_source("Big Doc", "x" * 20000)]
    result = _build_source_doc_payload(sources)
    # Should be truncated to 8000 chars per source
    assert len(result) < 10000


def test_enrich_tree_nodes_from_sources():
    from app.services.mindmap_service import _enrich_tree_nodes_from_sources
    sources = [make_source("Architecture Guide", "arch content")]
    tree = {"name": "KB", "children": [{"name": "Architecture Guide", "children": []}]}
    result = _enrich_tree_nodes_from_sources(tree, sources)
    child = result["children"][0]
    assert child["page_slug"].startswith("source:")
    assert child["page_type"] == "document"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_mindmap_service.py::test_build_source_doc_payload_basic tests/test_mindmap_service.py::test_build_source_doc_payload_truncates_large_text tests/test_mindmap_service.py::test_enrich_tree_nodes_from_sources -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement source doc functions**

Add to `app/services/mindmap_service.py`:

```python
_SOURCE_DOC_TEXT_LIMIT = 8000


def _build_source_doc_payload(sources: list) -> str:
    """Build payload from source documents."""
    lines = []
    for src in sources:
        title = _first_text(getattr(src, "title", None), "Untitled")
        text = _first_text(getattr(src, "full_text", None), "")
        if text:
            text = text[:_SOURCE_DOC_TEXT_LIMIT]
        lines.append(f"- {title}: {text}")
    return "\n".join(lines)


def _enrich_tree_nodes_from_sources(tree: dict, sources: list) -> dict:
    """Enrich nodes with source document metadata."""
    lookup: dict[str, list[dict]] = {}
    for src in sources:
        title = _first_text(getattr(src, "title", None))
        if not title:
            continue
        key = _normalize_name(title)
        entry = {
            "id": str(getattr(src, "id", "")),
            "title": title,
            "source_type": getattr(src, "source_type", "file"),
        }
        lookup.setdefault(key, []).append(entry)

    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = f"source:{match['id']}"
            node["page_type"] = "document"
            node["summary"] = match["title"][:_SUMMARY_MAX_LEN]
        for child in node.get("children", []):
            enrich_node(child)
        return node

    return enrich_node(tree)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_mindmap_service.py::test_build_source_doc_payload_basic tests/test_mindmap_service.py::test_build_source_doc_payload_truncates_large_text tests/test_mindmap_service.py::test_enrich_tree_nodes_from_sources -v
```

Expected: PASS

- [ ] **Step 5: Update generate_mindmap to handle source docs**

In `app/services/mindmap_service.py`, update `generate_mindmap`:

```python
async def generate_mindmap(
    db: AsyncSession,
    scope_type: str,
    scope_id: Optional[uuid.UUID],
    source_type: str = "wiki",
    source_ids: Optional[list[uuid.UUID]] = None,
    instruction: Optional[str] = None,
) -> WikiMindmap:
    if source_type == "source_docs" and source_ids:
        # Fetch source documents
        stmt = select(Source).where(Source.id.in_(source_ids))
        result = await db.execute(stmt)
        sources = list(result.scalars().all())
        if not sources:
            raise ValueError("No source documents found for the given IDs.")
        payload = _build_source_doc_payload(sources)
        page_count = len(sources)
    else:
        # Wiki mode (existing behavior)
        stmt = select(WikiPage).where(
            WikiPage.scope_type == scope_type,
            WikiPage.scope_id == scope_id,
            WikiPage.orphaned.is_(False),
        )
        result = await db.execute(stmt)
        pages = _filter_pages_for_mindmap(list(result.scalars().all()))
        if not pages:
            raise ValueError("No wiki pages found for this scope.")
        payload = _build_payload(pages)
        page_count = len(pages)

    # Build prompt with optional instruction
    prompt = _PROMPT_TEMPLATE.format(pages=payload)
    if instruction:
        prompt += f"\n\nAdditional instructions: {instruction}"

    registry = ProviderRegistry(db)
    llm = await registry.get_llm()
    raw = await llm.generate(prompt, system=_SYSTEM, temperature=0.3, max_tokens=4096)

    try:
        tree = json.loads(raw.strip())
    except json.JSONDecodeError:
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            tree = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc

    if not isinstance(tree, dict):
        raise ValueError(f"LLM returned unexpected JSON shape: {type(tree).__name__}")

    # Enrich nodes based on source type
    if source_type == "source_docs" and source_ids:
        tree = _enrich_tree_nodes_from_sources(tree, sources)
    else:
        tree = _enrich_tree_nodes(tree, pages)

    title = str(tree.get("name", "Knowledge Base"))

    existing = await get_mindmap(db, scope_type, scope_id)
    if existing:
        existing.title = title
        existing.tree_json = tree
        existing.wiki_page_count = page_count
        existing.source_type = source_type
        existing.source_ids = [str(sid) for sid in source_ids] if source_ids else None
        existing.instruction = instruction
        await db.flush()
        await db.refresh(existing)
        return existing

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

- [ ] **Step 6: Add Source import**

At the top of `app/services/mindmap_service.py`, add `Source` to the imports:

```python
from app.database.models import Source, WikiMindmap, WikiPage
```

- [ ] **Step 7: Run existing tests to verify no regression**

```bash
uv run pytest tests/test_mindmap_service.py -v
```

Expected: All existing tests still PASS

- [ ] **Step 8: Commit**

```bash
git add app/services/mindmap_service.py tests/test_mindmap_service.py
git commit -m "feat(mindmap): add source document support for generation"
```

---

## Task 5: Backend — LLM Node Summary Generation

**Files:**
- Modify: `app/services/mindmap_service.py`

**Interfaces:**
- Produces: `_generate_node_summaries(nodes, llm)` → `dict[str, str]`
- Produces: `_collect_unmatched_nodes(tree)` → `list[str]`
- Produces: `_apply_summaries(tree, summaries)` → `dict`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_mindmap_service.py

def test_collect_unmatched_nodes():
    from app.services.mindmap_service import _collect_unmatched_nodes
    tree = {
        "name": "KB",
        "children": [
            {"name": "Auth", "page_slug": "auth", "children": []},
            {"name": "Unmatched Topic", "children": []},
            {"name": "Another", "summary": "has summary", "children": []},
        ],
    }
    result = _collect_unmatched_nodes(tree)
    assert "Unmatched Topic" in result
    assert "Auth" not in result
    assert "Another" not in result


def test_apply_summaries():
    from app.services.mindmap_service import _apply_summaries
    tree = {
        "name": "KB",
        "children": [
            {"name": "Auth", "children": []},
            {"name": "Topic B", "children": []},
        ],
    }
    summaries = {"Topic B": "This is about topic B"}
    result = _apply_summaries(tree, summaries)
    assert result["children"][1]["summary"] == "This is about topic B"
    assert "summary" not in result["children"][0]


@pytest.mark.asyncio
async def test_generate_node_summaries_batches():
    from app.services.mindmap_service import _generate_node_summaries
    nodes = [f"Node {i}" for i in range(20)]
    mock_llm = AsyncMock()
    # Return valid JSON for each batch
    mock_llm.generate = AsyncMock(return_value=json.dumps([
        {"name": f"Node {i}", "summary": f"Summary {i}"} for i in range(15)
    ]))
    result = await _generate_node_summaries(nodes[:15], mock_llm)
    assert len(result) == 15
    assert result["Node 0"] == "Summary 0"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_mindmap_service.py::test_collect_unmatched_nodes tests/test_mindmap_service.py::test_apply_summaries tests/test_mindmap_service.py::test_generate_node_summaries_batches -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement summary functions**

Add to `app/services/mindmap_service.py`:

```python
_SUMMARY_BATCH_SIZE = 15
_SUMMARY_MAX_CHARS = 150

_SUMMARY_PROMPT = """\
Given the following node names from a knowledge map, generate a concise 
1-2 sentence summary for each node. The summary should explain what this 
concept/topic means in the context of the knowledge base.

Node names:
{node_names}

Return JSON array:
[
  {{"name": "Node Name", "summary": "Brief explanation of the concept."}},
  ...
]

Rules:
- Summary must be max 150 characters
- Use plain language, no jargon
- If the node name is unclear, make a reasonable assumption based on context
"""


def _collect_unmatched_nodes(tree: dict) -> list[str]:
    """Collect node names that have no page_slug and no summary."""
    unmatched = []

    def walk(node: dict):
        if not node.get("page_slug") and not node.get("summary"):
            name = node.get("name", "")
            if name:
                unmatched.append(name)
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return unmatched


def _apply_summaries(tree: dict, summaries: dict[str, str]) -> dict:
    """Apply generated summaries to tree nodes."""

    def walk(node: dict):
        name = node.get("name", "")
        if name in summaries and not node.get("summary"):
            node["summary"] = summaries[name][:_SUMMARY_MAX_CHARS]
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return tree


async def _generate_node_summaries(
    nodes: list[str],
    llm,
) -> dict[str, str]:
    """Generate summaries for unmatched nodes in batches."""
    summaries: dict[str, str] = {}

    for i in range(0, len(nodes), _SUMMARY_BATCH_SIZE):
        batch = nodes[i : i + _SUMMARY_BATCH_SIZE]
        prompt = _SUMMARY_PROMPT.format(node_names="\n".join(batch))

        try:
            result = await llm.generate(prompt, temperature=0.3, max_tokens=1024)
            cleaned = (
                result.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "name" in item and "summary" in item:
                        summaries[item["name"]] = item["summary"]
        except Exception:
            pass  # Skip summaries for this batch

    return summaries
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_mindmap_service.py::test_collect_unmatched_nodes tests/test_mindmap_service.py::test_apply_summaries tests/test_mindmap_service.py::test_generate_node_summaries_batches -v
```

Expected: PASS

- [ ] **Step 5: Integrate summary generation into generate_mindmap**

In `app/services/mindmap_service.py`, after node enrichment and before storing, add:

```python
    # Generate LLM summaries for unmatched nodes
    unmatched = _collect_unmatched_nodes(tree)
    if unmatched:
        summaries = await _generate_node_summaries(unmatched, llm)
        tree = _apply_summaries(tree, summaries)
```

Insert this block right after the enrichment block (after `tree = _enrich_tree_nodes(tree, pages)` or `tree = _enrich_tree_nodes_from_sources(tree, sources)`).

- [ ] **Step 6: Run all existing tests**

```bash
uv run pytest tests/test_mindmap_service.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/mindmap_service.py tests/test_mindmap_service.py
git commit -m "feat(mindmap): add LLM summary generation for unmatched nodes"
```

---

## Task 6: Frontend — Mindmap Page Route with List View

**Files:**
- Create: `frontend/src/app/(portal)/mindmap/page.tsx`
- Create: `frontend/src/components/mindmap/mindmap-list.tsx`

**Interfaces:**
- Consumes: `GET /api/mindmaps` → `MindmapSummary[]`
- Produces: Mindmap page at `/mindmap`

- [ ] **Step 1: Add Mindmap to sidebar navigation**

In `frontend/src/components/layout/sidebar.tsx`, add to the `navSections` array in the `"org-knowledge"` section:

```typescript
{ label: "Mindmap", href: "/mindmap", icon: "account_tree", requiredPermissions: ["wiki:read:own_dept", "wiki:read:all"] },
```

Add it after the "Chat" item.

- [ ] **Step 2: Create the MindmapList component**

```typescript
// frontend/src/components/mindmap/mindmap-list.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

type MindmapSummary = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

type MindmapListProps = {
  onView: (mindmap: MindmapSummary) => void;
  onRegenerate: (mindmap: MindmapSummary) => void;
  onDelete: (mindmap: MindmapSummary) => void;
  refreshKey: number;
};

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function scopeLabel(scopeType: string, scopeId: string | null): string {
  if (scopeType === "global") return "🌐 Global";
  if (scopeType === "department") return "🏢 Department";
  if (scopeType === "project") return "📁 Project";
  return scopeType;
}

export function MindmapList({ onView, onRegenerate, onDelete, refreshKey }: MindmapListProps) {
  const [mindmaps, setMindmaps] = useState<MindmapSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchMindmaps = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<MindmapSummary[]>("/api/mindmaps");
      setMindmaps(Array.isArray(data) ? data : []);
    } catch {
      setMindmaps([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMindmaps();
  }, [fetchMindmaps, refreshKey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="material-symbols-outlined text-3xl text-muted-foreground animate-spin">
          progress_activity
        </span>
      </div>
    );
  }

  if (mindmaps.length === 0) {
    return null; // Empty state handled by parent
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/50 border-b border-border">
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
                <span className="font-medium">{scopeLabel(mm.scope_type, mm.scope_id)}</span>
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
  );
}
```

- [ ] **Step 3: Create the Mindmap page**

```typescript
// frontend/src/app/(portal)/mindmap/page.tsx
"use client";

import { useState, useCallback } from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { MindmapList } from "@/components/mindmap/mindmap-list";
import { MindmapViewer } from "@/components/mindmap/mindmap-viewer";
import { GenerationDialog } from "@/components/mindmap/generation-dialog";
import { api } from "@/lib/api";

type MindmapSummary = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

type MindmapData = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  tree_json: Record<string, unknown>;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

export default function MindmapPage() {
  const [viewerMindmap, setViewerMindmap] = useState<MindmapData | null>(null);
  const [generationOpen, setGenerationOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [confirmDelete, setConfirmDelete] = useState<MindmapSummary | null>(null);

  const handleView = useCallback(async (mm: MindmapSummary) => {
    try {
      const data = await api<MindmapData>(`/api/mindmap?scope_type=${mm.scope_type}${mm.scope_id ? `&scope_id=${mm.scope_id}` : ""}`);
      setViewerMindmap(data);
    } catch {
      // Handle error
    }
  }, []);

  const handleRegenerate = useCallback(async (mm: MindmapSummary) => {
    if (!confirm(`Regenerate mindmap for ${mm.scope_type}? This will replace the current version.`)) return;
    try {
      await api(`/api/mindmap/${mm.id}`, { method: "DELETE" });
      await api("/api/mindmap/generate", {
        method: "POST",
        body: { scope_type: mm.scope_type, scope_id: mm.scope_id, source_type: mm.source_type },
      });
      setRefreshKey((k) => k + 1);
    } catch {
      // Handle error
    }
  }, []);

  const handleDelete = useCallback(async () => {
    if (!confirmDelete) return;
    try {
      await api(`/api/mindmap/${confirmDelete.id}`, { method: "DELETE" });
      setConfirmDelete(null);
      setRefreshKey((k) => k + 1);
    } catch {
      // Handle error
    }
  }, [confirmDelete]);

  const handleGenerated = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  // Viewer mode
  if (viewerMindmap) {
    return (
      <MindmapViewer
        mindmap={viewerMindmap}
        onBack={() => setViewerMindmap(null)}
        onRegenerate={() => {
          setViewerMindmap(null);
          handleRegenerate({
            id: viewerMindmap.id,
            scope_type: viewerMindmap.scope_type,
            scope_id: viewerMindmap.scope_id,
            title: viewerMindmap.title,
            source_type: viewerMindmap.source_type,
            wiki_page_count: viewerMindmap.wiki_page_count,
            generated_at: viewerMindmap.generated_at,
          });
        }}
        onDelete={() => {
          setViewerMindmap(null);
          setConfirmDelete({
            id: viewerMindmap.id,
            scope_type: viewerMindmap.scope_type,
            scope_id: viewerMindmap.scope_id,
            title: viewerMindmap.title,
            source_type: viewerMindmap.source_type,
            wiki_page_count: viewerMindmap.wiki_page_count,
            generated_at: viewerMindmap.generated_at,
          });
        }}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Mindmaps"
        description="Generate and manage knowledge maps from your wiki or source documents."
        action={
          <Button onClick={() => setGenerationOpen(true)} className="gap-2">
            <span className="material-symbols-outlined text-base">add</span>
            Generate
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <MindmapList
          onView={handleView}
          onRegenerate={handleRegenerate}
          onDelete={setConfirmDelete}
          refreshKey={refreshKey}
        />

        {refreshKey === 0 && (
          <EmptyState
            icon="account_tree"
            title="No mindmaps yet"
            description="Generate a knowledge map from Wiki pages or source documents."
            action={
              <Button onClick={() => setGenerationOpen(true)} className="gap-2 mt-2">
                <span className="material-symbols-outlined text-base">add</span>
                Generate Mindmap
              </Button>
            }
          />
        )}
      </div>

      <GenerationDialog
        open={generationOpen}
        onOpenChange={setGenerationOpen}
        onGenerated={handleGenerated}
      />

      {/* Delete confirmation dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-lg shadow-lg p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold mb-2">Delete Mindmap</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Are you sure you want to delete this mindmap? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 4: Verify the page loads**

```bash
cd D:\workspace\src\truongnqse05461\arkon\frontend
pnpm dev
```

Navigate to `http://localhost:3000/mindmap` — should see empty state with "No mindmaps yet".

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/\(portal\)/mindmap/page.tsx frontend/src/components/mindmap/mindmap-list.tsx frontend/src/components/layout/sidebar.tsx
git commit -m "feat(mindmap): add /mindmap page with list view and sidebar nav"
```

---

## Task 7: Frontend — Generation Dialog

**Files:**
- Create: `frontend/src/components/mindmap/generation-dialog.tsx`

**Interfaces:**
- Consumes: `GET /api/departments`, `GET /api/projects`, `GET /api/sources`
- Produces: `POST /api/mindmap/generate` with full params

- [ ] **Step 1: Create the GenerationDialog component**

```typescript
// frontend/src/components/mindmap/generation-dialog.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

type Scope = {
  type: "global" | "department" | "project";
  id: string | null;
  label: string;
};

type Source = {
  id: string;
  title: string | null;
  source_type: string;
};

type GenerationDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGenerated: () => void;
};

export function GenerationDialog({ open, onOpenChange, onGenerated }: GenerationDialogProps) {
  const [scopes, setScopes] = useState<Scope[]>([{ type: "global", id: null, label: "Global" }]);
  const [selectedScope, setSelectedScope] = useState<Scope>({ type: "global", id: null, label: "Global" });
  const [sourceType, setSourceType] = useState<"wiki" | "source_docs">("wiki");
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingSources, setLoadingSources] = useState(false);

  // Load scopes
  useEffect(() => {
    if (!open) return;
    async function loadScopes() {
      const base: Scope[] = [{ type: "global", id: null, label: "Global" }];
      try {
        const [depts, projects] = await Promise.all([
          api<{ id: string; name: string }[]>("/api/departments"),
          api<{ id: string; name: string }[]>("/api/projects"),
        ]);
        const deptScopes: Scope[] = depts.map((d) => ({ type: "department" as const, id: d.id, label: d.name }));
        const projScopes: Scope[] = projects.map((p) => ({ type: "project" as const, id: p.id, label: p.name }));
        setScopes([...base, ...deptScopes, ...projScopes]);
      } catch {
        setScopes(base);
      }
    }
    loadScopes();
  }, [open]);

  // Load sources when source_docs mode selected
  useEffect(() => {
    if (!open || sourceType !== "source_docs") return;
    async function loadSources() {
      setLoadingSources(true);
      try {
        const qs = selectedScope.id
          ? `scope_type=${selectedScope.type}&scope_id=${selectedScope.id}`
          : `scope_type=${selectedScope.type}`;
        const data = await api<Source[]>(`/api/sources?${qs}`);
        setSources(Array.isArray(data) ? data : []);
      } catch {
        setSources([]);
      } finally {
        setLoadingSources(false);
      }
    }
    loadSources();
  }, [open, sourceType, selectedScope]);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    try {
      await api("/api/mindmap/generate", {
        method: "POST",
        body: {
          scope_type: selectedScope.type,
          scope_id: selectedScope.id,
          source_type: sourceType,
          source_ids: sourceType === "source_docs" ? selectedSourceIds : undefined,
          instruction: instruction.trim() || undefined,
        },
      });
      onGenerated();
      onOpenChange(false);
      setInstruction("");
      setSelectedSourceIds([]);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  }, [selectedScope, sourceType, selectedSourceIds, instruction, onGenerated, onOpenChange]);

  const toggleSource = (id: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-lg w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">Generate Mindmap</h2>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          {/* Scope */}
          <div>
            <label className="block text-sm font-medium mb-1.5">Scope *</label>
            <select
              value={`${selectedScope.type}|${selectedScope.id ?? ""}`}
              onChange={(e) => {
                const [type, id] = e.target.value.split("|");
                const found = scopes.find((s) => s.type === type && (s.id ?? "") === id);
                if (found) setSelectedScope(found);
              }}
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background"
            >
              {scopes.map((s) => (
                <option key={`${s.type}|${s.id ?? ""}`} value={`${s.type}|${s.id ?? ""}`}>
                  {s.type === "global" ? "🌐" : s.type === "department" ? "🏢" : "📁"} {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Source Type */}
          <div>
            <label className="block text-sm font-medium mb-1.5">Source *</label>
            <select
              value={sourceType}
              onChange={(e) => {
                setSourceType(e.target.value as "wiki" | "source_docs");
                setSelectedSourceIds([]);
              }}
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background"
            >
              <option value="wiki">Wiki Pages</option>
              <option value="source_docs">Source Documents</option>
            </select>
          </div>

          {/* Source Documents Selector */}
          {sourceType === "source_docs" && (
            <div>
              <label className="block text-sm font-medium mb-1.5">Select Documents *</label>
              {loadingSources ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                  <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                  Loading documents…
                </div>
              ) : sources.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">No documents found in this scope.</p>
              ) : (
                <div className="border border-border rounded-md max-h-40 overflow-y-auto">
                  {sources.map((src) => (
                    <label
                      key={src.id}
                      className="flex items-center gap-2 px-3 py-2 hover:bg-muted/50 cursor-pointer border-b border-border last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSourceIds.includes(src.id)}
                        onChange={() => toggleSource(src.id)}
                        className="rounded"
                      />
                      <span className="text-sm truncate">{src.title || "Untitled"}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Instruction */}
          <div>
            <label className="block text-sm font-medium mb-1.5">Instruction (optional)</label>
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="e.g., Focus on API architecture and integration patterns"
              maxLength={500}
              rows={3}
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background resize-none"
            />
            <p className="text-xs text-muted-foreground mt-1">{instruction.length}/500 characters</p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-border">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={loading || (sourceType === "source_docs" && selectedSourceIds.length === 0)}
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined text-sm animate-spin mr-1.5">progress_activity</span>
                Generating…
              </>
            ) : (
              "Generate"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add Button import**

At the top of the file, add:

```typescript
import { Button } from "@/components/ui/button";
```

- [ ] **Step 3: Test the dialog opens**

Navigate to `/mindmap`, click "Generate" button. Dialog should appear with scope selector, source type, and instruction fields.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/mindmap/generation-dialog.tsx
git commit -m "feat(mindmap): add generation dialog with scope, source, instruction"
```

---

## Task 8: Frontend — Mindmap Viewer

**Files:**
- Create: `frontend/src/components/mindmap/mindmap-viewer.tsx`

**Interfaces:**
- Consumes: `MindmapData` with `tree_json`
- Reuses: `MindMapTree` from `@/components/chat/mindmap-tree`

- [ ] **Step 1: Create the MindmapViewer component**

```typescript
// frontend/src/components/mindmap/mindmap-viewer.tsx
"use client";

import { useCallback } from "react";
import { MindMapTree } from "@/components/chat/mindmap-tree";

type MindmapData = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  tree_json: Record<string, unknown>;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

type MindmapViewerProps = {
  mindmap: MindmapData;
  onBack: () => void;
  onRegenerate: () => void;
  onDelete: () => void;
};

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

export function MindmapViewer({ mindmap, onBack, onRegenerate, onDelete }: MindmapViewerProps) {
  const handleNodeClick = useCallback((node: { name: string; page_slug?: string }) => {
    if (node.page_slug) {
      if (node.page_slug.startsWith("source:")) {
        // Source doc — could open source detail in future
        return;
      }
      window.open(`/wiki/${node.page_slug}`, "_blank");
    }
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border shrink-0">
        <button
          type="button"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="Back to list"
        >
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold truncate">{mindmap.title}</h2>
          <p className="text-xs text-muted-foreground">
            {mindmap.wiki_page_count} pages · {mindmap.source_type === "source_docs" ? "Source Docs" : "Wiki"} · {formatAge(mindmap.generated_at)}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onRegenerate}
            title="Regenerate"
            className="p-2 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">refresh</span>
          </button>
          <button
            type="button"
            onClick={onDelete}
            title="Delete"
            className="p-2 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">delete</span>
          </button>
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 min-h-0">
        <MindMapTree
          tree={mindmap.tree_json as any}
          onNodeClick={handleNodeClick}
          metadata={{ pageCount: mindmap.wiki_page_count, generatedAt: mindmap.generated_at }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Test the viewer**

From the mindmap list, click the view (👁️) button on a mindmap. Should open full-screen tree view with back button and actions.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/mindmap/mindmap-viewer.tsx
git commit -m "feat(mindmap): add full-screen mindmap viewer component"
```

---

## Task 9: Frontend — Chat ↔ Mindmap Navigation

**Files:**
- Modify: `frontend/src/components/chat/chat-area.tsx`
- Modify: `frontend/src/components/chat/mindmap-node-popover.tsx`

**Interfaces:**
- Produces: "Ask in Chat" button in Mindmap page node popover
- Produces: Chat page reads `?input=` URL param

- [ ] **Step 1: Add prefilled input support to ChatArea**

In `frontend/src/components/chat/chat-area.tsx`, add at the top:

```typescript
import { useSearchParams } from "next/navigation";
```

Inside the `ChatArea` component, add after the `useChat` hook:

```typescript
  // Read prefilled input from URL (for Mindmap → Chat navigation)
  const searchParams = useSearchParams();
  useEffect(() => {
    const prefilled = searchParams.get("input");
    if (prefilled) {
      setInput(prefilled);
      // Clear the URL param without re-render
      window.history.replaceState({}, "", "/knowledge/chat");
    }
  }, [searchParams, setInput]);
```

- [ ] **Step 2: Add "Ask in Chat" to MindmapNodePopover**

In `frontend/src/components/chat/mindmap-node-popover.tsx`, the existing popover already has "Open Page" and "Ask Chat" buttons. For the Mindmap page context, we need a variant that navigates to Chat instead of seeding input.

Create a new prop or modify the existing `onAskChat` to support navigation. The simplest approach: the Mindmap page passes a different `onAskChat` that navigates:

In `frontend/src/components/mindmap/mindmap-viewer.tsx`, update the `handleNodeClick` to include "Ask in Chat" behavior. Add a new handler:

```typescript
  const handleAskInChat = useCallback((name: string) => {
    window.location.href = `/knowledge/chat?input=${encodeURIComponent(`Explain about "${name}"`)}`;
  }, []);
```

Then pass this to the tree via a custom popover or extend the existing one.

- [ ] **Step 3: Verify navigation flow**

1. Go to `/mindmap`
2. Click view on a mindmap
3. Right-click a node → popover appears
4. Click "Ask Chat" → navigates to `/knowledge/chat` with prefilled input
5. Chat input should have "Explain about 'NodeName'"

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/chat-area.tsx frontend/src/components/mindmap/mindmap-viewer.tsx
git commit -m "feat(mindmap): add Chat ↔ Mindmap navigation with prefilled input"
```

---

## Summary

| Task | Description | Sprint |
|------|-------------|--------|
| 1 | DB migration: extend WikiMindmap | 0.5 |
| 2 | Backend: GET /api/mindmaps | 0.5 |
| 3 | Backend: enhanced GenerateRequest schema | 0.5 |
| 4 | Backend: source document support | 1 |
| 5 | Backend: LLM node summaries | 1 |
| 6 | Frontend: /mindmap page with list view | 1 |
| 7 | Frontend: generation dialog | 1 |
| 8 | Frontend: mindmap viewer | 0.5 |
| 9 | Frontend: Chat ↔ Mindmap navigation | 0.5 |

**Total: ~6-7 sprints** (can parallelize backend tasks 2-5, frontend tasks 6-9)
