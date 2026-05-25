"use client";

import { useState, useCallback } from "react";
import { useChat } from "ai/react";
import type { UIMessage, Message } from "ai";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import { CitationPanel } from "./citation-panel";
import type { Attachment } from "./attachment-picker";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5055";

type ChatAreaProps = {
  sessionId: string;
  sessionTitle: string;
  initialMessages: UIMessage[];
  onSessionUpdated: () => void;
  onDeleteSession: () => void;
};

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("arkon_token") ?? "";
}

export function ChatArea({
  sessionId,
  sessionTitle,
  initialMessages,
  onSessionUpdated,
  onDeleteSession,
}: ChatAreaProps) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  const { messages, input, setInput, handleSubmit, isLoading } = useChat({
    api: `${API_BASE}/api/chat/sessions/${sessionId}/stream`,
    headers: { Authorization: `Bearer ${getToken()}` },
    body: { attachments: attachments.map(({ label: _label, ...rest }) => rest) },
    // UIMessage is a superset of Message in the AI SDK; cast required due to type version delta
    initialMessages: initialMessages as unknown as Message[],
    onFinish: () => {
      setAttachments([]);
      onSessionUpdated();
    },
  });

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return;
    handleSubmit({});
  }, [input, isLoading, handleSubmit]);

  const handleCitationClick = useCallback((slug: string) => {
    setSelectedSlug(slug);
  }, []);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-3 shrink-0">
        <span className="font-semibold text-sm text-foreground flex-1 truncate">
          {sessionTitle}
        </span>
        <button
          type="button"
          onClick={onDeleteSession}
          className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1 transition-colors"
        >
          <span
            className="material-symbols-outlined text-[14px]"
            style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 14" }}
          >
            delete
          </span>
          Delete
        </button>
      </div>

      {/* Messages */}
      <MessageList
        messages={messages as UIMessage[]}
        isLoading={isLoading}
        onCitationClick={handleCitationClick}
      />

      {/* Input */}
      <ChatInput
        input={input}
        onInputChange={setInput}
        onSubmit={handleSend}
        attachments={attachments}
        onAddAttachment={(a) => setAttachments((prev) => [...prev, a])}
        onRemoveAttachment={(i) => setAttachments((prev) => prev.filter((_, idx) => idx !== i))}
        isLoading={isLoading}
      />

      {/* Citation slide-out panel */}
      <CitationPanel slug={selectedSlug} onClose={() => setSelectedSlug(null)} />
    </div>
  );
}
