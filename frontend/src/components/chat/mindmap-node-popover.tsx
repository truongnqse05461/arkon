"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";
import type { TreeNode } from "./mindmap-tree";

type PopoverProps = {
  node: TreeNode;
  anchorRect: DOMRect;
  onOpenPage: (slug: string) => void;
  onAskChat: (name: string) => void;
  onClose: () => void;
};

const POPOVER_MAX_WIDTH = 320;
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

  const sources = node.sources ?? [];
  const hasSources = sources.length > 0;

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
      window.innerHeight - 200,
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
        className="fixed z-50 min-w-[220px] max-w-[320px] rounded-lg border border-border bg-popover text-popover-foreground shadow-lg overflow-hidden animate-in fade-in-0 zoom-in-95"
        style={{ left, top }}
        role="dialog"
        aria-label={`Node: ${node.name}`}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30">
          <span
            className="material-symbols-outlined shrink-0"
            style={{ fontSize: 16, color: hasSources ? "#6366f1" : "#9ca3af" }}
          >
            {hasSources ? "description" : "radio_button_unchecked"}
          </span>
          <span
            className="text-sm font-medium truncate flex-1"
            title={node.name}
          >
            {node.name}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
            aria-label="Close"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
          </button>
        </div>

        {/* Summary */}
        {node.summary ? (
          <div className="px-3 py-2 max-h-40 overflow-y-auto">
            <p className="text-xs text-foreground/80 leading-relaxed">
              {node.summary}
            </p>
          </div>
        ) : (
          <div className="px-3 py-2">
            <p className="text-xs text-muted-foreground italic">No summary available</p>
          </div>
        )}

        {/* Citations */}
        {hasSources && (
          <div className="px-3 py-2 flex flex-wrap gap-1.5 border-t border-border">
            {sources.map((src, i) => {
              const isSourceDoc = src.type === "source_doc";
              const href = isSourceDoc ? "#" : `/wiki/${src.slug}`;
              const icon = isSourceDoc ? "description" : "menu_book";
              const truncatedTitle = src.title.length > 30
                ? src.title.slice(0, 27) + "..."
                : src.title;

              return (
                <a
                  key={i}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-1 text-[11px] bg-muted rounded hover:bg-muted/80 transition-colors max-w-[140px]"
                  title={src.title}
                  onClick={(e) => {
                    if (isSourceDoc) {
                      e.preventDefault();
                      // Source docs don't have a viewer yet
                    } else {
                      e.preventDefault();
                      onOpenPage(src.slug);
                    }
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 12, flexShrink: 0 }}>
                    {icon}
                  </span>
                  <span className="truncate">{truncatedTitle}</span>
                </a>
              );
            })}
          </div>
        )}

        {/* Actions */}
        <div className="px-3 py-2 border-t border-border bg-muted/20">
          <button
            type="button"
            onClick={() => onAskChat(node.name)}
            className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 bg-muted text-foreground rounded text-xs font-medium hover:bg-muted/80 transition-colors border border-border"
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
