# Chat Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `【slug】` citation markers in chat assistant responses render as clickable footnote superscripts that open a wiki-page slide-out panel.

**Architecture:** A pure `extractCitations()` utility pre-processes the raw markdown string before ReactMarkdown, replacing `【slug】` with `<sup data-slug="...">` HTML. `rehype-raw` allows those tags to survive markdown parsing. A custom `sup` component override turns them into buttons. A `CitationPanel` slide-out drawer fetches and renders the referenced wiki page.

**Tech Stack:** React, ReactMarkdown, rehype-raw (new dep), Vercel AI SDK `UIMessage`, existing `api()` helper, Tailwind CSS.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `frontend/src/components/chat/citation-utils.ts` | Pure `extractCitations` function |
| Create | `frontend/src/components/chat/citation-panel.tsx` | Slide-out drawer with wiki content |
| Modify | `frontend/src/components/chat/message-bubble.tsx` | Wire citations + rehypeRaw + CitationSources |
| Modify | `frontend/src/components/chat/message-list.tsx` | Pass `onCitationClick` prop |
| Modify | `frontend/src/components/chat/chat-area.tsx` | `selectedSlug` state + CitationPanel render |
| Modify | `app/services/chat_agent.py` | Tighten system prompt citation instruction |

---

## Task 1: Install `rehype-raw` and create `citation-utils.ts`

**Files:**
- Install: `rehype-raw` package
- Create: `frontend/src/components/chat/citation-utils.ts`

- [ ] **Step 1: Install `rehype-raw`**

```bash
cd frontend
pnpm add rehype-raw
```

Expected output: `+ rehype-raw X.X.X` added to `node_modules`.

- [ ] **Step 2: Create `citation-utils.ts`**

Create `frontend/src/components/chat/citation-utils.ts` with this exact content:

```typescript
export type Citation = {
  slug: string;
  n: number;
  label: string;
};

// Only allow safe slug characters to prevent XSS via data-slug attribute
const VALID_SLUG_RE = /^[a-zA-Z0-9_\-\/]+$/;

export function extractCitations(text: string): {
  processed: string;
  citations: Citation[];
} {
  const seen = new Map<string, number>();
  const citations: Citation[] = [];

  // Pass 1: collect unique slugs in order of first appearance
  const matchRegex = /【([^】]+)】/g;
  let m: RegExpExecArray | null;
  while ((m = matchRegex.exec(text)) !== null) {
    const slug = m[1];
    if (!VALID_SLUG_RE.test(slug) || seen.has(slug)) continue;

    const n = seen.size + 1;
    seen.set(slug, n);

    // Label = last non-whitespace word before 【
    const before = text.slice(0, m.index);
    const labelMatch = before.match(/(\S+)\s*$/);
    citations.push({ slug, n, label: labelMatch ? labelMatch[1] : slug });
  }

  if (citations.length === 0) {
    return { processed: text, citations: [] };
  }

  // Pass 2: replace each 【slug】 with a superscript HTML marker
  const processed = text.replace(/【([^】]+)】/g, (_, slug: string) => {
    const n = seen.get(slug);
    if (n == null) return `【${slug}】`;
    return `<sup data-slug="${slug}" data-n="${n}">[${n}]</sup>`;
  });

  return { processed, citations };
}
```

- [ ] **Step 3: Verify the function manually**

Open `frontend/src/components/chat/citation-utils.ts` and mentally trace through these cases:

Input: `"GIM【entity/gim】 và MAU【entity/mau】 là hai khái niệm. GIM【entity/gim】 lại."`
Expected `citations`: `[{slug:"entity/gim",n:1,label:"GIM"},{slug:"entity/mau",n:2,label:"MAU"}]`
Expected `processed` contains: `GIM<sup data-slug="entity/gim" data-n="1">[1]</sup>` and `MAU<sup data-slug="entity/mau" data-n="2">[2]</sup>` and the second `GIM【entity/gim】` becomes `GIM<sup data-slug="entity/gim" data-n="1">[1]</sup>` (same number, deduped).

Input: `"no citations here"` → `citations: []`, `processed` unchanged.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd frontend
pnpm add rehype-raw
```
```bash
cd ..
rtk git add frontend/src/components/chat/citation-utils.ts frontend/package.json frontend/pnpm-lock.yaml
rtk git commit -m "feat(chat): add citation extraction utility and install rehype-raw"
```

---

## Task 2: Create `citation-panel.tsx`

**Files:**
- Create: `frontend/src/components/chat/citation-panel.tsx`

- [ ] **Step 1: Create `citation-panel.tsx`**

Create `frontend/src/components/chat/citation-panel.tsx` with this exact content:

```tsx
"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import type { WikiPageDetail } from "@/types/wiki";

type CitationPanelProps = {
  slug: string | null;
  onClose: () => void;
};

export function CitationPanel({ slug, onClose }: CitationPanelProps) {
  const [page, setPage] = useState<WikiPageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setPage(null);
    setError(null);
    setLoading(true);
    api<WikiPageDetail>(`/api/wiki/pages/${encodeURIComponent(slug)}`)
      .then(setPage)
      .catch(() => setError("Page not found or not accessible."))
      .finally(() => setLoading(false));
  }, [slug]);

  if (!slug) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-[480px] max-w-full bg-background border-l border-border shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
          <span className="text-xs text-muted-foreground font-mono flex-1 truncate">
            {slug.split("/").join(" / ")}
          </span>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close panel"
          >
            <span
              className="material-symbols-outlined text-[18px]"
              style={{ fontVariationSettings: "'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 18" }}
            >
              close
            </span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <span className="material-symbols-outlined text-sm animate-spin">
                progress_activity
              </span>
              Loading…
            </div>
          )}
          {error && (
            <p className="text-sm text-muted-foreground">{error}</p>
          )}
          {page && (
            <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none">
              <h1 className="text-base font-semibold mb-3">{page.title}</h1>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {page.content_md}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors from the new file.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/components/chat/citation-panel.tsx
rtk git commit -m "feat(chat): add CitationPanel slide-out drawer"
```

---

## Task 3: Update `message-bubble.tsx`

**Files:**
- Modify: `frontend/src/components/chat/message-bubble.tsx` (full replacement)

- [ ] **Step 1: Replace `message-bubble.tsx`**

Replace the entire content of `frontend/src/components/chat/message-bubble.tsx` with:

```tsx
"use client";

import type { UIMessage } from "ai";
import type { Element } from "hast";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { ToolCallRow } from "./tool-call-row";
import { extractCitations, type Citation } from "./citation-utils";

type MessageBubbleProps = {
  message: UIMessage;
  onCitationClick: (slug: string) => void;
};

function CitationSources({
  citations,
  onCitationClick,
}: {
  citations: Citation[];
  onCitationClick: (slug: string) => void;
}) {
  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground/60 mb-1">
        Sources
      </p>
      <ol className="list-none space-y-0.5">
        {citations.map(({ slug, n, label }) => (
          <li key={slug} className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground/60 shrink-0">[{n}]</span>
            <button
              onClick={() => onCitationClick(slug)}
              className="text-left text-muted-foreground hover:text-foreground hover:underline transition-colors truncate"
            >
              {label}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
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

  // Assistant message — render parts
  return (
    <div className="flex flex-col gap-1.5">
      {message.parts.map((part, i) => {
        if (part.type === "text") {
          const { processed, citations } = extractCitations(part.text);
          return (
            <div
              key={i}
              className="max-w-[85%] bg-muted/40 rounded-[2px_10px_10px_10px] px-3 py-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  sup({ node, children }) {
                    const el = node as Element;
                    const slug = el.properties?.["data-slug"] as string | undefined;
                    if (slug) {
                      return (
                        <sup>
                          <button
                            onClick={() => onCitationClick(slug)}
                            className="text-primary hover:underline cursor-pointer font-normal"
                          >
                            {children}
                          </button>
                        </sup>
                      );
                    }
                    return <sup>{children}</sup>;
                  },
                }}
              >
                {processed}
              </ReactMarkdown>
              {citations.length > 0 && (
                <CitationSources citations={citations} onCitationClick={onCitationClick} />
              )}
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors. If you see `Cannot find module 'hast'` add it:
```bash
pnpm add -D @types/hast
```

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/components/chat/message-bubble.tsx
rtk git commit -m "feat(chat): wire citation extraction and CitationSources into MessageBubble"
```

---

## Task 4: Thread `onCitationClick` through `message-list.tsx` and `chat-area.tsx`

**Files:**
- Modify: `frontend/src/components/chat/message-list.tsx` (full replacement)
- Modify: `frontend/src/components/chat/chat-area.tsx` (full replacement)

- [ ] **Step 1: Replace `message-list.tsx`**

Replace the entire content of `frontend/src/components/chat/message-list.tsx` with:

```tsx
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
```

- [ ] **Step 2: Replace `chat-area.tsx`**

Replace the entire content of `frontend/src/components/chat/chat-area.tsx` with:

```tsx
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

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-3 shrink-0">
        <span className="font-semibold text-sm text-foreground flex-1 truncate">
          {sessionTitle}
        </span>
        <button
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
        onCitationClick={setSelectedSlug}
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
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 4: Smoke test in the browser**

Start the dev server if it isn't already running:
```bash
cd frontend
pnpm run dev
```

1. Open `http://localhost:3000/knowledge/chat`
2. Start a new conversation and ask any question that will cause the LLM to cite wiki pages (e.g. "Tóm tắt wiki index")
3. Verify the response renders `[1]`, `[2]` superscripts as clickable buttons
4. Click a `[1]` button → CitationPanel slides in from the right with wiki content
5. Click the backdrop or `×` button → panel closes
6. Verify the Sources list at the bottom of the message lists all citations

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/components/chat/message-list.tsx frontend/src/components/chat/chat-area.tsx
rtk git commit -m "feat(chat): thread onCitationClick and render CitationPanel in ChatArea"
```

---

## Task 5: Update system prompt and deploy

**Files:**
- Modify: `app/services/chat_agent.py` (lines 473–477)

- [ ] **Step 1: Update the system prompt lines**

In `app/services/chat_agent.py`, find `_build_system_prompt` and replace:

```python
    lines = [
        "You are a helpful knowledge base assistant for this organization.",
        "Answer questions by searching and reading the knowledge base.",
        "Always cite page slugs when referencing wiki pages.",
        "Your answers are scoped to the user's department and workspace access only.",
    ]
```

With:

```python
    lines = [
        "You are a helpful knowledge base assistant for this organization.",
        "Answer questions by searching and reading the knowledge base.",
        "When citing wiki pages or sources, format citations inline as: label【slug】",
        "Examples: GIM【entity/gim】, the MAU spec【source/gim-mau-spec-150426-083136】",
        "Always use this exact 【】 bracket style — never bare slugs or Markdown links.",
        "Your answers are scoped to the user's department and workspace access only.",
    ]
```

- [ ] **Step 2: Deploy to the running Docker container**

```bash
docker cp app/services/chat_agent.py arkon_api:/app/app/services/chat_agent.py
docker restart arkon_api
```

Wait ~5 seconds then verify:
```bash
docker inspect arkon_api --format "{{.State.Status}}"
```
Expected: `running`

- [ ] **Step 3: End-to-end verification**

1. Open `http://localhost:3000/knowledge/chat`
2. Start a new conversation, ask: `"Tóm tắt về GIM và cách tính MAU"`
3. Verify the LLM now uses `GIM【entity/gim】` style (not raw slug text)
4. Verify `[1]` superscripts appear, the Sources list is at the bottom, and clicking opens the panel

- [ ] **Step 4: Commit**

```bash
rtk git add app/services/chat_agent.py
rtk git commit -m "feat(chat): tighten LLM citation format to label【slug】 brackets"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `extractCitations` pure function — Task 1
- ✅ `rehype-raw` installed — Task 1
- ✅ `CitationPanel` slide-out drawer with wiki fetch — Task 2
- ✅ Footnote `[N]` superscripts inline in text — Task 3
- ✅ Sources list at bottom of message — Task 3
- ✅ `onCitationClick` threaded through MessageList → MessageBubble — Task 4
- ✅ `selectedSlug` state in ChatArea — Task 4
- ✅ System prompt updated — Task 5
- ✅ Deduplication (same slug → same `[N]`) — citation-utils.ts pass-1 logic
- ✅ No citations → no overhead — early return in extractCitations
- ✅ Invalid slug sanitization — `VALID_SLUG_RE` check

**Type consistency:**
- `Citation = { slug, n, label }` defined in Task 1, used in Tasks 3 and 4 ✅
- `onCitationClick: (slug: string) => void` signature consistent across MessageBubble, MessageList, ChatArea ✅
- `CitationPanel` props `{ slug: string | null, onClose: () => void }` consistent ✅
