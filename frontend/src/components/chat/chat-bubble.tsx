"use client";

import { useState, useCallback, useEffect } from "react";
import { useChat } from "ai/react";
import type { UIMessage, Message } from "ai";
import { api } from "@/lib/api";
import { BubbleToggle } from "./bubble-toggle";
import { BubbleWelcome } from "./bubble-welcome";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import type { ChatSession } from "./session-panel";
import type { Attachment } from "./attachment-picker";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5055";

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("arkon_token") ?? "";
}

type ChatBubbleProps = {
  scopeType: string;
  scopeId: string | null;
  prefillInput: string | null;
  onPrefillConsumed: () => void;
};

export function ChatBubble({
  scopeType,
  scopeId,
  prefillInput,
  onPrefillConsumed,
}: ChatBubbleProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [initialMessages, setInitialMessages] = useState<UIMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState("");
  const [attachments] = useState<Attachment[]>([]);

  // Fetch sessions when bubble opens
  const fetchSessions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("scope_type", scopeType);
      if (scopeId) params.set("scope_id", scopeId);
      const data = await api<ChatSession[]>(
        `/api/chat/sessions?${params.toString()}`
      );
      setSessions(Array.isArray(data) ? data : []);
    } catch {
      setSessions([]);
    }
  }, [scopeType, scopeId]);

  useEffect(() => {
    if (isOpen) fetchSessions();
  }, [isOpen, fetchSessions]);

  // Handle prefill: open bubble and set input
  useEffect(() => {
    if (prefillInput) {
      setIsOpen(true);
      setInput(prefillInput);
      onPrefillConsumed();
    }
  }, [prefillInput, onPrefillConsumed]);

  // useChat hook for active session
  const { messages, handleSubmit, isLoading } = useChat({
    api: activeSessionId
      ? `${API_BASE}/api/chat/sessions/${activeSessionId}/stream`
      : `${API_BASE}/api/chat/sessions/placeholder/stream`,
    headers: { Authorization: `Bearer ${getToken()}` },
    body: {
      attachments: attachments.map(({ label: _label, ...rest }) => rest),
    },
    initialMessages: initialMessages as unknown as Message[],
    onFinish: () => {
      fetchSessions();
    },
  });

  const handleNewSession = useCallback(async () => {
    try {
      const s = await api<ChatSession>("/api/chat/sessions", {
        method: "POST",
        body: { scope_type: scopeType, scope_id: scopeId },
      });
      setSessions((prev) => [s, ...prev]);
      setActiveSessionId(s.id);
      setInitialMessages([]);
      setInput("");
    } catch {
      // ignore
    }
  }, [scopeType, scopeId]);

  const handleSelectSession = useCallback(async (id: string) => {
    setActiveSessionId(id);
    setLoadingMessages(true);
    try {
      const msgs = await api<
        {
          id: string;
          role: string;
          content: string | null;
          created_at: string;
        }[]
      >(`/api/chat/sessions/${id}/messages`);
      const uiMessages: UIMessage[] = msgs
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content ?? "",
          parts: [{ type: "text" as const, text: m.content ?? "" }],
          createdAt: new Date(m.created_at),
        }));
      setInitialMessages(uiMessages);
    } catch {
      setInitialMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  const handleDeleteSession = useCallback(
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

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return;
    if (!activeSessionId) {
      handleNewSession();
      return;
    }
    handleSubmit({});
  }, [input, isLoading, activeSessionId, handleSubmit, handleNewSession]);

  // Auto-submit after session creation when prefill triggered new session
  useEffect(() => {
    if (
      activeSessionId &&
      input.trim() &&
      !isLoading &&
      messages.length === 0
    ) {
      handleSubmit({});
    }
  }, [activeSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBack = useCallback(() => {
    setActiveSessionId(null);
    setInitialMessages([]);
    setInput("");
  }, []);

  return (
    <>
      <BubbleToggle onClick={() => setIsOpen(true)} isOpen={isOpen} />

      {isOpen && (
        <div className="fixed bottom-4 right-4 z-40 w-[400px] h-[500px] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-2rem)] bg-background border border-border rounded-xl shadow-lg flex flex-col overflow-hidden md:w-[400px] md:h-[500px]">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border flex items-center gap-2 shrink-0">
            {activeSessionId && (
              <button
                type="button"
                onClick={handleBack}
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="Back to conversations"
              >
                <span className="material-symbols-outlined text-[20px]">
                  arrow_back
                </span>
              </button>
            )}
            <span className="text-sm font-semibold flex-1 truncate">
              {activeSessionId
                ? sessions.find((s) => s.id === activeSessionId)?.title ??
                  "Chat"
                : "Chat"}
            </span>
            {activeSessionId && (
              <a
                href={`/knowledge/chat?session=${activeSessionId}`}
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="Open in full page"
              >
                <span className="material-symbols-outlined text-[18px]">
                  open_in_new
                </span>
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setActiveSessionId(null);
                setInitialMessages([]);
                setInput("");
              }}
              className="text-muted-foreground hover:text-foreground transition-colors"
              title="Close"
            >
              <span className="material-symbols-outlined text-[20px]">
                close
              </span>
            </button>
          </div>

          {/* Body */}
          {!activeSessionId ? (
            <BubbleWelcome
              sessions={sessions}
              onSelectSession={handleSelectSession}
              onNewSession={handleNewSession}
              onDeleteSession={handleDeleteSession}
            />
          ) : loadingMessages ? (
            <div className="flex-1 flex items-center justify-center">
              <span className="material-symbols-outlined text-2xl text-muted-foreground animate-spin">
                progress_activity
              </span>
            </div>
          ) : (
            <>
              <MessageList
                messages={messages as UIMessage[]}
                isLoading={isLoading}
                onCitationClick={() => {}}
              />
              <ChatInput
                input={input}
                onInputChange={setInput}
                onSubmit={handleSend}
                attachments={attachments}
                onAddAttachment={() => {}}
                onRemoveAttachment={() => {}}
                isLoading={isLoading}
              />
            </>
          )}
        </div>
      )}
    </>
  );
}
