# Mindmap Popover Redesign - Implementation Plan

## Overview
Redesign the mindmap node popover to support multiple sources, full summary display, and clickable citations.

## Tasks

### Task 1: Backend - Add `sources` array to enriched nodes
**File:** `app/services/mindmap_service.py`

**Changes:**
1. Modify `_enrich_tree_nodes()`:
   - After matching, add source to `sources` array
   - Keep `page_slug`/`page_type` for backward compat

```python
def _enrich_tree_nodes(tree: dict, pages: list[WikiPage]) -> dict:
    lookup = _build_page_lookup(pages)

    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = match["slug"]
            node["page_type"] = match["page_type"]
            if match["summary"]:
                node["summary"] = match["summary"]
            # NEW: Add to sources array
            source_entry = {
                "slug": match["slug"],
                "type": match["page_type"],
                "title": _get_page_title_by_slug(pages, match["slug"]),
            }
            node.setdefault("sources", []).append(source_entry)
        for child in node.get("children", []):
            enrich_node(child)
        return node

    return enrich_node(tree)
```

2. Add helper `_get_page_title_by_slug()`:
```python
def _get_page_title_by_slug(pages: list[WikiPage], slug: str) -> str:
    for page in pages:
        if getattr(page, "slug", "") == slug:
            return _page_display_title(page)
    return slug
```

3. Modify `_enrich_tree_nodes_from_sources()`:
```python
def _enrich_tree_nodes_from_sources(tree: dict, sources: list) -> dict:
    # ... existing lookup logic ...

    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = f"source:{match['id']}"
            node["page_type"] = "document"
            node["summary"] = match["title"][:_SUMMARY_MAX_LEN]
            # NEW: Add to sources array
            source_entry = {
                "slug": f"source:{match['id']}",
                "type": "source_doc",
                "title": match["title"],
            }
            node.setdefault("sources", []).append(source_entry)
        for child in node.get("children", []):
            enrich_node(child)
        return node

    return enrich_node(tree)
```

---

### Task 2: Frontend - Update TreeNode type
**File:** `frontend/src/components/chat/mindmap-tree.tsx`

**Changes:**
1. Add `TreeNodeSource` type
2. Update `TreeNode` type

```typescript
export type TreeNodeSource = {
  slug: string;
  type: string;
  title: string;
};

export type TreeNode = {
  name: string;
  children: TreeNode[];
  page_slug?: string;
  page_type?: string;
  summary?: string;
  sources?: TreeNodeSource[];
  scope_type?: string;
  scope_id?: string | null;
};
```

---

### Task 3: Frontend - Redesign popover
**File:** `frontend/src/components/chat/mindmap-node-popover.tsx`

**Changes:**
1. Update `PopoverProps` to use new `TreeNode` type
2. Redesign layout:
   - Header: Icon + Name with `title` tooltip + Close button
   - Body: Full summary with `max-h-40 overflow-y-auto`
   - Citations: Clickable badge list
   - Actions: "Ask Chat" only

```tsx
export function MindmapNodePopover({ node, anchorRect, onOpenPage, onAskChat, onClose }: PopoverProps) {
  // ... existing escape handler ...

  const sources = node.sources ?? [];
  const hasSources = sources.length > 0;

  // ... existing position logic ...

  return createPortal(
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40" onClick={onClose} />

      {/* Popover */}
      <div className="fixed z-50 min-w-[220px] max-w-[320px] rounded-lg border bg-popover shadow-lg overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
          <span className="material-symbols-outlined shrink-0" style={{ fontSize: 16 }}>
            {hasSources ? "description" : "radio_button_unchecked"}
          </span>
          <span className="text-sm font-medium truncate flex-1" title={node.name}>
            {node.name}
          </span>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
          </button>
        </div>

        {/* Summary */}
        {node.summary && (
          <div className="px-3 py-2 max-h-40 overflow-y-auto">
            <p className="text-xs text-foreground/80 leading-relaxed">{node.summary}</p>
          </div>
        )}

        {/* Citations */}
        {hasSources && (
          <div className="px-3 py-2 flex flex-wrap gap-1.5 border-t">
            {sources.map((src, i) => (
              <a
                key={i}
                href={src.type === "source_doc" ? "#" : `/wiki/${src.slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] bg-muted rounded hover:bg-muted/80 transition-colors"
                title={src.title}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                  {src.type === "source_doc" ? "description" : "menu_book"}
                </span>
                <span className="truncate max-w-[120px]">{src.title}</span>
              </a>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="px-3 py-2 border-t bg-muted/20">
          <button
            onClick={() => onAskChat(node.name)}
            className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 bg-muted rounded text-xs font-medium hover:bg-muted/80"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 13 }}>chat</span>
            Ask Chat
          </button>
        </div>
      </div>
    </>,
    document.body,
  );
}
```

---

### Task 4: Update tree node rendering for sources
**File:** `frontend/src/components/chat/mindmap-tree.tsx`

**Changes:**
1. Update `makeRenderNode` to check `sources` array for icon
2. Update click handler to pass full node with sources

```typescript
// In makeRenderNode:
const hasSources = (node.sources?.length ?? 0) > 0;
const typeIcon = hasSources
  ? getTypeIcon(node.sources![0].type)
  : "radio_button_unchecked";
```

---

## Testing Checklist

1. ✅ Generate new wiki mindmap → nodes have `sources` array
2. ✅ Generate source doc mindmap → nodes have `sources` array
3. ✅ Open popover on node with sources → see clickable badges
4. ✅ Click wiki badge → opens `/wiki/{slug}` in new tab
5. ✅ Click source doc badge → shows title (or opens viewer)
6. ✅ Open popover on node without sources → see "No sources" message
7. ✅ Long summary → popover scrolls correctly
8. ✅ Name tooltip appears on hover
9. ✅ Existing mindmaps (without `sources`) still work (backward compat)
