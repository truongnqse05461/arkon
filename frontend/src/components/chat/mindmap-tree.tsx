"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { CustomNodeElementProps } from "react-d3-tree";
import { MindmapNodePopover } from "./mindmap-node-popover";
import { wikiTypeColor } from "@/components/wiki/wiki-type-badge";

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

const ROOT_COLOR = "#c2b8e8";
const ROOT_TEXT = "#3a2a6a";
const DEFAULT_BASE = "#9ca3af";
const EDGE_COLOR = "#b0a8d0";

function getNodeStyle(nodeDatum: TreeNode, isRoot: boolean) {
  if (isRoot) return { bg: ROOT_COLOR, border: ROOT_COLOR, text: ROOT_TEXT };
  const type = nodeDatum.page_type;
  const base = type ? wikiTypeColor(type) : DEFAULT_BASE;
  if (nodeDatum.page_slug) {
    return { bg: `${base}1a`, border: `${base}40`, text: base };
  }
  // Unmatched nodes — slightly desaturated
  return { bg: `${DEFAULT_BASE}1a`, border: `${DEFAULT_BASE}40`, text: DEFAULT_BASE };
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
    const maxWidth = 260; // cap to prevent parent overlap with children
    const nodeWidth = Math.min(maxWidth, Math.max(100, label.length * charWidth + (hasChildren ? 40 : 20) + iconSpace + 10));

    return (
      <foreignObject x={0} y={isRoot ? -20 : -16} width={nodeWidth} height={isRoot ? 44 : 34}>
        <div
          // @ts-expect-error xmlns needed for SVG foreignObject
          xmlns="http://www.w3.org/1999/xhtml"
          className="mindmap-node"
          data-node-label={label}
          onContextMenu={(e) => {
            // Right-click = popover
            e.preventDefault();
            onNodeClick?.(node);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            background: style.bg,
            border: `${isCollapsed ? "1.5px dashed" : "1.5px solid"} ${isActive ? "#6366f1" : style.border ?? "#ccc"}`,
            borderRadius: 6,
            padding: isRoot ? "6px 12px" : "4px 10px",
            fontSize: isRoot ? 13 : 12,
            fontWeight: isRoot ? 700 : 400,
            cursor: "pointer",
            userSelect: "none",
            whiteSpace: "nowrap",
            height: isRoot ? 38 : 30,
            boxSizing: "border-box",
            boxShadow: isActive ? "0 0 0 2px rgba(99,102,241,0.3)" : undefined,
            transition: "border-color 0.15s, box-shadow 0.15s",
          }}
          onClick={() => {
            // Left-click = expand/collapse (if has children), otherwise popover
            if (hasChildren) {
              toggleNode();
            } else {
              onNodeClick?.(node);
            }
          }}
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
                color: isCollapsed ? "#5a4a8a" : "#8a7aaa",
                fontSize: 12,
                background: isCollapsed ? "#e8e0f0" : "#f0ecf5",
                borderRadius: 4,
                padding: "2px 6px",
                lineHeight: 1,
                flexShrink: 0,
                fontWeight: 600,
              }}
              title={isCollapsed ? "Expand (left-click) · Info (right-click)" : "Collapse (left-click) · Info (right-click)"}
            >
              {isCollapsed ? "▸" : "▾"}
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
  }, []);

  // Close popover only when zoom actually changes (user zoomed)
  const prevZoomRef = useRef(zoom);
  useEffect(() => {
    if (prevZoomRef.current !== zoom) {
      prevZoomRef.current = zoom;
      setPopoverState(null);
    }
  }, [zoom]);

  const handleNodeClick = useCallback((node: TreeNode) => {
    // Find the SVG foreignObject element for this node
    const el = containerRef.current?.querySelector(
      `[data-node-label="${CSS.escape(node.name)}"]`,
    );
    if (el) {
      const rect = el.getBoundingClientRect();
      setPopoverState({ node, rect });
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

  // Auto fit-to-viewport on first render
  useEffect(() => {
    if (!ready) return;
    const timer = requestAnimationFrame(() => handleFitToView());
    return () => cancelAnimationFrame(timer);
  }, [ready, handleFitToView, tree]);

  // Fix SVG rendering order: move edges (path) before nodes (g > foreignObject)
  // SVG doesn't support z-index; later elements render on top.
  // This must be recursive because react-d3-tree nests <g> groups at every level.
  useEffect(() => {
    if (!containerRef.current) return;

    function reorderEdgesBehindNodes(group: SVGGElement) {
      // Reorder children of this group: paths first, then groups
      const children = Array.from(group.children);
      const paths: Element[] = [];
      const others: Element[] = [];
      for (const child of children) {
        if (child.tagName === "path") paths.push(child);
        else others.push(child);
      }
      // If any path comes after any non-path, reorder
      const needsReorder = paths.some((p) => {
        const pIdx = children.indexOf(p);
        return others.some((o) => children.indexOf(o) < pIdx);
      });
      if (needsReorder) {
        for (const p of paths) group.insertBefore(p, group.firstChild);
      }
      // Recurse into child groups
      for (const child of others) {
        if (child.tagName === "g") reorderEdgesBehindNodes(child as SVGGElement);
      }
    }

    const observer = new MutationObserver(() => {
      const svg = containerRef.current?.querySelector("svg");
      if (!svg) return;
      const rootG = svg.querySelector("g");
      if (!rootG) return;
      reorderEdgesBehindNodes(rootG);
    });
    observer.observe(containerRef.current, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [ready]);

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
          separation={{ siblings: 1.8, nonSiblings: 2.2 }}
          nodeSize={{ x: 320, y: 60 }}
          collapsible
          initialDepth={1}
          pathClassFunc={() => "mindmap-edge"}
          zoomable
          scaleExtent={{ min: 0.2, max: 3 }}
        />
      )}

      {/* Root metadata below tree */}
      {metadata && (
        <div className="absolute bottom-3 left-3 text-[10px] text-muted-foreground bg-background/80 px-2 py-0.5 rounded border border-border/50">
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

      {/* Edge colour + node hover + edge-behind-node fix */}
      <style>{`
        .mindmap-edge { stroke: ${EDGE_COLOR}; stroke-width: 1.5px; fill: none; }
        .mindmap-node:hover { filter: brightness(1.08); box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
        .rd3t-g { transition: transform 200ms ease-out; }
      `}</style>
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
