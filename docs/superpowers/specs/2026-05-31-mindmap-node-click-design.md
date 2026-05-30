# MindMap Node Click → Chat Input — Design Spec

**Date:** 2026-05-31  
**Status:** Approved  
**Scope:** MindMap panel — node click interaction only

---

## Overview

When a user clicks any node pill in the MindMap panel, the chat input is populated with a pre-formed question about that node. The input is not auto-submitted — the user can read, edit, or clear it before sending.

---

## User-Facing Behaviour

### Click interaction

| Mode | Node type | Click target | Result |
|---|---|---|---|
| Open | Any (root, branch, leaf) | Pill body | Chat input filled with `Explain about "<node name>"` |
| Fullscreen | Any | Pill body | Panel exits fullscreen → returns to open → chat input filled |
| Collapsed | — | — | Tree not rendered; no change |
| Any | Branch node | `›/‹` expand button | Expand/collapse only; input not touched |

### Expand/collapse unchanged

The `›/‹` button retains its existing behaviour. Clicking it expands or collapses the branch and does **not** populate the chat input. `stopPropagation` prevents the pill click handler from firing.

### Input template

```
Explain about "<node name>"
```

The node name is the exact `name` field from the tree JSON (e.g. `"RAG System"`, `"Architecture"`, `"Knowledge Base"`). The input is filled but not submitted — the user sends it manually.

### Fullscreen exit

When the panel is in fullscreen and the user clicks a node, the panel transitions to the open state (`w-[340px]`) before the input is filled. This makes the populated input immediately visible to the user.

---

## Architecture

### No backend changes

This feature is entirely frontend. No new API endpoints, no schema changes.

### Files modified

| File | Change |
|---|---|
| `frontend/src/components/chat/mindmap-tree.tsx` | Add `onNodeClick` prop; convert `renderNode` to factory; wire pill click + fix expand button |
| `frontend/src/components/chat/mindmap-panel.tsx` | Accept `onNodeClick` prop; create internal `handleNodeClick` with fullscreen-exit logic; pass to `MindMapTree` |
| `frontend/src/components/chat/chat-area.tsx` | Pass `onNodeClick={(name) => setInput(\`Explain about "${name}"\`)}` to `<MindMapPanel />` |

### Data flow

```
User clicks node pill
  → MindMapTree calls onNodeClick(name)
    → MindMapPanel.handleNodeClick(name)
        if panelState === "fullscreen": setPanelState("open")
        then: props.onNodeClick(name)
          → ChatArea: setInput(`Explain about "${name}"`)
            → ChatInput renders filled input
```

### `mindmap-tree.tsx` detail

`renderNode` is currently a plain function. It becomes a factory to close over `onNodeClick`:

```tsx
function makeRenderNode(onNodeClick?: (name: string) => void) {
  return function renderNode({ nodeDatum, toggleNode }: CustomNodeElementProps) {
    // ...
    return (
      <foreignObject ...>
        <div
          style={{ cursor: "pointer", ... }}
          onClick={() => onNodeClick?.(label)}
        >
          <span>{label}</span>
          {hasChildren && (
            <span
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

Key changes from current code:
- All nodes get `cursor: pointer` (previously leaf nodes had `cursor: default`)
- Pill `onClick` calls `onNodeClick?.(label)` (previously called `toggleNode` for branch nodes, nothing for leaf nodes)
- Expand button `onClick` stops propagation and calls `toggleNode`
- `renderCustomNodeElement={makeRenderNode(onNodeClick)}` on the `<Tree>` component

### `mindmap-panel.tsx` detail

Accepts a new optional prop and wraps it with fullscreen-exit logic:

```tsx
type MindMapPanelProps = {
  onNodeClick?: (name: string) => void;
};

// Inside component:
const handleNodeClick = useCallback((name: string) => {
  if (panelState === "fullscreen") setPanelState("open");
  props.onNodeClick?.(name);
}, [panelState, props.onNodeClick]);

// Passed to MindMapTree:
<MindMapTree tree={mindmap.tree_json} onNodeClick={handleNodeClick} />
```

### `chat-area.tsx` detail

One-line addition to the `<MindMapPanel />` render:

```tsx
<MindMapPanel onNodeClick={(name) => setInput(`Explain about "${name}"`)} />
```

`setInput` is already available from `useChat`.

---

## Out of Scope

- Auto-submitting the question (user always sends manually)
- Customising the question template
- Navigating to the wiki page for a node
- Highlighting the selected node in the tree
