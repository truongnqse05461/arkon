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
