"use client";

import { useEffect } from "react";
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

const POPOVER_MAX_WIDTH = 280;
const POPOVER_PADDING = 12;

export function MindmapNodePopover({
  node,
  anchorRect,
  onOpenPage,
  onAskChat,
  onClose,
}: PopoverProps) {
  // Global Escape key handler (works even when focus is inside the popover)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // SSR guard – window is undefined during server-side rendering
  if (typeof window === "undefined") return null;

  const hasPage = Boolean(node.page_slug);
  const typeIcon = hasPage ? wikiTypeIcon(node.page_type ?? "") : "radio_button_unchecked";
  const typeColor = hasPage ? wikiTypeColor(node.page_type ?? "") : "#9ca3af";
  const typeLabel = hasPage ? (node.page_type ?? "page") : "unlinked";

  // Position: prefer right of node, flip left if not enough space
  const spaceRight = window.innerWidth - anchorRect.right;
  const flipLeft = spaceRight < POPOVER_MAX_WIDTH + POPOVER_PADDING * 2;
  const left = flipLeft
    ? Math.max(POPOVER_PADDING, anchorRect.left - POPOVER_MAX_WIDTH - 8)
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
        tabIndex={-1}
      />
      {/* Popover */}
      <div
        className="fixed z-50 min-w-[200px] max-w-[280px] rounded-lg border border-border bg-popover text-popover-foreground shadow-lg overflow-hidden animate-in fade-in-0 zoom-in-95"
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
