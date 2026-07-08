"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { CustomNodeElementProps } from "react-d3-tree";
import { MindmapNodePopover } from "./mindmap-node-popover";
import {
  EDGE_COLOR,
  getNodeStyle,
  getNodeWidth,
  getTypeIcon,
  mindmapPathFunc,
} from "./mindmap-tree-layout";

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

function makeRenderNode(
  onNodeClick?: (node: TreeNode, anchorRect: DOMRect) => void,
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
    const nodeWidth = getNodeWidth(node, isRoot);
    const fh = isRoot ? 44 : 34;
    const fy = isRoot ? -20 : -16;

    return (
      <>
        <rect
          x={0}
          y={fy}
          width={nodeWidth}
          height={fh}
          rx={8}
          ry={8}
          fill={style.bg}
          stroke={isActive ? "#6366f1" : style.border ?? "#ccc"}
          strokeWidth={isCollapsed ? 1.5 : 1.5}
          strokeDasharray={isCollapsed ? "4 2" : undefined}
        />
        <foreignObject x={0} y={fy} width={nodeWidth} height={fh}>
          <div
            // @ts-expect-error xmlns needed for SVG foreignObject
            xmlns="http://www.w3.org/1999/xhtml"
            className="mindmap-node"
            data-node-label={label}
            onContextMenu={(e) => {
              e.preventDefault();
              onNodeClick?.(node, e.currentTarget.getBoundingClientRect());
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              background: "transparent",
              padding: isRoot ? "6px 12px" : "4px 10px",
              fontSize: isRoot ? 13 : 12,
              fontWeight: isRoot ? 700 : 400,
              cursor: "pointer",
              userSelect: "none",
              whiteSpace: "nowrap",
              height: isRoot ? 38 : 30,
              boxSizing: "border-box",
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onClick={(e) => {
              if (hasChildren) {
                toggleNode();
              } else {
                onNodeClick?.(node, e.currentTarget.getBoundingClientRect());
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
      </>
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

  const handleNodeClick = useCallback((node: TreeNode, rect: DOMRect) => {
    setPopoverState({ node, rect });
  }, []);

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
          pathFunc={mindmapPathFunc}
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

      {/* Edge colour + smooth zoom */}
      <style>{`
        .mindmap-edge { stroke: ${EDGE_COLOR}; stroke-width: 1.5px; fill: none; }
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
