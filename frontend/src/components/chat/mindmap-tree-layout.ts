"use client";

import type { Orientation, PathFunction, TreeLinkDatum } from "react-d3-tree";
import { wikiTypeColor } from "@/components/wiki/wiki-type-badge";

import type { TreeNode } from "./mindmap-tree";

export const ROOT_COLOR = "#c2b8e8";
export const ROOT_TEXT = "#3a2a6a";
export const DEFAULT_BASE = "#9ca3af";
export const EDGE_COLOR = "#b0a8d0";

const LINK_GAP = 4;
const MAX_NODE_WIDTH = 260;

export function getNodeStyle(nodeDatum: TreeNode, isRoot: boolean) {
  if (isRoot) return { bg: ROOT_COLOR, border: ROOT_COLOR, text: ROOT_TEXT };
  const type = nodeDatum.page_type;
  const base = type ? wikiTypeColor(type) : DEFAULT_BASE;
  if (nodeDatum.page_slug) {
    return { bg: `${base}1a`, border: `${base}40`, text: base };
  }
  return { bg: `${DEFAULT_BASE}1a`, border: `${DEFAULT_BASE}40`, text: DEFAULT_BASE };
}

export function getTypeIcon(pageType?: string): string | null {
  const icons: Record<string, string> = {
    entity: "person",
    concept: "lightbulb",
    topic: "topic",
    source: "description",
  };
  return icons[pageType ?? ""] ?? null;
}

export function getNodeWidth(node: TreeNode, isRoot: boolean): number {
  const hasChildren = Array.isArray(node.children) && node.children.length > 0;
  const typeIcon = getTypeIcon(node.page_slug ? node.page_type : undefined);
  const charWidth = isRoot ? 9 : 8;
  const iconSpace = typeIcon ? 18 : 0;
  return Math.min(
    MAX_NODE_WIDTH,
    Math.max(100, node.name.length * charWidth + (hasChildren ? 40 : 20) + iconSpace + 10),
  );
}

function pointFor(linkNode: TreeLinkDatum["source"], side: "source" | "target") {
  const node = linkNode.data as unknown as TreeNode;
  const isRoot = linkNode.depth === 0;
  const nodeWidth = getNodeWidth(node, isRoot);
  const xOffset = side === "source" ? nodeWidth + LINK_GAP : -LINK_GAP;

  return {
    x: linkNode.y + xOffset,
    y: linkNode.x,
  };
}

export const mindmapPathFunc: PathFunction = (linkData: TreeLinkDatum, orientation: Orientation) => {
  if (orientation !== "horizontal") {
    const { source, target } = linkData;
    return `M${source.x},${source.y}L${target.x},${target.y}`;
  }

  const source = pointFor(linkData.source, "source");
  const target = pointFor(linkData.target, "target");
  const midX = source.x + (target.x - source.x) / 2;

  return [
    `M${source.x},${source.y}`,
    `C${midX},${source.y}`,
    `${midX},${target.y}`,
    `${target.x},${target.y}`,
  ].join(" ");
};
