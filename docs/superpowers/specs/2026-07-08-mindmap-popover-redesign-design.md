# Mindmap Node Popover Redesign

**Date:** 2026-07-08  
**Status:** Approved  
**Related:** [[2026-07-08-mindmap-page-and-generation-design]]

## Problem

Current mindmap node popover has UX issues:
1. Name is truncated without tooltip
2. Summary is clamped to 2 lines (`line-clamp-2`)
3. Single "Open Page" button doesn't support multiple sources
4. Nodes show "No linked wiki page" even when they have summaries

## Design

### Backend: Multiple Sources per Node

**Current:** Each node has `page_slug` (single string) and `page_type` (single string)  
**New:** Each node has `sources` array

```python
# Node JSON structure
{
  "name": "Node Name",
  "children": [...],
  "summary": "LLM-generated or page summary",
  "sources": [
    {"slug": "page-slug", "type": "wiki_page", "title": "Page Title"},
    {"slug": "source:uuid", "type": "source_doc", "title": "document.pdf"}
  ]
}
```

**Enrichment logic:**
- Wiki mode: Matched wiki pages → append to `sources[]`
- Source doc mode: Matched sources → append to `sources[]`
- LLM generation: Include `sources` in output JSON schema
- Backward compat: Keep `page_slug`/`page_type` for existing code that reads them

### Frontend: TreeNode Type Update

```typescript
type TreeNodeSource = {
  slug: string;
  type: string;
  title: string;
};

type TreeNode = {
  name: string;
  children: TreeNode[];
  summary?: string;
  sources?: TreeNodeSource[];
  // Keep for backward compat
  page_slug?: string;
  page_type?: string;
};
```

### Frontend: Popover Layout

```
┌─────────────────────────────────────┐
│ 📄 Node Name (title tooltip)   [x] │
├─────────────────────────────────────┤
│ Summary text goes here with full    │
│ content, scrollable if exceeds      │
│ max height (max-h-40 overflow-y)    │
├─────────────────────────────────────┤
│ [Wiki: Page Title] [doc.pdf]       │ ← clickable badges
├─────────────────────────────────────┤
│            [ Ask Chat ]             │
└─────────────────────────────────────┘
```

**Changes:**
1. **Name**: Add `title={node.name}` for native tooltip
2. **Summary**: Remove `line-clamp-2`, add `max-h-40 overflow-y-auto`
3. **Citations**: Replace "Open Page" button with clickable badge list
4. **Actions**: Keep "Ask Chat" only

### Citation Badge Behavior

- Wiki pages: Click opens `/wiki/{slug}` in new tab
- Source docs: Click opens source viewer (or shows title only if no viewer)
- Badge shows truncated title (max 30 chars) with full title in tooltip

## Files to Modify

1. `app/services/mindmap_service.py` — Add `sources` to nodes during enrichment
2. `frontend/src/components/chat/mindmap-tree.tsx` — Update `TreeNode` type
3. `frontend/src/components/chat/mindmap-node-popover.tsx` — Redesign popover UI

## Testing

1. Generate new mindmap → verify nodes have `sources` array
2. Open popover on node with sources → see clickable badges
3. Click badge → opens correct page
4. Open popover on node without sources → see "No sources" message
5. Long summary → popover scrolls correctly
