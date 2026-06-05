# MindMap Generation Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `cook` with this plan path before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep MindMap generation wiki-based, but generate from translated, content-bearing wiki pages only. Exclude `_index`, `_log`, and empty/stub pages so the map helps users understand actual knowledge.

**Architecture:** Backend-only refinement in `app/services/mindmap_service.py` plus focused service tests. API and frontend stay unchanged.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, pytest

**Spec:** `docs/superpowers/specs/2026-06-05-mindmap-generation-refinement-design.md`

---

## File Map

### Modify

- `app/services/mindmap_service.py` - translated-aware payload, page filtering, prompt refinement
- `tests/test_mindmap_service.py` - helper and generation tests

### Do Not Modify

- `app/routers/mindmap.py` - endpoint contract unchanged
- `frontend/src/components/chat/*` - UI unchanged
- DB migrations - no schema change in this iteration

---

## Task 1: Add translated-aware page helpers

**Files:**

- Modify: `app/services/mindmap_service.py`
- Modify: `tests/test_mindmap_service.py`

- [x] **Step 1: Read current service and model fields**

Read:

```powershell
Get-Content -Path app\services\mindmap_service.py
Get-Content -Path tests\test_mindmap_service.py
```

Confirm `WikiPage` has:

- `slug`
- `title`
- `summary`
- `content_md`
- `title_translated`
- `summary_translated`
- `content_md_translated`
- `orphaned`

- [x] **Step 2: Expand the test page factory**

Update `make_page()` in `tests/test_mindmap_service.py` so tests can set:

```python
slug="page"
summary=""
title_translated=None
summary_translated=None
content_md_translated=None
source_ids=None
```

Keep defaults compatible with existing tests.

- [x] **Step 3: Add tests for display text selection**

Add tests before generation tests:

```python
def test_build_payload_prefers_translated_title_and_summary():
    from app.services.mindmap_service import _build_payload

    pages = [
        make_page(
            "Original Title",
            content="Original content " * 20,
            title_translated="Tieu de dich",
            summary_translated="Tom tat da dich " * 10,
        )
    ]

    result = _build_payload(pages)

    assert "Tieu de dich" in result
    assert "Tom tat da dich" in result
    assert "Original Title" not in result
```

```python
def test_build_payload_falls_back_to_original_content():
    from app.services.mindmap_service import _build_payload

    pages = [make_page("Architecture", content="Original architecture content " * 20)]

    result = _build_payload(pages)

    assert "Architecture" in result
    assert "Original architecture content" in result
```

- [x] **Step 4: Add helper functions in service**

In `app/services/mindmap_service.py`, add `Optional` already exists; no new typing import needed unless using `Any`.

Add helpers above `_build_payload`:

```python
def _first_text(*values: Optional[str]) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _page_display_title(page: WikiPage) -> str:
    return _first_text(getattr(page, "title_translated", None), getattr(page, "title", ""))


def _page_display_text(page: WikiPage) -> str:
    return _first_text(
        getattr(page, "summary_translated", None),
        getattr(page, "content_md_translated", None),
        getattr(page, "summary", None),
        getattr(page, "content_md", ""),
    )
```

- [x] **Step 5: Update `_build_payload()`**

Change from raw `p.title` and `p.content_md` to helpers:

```python
def _build_payload(pages: list) -> str:
    if len(pages) < SMALL_WIKI_THRESHOLD:
        lines = [
            f"- {_page_display_title(p)}: {_page_display_text(p)[:EXCERPT_CHARS].strip()}"
            for p in pages
        ]
    else:
        lines = [f"- {_page_display_title(p)}" for p in pages]
    return "\n".join(lines)
```

- [x] **Step 6: Run targeted tests**

```powershell
pytest tests/test_mindmap_service.py -q
```

Expected: existing tests plus new display-selection tests pass.

---

## Task 2: Filter internal and low-content wiki pages

**Files:**

- Modify: `app/services/mindmap_service.py`
- Modify: `tests/test_mindmap_service.py`

- [x] **Step 1: Add filter tests**

Add tests:

```python
def test_filter_pages_excludes_wiki_index_and_log():
    from app.services.mindmap_service import _filter_pages_for_mindmap

    pages = [
        make_page("Wiki Index", content="Index content " * 20, slug="_index"),
        make_page("Wiki Log", content="Log content " * 20, slug="_log"),
        make_page("Policy", content="Policy learning content " * 20, slug="policy"),
    ]

    result = _filter_pages_for_mindmap(pages)

    assert [p.title for p in result] == ["Policy"]
```

```python
def test_filter_pages_excludes_empty_or_short_content():
    from app.services.mindmap_service import _filter_pages_for_mindmap

    pages = [
        make_page("Stub", content="short", slug="stub"),
        make_page("Useful", content="Useful process content " * 20, slug="useful"),
    ]

    result = _filter_pages_for_mindmap(pages)

    assert [p.title for p in result] == ["Useful"]
```

- [x] **Step 2: Add filter constants**

In `app/services/mindmap_service.py`, add:

```python
MIN_MEANINGFUL_CHARS = 40
INTERNAL_PAGE_SLUGS = {"_index", "_log"}
```

Place near `SMALL_WIKI_THRESHOLD`.

- [x] **Step 3: Add filter helpers**

Add below display helpers:

```python
def _is_internal_page(page: WikiPage) -> bool:
    slug = _first_text(getattr(page, "slug", ""))
    return slug in INTERNAL_PAGE_SLUGS


def _is_meaningful_page(page: WikiPage) -> bool:
    return bool(_page_display_title(page)) and len(_page_display_text(page)) >= MIN_MEANINGFUL_CHARS


def _filter_pages_for_mindmap(pages: list[WikiPage]) -> list[WikiPage]:
    return [
        page
        for page in pages
        if not _is_internal_page(page) and _is_meaningful_page(page)
    ]
```

- [x] **Step 4: Use filtered pages in `generate_mindmap()`**

After DB result:

```python
pages = _filter_pages_for_mindmap(list(result.scalars().all()))
```

Keep existing error message:

```python
if not pages:
    raise ValueError("No wiki pages found for this scope.")
```

This ensures the router behavior does not change.

- [x] **Step 5: Update generation tests**

Add:

```python
@pytest.mark.asyncio
async def test_generate_mindmap_uses_only_filtered_pages_and_count():
    from app.services.mindmap_service import generate_mindmap
    db = AsyncMock()
    pages = [
        make_page("Wiki Index", content="Index content " * 20, slug="_index"),
        make_page("Architecture", content="Architecture content " * 20, slug="architecture"),
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": []}
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=json.dumps(tree))
    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            result = await generate_mindmap(db, "global", None)

    assert result.wiki_page_count == 1
    prompt = mock_llm.generate.call_args.args[0]
    assert "Architecture" in prompt
    assert "Wiki Index" not in prompt
```

Add:

```python
@pytest.mark.asyncio
async def test_generate_mindmap_raises_when_only_internal_pages():
    from app.services.mindmap_service import generate_mindmap
    db = AsyncMock()
    pages = [make_page("Wiki Log", content="Log content " * 20, slug="_log")]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValueError, match="No wiki pages"):
        await generate_mindmap(db, "global", None)
```

- [x] **Step 6: Run targeted tests**

```powershell
pytest tests/test_mindmap_service.py -q
```

Expected: all MindMap service tests pass.

---

## Task 3: Refine prompt and excerpt size

**Files:**

- Modify: `app/services/mindmap_service.py`
- Modify: `tests/test_mindmap_service.py`

- [x] **Step 1: Increase excerpt length**

Change:

```python
EXCERPT_CHARS = 300
```

to:

```python
EXCERPT_CHARS = 600
```

Update old test expectations that mention `300` excerpt chars.

- [x] **Step 2: Replace prompt wording**

Replace `_PROMPT_TEMPLATE` with learner-facing intent:

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

Rules:
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

Use ASCII hyphen, not an em dash.

- [x] **Step 3: Add prompt smoke assertion**

In `test_generate_mindmap_calls_llm_and_upserts`, assert prompt contains:

```python
prompt = mock_llm.generate.call_args.args[0]
assert "learner-facing concept map" in prompt
assert "Wiki knowledge pages" in prompt
```

- [x] **Step 4: Run targeted tests**

```powershell
pytest tests/test_mindmap_service.py -q
```

Expected: all MindMap service tests pass.

---

## Task 4: Broader validation

**Files:**

- No planned edits unless failures require focused fixes.

- [x] **Step 1: Run MindMap router tests**

```powershell
pytest tests/test_mindmap_router.py -q
```

Expected: pass. Router behavior should be unchanged.

- [x] **Step 2: Run backend syntax/import check**

```powershell
python -m compileall app\services\mindmap_service.py tests\test_mindmap_service.py
```

Expected: no syntax errors.

- [ ] **Step 3: Optional manual validation with existing app**

If local services are running and a bad cached MindMap exists:

1. Delete the cached MindMap via UI regenerate or `DELETE /api/mindmap/{id}`.
2. Generate MindMap for a scope that has `_index` and `_log`.
3. Confirm generated tree no longer includes `Wiki Index`, `Wiki Log`, or `Administrative Pages` as top concepts.
4. Confirm translated titles appear when `title_translated` exists.

---

## Task 5: Documentation and handoff

**Files:**

- Optional: update project docs only if implementation changes user-visible behavior text elsewhere.

- [x] **Step 1: Record implementation result**

After implementation, update this plan checkboxes and note:

- tests run
- tests passed/failed
- existing caches are manually regenerated when needed

Result:

- `.\.venv\Scripts\python.exe -m pytest tests\test_mindmap_service.py -q` - 15 passed
- `.\.venv\Scripts\python.exe -m pytest tests\test_mindmap_router.py -q` - 4 passed
- `.\.venv\Scripts\python.exe -m compileall app\services\mindmap_service.py tests\test_mindmap_service.py` - passed
- Existing caches remain manual regenerate/delete only.

- [x] **Step 2: Handoff command**

Use:

```powershell
cook docs\superpowers\plans\2026-06-05-mindmap-generation-refinement.md --fast
```

---

## Acceptance Criteria

- `_index` and `_log` are never included in generation payload.
- Empty/stub pages are filtered before LLM call.
- Payload prefers translated wiki fields.
- Prompt tells the LLM to produce a learner-facing concept map.
- `wiki_page_count` reflects the filtered page count.
- Existing API response shape unchanged.
- `pytest tests/test_mindmap_service.py -q` passes.
- `pytest tests/test_mindmap_router.py -q` passes.

---

## Cache Regeneration Decision

- Existing bad caches remain until users manually regenerate/delete them.
- No automatic cache invalidation in this release.
