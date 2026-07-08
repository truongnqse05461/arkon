"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { CustomNodeElementProps } from "react-d3-tree";
import { MindmapNodePopover } from "./mindmap-node-popover";

// react-d3-tree uses browser APIs — no SSR
const Tree = dynamic(() => import("react-d3-tree"), { ssr: false });

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
  if (isRoot) return { bg: ROOT_COLOR, border: ROOT_COLOR, text: ROOT_TEXT };
  const type = nodeDatum.page_type;
  if (type && TYPE_COLORS[type]) {
    return { bg: TYPE_COLORS[type].bg, border: TYPE_COLORS[type].border, text: TYPE_COLORS[type].text };
  }
  // Unmatched nodes — slightly desaturated
  if (!nodeDatum.page_slug) return { bg: "#f0f0f0", border: "#ddd", text: "#666" };
  return { bg: DEFAULT_NODE_COLOR, border: "#ccc", text: DEFAULT_NODE_TEXT };
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
