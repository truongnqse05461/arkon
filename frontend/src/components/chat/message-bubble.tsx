"use client";

import type { UIMessage } from "ai";
import type { Element } from "hast";
import { useMemo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import { ToolCallRow } from "./tool-call-row";
import { extractCitations, type Citation } from "./citation-utils";

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    sup: [...(defaultSchema.attributes?.sup ?? []), "dataSlug", "dataN"],
  },
};

type MessageBubbleProps = {
  message: UIMessage;
  onCitationClick: (slug: string) => void;
};

function CitationSources({
  citations,
  onCitationClick,
}: {
  citations: Citation[];
  onCitationClick: (slug: string) => void;
}) {
  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground/60 mb-1">
        Sources
      </p>
      <ul className="list-none space-y-0.5">
        {citations.map(({ slug, n, label }) => (
          <li key={slug} className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground/60 shrink-0">[{n}]</span>
            <button
              type="button"
              onClick={() => onCitationClick(slug)}
              aria-label={`View source ${n}: ${label}`}
              className="text-left text-muted-foreground hover:text-foreground hover:underline transition-colors truncate"
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === "user";

  const markdownComponents = useMemo(() => ({
    sup({ node, children }: { node?: unknown; children?: ReactNode }) {
      if (!node || typeof node !== "object" || (node as { type?: string }).type !== "element") {
        return <sup>{children}</sup>;
      }
      const el = node as Element;
      const slug = el.properties?.["data-slug"] as string | undefined;
      if (slug) {
        return (
          <sup>
            <button
              type="button"
              onClick={() => onCitationClick(slug)}
              aria-label={`View source: ${slug}`}
              className="text-primary hover:underline cursor-pointer font-normal"
            >
              {children}
            </button>
          </sup>
        );
      }
      return <sup>{children}</sup>;
    },
  }), [onCitationClick]);

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] bg-foreground text-background rounded-[10px_10px_2px_10px] px-3 py-2 text-sm leading-relaxed">
          {typeof message.content === "string" ? message.content : null}
        </div>
      </div>
    );
  }

  // Assistant message — render parts
  return (
    <div className="flex flex-col gap-1.5">
      {message.parts.map((part, i) => {
        if (part.type === "text") {
          const { processed, citations } = extractCitations(part.text);
          return (
            <div
              key={i}
              className="max-w-[85%] bg-muted/40 rounded-[2px_10px_10px_10px] px-3 py-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
                components={markdownComponents}
              >
                {processed}
              </ReactMarkdown>
              {citations.length > 0 && (
                <CitationSources citations={citations} onCitationClick={onCitationClick} />
              )}
            </div>
          );
        }

        if (part.type === "tool-invocation") {
          const inv = part.toolInvocation;
          return (
            <ToolCallRow
              key={i}
              toolName={inv.toolName}
              args={inv.args}
              result={inv.state === "result" ? JSON.stringify(inv.result) : undefined}
              state={inv.state === "result" ? "result" : "call"}
            />
          );
        }

        return null;
      })}
    </div>
  );
}
