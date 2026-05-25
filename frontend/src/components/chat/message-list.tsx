"use client";

import { useEffect, useRef } from "react";
import type { UIMessage } from "ai";
import { MessageBubble } from "./message-bubble";

type MessageListProps = {
  messages: UIMessage[];
  isLoading: boolean;
  onCitationClick: (slug: string) => void;
};

export function MessageList({ messages, isLoading, onCitationClick }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <span
            className="material-symbols-outlined text-4xl mb-2 block"
            style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 48" }}
          >
            chat
          </span>
          <p className="text-sm">Ask anything about your organization&apos;s knowledge base.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          onCitationClick={onCitationClick}
        />
      ))}
      {isLoading && (
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="material-symbols-outlined text-sm animate-spin">
            progress_activity
          </span>
          <span className="text-xs">Thinking…</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
