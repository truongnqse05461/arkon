"use client";

import { cn } from "@/lib/utils";

type SessionItemProps = {
  id: string;
  title: string;
  updatedAt: string;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
};

function relativeTime(isoString: string): string {
  const now = Date.now();
  const ts = new Date(isoString).getTime();
  const diff = Math.floor((now - ts) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(isoString).toLocaleDateString();
}

export function SessionItem({ id: _id, title, updatedAt, isActive, onSelect, onDelete }: SessionItemProps) {
  return (
    <div
      className={cn(
        "group flex items-start gap-1 rounded-md px-2 py-1.5 cursor-pointer transition-colors",
        isActive ? "bg-black/[0.05]" : "hover:bg-black/[0.03]"
      )}
      onClick={onSelect}
    >
      <div className="flex-1 min-w-0">
        <div className={cn("text-[12px] truncate", isActive ? "font-medium text-foreground" : "text-muted-foreground")}>
          {title}
        </div>
        <div className="text-[10px] text-muted-foreground/60">{relativeTime(updatedAt)}</div>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="opacity-0 group-hover:opacity-100 text-muted-foreground/40 hover:text-destructive transition-all shrink-0 mt-0.5"
      >
        <span
          className="material-symbols-outlined text-[13px]"
          style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 14" }}
        >
          close
        </span>
      </button>
    </div>
  );
}
