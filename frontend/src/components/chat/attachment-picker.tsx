"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";

export type Attachment = {
  type: "wiki" | "source";
  slug?: string;
  id?: string;
  label: string;
};

type WikiPageResult = { slug: string; title: string };
type SourceResult = { id: string; title: string; file_name?: string };

type AttachmentPickerProps = {
  onAdd: (attachment: Attachment) => void;
};

export function AttachmentPicker({ onAdd }: AttachmentPickerProps) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"wiki" | "source">("wiki");
  const [query, setQuery] = useState("");
  const [wikiResults, setWikiResults] = useState<WikiPageResult[]>([]);
  const [sourceResults, setSourceResults] = useState<SourceResult[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (q: string, t: "wiki" | "source") => {
    if (!q.trim()) {
      setWikiResults([]);
      setSourceResults([]);
      return;
    }
    setLoading(true);
    try {
      if (t === "wiki") {
        const results = await api<WikiPageResult[]>(`/api/wiki/pages?search=${encodeURIComponent(q)}&limit=10`);
        setWikiResults(Array.isArray(results) ? results : []);
      } else {
        const results = await api<{ items: SourceResult[] }>(`/api/sources?search=${encodeURIComponent(q)}&page_size=10`);
        setSourceResults(results?.items ?? []);
      }
    } catch {
      // silently fail — picker shows empty on error
    } finally {
      setLoading(false);
    }
  }, []);

  const handleQueryChange = (v: string) => {
    setQuery(v);
    search(v, tab);
  };

  const handleTabChange = (t: "wiki" | "source") => {
    setTab(t);
    search(query, t);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        title="Attach wiki page or document"
        className="w-8 h-8 flex items-center justify-center border border-border rounded-md bg-background hover:bg-muted transition-colors text-muted-foreground shrink-0"
      >
        <span
          className="material-symbols-outlined text-[18px]"
          style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 18" }}
        >
          attach_file
        </span>
      </button>
    );
  }

  return (
    <div className="relative shrink-0">
      <button
        onClick={() => setOpen(false)}
        className="w-8 h-8 flex items-center justify-center border border-border rounded-md bg-muted transition-colors text-muted-foreground"
      >
        <span className="material-symbols-outlined text-[18px]">attach_file</span>
      </button>

      <div className="absolute bottom-10 left-0 w-72 bg-background border border-border rounded-lg shadow-lg z-50">
        {/* Tabs */}
        <div className="flex border-b border-border">
          {(["wiki", "source"] as const).map((t) => (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                tab === t
                  ? "border-b-2 border-foreground text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "wiki" ? "Wiki pages" : "Documents"}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="p-2">
          <input
            autoFocus
            type="text"
            placeholder={tab === "wiki" ? "Search wiki pages…" : "Search documents…"}
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            className="w-full px-2 py-1.5 text-xs border border-border rounded-md bg-muted/30 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* Results */}
        <div className="max-h-48 overflow-y-auto">
          {loading && (
            <div className="px-3 py-2 text-xs text-muted-foreground">Searching…</div>
          )}
          {!loading && tab === "wiki" && wikiResults.map((r) => (
            <button
              key={r.slug}
              onClick={() => {
                onAdd({ type: "wiki", slug: r.slug, label: r.title || r.slug });
                setOpen(false);
                setQuery("");
              }}
              className="w-full text-left px-3 py-2 hover:bg-muted text-xs transition-colors"
            >
              <div className="font-medium truncate">{r.title}</div>
              <div className="text-muted-foreground font-mono">{r.slug}</div>
            </button>
          ))}
          {!loading && tab === "source" && sourceResults.map((r) => (
            <button
              key={r.id}
              onClick={() => {
                onAdd({ type: "source", id: r.id, label: r.title || r.file_name || r.id });
                setOpen(false);
                setQuery("");
              }}
              className="w-full text-left px-3 py-2 hover:bg-muted text-xs transition-colors"
            >
              <div className="font-medium truncate">{r.title || r.file_name}</div>
              <div className="text-muted-foreground font-mono truncate">{r.id}</div>
            </button>
          ))}
          {!loading && query && tab === "wiki" && wikiResults.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">No wiki pages found.</div>
          )}
          {!loading && query && tab === "source" && sourceResults.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">No documents found.</div>
          )}
        </div>
      </div>
    </div>
  );
}
