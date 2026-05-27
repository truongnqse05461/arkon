"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { WikiPageDetail } from "@/types/wiki";
import { BilingualPageView } from "@/components/wiki/bilingual-page-view";

type SourceDetail = {
  id: string;
  title?: string;
  file_name?: string;
  knowledge_type?: string;
  status?: string;
  download_url?: string;
};

type CitationPanelProps = {
  slug: string | null;
  onClose: () => void;
};

export function CitationPanel({ slug, onClose }: CitationPanelProps) {
  const [page, setPage] = useState<WikiPageDetail | null>(null);
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const maybeSourceId = slug?.startsWith("source/") ? slug.slice("source/".length) : null;
  const isSource = maybeSourceId != null && UUID_RE.test(maybeSourceId);
  const sourceId = isSource ? maybeSourceId : null;

  useEffect(() => {
    if (!slug) return;
    let isMounted = true;
    setPage(null);
    setSource(null);
    setError(null);
    setLoading(true);

    if (isSource && sourceId) {
      api<SourceDetail>(`/api/sources/${encodeURIComponent(sourceId)}`)
        .then((data) => { if (isMounted) setSource(data); })
        .catch(() => { if (isMounted) setError("Source not found or not accessible."); })
        .finally(() => { if (isMounted) setLoading(false); });
    } else {
      api<WikiPageDetail>(`/api/wiki/pages/${slug.split("/").map(encodeURIComponent).join("/")}`)
        .then((data) => { if (isMounted) setPage(data); })
        .catch(() => { if (isMounted) setError("Page not found or not accessible."); })
        .finally(() => { if (isMounted) setLoading(false); });
    }
    return () => { isMounted = false; };
  }, [slug, isSource, sourceId]);

  if (!slug) return null;

  const panelLabel = isSource
    ? (source?.title || source?.file_name || sourceId || slug)
    : slug.split("/").join(" / ");

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
        aria-label={panelLabel}
        className="fixed right-0 top-0 z-50 h-full w-[480px] max-w-full bg-background border-l border-border shadow-xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
          <span className="text-xs text-muted-foreground font-mono flex-1 truncate">
            {panelLabel}
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
          {source && (
            <div className="space-y-3">
              <div>
                <p className="text-base font-semibold text-foreground">{source.title || source.file_name}</p>
                {source.title && source.file_name && source.title !== source.file_name && (
                  <p className="text-xs text-muted-foreground mt-0.5">{source.file_name}</p>
                )}
              </div>
              <dl className="text-sm space-y-1">
                {source.knowledge_type && (
                  <div className="flex gap-2">
                    <dt className="text-muted-foreground w-28 shrink-0">Knowledge type</dt>
                    <dd className="capitalize">{source.knowledge_type}</dd>
                  </div>
                )}
                {source.status && (
                  <div className="flex gap-2">
                    <dt className="text-muted-foreground w-28 shrink-0">Status</dt>
                    <dd className="capitalize">{source.status}</dd>
                  </div>
                )}
              </dl>
              {source.download_url && (
                <a
                  href={source.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                >
                  <span className="material-symbols-outlined text-[14px]">download</span>
                  Download original
                </a>
              )}
            </div>
          )}
          {page && (
            <div className="space-y-3">
              <div>
                <h2 className="text-base font-semibold text-foreground">{page.title}</h2>
                {page.title_translated && page.title_translated !== page.title && (
                  <p className="text-xs text-muted-foreground mt-0.5">{page.title_translated}</p>
                )}
              </div>
              <BilingualPageView
                title={page.title}
                contentMd={page.content_md}
                titleTranslated={page.title_translated ?? null}
                contentMdTranslated={page.content_md_translated ?? null}
                sourceLanguage={page.source_language ?? null}
                targetLanguage={page.target_language ?? null}
              />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
