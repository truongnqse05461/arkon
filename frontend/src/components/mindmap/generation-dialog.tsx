"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Scope = {
  type: "global" | "department" | "project";
  id: string | null;
  label: string;
};

type Source = {
  id: string;
  title: string | null;
  source_type: string;
};

type GenerationDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGenerated: () => void;
};

export function GenerationDialog({ open, onOpenChange, onGenerated }: GenerationDialogProps) {
  const [scopes, setScopes] = useState<Scope[]>([{ type: "global", id: null, label: "Global" }]);
  const [selectedScope, setSelectedScope] = useState<Scope>({ type: "global", id: null, label: "Global" });
  const [sourceType, setSourceType] = useState<"wiki" | "source_docs">("wiki");
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingSources, setLoadingSources] = useState(false);

  useEffect(() => {
    if (!open) return;
    async function loadScopes() {
      const base: Scope[] = [{ type: "global", id: null, label: "Global" }];
      try {
        const [depts, projects] = await Promise.all([
          api<{ id: string; name: string }[]>("/api/departments"),
          api<{ id: string; name: string }[]>("/api/projects"),
        ]);
        const deptScopes: Scope[] = depts.map((d) => ({ type: "department" as const, id: d.id, label: d.name }));
        const projScopes: Scope[] = projects.map((p) => ({ type: "project" as const, id: p.id, label: p.name }));
        setScopes([...base, ...deptScopes, ...projScopes]);
      } catch {
        setScopes(base);
      }
    }
    loadScopes();
  }, [open]);

  useEffect(() => {
    if (!open || sourceType !== "source_docs") return;
    async function loadSources() {
      setLoadingSources(true);
      try {
        const qs = selectedScope.id
          ? `scope_type=${selectedScope.type}&scope_id=${selectedScope.id}`
          : `scope_type=${selectedScope.type}`;
        const data = await api<Source[]>(`/api/sources?${qs}`);
        setSources(Array.isArray(data) ? data : []);
      } catch {
        setSources([]);
      } finally {
        setLoadingSources(false);
      }
    }
    loadSources();
  }, [open, sourceType, selectedScope]);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    try {
      await api("/api/mindmap/generate", {
        method: "POST",
        body: {
          scope_type: selectedScope.type,
          scope_id: selectedScope.id,
          source_type: sourceType,
          source_ids: sourceType === "source_docs" ? selectedSourceIds : undefined,
          instruction: instruction.trim() || undefined,
        },
      });
      onGenerated();
      onOpenChange(false);
      setInstruction("");
      setSelectedSourceIds([]);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  }, [selectedScope, sourceType, selectedSourceIds, instruction, onGenerated, onOpenChange]);

  const toggleSource = (id: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-lg w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">Generate Mindmap</h2>
          <button type="button" onClick={() => onOpenChange(false)} className="text-muted-foreground hover:text-foreground transition-colors">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">Scope *</label>
            <select
              value={`${selectedScope.type}|${selectedScope.id ?? ""}`}
              onChange={(e) => {
                const [type, id] = e.target.value.split("|");
                const found = scopes.find((s) => s.type === type && (s.id ?? "") === id);
                if (found) setSelectedScope(found);
              }}
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background"
            >
              {scopes.map((s) => (
                <option key={`${s.type}|${s.id ?? ""}`} value={`${s.type}|${s.id ?? ""}`}>
                  {s.type === "global" ? "\u{1F310}" : s.type === "department" ? "\u{1F3E2}" : "\u{1F4C1}"} {s.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Source *</label>
            <select
              value={sourceType}
              onChange={(e) => {
                setSourceType(e.target.value as "wiki" | "source_docs");
                setSelectedSourceIds([]);
              }}
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background"
            >
              <option value="wiki">Wiki Pages</option>
              <option value="source_docs">Source Documents</option>
            </select>
          </div>

          {sourceType === "source_docs" && (
            <div>
              <label className="block text-sm font-medium mb-1.5">Select Documents *</label>
              {loadingSources ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                  <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                  Loading documents...
                </div>
              ) : sources.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">No documents found in this scope.</p>
              ) : (
                <div className="border border-border rounded-md max-h-40 overflow-y-auto">
                  {sources.map((src) => (
                    <label key={src.id} className="flex items-center gap-2 px-3 py-2 hover:bg-muted/50 cursor-pointer border-b border-border last:border-0">
                      <input type="checkbox" checked={selectedSourceIds.includes(src.id)} onChange={() => toggleSource(src.id)} className="rounded" />
                      <span className="text-sm truncate">{src.title || "Untitled"}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5">Instruction (optional)</label>
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="e.g., Focus on API architecture and integration patterns"
              maxLength={500}
              rows={3}
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background resize-none"
            />
            <p className="text-xs text-muted-foreground mt-1">{instruction.length}/500 characters</p>
          </div>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-border">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleGenerate} disabled={loading || (sourceType === "source_docs" && selectedSourceIds.length === 0)}>
            {loading ? (
              <>
                <span className="material-symbols-outlined text-sm animate-spin mr-1.5">progress_activity</span>
                Generating...
              </>
            ) : "Generate"}
          </Button>
        </div>
      </div>
    </div>
  );
}
