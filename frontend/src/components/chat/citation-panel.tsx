"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import type { WikiPageDetail } from "@/types/wiki";
import { preprocessWikilinks, wikiUrlTransform } from "@/components/wiki/wiki-content";

type CitationPanelProps = {
  slug: string | null;
  onClose: () => void;
};

export function CitationPanel({ slug, onClose }: CitationPanelProps) {
  const [page, setPage] = useState<WikiPageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    let isMounted = true;
    setPage(null);
    setError(null);
    setLoading(true);
    api<WikiPageDetail>(`/api/wiki/pages/${slug.split("/").map(encodeURIComponent).join("/")}`)
      .then((data) => { if (isMounted) setPage(data); })
      .catch(() => { if (isMounted) setError("Page not found or not accessible."); })
      .finally(() => { if (isMounted) setLoading(false); });
    return () => { isMounted = false; };
  }, [slug]);

  if (!slug) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Wiki page: ${slug}`}
        className="fixed right-0 top-0 z-50 h-full w-[480px] max-w-full bg-background border-l border-border shadow-xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
          <span className="text-xs text-muted-foreground font-mono flex-1 truncate">
            {slug.split("/").join(" / ")}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close panel"
          >
            <span
              className="material-symbols-outlined text-[18px]"
              style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 18" }}
            >
              close
            </span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <span className="material-symbols-outlined text-sm animate-spin">
                progress_activity
              </span>
              Loading…
            </div>
          )}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          {page && (
            <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none">
              <h1 className="text-base font-semibold mb-3">{page.title}</h1>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                urlTransform={wikiUrlTransform}
              >
                {preprocessWikilinks(page.content_md)}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
