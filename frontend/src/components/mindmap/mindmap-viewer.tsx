"use client";

import { useState, useCallback } from "react";
import { ChatBubble } from "@/components/chat/chat-bubble";
import { MindMapTree } from "@/components/chat/mindmap-tree";
import { formatAge } from "@/lib/format-age";

type MindmapData = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  tree_json: Record<string, unknown>;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

type MindmapViewerProps = {
  mindmap: MindmapData;
  onBack: () => void;
  onRegenerate: () => void;
  onDelete: () => void;
};

export function MindmapViewer({ mindmap, onBack, onRegenerate, onDelete }: MindmapViewerProps) {
  const [prefillInput, setPrefillInput] = useState<string | null>(null);

  const handleAskInChat = useCallback((name: string) => {
    setPrefillInput(`Explain about "${name}"`);
  }, []);

  const handleNodeClick = useCallback((node: { name: string; page_slug?: string }) => {
    if (node.page_slug) {
      if (node.page_slug.startsWith("source:")) {
        return;
      }
      window.open(`/wiki/${node.page_slug}`, "_blank");
    } else {
      handleAskInChat(node.name);
    }
  }, [handleAskInChat]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border shrink-0">
        <button type="button" onClick={onBack} className="text-muted-foreground hover:text-foreground transition-colors" title="Back to list">
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold truncate">{mindmap.title}</h2>
          <p className="text-xs text-muted-foreground">
            {mindmap.wiki_page_count} {mindmap.wiki_page_count === 1 ? "page" : "pages"} · {mindmap.source_type === "source_docs" ? "Source Docs" : "Wiki"} · {formatAge(mindmap.generated_at)}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={onRegenerate} title="Regenerate" className="p-2 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors">
            <span className="material-symbols-outlined text-[20px]">refresh</span>
          </button>
          <button type="button" onClick={onDelete} title="Delete" className="p-2 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors">
            <span className="material-symbols-outlined text-[20px]">delete</span>
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <MindMapTree
          tree={mindmap.tree_json as any}
          onNodeClick={handleNodeClick}
          metadata={{ pageCount: mindmap.wiki_page_count, generatedAt: mindmap.generated_at }}
        />
      </div>

      <ChatBubble
        scopeType={mindmap.scope_type}
        scopeId={mindmap.scope_id}
        prefillInput={prefillInput}
        onPrefillConsumed={() => setPrefillInput(null)}
      />
    </div>
  );
}
