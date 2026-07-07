# Mindmap UX Improvement — Design Spec

> Medium rework focusing on actionable nodes, visual differentiation, and panel UX polish. Excludes generation quality improvements.

## Problem Statement

The current mindmap feature renders all nodes identically (pill shape, same color), offers only "seed chat input" on click, and provides no way to preview or navigate to the underlying wiki page. Users cannot distinguish node types, and the panel UX has several friction points (fullscreen exits on node click, flat scope selector, regenerate only in fullscreen).

## Goals

1. **Actionable nodes** — Click a node to see a contextual popover with page metadata and action buttons (Open Page, Ask Chat)
2. **Visual differentiation** — Nodes styled by page type (entity, concept, topic, article) with distinct colors and icons
3. **Better zoom/pan** — Fit-to-viewport, smooth zoom, reset zoom controls
4. **Panel polish** — Grouped scope selector, regenerate in all states, improved empty/error states

## Non-Goals

- Generation quality improvements (LLM prompts, incremental regeneration)
- Search/filter functionality
- Node drag-and-drop reordering
- Real-time collaborative editing

---

## 1. Data Model — Enriched Tree Nodes

### Tree Node Schema Extension

Each node in `tree_json` gains optional metadata fields. The existing `name` and `children` fields remain unchanged, preserving backward compatibility.

```typescript
interface TreeNode {
  // Existing fields (unchanged)
  name: string;
  children: TreeNode[];

  // New optional fields
  page_slug?: string;              // Wiki page slug (null if no match)
  page_type?: "entity" | "concept" | "topic" | "article";
  summary?: string;                // Page summary, max 200 chars
  scope_type?: string;             // "global" | "department" | "project"
  scope_id?: string | null;        // Scope ID
}
```

### Backend Enrichment Logic

In `mindmap_service.py`, after LLM returns the tree JSON:

```
1. Fetch all wiki pages in scope (already available from build_payload step)
2. Build lookup map: normalized_title → { slug, page_type, summary }
3. Traverse tree recursively, for each node:
   a. Normalize node name: lowercase, strip punctuation, collapse whitespace
   b. Try exact match in lookup map
   c. If no exact match: fuzzy match using difflib.SequenceMatcher (threshold 0.75)
   d. If multiple fuzzy matches: prefer page with longer summary (more content)
   e. If match found: set page_slug, page_type, summary (truncated to 200 chars)
   f. If no match: leave fields unset (node renders as "unmatched")
```

### Fuzzy Matching Strategy

- **Exact match first:** Normalized node name == normalized page title
- **Fuzzy fallback:** `SequenceMatcher.ratio() >= 0.75`
- **Disambiguation:** When multiple pages match, prefer the one with longer summary (indicates more content/relevance)
- **Performance:** For wikis < 150 pages, O(n*m) traversal is acceptable. For larger wikis, pre-index by first 3 characters to narrow candidate set.

### Storage Impact

Enriched tree adds ~50-100 bytes per node (slug + type + summary). For a typical 50-node tree: ~3-5 KB additional storage. Negligible compared to existing `tree_json` size.

---

## 2. Contextual Popover

### Behavior

- **Click node label** → Open popover anchored to the node
- **Click outside / Escape** → Close popover
- **Click another node** → Close current popover, open new one
- **Zoom/pan while popover open** → Close popover immediately
- **Fullscreen mode** → Popover works in fullscreen (no exit fullscreen on click)

### Popover Content — Node with Linked Page

```
┌─────────────────────────────────────┐
│  📄 Authentication                  │  ← page type icon + name
│  ─────────────────────────────────  │
│  Concept · 3 related pages          │  ← type label
│                                     │
│  Methods and patterns for           │  ← summary (max 2 lines, line-clamp)
│  authenticating users...            │
│                                     │
│  [Open Page]  [Ask Chat]            │  ← action buttons
└─────────────────────────────────────┘
```

### Popover Content — Node without Linked Page

```
┌─────────────────────────────────┐
│  🔘 Advanced Topics             │  ← generic icon + name
│  ─────────────────────────────  │
│  No linked wiki page            │
│                                 │
│  [Ask Chat]                     │  ← only Ask Chat action
└─────────────────────────────────┘
```

### Action Buttons

| Button | Action | Visibility |
|--------|--------|-----------|
| **Open Page** | Navigate to `/wiki/{slug}` | Only when `page_slug` exists |
| **Ask Chat** | Set chat input to `Explain about "{node name}"` | Always |

### Technical Implementation

- **Library:** `@radix-ui/react-popover` (check if already in dependencies; if not, install)
- **Positioning:** Use `getBoundingClientRect()` from the SVG node element as anchor. Prefer right-side placement; flip left if insufficient space. Vertically centered on the node.
- **Dimensions:** Max width 280px, min width 200px
- **Animation:** Fade + scale (150ms ease-out)
- **z-index:** Above tree SVG (z-50), below fullscreen overlay

### Edge Cases

- **Rapid clicks:** Debounce 200ms; close existing popover before opening new one
- **Node in collapsed branch:** Popover still works (node is visible even if children are hidden)
- **Long node names:** Truncate with ellipsis, show full name in popover title
- **Empty summary:** Show "No summary available" in popover

---

## 3. Visual Differentiation

### Node Color Scheme by Page Type

| Page Type | Background | Border | Text | Icon |
|-----------|-----------|--------|------|------|
| `entity` | `emerald-50` | `emerald-300` | `emerald-900` | 🏢 |
| `concept` | `violet-50` | `violet-300` | `violet-900` | 💡 |
| `topic` | `sky-50` | `sky-300` | `sky-900` | 📑 |
| `article` | `amber-50` | `amber-300` | `amber-900` | 📄 |
| `unmatched` | `gray-50` | `gray-300` | `gray-700` | 🔘 |
| `root` | `purple-50` | `purple-400` | `purple-900` | 🌳 |

### Node Shape & Size

- **Root node:** Larger padding (px-4 py-2), bold text, icon prefix
- **Branch node (has children):** Standard padding (px-3 py-1.5), chevron icon suffix for expand/collapse
- **Leaf node (no children):** Slightly smaller, opacity 0.85
- **Collapsed node:** Dashed border (indicates hidden children)

### Hover & Active States

- **Hover on label:** Background brightens 1 shade, `cursor: pointer`, subtle shadow (`shadow-sm`)
- **Hover on chevron:** Chevron color changes, does not affect label
- **Popover open (active):** `ring-2 ring-primary` on node, persists while popover is visible

### Root Node Enhancement

Move cache metadata to root node display:

```
Before:  [🌳 Knowledge Base]
After:   [🌳 Knowledge Base]
         [12 pages · 3 days ago]   ← small text below name
```

This replaces the footer metadata display when in tree view. Footer still shows in empty/error states.

---

## 4. Zoom & Pan Improvements

### New Controls

Add to existing zoom control panel (bottom-right):

| Button | Icon | Action |
|--------|------|--------|
| Zoom In | `add` | Increase zoom level (+0.25) |
| Zoom Out | `remove` | Decrease zoom level (-0.25) |
| Fit to View | `fit_screen` | Auto-calculate zoom to fit entire tree in viewport |
| Reset | `restart_alt` | Return to initial zoom/pan state |

### Behavior Changes

- **Smooth zoom:** CSS transition 200ms on transform (react-d3-tree supports `transitionDuration` prop)
- **Mouse wheel zoom:** Already supported by react-d3-tree via `zoomable` prop — ensure it's enabled
- **Pan cursor:** `cursor: grab` when not dragging, `cursor: grabbing` when dragging
- **Fit-to-viewport:** On mount and on "Fit to View" click, calculate bounding box of all visible nodes, compute zoom level and translate to center the tree

### Initial State

- **Initial depth:** Keep at 1 (root + first level expanded)
- **Initial zoom:** Fit-to-viewport on first render (auto-center tree)

---

## 5. Panel UX Improvements

### Panel State Behavior

**Remove "exit fullscreen on node click":**

Current: `handleNodeClick` calls `setPanelState("open")` when in fullscreen
New: `handleNodeClick` only triggers popover, does not change panel state

**Panel width:**

- `open` mode: 340px → 380px (more space for popover positioning)
- `fullscreen`: Unchanged (full viewport)

### Scope Selector — Grouped Display

Replace flat `<select>` with grouped display using `<optgroup>` or custom Radix Select:

```
🌐 Global
─────────────
🏢 Engineering
🏢 Marketing
─────────────
📁 Project Alpha
📁 Project Beta
```

Implementation: Group `scopes` array by `type`, render with visual separators.

### Regenerate Button — Always Available

Current: Regenerate button only appears in fullscreen header
New: Add regenerate button to:
- Open mode header (next to fullscreen/collapse buttons)
- Cache footer (as a text link: "Regenerate")

### Empty State Improvement

```
Before:
  "No MindMap for this scope yet."
  [Generate MindMap]

After:
  🌳 (icon)
  "No MindMap yet"
  "Generate a knowledge map from {count} wiki pages in this scope"
  [Generate MindMap]

  Where {count} = number of wiki pages in the scope (fetch from existing API or show generic text if unavailable)
```

### Error State Improvement

Map error messages to helpful guidance:

| Error | Display |
|-------|---------|
| No wiki pages found | "No wiki pages in this scope. Add wiki pages first." |
| Generation failed (generic) | "Generation failed. Please try again." + Retry button |
| Network error | "Connection failed. Check your network." + Retry button |

---

## 6. Implementation Summary

### Files to Modify

| File | Changes |
|------|---------|
| `app/services/mindmap_service.py` | Add `_enrich_tree_nodes()` post-processing function |
| `app/database/models.py` | No schema change (tree_json is already JSONB) |
| `app/routers/mindmap.py` | No change (response schema unchanged) |
| `frontend/src/components/chat/mindmap-tree.tsx` | Node rendering with type-based styling, popover integration |
| `frontend/src/components/chat/mindmap-panel.tsx` | Scope selector grouping, regenerate button, panel width, empty/error states |
| `frontend/package.json` | Add `@radix-ui/react-popover` if not present |

### Files to Create

| File | Purpose |
|------|---------|
| `frontend/src/components/chat/mindmap-node-popover.tsx` | Popover component for node preview |

### Backward Compatibility

- Existing `tree_json` data without enriched fields still renders correctly (all nodes show as "unmatched" style)
- Existing API contract unchanged
- Frontend gracefully handles missing optional fields

### Testing Strategy

- **Backend:** Unit tests for `_enrich_tree_nodes()` — exact match, fuzzy match, no match, multi-match disambiguation
- **Frontend:** Component tests for popover (open/close, action buttons), node styling by type, grouped scope selector
- **Integration:** Generate mindmap → verify enriched fields present → render tree → click node → popover shows correct data

---

## 7. Success Criteria

1. Click any node → popover appears within 100ms with relevant info
2. Nodes visually distinguishable by page type (color + icon)
3. "Open Page" navigates to correct wiki page
4. Fit-to-viewport shows entire tree without manual zooming
5. Scope selector shows grouped options with clear hierarchy
6. Regenerate accessible from both open and fullscreen modes
7. Empty state shows helpful guidance with wiki page count

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Fuzzy matching produces wrong page association | Conservative threshold (0.75), show "unmatched" style for low-confidence matches, user can always use "Ask Chat" as fallback |
| Popover positioning breaks on edge nodes | Use Radix Popover's built-in collision detection and flip middleware |
| Enriched tree increases API response size | Summary truncated to 200 chars, only ~50-100 bytes per node added |
| react-d3-tree SVG node refs not accessible for popover anchoring | Use node's `foreignObject` element or calculate position from tree coordinates |
| Panel width increase affects chat area | 380px is still reasonable; chat area has flex-1 so it adapts |
