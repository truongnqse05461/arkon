"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

type ToolCallRowProps = {
  toolName: string;
  args: Record<string, unknown>;
  result?: string;
  state: "call" | "result";
};

export function ToolCallRow({ toolName, args, result, state }: ToolCallRowProps) {
  const [expanded, setExpanded] = useState(false);

  const argsPreview = Object.entries(args)
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(", ");

  return (
    <div className={cn("border border-border rounded-md overflow-hidden bg-muted/30 text-xs max-w-[85%]")}>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-muted/50 transition-colors"
      >
        <span className="text-muted-foreground shrink-0">
          {state === "result" ? "✓" : "⋯"}
        </span>
        <span className="font-mono text-muted-foreground font-medium shrink-0">{toolName}</span>
        <span className="text-muted-foreground/70 truncate flex-1">{argsPreview}</span>
        <span
          className="material-symbols-outlined text-[12px] text-muted-foreground/50 shrink-0"
          style={{
            fontVariationSettings: "'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 12",
            transform: expanded ? "rotate(0deg)" : "rotate(-90deg)",
            transition: "transform 0.15s",
          }}
        >
          expand_more
        </span>
      </button>

      {expanded && (
        <div className="px-3 py-2 border-t border-border bg-muted/10 font-mono text-[11px] text-muted-foreground space-y-1">
          <div>
            <span className="text-muted-foreground/50 uppercase tracking-wide text-[9px]">args</span>
            <pre className="mt-0.5 whitespace-pre-wrap break-all">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
          {result && (
            <div>
              <span className="text-muted-foreground/50 uppercase tracking-wide text-[9px]">result</span>
              <pre className="mt-0.5 whitespace-pre-wrap break-all line-clamp-10">{result}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
