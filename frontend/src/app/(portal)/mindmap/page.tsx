"use client";

import { useState, useCallback } from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { MindmapList } from "@/components/mindmap/mindmap-list";
import { MindmapViewer } from "@/components/mindmap/mindmap-viewer";
import { GenerationDialog } from "@/components/mindmap/generation-dialog";
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

export default function MindmapPage() {
  const [viewerMindmap, setViewerMindmap] = useState<MindmapData | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [confirmDelete, setConfirmDelete] = useState<MindmapSummary | null>(null);
  const [generationOpen, setGenerationOpen] = useState(false);

  const handleView = useCallback(async (mm: MindmapSummary) => {
    try {
      const data = await api<MindmapData>(`/api/mindmap?scope_type=${mm.scope_type}${mm.scope_id ? `&scope_id=${mm.scope_id}` : ""}`);
      setViewerMindmap(data);
    } catch {
      // Handle error
    }
  }, []);

  const handleRegenerate = useCallback(async (mm: MindmapSummary) => {
    if (!confirm(`Regenerate mindmap for ${mm.scope_type}? This will replace the current version.`)) return;
    try {
      await api(`/api/mindmap/${mm.id}`, { method: "DELETE" });
      await api("/api/mindmap/generate", {
        method: "POST",
        body: { scope_type: mm.scope_type, scope_id: mm.scope_id, source_type: mm.source_type },
      });
      setRefreshKey((k) => k + 1);
    } catch {
      // Handle error
    }
  }, []);

  const handleDelete = useCallback(async () => {
    if (!confirmDelete) return;
    try {
      await api(`/api/mindmap/${confirmDelete.id}`, { method: "DELETE" });
      setConfirmDelete(null);
      setViewerMindmap(null);
      setRefreshKey((k) => k + 1);
    } catch {
      // Handle error
    }
  }, [confirmDelete]);

  const handleGenerated = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  if (viewerMindmap) {
    return (
      <MindmapViewer
        mindmap={viewerMindmap}
        onBack={() => setViewerMindmap(null)}
        onRegenerate={() => {
          setViewerMindmap(null);
          handleRegenerate({
            id: viewerMindmap.id,
            scope_type: viewerMindmap.scope_type,
            scope_id: viewerMindmap.scope_id,
            title: viewerMindmap.title,
            source_type: viewerMindmap.source_type,
            wiki_page_count: viewerMindmap.wiki_page_count,
            generated_at: viewerMindmap.generated_at,
          });
        }}
        onDelete={() => {
          setViewerMindmap(null);
          setConfirmDelete({
            id: viewerMindmap.id,
            scope_type: viewerMindmap.scope_type,
            scope_id: viewerMindmap.scope_id,
            title: viewerMindmap.title,
            source_type: viewerMindmap.source_type,
            wiki_page_count: viewerMindmap.wiki_page_count,
            generated_at: viewerMindmap.generated_at,
          });
        }}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Mindmaps"
        description="Generate and manage knowledge maps from your wiki or source documents."
        action={
          <Button onClick={() => setGenerationOpen(true)} className="gap-2">
            <span className="material-symbols-outlined text-base">add</span>
            Generate
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <MindmapList
          onView={handleView}
          onRegenerate={handleRegenerate}
          onDelete={setConfirmDelete}
          refreshKey={refreshKey}
        />

        {refreshKey === 0 && (
          <EmptyState
            icon="account_tree"
            title="No mindmaps yet"
            description="Generate a knowledge map from Wiki pages or source documents."
            action={
              <Button onClick={() => setGenerationOpen(true)} className="gap-2 mt-2">
                <span className="material-symbols-outlined text-base">add</span>
                Generate Mindmap
              </Button>
            }
          />
        )}
      </div>

      <GenerationDialog open={generationOpen} onOpenChange={setGenerationOpen} onGenerated={handleGenerated} />

      {/* Delete confirmation dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-lg shadow-lg p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold mb-2">Delete Mindmap</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Are you sure you want to delete this mindmap? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
