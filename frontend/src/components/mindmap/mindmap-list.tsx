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

type Scope = {
  type: string;
  id: string | null;
  name: string;
};

type MindmapListProps = {
  onView: (mindmap: MindmapSummary) => void;
  onRegenerate: (mindmap: MindmapSummary) => void;
  onDelete: (mindmap: MindmapSummary) => void;
  refreshKey: number;
  onDataLoaded: (hasItems: boolean) => void;
};

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

export function MindmapList({ onView, onRegenerate, onDelete, refreshKey, onDataLoaded }: MindmapListProps) {
  const [mindmaps, setMindmaps] = useState<MindmapSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [scopes, setScopes] = useState<Scope[]>([]);

  // Load scope names for display
  useEffect(() => {
    async function loadScopes() {
      try {
        const [depts, projects] = await Promise.all([
          api<{ id: string; name: string }[]>("/api/departments"),
          api<{ id: string; name: string }[]>("/api/projects"),
        ]);
        const allScopes: Scope[] = [
          { type: "global", id: null, name: "Global" },
          ...depts.map((d) => ({ type: "department", id: d.id, name: d.name })),
          ...projects.map((p) => ({ type: "project", id: p.id, name: p.name })),
        ];
        setScopes(allScopes);
      } catch {
        setScopes([{ type: "global", id: null, name: "Global" }]);
      }
    }
    loadScopes();
  }, []);

  const fetchMindmaps = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<MindmapSummary[]>("/api/mindmaps");
      const items = Array.isArray(data) ? data : [];
      setMindmaps(items);
      onDataLoaded(items.length > 0);
    } catch {
      setMindmaps([]);
      onDataLoaded(false);
    } finally {
      setLoading(false);
    }
  }, [onDataLoaded]);

  useEffect(() => {
    fetchMindmaps();
  }, [fetchMindmaps, refreshKey]);

  const getScopeLabel = (scopeType: string, scopeId: string | null): string => {
    const scope = scopes.find((s) => s.type === scopeType && (s.id ?? null) === (scopeId ?? null));
    if (scope) {
      const icon = scopeType === "global" ? "🌐" : scopeType === "department" ? "🏢" : "📁";
      return `${icon} ${scope.name}`;
    }
    if (scopeType === "global") return "🌐 Global";
    if (scopeType === "department") return "🏢 Department";
    if (scopeType === "project") return "📁 Project";
    return scopeType;
  };

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
                <span className="font-medium">{getScopeLabel(mm.scope_type, mm.scope_id)}</span>
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
