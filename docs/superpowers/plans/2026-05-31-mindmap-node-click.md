# MindMap Node Click → Chat Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking any MindMap node pill fills the chat input with `Explain about "<node name>"` — exiting fullscreen first if needed.

**Architecture:** Pure frontend change across 3 files. `MindMapTree` gains an `onNodeClick` callback prop via a render-function factory. `MindMapPanel` wraps it with fullscreen-exit logic. `ChatArea` wires `setInput` to the callback. No backend changes.

**Tech Stack:** Next.js 16 + React 19, TypeScript, react-d3-tree

**Spec:** `docs/superpowers/specs/2026-05-31-mindmap-node-click-design.md`

---

## File Map

### Modify
- `frontend/src/components/chat/mindmap-tree.tsx` — add `onNodeClick` prop, convert `renderNode` to factory, fix expand button
- `frontend/src/components/chat/mindmap-panel.tsx` — add `onNodeClick` prop + `handleNodeClick` with fullscreen-exit
- `frontend/src/components/chat/chat-area.tsx` — pass `onNodeClick` to `<MindMapPanel />`

---

## Task 1: Update MindMapTree — node click callback

**Files:**
- Modify: `frontend/src/components/chat/mindmap-tree.tsx`

- [ ] **Step 1: Read the current file**

Read `frontend/src/components/chat/mindmap-tree.tsx` in full so you understand the exact current shape before editing.

- [ ] **Step 2: Update `MindMapTreeProps` and convert `renderNode` to a factory**

The current `renderNode` is a plain function that receives `{ nodeDatum, toggleNode }`. Replace it with `makeRenderNode` — a factory that closes over `onNodeClick` — and update `MindMapTreeProps` to accept the new prop.

Replace the entire contents of `frontend/src/components/chat/mindmap-tree.tsx` with:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { CustomNodeElementProps, RawNodeDatum } from "react-d3-tree";

// react-d3-tree uses browser APIs — no SSR
const Tree = dynamic(() => import("react-d3-tree"), { ssr: false });

export type TreeNode = RawNodeDatum;

type MindMapTreeProps = {
  tree: TreeNode;
  onNodeClick?: (name: string) => void;
};

const ROOT_COLOR = "#c2b8e8";
const ROOT_TEXT = "#3a2a6a";
const NODE_COLOR = "#dde8f5";
const NODE_TEXT = "#2a4a7a";
const EDGE_COLOR = "#b0a8d0";

function makeRenderNode(onNodeClick?: (name: string) => void) {
  return function renderNode({ nodeDatum, toggleNode }: CustomNodeElementProps) {
    const isRoot = (nodeDatum.__rd3t?.depth ?? 0) === 0;
    const hasChildren = Array.isArray(nodeDatum.children) && nodeDatum.children.length > 0;
    const isCollapsed = nodeDatum.__rd3t?.collapsed ?? false;
    const label: string = nodeDatum.name;
    const charWidth = isRoot ? 9 : 8;
    const nodeWidth = Math.max(90, label.length * charWidth + (hasChildren ? 32 : 20));

    return (
      <foreignObject x={0} y={-14} width={nodeWidth} height={30}>
        <div
          // @ts-expect-error xmlns needed for SVG foreignObject
          xmlns="http://www.w3.org/1999/xhtml"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            background: isRoot ? ROOT_COLOR : NODE_COLOR,
            borderRadius: 6,
            padding: "3px 8px",
            fontSize: isRoot ? 13 : 12,
            fontWeight: isRoot ? 700 : 400,
            cursor: "pointer",
            userSelect: "none",
            whiteSpace: "nowrap",
            height: 28,
            boxSizing: "border-box",
          }}
          onClick={() => onNodeClick?.(label)}
        >
          <span style={{ color: isRoot ? ROOT_TEXT : NODE_TEXT, flex: 1 }}>{label}</span>
          {hasChildren && (
            <span
              style={{
                color: "#5a4a8a",
                fontSize: 11,
                background: "#e8e0f0",
                borderRadius: 3,
                padding: "1px 4px",
                lineHeight: 1,
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

export function MindMapTree({ tree, onNodeClick }: MindMapTreeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [translate, setTranslate] = useState({ x: 60, y: 200 });
  const [zoom, setZoom] = useState(0.85);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (containerRef.current) {
      const { height } = containerRef.current.getBoundingClientRect();
      setTranslate({ x: 60, y: height / 2 });
      setReady(true);
    }
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
          onUpdate={({ zoom: z }: { zoom: number }) => setZoom(Math.min(Math.max(z, 0.2), 3))}
          renderCustomNodeElement={makeRenderNode(onNodeClick)}
          separation={{ siblings: 1.3, nonSiblings: 1.8 }}
          nodeSize={{ x: 240, y: 52 }}
          collapsible
          initialDepth={1}
          pathClassFunc={() => "mindmap-edge"}
        />
      )}
      {/* Zoom controls */}
      <div style={{ position: "absolute", bottom: 10, right: 10, display: "flex", flexDirection: "column", gap: 4 }}>
        <button
          onClick={() => setZoom((z) => Math.min(z + 0.15, 3))}
          className="w-7 h-7 flex items-center justify-center bg-muted hover:bg-muted/80 rounded text-sm font-bold text-foreground border border-border"
          type="button"
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(z - 0.15, 0.2))}
          className="w-7 h-7 flex items-center justify-center bg-muted hover:bg-muted/80 rounded text-sm font-bold text-foreground border border-border"
          type="button"
          aria-label="Zoom out"
        >
          −
        </button>
      </div>
      {/* Edge colour override */}
      <style>{`.mindmap-edge { stroke: ${EDGE_COLOR}; stroke-width: 1.5px; fill: none; }`}</style>
    </div>
  );
}
```

Key changes vs current file:
- `MindMapTreeProps` gains `onNodeClick?: (name: string) => void`
- `renderNode` renamed to `makeRenderNode(onNodeClick?)` — a factory returning the render function
- Pill `onClick` → `onNodeClick?.(label)` for **all** nodes (root, branch, leaf)
- Expand `‹/›` span gets `onClick={(e) => { e.stopPropagation(); toggleNode(); }}` — stops the pill click firing
- All nodes: `cursor: "pointer"` (was `cursor: hasChildren ? "pointer" : "default"`)
- `renderCustomNodeElement={makeRenderNode(onNodeClick)}` on `<Tree>`

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors. If you see errors about `onClick` on the `span` element, check that the `onClick` type is `React.MouseEvent<HTMLSpanElement>` — the inline handler `(e) => { e.stopPropagation(); toggleNode(); }` is correctly typed.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/chat/mindmap-tree.tsx
git commit -m "feat(mindmap): add onNodeClick prop with factory render, fix expand stopPropagation"
```

---

## Task 2: Update MindMapPanel — accept onNodeClick + fullscreen-exit logic

**Files:**
- Modify: `frontend/src/components/chat/mindmap-panel.tsx`

- [ ] **Step 1: Read the current file**

Read `frontend/src/components/chat/mindmap-panel.tsx` in full. Key lines to note:
- Line 52: `export function MindMapPanel()` — no props currently
- Line 305: `{mindmap && <MindMapTree tree={mindmap.tree_json} />}` — where you'll add `onNodeClick`

- [ ] **Step 2: Add `onNodeClick` prop type to the component signature**

Change the component signature from:

```tsx
export function MindMapPanel() {
```

To:

```tsx
type MindMapPanelProps = {
  onNodeClick?: (name: string) => void;
};

export function MindMapPanel({ onNodeClick }: MindMapPanelProps) {
```

Insert the `type MindMapPanelProps` block immediately before the `export function MindMapPanel()` line (after the `// ---------------------------------------------------------------------------` comment block that precedes it).

- [ ] **Step 3: Add `handleNodeClick` callback after the existing `handleScopeChange` callback**

After the `handleScopeChange` `useCallback` block (around line 154–159), add:

```tsx
  const handleNodeClick = useCallback((name: string) => {
    if (panelState === "fullscreen") setPanelState("open");
    onNodeClick?.(name);
  }, [panelState, onNodeClick]);
```

This must go before the `const scopeValue` line.

- [ ] **Step 4: Pass `handleNodeClick` to `<MindMapTree>`**

Find the line (around line 305):
```tsx
        {mindmap && <MindMapTree tree={mindmap.tree_json} />}
```

Replace with:
```tsx
        {mindmap && <MindMapTree tree={mindmap.tree_json} onNodeClick={handleNodeClick} />}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/components/chat/mindmap-panel.tsx
git commit -m "feat(mindmap): add onNodeClick prop with fullscreen-exit to MindMapPanel"
```

---

## Task 3: Wire onNodeClick in ChatArea + manual smoke test

**Files:**
- Modify: `frontend/src/components/chat/chat-area.tsx`

- [ ] **Step 1: Read the current file**

Read `frontend/src/components/chat/chat-area.tsx`. Note:
- `setInput` is available from the `useChat` destructure (line ~37)
- `<MindMapPanel />` is rendered with no props at line ~102

- [ ] **Step 2: Pass `onNodeClick` to `<MindMapPanel />`**

Find:
```tsx
      <MindMapPanel />
```

Replace with:
```tsx
      <MindMapPanel onNodeClick={(name) => setInput(`Explain about "${name}"`)} />
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 4: Run the dev server and smoke-test**

```bash
cd frontend && pnpm dev
```

Open `http://localhost:3000/knowledge/chat`. With a session selected:

1. Open the MindMap panel and generate a MindMap (or use a cached one)
2. Click a **leaf node** (no `›` button) — chat input should fill with `Explain about "<name>"`
3. Click a **branch node's pill** (not the `›` button) — input should fill and branch should NOT collapse
4. Click the **`›` button** on a branch — branch should collapse/expand; input should NOT change
5. Enter fullscreen (`⤢`), click any node — panel should exit fullscreen AND input should fill

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/chat/chat-area.tsx
git commit -m "feat(mindmap): wire node click to fill chat input via setInput"
```
