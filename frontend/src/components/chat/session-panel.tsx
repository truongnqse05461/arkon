"use client";

import { useState } from "react";
import { SessionItem } from "./session-item";

export type ChatSession = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

type SessionPanelProps = {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
};

function groupByDate(sessions: ChatSession[]): { label: string; items: ChatSession[] }[] {
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();
  const groups: Record<string, ChatSession[]> = {};

  for (const s of sessions) {
    const d = new Date(s.updated_at).toDateString();
    const label = d === today ? "Today" : d === yesterday ? "Yesterday" : "Older";
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  }

  return ["Today", "Yesterday", "Older"]
    .filter((l) => groups[l])
    .map((l) => ({ label: l, items: groups[l] }));
}

export function SessionPanel({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}: SessionPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const grouped = groupByDate(sessions);

  if (collapsed) {
    return (
      <div className="w-9 flex-shrink-0 bg-card/30 border-r border-border flex flex-col items-center pt-2 gap-1.5">
        <button
          onClick={() => setCollapsed(false)}
          title="Expand"
          className="w-6 h-6 flex items-center justify-center border border-border rounded bg-background text-muted-foreground hover:text-foreground"
        >
          <span
            className="material-symbols-outlined text-[14px]"
            style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 14" }}
          >
            chevron_right
          </span>
        </button>
        <button
          onClick={onNewSession}
          title="New chat"
          className="w-6 h-6 flex items-center justify-center border border-border rounded bg-background text-muted-foreground hover:text-foreground text-[13px]"
        >
          +
        </button>
      </div>
    );
  }

  return (
    <div className="w-[220px] flex-shrink-0 bg-card/30 border-r border-border flex flex-col">
      {/* Header */}
      <div className="px-3 py-2 flex items-center justify-between border-b border-border shrink-0">
        <span className="text-[11px] font-semibold text-foreground">Conversations</span>
        <div className="flex gap-1">
          <button
            onClick={onNewSession}
            title="New chat"
            className="w-5 h-5 flex items-center justify-center border border-border rounded bg-background text-muted-foreground hover:text-foreground text-[13px]"
          >
            +
          </button>
          <button
            onClick={() => setCollapsed(true)}
            title="Collapse"
            className="w-5 h-5 flex items-center justify-center border border-border rounded bg-background text-muted-foreground hover:text-foreground"
          >
            <span
              className="material-symbols-outlined text-[14px]"
              style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 14" }}
            >
              chevron_left
            </span>
          </button>
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {sessions.length === 0 ? (
          <p className="text-[11px] text-muted-foreground/50 px-2 py-3">No conversations yet.</p>
        ) : (
          grouped.map((group) => (
            <div key={group.label} className="mb-1">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/50">
                {group.label}
              </div>
              {group.items.map((s) => (
                <SessionItem
                  key={s.id}
                  id={s.id}
                  title={s.title}
                  updatedAt={s.updated_at}
                  isActive={s.id === activeSessionId}
                  onSelect={() => onSelectSession(s.id)}
                  onDelete={() => onDeleteSession(s.id)}
                />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
