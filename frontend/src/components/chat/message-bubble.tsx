"use client";

import type { UIMessage } from "ai";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ToolCallRow } from "./tool-call-row";

type MessageBubbleProps = {
  message: UIMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] bg-foreground text-background rounded-[10px_10px_2px_10px] px-3 py-2 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message: render parts
  return (
    <div className="flex flex-col gap-1.5">
      {message.parts.map((part, i) => {
        if (part.type === "text") {
          return (
            <div
              key={i}
              className="max-w-[85%] bg-muted/40 rounded-[2px_10px_10px_10px] px-3 py-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {part.text}
              </ReactMarkdown>
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
