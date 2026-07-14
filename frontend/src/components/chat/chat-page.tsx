"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import type { UIMessage } from "ai";
import { api } from "@/lib/api";
import { SessionPanel, type ChatSession } from "./session-panel";
import { ChatArea } from "./chat-area";

type MessageRecord = {
  id: string;
  role: string;
  content: string | null;
  tool_name: string | null;
  tool_call_id: string | null;
  tool_input: Record<string, unknown> | null;
  created_at: string;
};

function recordsToUIMessages(records: MessageRecord[]): UIMessage[] {
  return records
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      content: m.content ?? "",
      parts: [{ type: "text" as const, text: m.content ?? "" }],
      createdAt: new Date(m.created_at),
    }));
}

export function ChatPage() {
  const searchParams = useSearchParams();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [initialMessages, setInitialMessages] = useState<UIMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const didAutoSelect = useRef(false);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await api<ChatSession[]>("/api/chat/sessions");
      setSessions(data);
      return data;
    } catch {
      setSessions([]);
      return [];
    }
  }, []);

  const selectSession = useCallback(async (id: string) => {
    setActiveSessionId(id);
    setLoadingMessages(true);
    try {
      const msgs = await api<MessageRecord[]>(`/api/chat/sessions/${id}/messages`);
      setInitialMessages(recordsToUIMessages(msgs));
    } catch {
      setInitialMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // Load sessions on mount
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Auto-select session from ?session= query param (once)
  useEffect(() => {
    const sessionId = searchParams.get("session");
    if (!sessionId || didAutoSelect.current) return;
    didAutoSelect.current = true;
    fetchSessions().then((loaded) => {
      const found = loaded.find((s) => s.id === sessionId);
      if (found) {
        selectSession(sessionId);
      }
    });
  }, [searchParams, fetchSessions, selectSession]);

  const newSession = useCallback(async () => {
    try {
      const s = await api<ChatSession>("/api/chat/sessions", { method: "POST" });
      setSessions((prev) => [s, ...prev]);
      setActiveSessionId(s.id);
      setInitialMessages([]);
    } catch {
      // ignore
    }
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      try {
        await api(`/api/chat/sessions/${id}`, { method: "DELETE" });
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeSessionId === id) {
          setActiveSessionId(null);
          setInitialMessages([]);
        }
      } catch {
        // ignore
      }
    },
    [activeSessionId]
  );

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;

  return (
    <div className="flex flex-1 min-h-0 -mx-6 -mt-4 -mb-6 md:-mx-8 md:-mb-8 lg:-mx-10 lg:-mb-10">
      <SessionPanel
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={selectSession}
        onNewSession={newSession}
        onDeleteSession={deleteSession}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {!activeSessionId ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <span
                className="material-symbols-outlined text-5xl mb-3 block"
                style={{ fontVariationSettings: "'FILL' 0, 'wght' 200, 'GRAD' 0, 'opsz' 48" }}
              >
                chat
              </span>
              <p className="text-sm mb-3">Select a conversation or start a new one.</p>
              <button
                onClick={newSession}
                className="px-4 py-2 bg-foreground text-background rounded-lg text-sm hover:bg-foreground/90 transition-colors"
              >
                New conversation
              </button>
            </div>
          </div>
        ) : loadingMessages ? (
          <div className="flex-1 flex items-center justify-center">
            <span className="material-symbols-outlined text-2xl text-muted-foreground animate-spin">
              progress_activity
            </span>
          </div>
        ) : (
          <ChatArea
            key={activeSessionId}
            sessionId={activeSessionId}
            sessionTitle={activeSession?.title ?? "(New conversation)"}
            initialMessages={initialMessages}
            onSessionUpdated={fetchSessions}
            onDeleteSession={() => deleteSession(activeSessionId)}
          />
        )}
      </div>
    </div>
  );
}
