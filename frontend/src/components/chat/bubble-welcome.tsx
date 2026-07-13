"use client";

import type { ChatSession } from "./session-panel";

type BubbleWelcomeProps = {
  sessions: ChatSession[];
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
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

export function BubbleWelcome({
  sessions,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}: BubbleWelcomeProps) {
  return (
    <div className="flex flex-col h-full">
      {/* New Chat button */}
      <div className="px-4 pt-4 pb-2 shrink-0">
        <button
          type="button"
          onClick={onNewSession}
          className="w-full px-4 py-2.5 bg-foreground text-background rounded-lg text-sm font-medium hover:bg-foreground/90 transition-colors flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground/50 text-center py-8">
            Start a conversation about this mindmap.
          </p>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="group flex items-start gap-1 rounded-md px-2 py-1.5 cursor-pointer hover:bg-black/[0.03] transition-colors"
                onClick={() => onSelectSession(s.id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] truncate text-muted-foreground">
                    {s.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground/60">
                    {relativeTime(s.updated_at)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(s.id);
                  }}
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
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
