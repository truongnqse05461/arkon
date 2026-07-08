"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

type MindmapSummary = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  title: string;
  source_type: string;
  wiki_page_count: number;
  generated_at: string;
};

type MindmapListProps = {
  onView: (mindmap: MindmapSummary) => void;
  onRegenerate: (mindmap: MindmapSummary) => void;
  onDelete: (mindmap: MindmapSummary) => void;
  refreshKey: number;
};

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function scopeLabel(scopeType: string, scopeId: string | null): string {
  if (scopeType === "global") return "🌐 Global";
  if (scopeType === "department") return "🏢 Department";
  if (scopeType === "project") return "🏁 Project";
  return scopeType;
}

export function MindmapList({ onView, onRegenerate, onDelete, refreshKey }: MindmapListProps) {
  const [mindmaps, setMindmaps] = useState<MindmapSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchMindmaps = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<MindmapSummary[]>("/api/mindmaps");
      setMindmaps(Array.isArray(data) ? data : []);
    } catch {
      setMindmaps([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMindmaps();
  }, [fetchMindmaps, refreshKey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="material-symbols-outlined text-3xl text-muted-foreground animate-spin">
          progress_activity
        </span>
      </div>
    );
  }

  if (mindmaps.length === 0) {
    return null;
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/50 border-b border-border">
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Scope</th>
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Source</th>
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Pages</th>
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Generated</th>
            <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">Actions</th>
          </tr>
        </thead>
        <tbody>
          {mindmaps.map((mm) => (
            <tr key={mm.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
              <td className="px-4 py-3">
                <span className="font-medium">{scopeLabel(mm.scope_type, mm.scope_id)}</span>
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted">
                  {mm.source_type === "source_docs" ? "Source Doc" : "Wiki"}
                </span>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{mm.wiki_page_count}</td>
              <td className="px-4 py-3 text-muted-foreground">{formatAge(mm.generated_at)}</td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    onClick={() => onView(mm)}
                    title="View"
                    className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <span className="material-symbols-outlined text-[18px]">visibility</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onRegenerate(mm)}
                    title="Regenerate"
                    className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <span className="material-symbols-outlined text-[18px]">refresh</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(mm)}
                    title="Delete"
                    className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <span className="material-symbols-outlined text-[18px]">delete</span>
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
