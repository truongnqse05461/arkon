# Mindmap UX Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make mindmap nodes actionable (popover with page preview + navigation), visually differentiated by page type, and improve panel UX (grouped scope selector, better zoom controls, regenerate everywhere).

**Architecture:** Backend enriches LLM-generated tree nodes with wiki page metadata (slug, type, summary) via fuzzy matching. Frontend renders type-based node colors, shows a contextual popover on click (using `createPortal`), and improves panel controls.

**Tech Stack:** Python (FastAPI, SQLAlchemy), TypeScript (Next.js 16, react-d3-tree, Tailwind CSS, `@base-ui/react`)

## Global Constraints

- Python 3.11+, async/await throughout
- Frontend uses `@base-ui/react` for UI primitives (not Radix)
- Tree node schema is backward-compatible — existing `tree_json` without enriched fields must still render
- No new npm packages — use `createPortal` for popover (pattern from `wikilink-autocomplete.tsx`)
- Use existing `wikiTypeIcon()` / `wikiTypeColor()` from `wiki-type-badge.tsx` for node styling
- All frontend components are `"use client"`

---

### Task 1: Backend — Add `_enrich_tree_nodes()` function

**Files:**
- Modify: `app/services/mindmap_service.py`
- Test: `tests/test_mindmap_service.py`

**Interfaces:**
- Consumes: `list[WikiPage]` (already fetched in `generate_mindmap`), raw tree dict from LLM
- Produces: Enriched tree dict with optional `page_slug`, `page_type`, `summary` per node

- [ ] **Step 1: Update `make_page` helper to include `page_type`**

The existing `make_page` helper in `tests/test_mindmap_service.py` does not set `page_type`. Add it:

```python
# tests/test_mindmap_service.py — in make_page(), add after p.scope_id = scope_id:

    p.page_type = "concept"  # default for tests
```

Also add `page_type` parameter to the function signature:

```python
def make_page(
    title: str,
    content: str = "content " * 10,
    scope_type: str = "global",
    scope_id=None,
    slug: str = "page",
    summary: str = "",
    page_type: str = "concept",  # NEW
    title_translated=None,
    summary_translated=None,
    content_md_translated=None,
    source_ids=None,
):
    p = MagicMock()
    p.slug = slug
    p.title = title
    p.page_type = page_type  # NEW
    # ... rest unchanged
```

- [ ] **Step 2: Write failing tests for `_enrich_tree_nodes()`**

```python
# tests/test_mindmap_service.py — append at end of file

def test_enrich_tree_exact_match():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("Authentication", slug="auth", summary="Auth methods", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    assert child["page_slug"] == "auth"
    assert child["page_type"] == "concept"  # default from make_page mock
    assert child["summary"] == "Auth methods"


def test_enrich_tree_fuzzy_match():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("User Authentication Methods", slug="user-auth", summary="How users authenticate", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    # "Authentication" vs "User Authentication Methods" — fuzzy should match
    assert child["page_slug"] == "user-auth"


def test_enrich_tree_no_match():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("Deployment Guide", slug="deploy", summary="Deploy steps", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    assert "page_slug" not in child


def test_enrich_tree_summary_truncated():
    from app.services.mindmap_service import _enrich_tree_nodes
    long_summary = "x" * 300
    pages = [
        make_page("Auth", slug="auth", summary=long_summary, content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Auth", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    assert len(result["children"][0]["summary"]) <= 200


def test_enrich_tree_nested_nodes():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("Auth", slug="auth", summary="Auth", content="x" * 60),
        make_page("OAuth", slug="oauth", summary="OAuth flow", content="x" * 60),
    ]
    tree = {
        "name": "KB",
        "children": [
            {"name": "Auth", "children": [
                {"name": "OAuth", "children": []}
            ]}
        ],
    }
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["page_slug"] == "auth"
    assert result["children"][0]["children"][0]["page_slug"] == "oauth"


def test_enrich_tree_prefers_longer_summary_on_ambiguous_match():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("API", slug="api-short", summary="Short", content="x" * 60),
        make_page("API", slug="api-long", summary="A much longer and more detailed summary about APIs", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "API", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["page_slug"] == "api-long"


def test_enrich_tree_preserves_existing_fields():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [make_page("Auth", slug="auth", summary="Auth", content="x" * 60)]
    tree = {"name": "KB", "children": [{"name": "Auth", "children": [], "custom": "value"}]}
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["custom"] == "value"
    assert result["children"][0]["page_slug"] == "auth"


def test_enrich_tree_page_type_propagation():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("Users", slug="users", page_type="entity", summary="User model", content="x" * 60),
        make_page("Auth", slug="auth", page_type="concept", summary="Auth methods", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [
        {"name": "Users", "children": []},
        {"name": "Auth", "children": []},
    ]}
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["page_type"] == "entity"
    assert result["children"][1]["page_type"] == "concept"


def test_enrich_tree_empty_children():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = []
    tree = {"name": "KB", "children": []}
    result = _enrich_tree_nodes(tree, pages)
    assert result == {"name": "KB", "children": []}
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd D:/workspace/src/truongnqse05461/arkon
python -m pytest tests/test_mindmap_service.py::test_enrich_tree_exact_match -v
```

Expected: FAIL — `_enrich_tree_nodes` not defined.

- [ ] **Step 4: Implement `_enrich_tree_nodes()`**

```python
# app/services/mindmap_service.py — add after _filter_pages_for_mindmap()

import re
from difflib import SequenceMatcher

_SUMMARY_MAX_LEN = 200
_FUZZY_THRESHOLD = 0.75


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", name.lower())).strip()


def _build_page_lookup(pages: list[WikiPage]) -> dict[str, list[dict]]:
    """Build normalized_title → list of page metadata dicts."""
    lookup: dict[str, list[dict]] = {}
    for page in pages:
        title = _page_display_title(page)
        if not title:
            continue
        key = _normalize_name(title)
        summary_raw = _first_text(
            getattr(page, "summary_translated", None),
            getattr(page, "summary", None),
        )
        entry = {
            "slug": getattr(page, "slug", ""),
            "page_type": getattr(page, "page_type", "concept"),
            "summary": summary_raw[:_SUMMARY_MAX_LEN] if summary_raw else "",
        }
        lookup.setdefault(key, []).append(entry)
    return lookup


def _match_node(node_name: str, lookup: dict[str, list[dict]]) -> Optional[dict]:
    """Find best matching page for a node name. Returns metadata dict or None."""
    normalized = _normalize_name(node_name)
    if not normalized:
        return None

    # Exact match
    if normalized in lookup:
        candidates = lookup[normalized]
        return max(candidates, key=lambda c: len(c.get("summary", "")))

    # Fuzzy match
    best_score = 0.0
    best_entry = None
    for page_key, entries in lookup.items():
        score = SequenceMatcher(None, normalized, page_key).ratio()
        if score > best_score:
            best_score = score
            best_entry = max(entries, key=lambda c: len(c.get("summary", "")))

    if best_score >= _FUZZY_THRESHOLD and best_entry:
        return best_entry
    return None


def _enrich_tree_nodes(tree: dict, pages: list[WikiPage]) -> dict:
    """Enrich tree nodes with wiki page metadata (slug, type, summary)."""
    lookup = _build_page_lookup(pages)

    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = match["slug"]
            node["page_type"] = match["page_type"]
            if match["summary"]:
                node["summary"] = match["summary"]
        for child in node.get("children", []):
            enrich_node(child)
        return node

    return enrich_node(tree)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd D:/workspace/src/truongnqse05461/arkon
python -m pytest tests/test_mindmap_service.py -v -k "enrich"
```

Expected: All 8 enrichment tests PASS.

- [ ] **Step 6: Integrate enrichment into `generate_mindmap()`**

```python
# app/services/mindmap_service.py — in generate_mindmap(), after tree is parsed and validated (line ~170),
# before the upsert block, add:

    tree = _enrich_tree_nodes(tree, pages)
```

The full function becomes (showing the changed section):

```python
    if not isinstance(tree, dict):
        raise ValueError(f"LLM returned unexpected JSON shape: {type(tree).__name__}")

    tree = _enrich_tree_nodes(tree, pages)  # <-- NEW LINE

    title = str(tree.get("name", "Knowledge Base"))
    # ... rest unchanged
```

- [ ] **Step 7: Run all mindmap service tests**

```bash
cd D:/workspace/src/truongnqse05461/arkon
python -m pytest tests/test_mindmap_service.py -v
```

Expected: All tests PASS (existing + new enrichment tests).

- [ ] **Step 8: Run mindmap router tests**

```bash
cd D:/workspace/src/truongnqse05461/arkon
python -m pytest tests/test_mindmap_router.py -v
```

Expected: All router tests PASS (no API contract change).

- [ ] **Step 9: Commit**

```bash
git add app/services/mindmap_service.py tests/test_mindmap_service.py
git commit -m "feat(mindmap): enrich tree nodes with wiki page metadata"
```

---

### Task 2: Frontend — Create `MindmapNodePopover` component

**Files:**
- Create: `frontend/src/components/chat/mindmap-node-popover.tsx`

**Interfaces:**
- Consumes: `TreeNode` (with optional `page_slug`, `page_type`, `summary`)
- Produces: Popover component with "Open Page" and "Ask Chat" actions
- Uses: `createPortal` (pattern from `wikilink-autocomplete.tsx`), `wikiTypeIcon`/`wikiTypeColor` from `wiki-type-badge.tsx`

- [ ] **Step 1: Create the popover component**

```tsx
// frontend/src/components/chat/mindmap-node-popover.tsx
"use client";

import { createPortal } from "react-dom";
import { wikiTypeIcon, wikiTypeColor } from "@/components/wiki/wiki-type-badge";
import type { TreeNode } from "./mindmap-tree";

type PopoverProps = {
  node: TreeNode;
  anchorRect: DOMRect;
  onOpenPage: (slug: string) => void;
  onAskChat: (name: string) => void;
  onClose: () => void;
};

const POPOVER_WIDTH = 260;
const POPOVER_PADDING = 12;

export function MindmapNodePopover({
  node,
  anchorRect,
  onOpenPage,
  onAskChat,
  onClose,
}: PopoverProps) {
  const hasPage = Boolean(node.page_slug);
  const typeIcon = hasPage ? wikiTypeIcon(node.page_type ?? "") : "radio_button_unchecked";
  const typeColor = hasPage ? wikiTypeColor(node.page_type ?? "") : "#9ca3af";
  const typeLabel = hasPage ? (node.page_type ?? "page") : "unlinked";

  // Position: prefer right of node, flip left if not enough space
  const spaceRight = window.innerWidth - anchorRect.right;
  const flipLeft = spaceRight < POPOVER_WIDTH + POPOVER_PADDING * 2;
  const left = flipLeft
    ? anchorRect.left - POPOVER_WIDTH - 8
    : anchorRect.right + 8;
  const top = Math.max(
    POPOVER_PADDING,
    Math.min(
      anchorRect.top + anchorRect.height / 2 - 60,
      window.innerHeight - 160,
    ),
  );

  return createPortal(
    <>
      {/* Backdrop to catch outside clicks */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        tabIndex={-1}
      />
      {/* Popover */}
      <div
        className="fixed z-50 w-[260px] rounded-lg border border-border bg-popover text-popover-foreground shadow-lg overflow-hidden"
        style={{ left, top }}
        role="dialog"
        aria-label={`Node: ${node.name}`}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30">
          <span
            className="material-symbols-outlined shrink-0"
            style={{ fontSize: 16, color: typeColor }}
          >
            {typeIcon}
          </span>
          <span className="text-sm font-medium truncate flex-1">{node.name}</span>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
            aria-label="Close"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
          </button>
        </div>

        {/* Body */}
        <div className="px-3 py-2 space-y-2">
          <p className="text-[11px] text-muted-foreground capitalize">{typeLabel}</p>
          {hasPage && node.summary ? (
            <p className="text-xs text-foreground/80 leading-relaxed line-clamp-2">
              {node.summary}
            </p>
          ) : hasPage ? (
            <p className="text-xs text-muted-foreground italic">No summary available</p>
          ) : (
            <p className="text-xs text-muted-foreground italic">No linked wiki page</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 px-3 py-2 border-t border-border bg-muted/20">
          {hasPage && (
            <button
              type="button"
              onClick={() => onOpenPage(node.page_slug!)}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 bg-primary text-primary-foreground rounded text-xs font-medium hover:bg-primary/90 transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 13 }}>open_in_new</span>
              Open Page
            </button>
          )}
          <button
            type="button"
            onClick={() => onAskChat(node.name)}
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 bg-muted text-foreground rounded text-xs font-medium hover:bg-muted/80 transition-colors border border-border"
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

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd D:/workspace/src/truongnqse05461/arkon/frontend
npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: No errors related to `mindmap-node-popover.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/mindmap-node-popover.tsx
git commit -m "feat(mindmap): add node popover component"
```

---

### Task 3: Frontend — Update `MindMapTree` with type-based styling and popover

**Files:**
- Modify: `frontend/src/components/chat/mindmap-tree.tsx`

**Interfaces:**
- Consumes: `MindmapNodePopover` from Task 2, `TreeNode` with enriched fields
- Produces: Updated `onNodeClick` callback signature (now passes node data, not just name)

- [ ] **Step 1: Define type-based color constants and update TreeNode**

```tsx
// frontend/src/components/chat/mindmap-tree.tsx — replace type and constants section

export type TreeNode = {
  name: string;
  children: TreeNode[];
  page_slug?: string;
  page_type?: string;
  summary?: string;
  scope_type?: string;
  scope_id?: string | null;
};

type MindMapTreeProps = {
  tree: TreeNode;
  onNodeClick?: (node: TreeNode) => void;
  metadata?: { pageCount: number; generatedAt: string };
};

// Type-based colors (from wiki-type-badge.tsx style)
const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  entity: { bg: "#fdf4f0", border: "#f0b89a", text: "#7a3d1a" },
  concept: { bg: "#f5f0ed", border: "#c4b3a3", text: "#5a4a3a" },
  topic: { bg: "#f0f5f3", border: "#9ac4b3", text: "#2a5a4a" },
  source: { bg: "#f3f0f5", border: "#b39ac4", text: "#4a2a5a" },
};

const ROOT_COLOR = "#c2b8e8";
const ROOT_TEXT = "#3a2a6a";
const DEFAULT_NODE_COLOR = "#dde8f5";
const DEFAULT_NODE_TEXT = "#2a4a7a";
const EDGE_COLOR = "#b0a8d0";

function getNodeStyle(nodeDatum: TreeNode, isRoot: boolean) {
  if (isRoot) return { bg: ROOT_COLOR, text: ROOT_TEXT };
  const type = nodeDatum.page_type;
  if (type && TYPE_COLORS[type]) {
    return { bg: TYPE_COLORS[type].bg, text: TYPE_COLORS[type].text };
  }
  // Unmatched nodes — slightly desaturated
  if (!nodeDatum.page_slug) return { bg: "#f0f0f0", text: "#666" };
  return { bg: DEFAULT_NODE_COLOR, text: DEFAULT_NODE_TEXT };
}

function getTypeIcon(pageType?: string): string | null {
  const icons: Record<string, string> = {
    entity: "person",
    concept: "lightbulb",
    topic: "topic",
    source: "description",
  };
  return icons[pageType ?? ""] ?? null;
}
```

- [ ] **Step 2: Update `makeRenderNode` to use type styling and handle click with node data**

```tsx
// frontend/src/components/chat/mindmap-tree.tsx — replace makeRenderNode function

function makeRenderNode(
  onNodeClick?: (node: TreeNode) => void,
  activeNodeKey?: string | null,
) {
  return function renderNode({ nodeDatum, toggleNode }: CustomNodeElementProps) {
    const depth = nodeDatum.__rd3t?.depth ?? 0;
    const isRoot = depth === 0;
    const hasChildren = Array.isArray(nodeDatum.children) && nodeDatum.children.length > 0;
    const isCollapsed = nodeDatum.__rd3t?.collapsed ?? false;
    const label: string = nodeDatum.name;
    const node = nodeDatum as unknown as TreeNode;
    const style = getNodeStyle(node, isRoot);
    const typeIcon = getTypeIcon(node.page_slug ? node.page_type : undefined);
    const isActive = activeNodeKey === label;
    const charWidth = isRoot ? 9 : 8;
    const iconSpace = typeIcon ? 18 : 0;
    const nodeWidth = Math.max(90, label.length * charWidth + (hasChildren ? 32 : 20) + iconSpace + 8);

    return (
      <foreignObject x={0} y={isRoot ? -18 : -14} width={nodeWidth} height={isRoot ? 40 : 30}>
        <div
          // @ts-expect-error xmlns needed for SVG foreignObject
          xmlns="http://www.w3.org/1999/xhtml"
          data-node-label={label}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            background: style.bg,
            border: `${isCollapsed ? "1.5px dashed" : "1.5px solid"} ${isActive ? "#6366f1" : style.border ?? "#ccc"}`,
            borderRadius: 6,
            padding: isRoot ? "5px 10px" : "3px 8px",
            fontSize: isRoot ? 13 : 12,
            fontWeight: isRoot ? 700 : 400,
            cursor: "pointer",
            userSelect: "none",
            whiteSpace: "nowrap",
            height: isRoot ? 36 : 28,
            boxSizing: "border-box",
            boxShadow: isActive ? "0 0 0 2px rgba(99,102,241,0.3)" : undefined,
            transition: "border-color 0.15s, box-shadow 0.15s",
          }}
          onClick={() => onNodeClick?.(node)}
        >
          {typeIcon && (
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 13, color: style.text, opacity: 0.7, flexShrink: 0 }}
            >
              {typeIcon}
            </span>
          )}
          <span style={{ color: style.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
            {label}
          </span>
          {hasChildren && (
            <span
              style={{
                color: "#5a4a8a",
                fontSize: 11,
                background: "#e8e0f0",
                borderRadius: 3,
                padding: "1px 4px",
                lineHeight: 1,
                flexShrink: 0,
              }}
              onClick={(e) => { e.stopPropagation(); toggleNode(); }}
            >
              {isCollapsed ? "›" : "‹"}
            </span>
          )}
        </div>
      </foreignObject>
    );
  };
}
```

- [ ] **Step 3: Update `MindMapTree` component to manage popover state**

```tsx
// frontend/src/components/chat/mindmap-tree.tsx — replace MindMapTree function

export function MindMapTree({ tree, onNodeClick, metadata }: MindMapTreeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [translate, setTranslate] = useState({ x: 60, y: 200 });
  const [zoom, setZoom] = useState(0.85);
  const [ready, setReady] = useState(false);
  const [popoverState, setPopoverState] = useState<{
    node: TreeNode;
    rect: DOMRect;
  } | null>(null);

  useEffect(() => {
    if (containerRef.current) {
      const { height } = containerRef.current.getBoundingClientRect();
      setTranslate({ x: 60, y: height / 2 });
      setReady(true);
    }
  }, []);

  // Close popover on zoom/pan
  const handleUpdate = useCallback(({ zoom: z }: { zoom: number }) => {
    setZoom(Math.min(Math.max(z, 0.2), 3));
    setPopoverState(null);
  }, []);

  const handleNodeClick = useCallback((node: TreeNode) => {
    // Find the SVG foreignObject element for this node
    const el = containerRef.current?.querySelector(
      `[data-node-label="${CSS.escape(node.name)}"]`,
    );
    if (el) {
      const rect = el.getBoundingClientRect();
      setPopoverState((prev) =>
        prev?.node.name === node.name ? null : { node, rect },
      );
    } else {
      // Fallback: pass to parent
      onNodeClick?.(node);
    }
  }, [onNodeClick]);

  const handleOpenPage = useCallback((slug: string) => {
    setPopoverState(null);
    window.open(`/wiki/${slug}`, "_blank");
  }, []);

  const handleAskChat = useCallback((name: string) => {
    setPopoverState(null);
    onNodeClick?.({ name, children: [] });
  }, [onNodeClick]);

  const renderNode = useMemo(
    () => makeRenderNode(handleNodeClick, popoverState?.node.name),
    [handleNodeClick, popoverState?.node.name],
  );

  const handleFitToView = useCallback(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const svgEl = container.querySelector("svg");
    if (!svgEl) return;
    const gEl = svgEl.querySelector("g");
    if (!gEl) return;

    const bbox = (gEl as SVGGElement).getBBox();
    if (bbox.width === 0 || bbox.height === 0) return;

    const containerRect = container.getBoundingClientRect();
    const padding = 40;
    const scaleX = (containerRect.width - padding * 2) / bbox.width;
    const scaleY = (containerRect.height - padding * 2) / bbox.height;
    const newZoom = Math.min(Math.max(Math.min(scaleX, scaleY), 0.2), 3);

    setZoom(newZoom);
    setTranslate({
      x: containerRect.width / 2 - (bbox.x + bbox.width / 2) * newZoom,
      y: containerRect.height / 2 - (bbox.y + bbox.height / 2) * newZoom,
    });
    setPopoverState(null);
  }, []);

  const handleReset = useCallback(() => {
    if (containerRef.current) {
      const { height } = containerRef.current.getBoundingClientRect();
      setTranslate({ x: 60, y: height / 2 });
    }
    setZoom(0.85);
    setPopoverState(null);
  }, []);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative", background: "#fff" }}>
      {ready && (
        <Tree
          data={tree}
          orientation="horizontal"
          pathFunc="diagonal"
          translate={translate}
          zoom={zoom}
          onUpdate={handleUpdate}
          renderCustomNodeElement={renderNode}
          separation={{ siblings: 1.3, nonSiblings: 1.8 }}
          nodeSize={{ x: 240, y: 52 }}
          collapsible
          initialDepth={1}
          pathClassFunc={() => "mindmap-edge"}
          zoomable
          scaleExtent={{ min: 0.2, max: 3 }}
          translateExtent={{ xMin: -Infinity, yMin: -Infinity, xMax: Infinity, yMax: Infinity }}
        />
      )}

      {/* Root metadata below tree */}
      {metadata && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 text-[10px] text-muted-foreground bg-background/80 px-2 py-0.5 rounded border border-border/50">
          {metadata.pageCount} pages · {formatAge(metadata.generatedAt)}
        </div>
      )}

      {/* Zoom controls */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-1.5">
        <button
          onClick={() => setZoom((z) => Math.min(z + 0.25, 3))}
          className="w-7 h-7 flex items-center justify-center bg-muted hover:bg-muted/80 rounded text-sm font-bold text-foreground border border-border transition-colors"
          type="button"
          aria-label="Zoom in"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span>
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(z - 0.25, 0.2))}
          className="w-7 h-7 flex items-center justify-center bg-muted hover:bg-muted/80 rounded text-sm font-bold text-foreground border border-border transition-colors"
          type="button"
          aria-label="Zoom out"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>remove</span>
        </button>
        <div className="h-px bg-border my-0.5" />
        <button
          onClick={handleFitToView}
          className="w-7 h-7 flex items-center justify-center bg-muted hover:bg-muted/80 rounded text-foreground border border-border transition-colors"
          type="button"
          aria-label="Fit to view"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>fit_screen</span>
        </button>
        <button
          onClick={handleReset}
          className="w-7 h-7 flex items-center justify-center bg-muted hover:bg-muted/80 rounded text-foreground border border-border transition-colors"
          type="button"
          aria-label="Reset zoom"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>restart_alt</span>
        </button>
      </div>

      {/* Popover */}
      {popoverState && (
        <MindmapNodePopover
          node={popoverState.node}
          anchorRect={popoverState.rect}
          onOpenPage={handleOpenPage}
          onAskChat={handleAskChat}
          onClose={() => setPopoverState(null)}
        />
      )}

      {/* Edge colour override */}
      <style>{`.mindmap-edge { stroke: ${EDGE_COLOR}; stroke-width: 1.5px; fill: none; }`}</style>
    </div>
  );
}

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}
```

- [ ] **Step 4: Update imports at top of file**

```tsx
// frontend/src/components/chat/mindmap-tree.tsx — add import
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { CustomNodeElementProps } from "react-d3-tree";
import { MindmapNodePopover } from "./mindmap-node-popover";
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd D:/workspace/src/truongnqse05461/arkon/frontend
npx tsc --noEmit --pretty 2>&1 | head -30
```

Expected: No errors. Note: `onNodeClick` signature change from `(name: string)` to `(node: TreeNode)` — Task 4 will update the caller.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/chat/mindmap-tree.tsx
git commit -m "feat(mindmap): type-based node styling, popover integration, zoom controls"
```

---

### Task 4: Frontend — Update `MindMapPanel` with panel UX improvements

**Files:**
- Modify: `frontend/src/components/chat/mindmap-panel.tsx`

**Interfaces:**
- Consumes: Updated `MindMapTree` from Task 3 (new `onNodeClick` signature, `metadata` prop)
- Produces: Improved panel with grouped scope selector, wider panel, regenerate everywhere, better states

- [ ] **Step 1: Update `handleNodeClick` to match new signature**

The `onNodeClick` callback now receives `TreeNode` instead of `string`. Update the handler:

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — replace handleNodeClick

const handleNodeClick = useCallback((node: { name: string; page_slug?: string }) => {
  if (node.page_slug) {
    // Navigate to wiki page
    window.open(`/wiki/${node.page_slug}`, "_blank");
  } else {
    // Fallback: seed chat input
    onNodeClick?.(node.name);
  }
}, [onNodeClick]);
```

- [ ] **Step 2: Remove "exit fullscreen on node click" behavior**

The old code had `if (panelState === "fullscreen") setPanelState("open");` in `handleNodeClick`. The new handler above already removes this. Verify no other code path changes panel state on node click.

- [ ] **Step 3: Update panel width from 340px to 380px**

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — find the "open" return block
// Change: className="w-[340px] ..."
// To:     className="w-[380px] ..."

<div className="w-[380px] flex-shrink-0 flex flex-col border-l border-border bg-background">
```

- [ ] **Step 4: Add grouped scope selector**

Replace the flat `<select>` with grouped `<optgroup>`:

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — replace the <select> in header()

// Group scopes by type
const groupedScopes = scopes.reduce(
  (acc, s) => {
    acc[s.type] = acc[s.type] || [];
    acc[s.type].push(s);
    return acc;
  },
  {} as Record<string, Scope[]>,
);

// In the header JSX, replace the <select> with:
<select
  value={scopeValue}
  onChange={handleScopeChange}
  disabled={isGenerating}
  className="flex-1 min-w-0 text-xs border border-border rounded px-1.5 py-0.5 bg-background text-foreground disabled:opacity-50"
>
  {groupedScopes["global"]?.map((s) => (
    <option key={`${s.type}|${s.id ?? ""}`} value={`${s.type}|${s.id ?? ""}`}>
      🌐 {s.label}
    </option>
  ))}
  {groupedScopes["department"]?.length > 0 && (
    <optgroup label="Departments">
      {groupedScopes["department"].map((s) => (
        <option key={`${s.type}|${s.id ?? ""}`} value={`${s.type}|${s.id ?? ""}`}>
          🏢 {s.label}
        </option>
      ))}
    </optgroup>
  )}
  {groupedScopes["project"]?.length > 0 && (
    <optgroup label="Projects">
      {groupedScopes["project"].map((s) => (
        <option key={`${s.type}|${s.id ?? ""}`} value={`${s.type}|${s.id ?? ""}`}>
          📁 {s.label}
        </option>
      ))}
    </optgroup>
  )}
</select>
```

- [ ] **Step 5: Add regenerate button to open mode header**

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — in header(), add regenerate button
// Place it before the fullscreen button, visible in both open and fullscreen modes

<button
  type="button"
  onClick={handleRegenerate}
  disabled={isGenerating || status === "empty"}
  title="Regenerate"
  className="text-xs text-muted-foreground hover:text-foreground disabled:opacity-40 px-1.5 py-0.5 rounded hover:bg-muted transition-colors"
>
  <span
    className="material-symbols-outlined text-[14px]"
    style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
  >
    refresh
  </span>
</button>
```

Remove the `inFullscreen &&` condition that gates this button.

- [ ] **Step 6: Update empty state**

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — replace empty state in body()

if (status === "empty") {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6">
      <span
        className="material-symbols-outlined text-3xl text-muted-foreground/50"
        style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
      >
        account_tree
      </span>
      <p className="text-sm font-medium text-foreground">No MindMap yet</p>
      <p className="text-xs text-muted-foreground text-center">
        Generate a knowledge map from wiki pages in this scope.
      </p>
      <button
        type="button"
        onClick={handleGenerate}
        className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs font-medium hover:bg-primary/90 transition-colors"
      >
        Generate MindMap
      </button>
    </div>
  );
}
```

- [ ] **Step 7: Update error state with helpful guidance**

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — replace error state in body()

if (status === "error") {
  const isNoPages = errorMsg?.toLowerCase().includes("no wiki pages");
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6">
      <span
        className="material-symbols-outlined text-2xl text-destructive/70"
        style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
      >
        {isNoPages ? "description" : "error"}
      </span>
      <p className="text-xs text-destructive text-center font-medium">
        {isNoPages ? "No wiki pages in this scope" : errorMsg}
      </p>
      <p className="text-[11px] text-muted-foreground text-center">
        {isNoPages
          ? "Add wiki pages to this scope first, then generate the mindmap."
          : "Something went wrong. Please try again."}
      </p>
      <button
        type="button"
        onClick={isNoPages ? undefined : () => loadMindmap(selectedScope)}
        disabled={isNoPages}
        className="px-3 py-1.5 bg-muted text-foreground rounded-md text-xs hover:bg-muted/80 transition-colors disabled:opacity-50"
      >
        Retry
      </button>
    </div>
  );
}
```

- [ ] **Step 8: Pass metadata to MindMapTree**

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — in the "ready" return block

// ready
return (
  <div className="flex-1 min-h-0 overflow-hidden">
    {mindmap && (
      <MindMapTree
        tree={mindmap.tree_json}
        onNodeClick={handleNodeClick}
        metadata={{
          pageCount: mindmap.wiki_page_count,
          generatedAt: mindmap.generated_at,
        }}
      />
    )}
  </div>
);
```

- [ ] **Step 9: Update cache footer with regenerate link**

```tsx
// frontend/src/components/chat/mindmap-panel.tsx — replace cacheFooter

const cacheFooter =
  mindmap && status === "ready" ? (
    <div className="px-3 py-1.5 border-t border-border flex items-center justify-between text-[10px] text-muted-foreground shrink-0">
      <span>{mindmap.wiki_page_count} pages · generated {formatAge(mindmap.generated_at)}</span>
      <button
        type="button"
        onClick={handleRegenerate}
        disabled={isGenerating}
        className="text-[10px] text-muted-foreground hover:text-foreground underline-offset-2 hover:underline transition-colors disabled:opacity-40"
      >
        Regenerate
      </button>
    </div>
  ) : null;
```

- [ ] **Step 10: Remove the `loadMindmap` useCallback (unused after useEffect handles scope changes)**

The `loadMindmap` callback on line 84-101 is only used in the error retry button. Keep it but ensure it's consistent with the new error handling.

- [ ] **Step 11: Verify TypeScript compiles**

```bash
cd D:/workspace/src/truongnqse05461/arkon/frontend
npx tsc --noEmit --pretty 2>&1 | head -30
```

Expected: No errors.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/components/chat/mindmap-panel.tsx
git commit -m "feat(mindmap): grouped scope selector, regenerate everywhere, improved states"
```

---

### Task 5: Frontend — Verify full integration with dev build

**Files:**
- No file changes — verification only

- [ ] **Step 1: Run TypeScript check on entire frontend**

```bash
cd D:/workspace/src/truongnqse05461/arkon/frontend
npx tsc --noEmit --pretty
```

Expected: Zero errors.

- [ ] **Step 2: Run backend tests**

```bash
cd D:/workspace/src/truongnqse05461/arkon
python -m pytest tests/test_mindmap_service.py tests/test_mindmap_router.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Run frontend build**

```bash
cd D:/workspace/src/truongnqse05461/arkon/frontend
npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit any fixes if needed**

```bash
git add -A
git commit -m "fix(mindmap): address integration issues"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Backend enrichment function + tests | `mindmap_service.py`, `test_mindmap_service.py` |
| 2 | Popover component | `mindmap-node-popover.tsx` |
| 3 | Tree: type styling, popover, zoom controls | `mindmap-tree.tsx` |
| 4 | Panel: grouped selector, regenerate, states | `mindmap-panel.tsx` |
| 5 | Integration verification | No changes |

**Estimated effort:** 3-5 days for a developer familiar with the codebase.

**Dependencies:** Task 2 → Task 3 (popover used by tree). Task 3 → Task 4 (tree API change consumed by panel). Task 1 is independent of frontend tasks.

**Parallelization:** Task 1 (backend) and Task 2 (popover component) can run in parallel. Tasks 3 and 4 are sequential.
