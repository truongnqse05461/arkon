"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { MindMapTree, type TreeNode } from "./mindmap-tree";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Scope = {
  type: "global" | "department" | "project";
  id: string | null;
  label: string;
};

type MindmapData = {
  id: string;
  title: string;
  tree_json: TreeNode;
  wiki_page_count: number;
  generated_at: string;
};

type PanelState = "collapsed" | "open" | "fullscreen";

type Department = { id: string; name: string };
type Project = { id: string; name: string };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function scopeToParams(scope: Scope): string {
  const p = new URLSearchParams({ scope_type: scope.type });
  if (scope.id) p.set("scope_id", scope.id);
  return p.toString();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MindMapPanel() {
  const [panelState, setPanelState] = useState<PanelState>("open");
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [selectedScope, setSelectedScope] = useState<Scope>({ type: "global", id: null, label: "Global" });
  const [mindmap, setMindmap] = useState<MindmapData | null>(null);
  const [status, setStatus] = useState<"loading" | "empty" | "ready" | "generating" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load scope list once
  useEffect(() => {
    async function loadScopes() {
      const base: Scope[] = [{ type: "global", id: null, label: "Global" }];
      try {
        const [depts, projects] = await Promise.all([
          api<Department[]>("/api/departments"),
          api<Project[]>("/api/projects"),
        ]);
        const deptScopes: Scope[] = depts.map((d) => ({ type: "department" as const, id: d.id, label: d.name }));
        const projScopes: Scope[] = projects.map((p) => ({ type: "project" as const, id: p.id, label: p.name }));
        setScopes([...base, ...deptScopes, ...projScopes]);
      } catch {
        setScopes(base);
      }
    }
    loadScopes();
  }, []);

  // Load mindmap whenever scope changes
  const loadMindmap = useCallback(async (scope: Scope) => {
    setStatus("loading");
    setMindmap(null);
    setErrorMsg(null);
    try {
      const data = await api<MindmapData>(`/api/mindmap?${scopeToParams(scope)}`);
      setMindmap(data);
      setStatus("ready");
    } catch (err: unknown) {
      const apiErr = err as { status?: number; message?: string };
      if (apiErr?.status === 404) {
        setStatus("empty");
      } else {
        setStatus("error");
        setErrorMsg(apiErr?.message ?? "Failed to load MindMap.");
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      setStatus("loading");
      setMindmap(null);
      setErrorMsg(null);
      try {
        const data = await api<MindmapData>(`/api/mindmap?${scopeToParams(selectedScope)}`);
        if (!cancelled) {
          setMindmap(data);
          setStatus("ready");
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const apiErr = err as { status?: number; message?: string };
          if (apiErr?.status === 404) {
            setStatus("empty");
          } else {
            setStatus("error");
            setErrorMsg(apiErr?.message ?? "Failed to load MindMap.");
          }
        }
      }
    }
    run();
    return () => { cancelled = true; };
  }, [selectedScope]);

  const handleGenerate = useCallback(async () => {
    setStatus("generating");
    setErrorMsg(null);
    try {
      const data = await api<MindmapData>("/api/mindmap/generate", {
        method: "POST",
        body: { scope_type: selectedScope.type, scope_id: selectedScope.id },
      });
      setMindmap(data);
      setStatus("ready");
    } catch (err: unknown) {
      const apiErr = err as { message?: string };
      setStatus("error");
      setErrorMsg(apiErr?.message ?? "Generation failed.");
    }
  }, [selectedScope]);

  const handleRegenerate = useCallback(async () => {
    if (!mindmap) return;
    try {
      await api(`/api/mindmap/${mindmap.id}`, { method: "DELETE" });
    } catch {
      // ignore — proceed to regenerate regardless
    }
    await handleGenerate();
  }, [mindmap, handleGenerate]);

  const handleScopeChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value; // "global|" or "department|<id>" or "project|<id>"
    const [type, id] = value.split("|") as ["global" | "department" | "project", string];
    const found = scopes.find((s) => s.type === type && (s.id ?? "") === (id ?? ""));
    if (found) setSelectedScope(found);
  }, [scopes]);

  const scopeValue = `${selectedScope.type}|${selectedScope.id ?? ""}`;
  const isGenerating = status === "generating";

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const header = (inFullscreen = false) => (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30 shrink-0">
      <span className="text-xs font-bold text-foreground flex-shrink-0">
        <span
          className="material-symbols-outlined text-[14px] align-middle mr-1"
          style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
        >
          account_tree
        </span>
        MindMap
      </span>
      <select
        value={scopeValue}
        onChange={handleScopeChange}
        disabled={isGenerating}
        className="flex-1 min-w-0 text-xs border border-border rounded px-1.5 py-0.5 bg-background text-foreground disabled:opacity-50"
      >
        {scopes.map((s) => (
          <option key={`${s.type}|${s.id ?? ""}`} value={`${s.type}|${s.id ?? ""}`}>
            {s.type === "global" ? "🌐 " : s.type === "department" ? "🏢 " : "📁 "}
            {s.label}
          </option>
        ))}
      </select>
      <div className="flex items-center gap-1 flex-shrink-0">
        {inFullscreen && (
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={isGenerating || status === "empty"}
            title="Regenerate"
            className="text-xs text-muted-foreground hover:text-foreground disabled:opacity-40 px-1.5 py-0.5 rounded hover:bg-muted transition-colors"
          >
            <span
              className="material-symbols-outlined text-[14px]"
              style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
            >
              refresh
            </span>
          </button>
        )}
        <button
          type="button"
          onClick={() => setPanelState(panelState === "fullscreen" ? "open" : "fullscreen")}
          title={panelState === "fullscreen" ? "Exit full screen" : "Full screen"}
          disabled={isGenerating}
          className="text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
        >
          <span
            className="material-symbols-outlined text-[15px]"
            style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
          >
            {panelState === "fullscreen" ? "close_fullscreen" : "open_in_full"}
          </span>
        </button>
        {!inFullscreen && (
          <button
            type="button"
            onClick={() => setPanelState("collapsed")}
            title="Collapse"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <span
              className="material-symbols-outlined text-[15px]"
              style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
            >
              chevron_right
            </span>
          </button>
        )}
        {inFullscreen && (
          <button
            type="button"
            onClick={() => setPanelState("open")}
            title="Close"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <span
              className="material-symbols-outlined text-[15px]"
              style={{ fontVariationSettings: "'FILL' 0, 'wght' 300" }}
            >
              close
            </span>
          </button>
        )}
      </div>
    </div>
  );

  const body = () => {
    if (status === "loading") {
      return (
        <div className="flex-1 flex items-center justify-center gap-2 text-muted-foreground text-sm">
          <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
          Loading…
        </div>
      );
    }
    if (status === "empty") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
          <p className="text-xs text-muted-foreground text-center">No MindMap for this scope yet.</p>
          <button
            type="button"
            onClick={handleGenerate}
            className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs font-medium hover:bg-primary/90 transition-colors"
          >
            Generate MindMap
          </button>
        </div>
      );
    }
    if (status === "generating") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center gap-2">
          <span className="material-symbols-outlined text-xl text-primary animate-spin">progress_activity</span>
          <p className="text-xs text-muted-foreground">Analysing wiki pages…</p>
        </div>
      );
    }
    if (status === "error") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
          <p className="text-xs text-destructive text-center">{errorMsg}</p>
          <button
            type="button"
            onClick={() => loadMindmap(selectedScope)}
            className="px-3 py-1.5 bg-muted text-foreground rounded-md text-xs hover:bg-muted/80 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    // ready
    return (
      <div className="flex-1 min-h-0 overflow-hidden">
        {mindmap && <MindMapTree tree={mindmap.tree_json} />}
      </div>
    );
  };

  const cacheFooter =
    mindmap && status === "ready" ? (
      <div className="px-3 py-1.5 border-t border-border text-[10px] text-muted-foreground shrink-0">
        {mindmap.wiki_page_count} pages · generated {formatAge(mindmap.generated_at)}
      </div>
    ) : null;

  // ---------------------------------------------------------------------------
  // Panel states
  // ---------------------------------------------------------------------------

  if (panelState === "collapsed") {
    return (
      <div className="w-8 flex-shrink-0 flex flex-col items-center pt-3 gap-2 bg-muted/20 border-l border-border">
        <span
          className="text-[9px] font-bold text-muted-foreground tracking-widest"
          style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
        >
          MINDMAP
        </span>
        <button
          type="button"
          onClick={() => setPanelState("open")}
          title="Open MindMap"
          className="w-6 h-6 flex items-center justify-center bg-primary text-primary-foreground rounded text-xs hover:bg-primary/90 transition-colors"
        >
          <span
            className="material-symbols-outlined text-[14px]"
            style={{ fontVariationSettings: "'FILL' 0, 'wght' 400" }}
          >
            chevron_left
          </span>
        </button>
      </div>
    );
  }

  if (panelState === "fullscreen") {
    return (
      <div className="fixed inset-0 z-50 bg-background flex flex-col">
        {header(true)}
        {body()}
        {cacheFooter}
      </div>
    );
  }

  // open
  return (
    <div className="w-[340px] flex-shrink-0 flex flex-col border-l border-border bg-background">
      {header(false)}
      {body()}
      {cacheFooter}
    </div>
  );
}
