"use client";

import { useRef, type KeyboardEvent } from "react";
import type { Attachment } from "./attachment-picker";
import { AttachmentPicker } from "./attachment-picker";

type ChatInputProps = {
  input: string;
  onInputChange: (v: string) => void;
  onSubmit: () => void;
  attachments: Attachment[];
  onAddAttachment: (a: Attachment) => void;
  onRemoveAttachment: (index: number) => void;
  isLoading: boolean;
};

export function ChatInput({
  input,
  onInputChange,
  onSubmit,
  attachments,
  onAddAttachment,
  onRemoveAttachment,
  isLoading,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isLoading) onSubmit();
    }
  };

  return (
    <div className="border-t border-border bg-background px-4 py-3 shrink-0">
      {/* Attachment chips */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {attachments.map((a, i) => (
            <div
              key={i}
              className="inline-flex items-center gap-1 px-2 py-0.5 bg-muted rounded-full text-xs text-foreground"
            >
              <span
                className="material-symbols-outlined text-[13px]"
                style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 14" }}
              >
                {a.type === "wiki" ? "auto_stories" : "description"}
              </span>
              <span className="max-w-[160px] truncate">{a.label}</span>
              <button
                onClick={() => onRemoveAttachment(i)}
                className="text-muted-foreground hover:text-foreground ml-0.5"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your knowledge base…"
          rows={1}
          disabled={isLoading}
          className="flex-1 resize-none bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground disabled:opacity-50 min-h-[36px] max-h-[120px]"
        />

        <AttachmentPicker onAdd={onAddAttachment} />

        <button
          onClick={onSubmit}
          disabled={!input.trim() || isLoading}
          className="w-8 h-8 flex items-center justify-center bg-foreground text-background rounded-lg disabled:opacity-40 disabled:cursor-not-allowed hover:bg-foreground/90 transition-colors shrink-0"
        >
          <span
            className="material-symbols-outlined text-[16px]"
            style={{ fontVariationSettings: "'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 16" }}
          >
            arrow_upward
          </span>
        </button>
      </div>

      <p className="text-[10px] text-muted-foreground/50 text-center mt-2">
        Answers are scoped to your department and workspace access.
      </p>
    </div>
  );
}
