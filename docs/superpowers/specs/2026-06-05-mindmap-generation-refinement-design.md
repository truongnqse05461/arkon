# MindMap Generation Refinement - Design Spec

**Date:** 2026-06-05
**Status:** Draft
**Scope:** Backend MindMap generation quality only

---

## Overview

Refine MindMap generation while keeping the current wiki-based mechanism. Source-file generation is out of scope because source translation does not exist before wiki generation. The MindMap should use translated wiki content when available, ignore administrative/wiki-maintenance pages, and prompt the LLM to build a learner-facing concept map from meaningful knowledge content.

Current issue: generated maps can surface unhelpful nodes such as `Wiki Index` and `Wiki Log`, because the service passes raw wiki pages to the LLM without filtering or translated-content preference.

---

## Goals

- Generate from wiki pages, not source files.
- Prefer translated wiki title/content when available.
- Exclude wiki administrative pages from generation.
- Exclude pages with no meaningful learning content.
- Improve the prompt so output is concept-oriented, not page-list-oriented.
- Keep existing API contract and UI behavior unchanged.

---

## Non-Goals

- Source-file MindMap generation.
- Storing translated source content.
- Reordering the ingestion or translation pipeline.
- New frontend controls.
- New API endpoints.
- DB schema changes unless implementation proves cache language metadata is required.

---

## User-Facing Behavior

### Before

For a small scope, MindMap generation sends each wiki page title plus the first 300 chars of `content_md`. Administrative pages are eligible. A scope with only `_index` and `_log` can produce a tree like:

```text
Knowledge Base Meta
  Administrative Pages
    Wiki Index
    Wiki Log
```

### After

MindMap generation uses content-bearing wiki pages only. If translated wiki fields exist, the generated tree should use the translated language.

Expected output shape:

```text
<Domain Topic>
  <Concept / Process / System>
    <Key Subtopic>
```

If no eligible content pages remain after filtering, generation returns the existing error path: `No wiki pages found for this scope.`

---

## Data Selection Rules

### Scope filter

Keep current scope behavior:

- `WikiPage.scope_type == scope_type`
- `WikiPage.scope_id == scope_id`
- `WikiPage.orphaned.is_(False)`

### Admin page filter

Exclude pages whose slug is an internal maintenance page:

- `_index`
- `_log`

Use existing constants from `app.services.wiki_service` if available:

- `INDEX_SLUG`
- `LOG_SLUG`

Also exclude pages with no source backing unless they still have meaningful content and are not internal maintenance pages. Recommended first implementation: do not blanket-filter `source_ids == []`, because manually authored wiki pages can be valid knowledge.

### Meaningful content filter

After choosing display content, exclude pages whose selected text is too short or clearly maintenance-only.

Minimum rule:

- selected title must be non-empty
- selected content/summary text length after cleanup must be at least 40 chars

This threshold avoids empty pages and index stubs without overfitting.

---

## Translated Content Preference

For each eligible `WikiPage`, build the payload item using:

```text
display_title =
  title_translated if present and non-empty
  else title

display_text =
  summary_translated if present and non-empty
  else content_md_translated if present and non-empty
  else summary if present and non-empty
  else content_md
```

Rationale:

- `summary_translated` is compact and usually better for prompt payload.
- `content_md_translated` is next best when summary translation is absent.
- original summary/content is fallback.

Implementation should strip whitespace and ignore empty strings.

---

## Payload Strategy

Keep the existing adaptive strategy:

| Page count | Payload |
|---|---|
| `< 150` | `title + excerpt` |
| `>= 150` | titles only |

Change the source of title/excerpt to the translated-aware display fields.

For small scopes, use a larger but still bounded excerpt:

- Existing: 300 chars
- New: 600 chars

Reason: 300 chars often captures headings/intro only. 600 chars gives the LLM enough concept material without a large cost increase.

For large scopes, titles only is acceptable, but titles must use `display_title`.

---

## Prompt Refinement

Replace the current page-grouping prompt with learner-facing intent:

```text
You are given wiki knowledge pages from an organization's knowledge base.
Create a learner-facing concept map that helps a user understand the actual
knowledge content.

Do not mirror wiki navigation or maintenance structure. Ignore administrative,
index, log, changelog, navigation, and metadata pages if they appear in the
input. Prefer concepts, processes, systems, entities, policies, decisions,
relationships, and dependencies.
```

Rules retained:

- Return valid JSON only.
- Root name is 2-4 words.
- Every node has `children`.
- Depth should match content complexity.

Additional rules:

- Node names must be concise, user-facing concepts.
- Avoid node names like `Wiki Index`, `Wiki Log`, `Administrative Pages`, `Metadata`, `Source List`.
- Do not include duplicate sibling names.

---

## Backend Changes

### Modify `app/services/mindmap_service.py`

Add helper functions:

```python
def _first_text(*values: Optional[str]) -> str:
    ...

def _page_display_title(page: WikiPage) -> str:
    ...

def _page_display_text(page: WikiPage) -> str:
    ...

def _is_internal_page(page: WikiPage) -> bool:
    ...

def _is_meaningful_page(page: WikiPage) -> bool:
    ...

def _filter_pages_for_mindmap(pages: list[WikiPage]) -> list[WikiPage]:
    ...
```

Update `_build_payload(pages)` to use display title/text helpers.

Update `generate_mindmap()`:

1. Fetch current scoped pages.
2. Filter pages with `_filter_pages_for_mindmap`.
3. Raise `ValueError("No wiki pages found for this scope.")` if filtered result empty.
4. Build payload from filtered pages.
5. Store `wiki_page_count` as filtered count.

### No router changes

`app/routers/mindmap.py` keeps current endpoint contract.

### No frontend changes

The tree renderer and panel behavior remain unchanged.

---

## Testing Strategy

Update `tests/test_mindmap_service.py`.

Required tests:

- `_build_payload` prefers translated title and translated summary.
- `_build_payload` falls back to original title/content when no translated fields exist.
- `_filter_pages_for_mindmap` excludes `_index`.
- `_filter_pages_for_mindmap` excludes `_log`.
- `_filter_pages_for_mindmap` excludes short/empty content pages.
- `generate_mindmap` sends only filtered pages and stores filtered `wiki_page_count`.
- `generate_mindmap` raises when DB has only internal/empty pages.
- Existing JSON parsing/update tests still pass.

---

## Risks

- Some valid short wiki pages may be filtered out.
- Manually written pages without sources may still appear; this is intentional for first version.
- Existing cached poor MindMaps remain until user manually regenerates or deletes cache.
- If target language changes after a cache is generated, existing cache may be stale.

Mitigation:

- Keep threshold low at 40 chars.
- Prompt also rejects administrative concepts.
- User manually regenerates existing cache when needed.

---

## Success Criteria

- Screenshot case no longer produces `Wiki Index` / `Wiki Log` nodes.
- Generated node labels use translated language when translated wiki fields exist.
- Existing `/api/mindmap` API response shape unchanged.
- MindMap service tests pass.
- No frontend change required.

---

## Cache Regeneration Decision

Existing cached MindMaps are not auto-invalidated. Users regenerate them manually.
