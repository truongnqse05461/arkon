# Chat Citations Feature Design

## Goal

Make wiki and source references in chat assistant responses clickable. Clicking a citation opens a slide-out panel showing the referenced wiki page content, without leaving the chat.

## Architecture

Frontend-only change. No new API endpoints. No database changes.

**Data flow:**
1. LLM emits `label【slug】` notation inline (e.g. `GIM【entity/gim】`, `the MAU spec【source/gim-mau-spec-150426-083136】`)
2. `extractCitations(text)` preprocesses the raw markdown string before rendering:
   - Finds all `【slug】` patterns via `/【([^】]+)】/g`
   - Assigns sequential citation numbers (deduplicated — same slug always gets the same `[N]`)
   - Extracts `label` from the word(s) immediately before `【...】`
   - Replaces each marker with `<sup data-slug="{slug}" data-n="{N}">[N]</sup>`
   - Returns `{ processed: string, citations: {slug, n, label}[] }`
3. `MessageBubble` passes `processed` to ReactMarkdown with `rehype-raw` so `<sup>` survives
4. Custom `sup` component override detects `data-slug` and renders a styled `<button>` calling `onCitationClick(slug)`
5. `CitationSources` component renders a numbered sources list below the markdown block
6. `ChatArea` holds `selectedSlug: string | null` state; clicking any citation (inline or in sources list) sets it, opening `CitationPanel`

## File Structure

**New files:**
- `frontend/src/components/chat/citation-utils.ts` — pure `extractCitations` utility
- `frontend/src/components/chat/citation-panel.tsx` — slide-out drawer

**Modified files:**
- `frontend/src/components/chat/message-bubble.tsx` — wire `extractCitations`, custom `sup`, `CitationSources`
- `frontend/src/components/chat/chat-area.tsx` — `selectedSlug` state, `CitationPanel` render
- `frontend/src/components/chat/message-list.tsx` — pass `onCitationClick` prop
- `app/services/chat_agent.py` — tighten system prompt citation format instruction

## Component Details

### `citation-utils.ts`

```typescript
export type Citation = { slug: string; n: number; label: string };

export function extractCitations(text: string): {
  processed: string;
  citations: Citation[];
} 
```

- Input: raw LLM markdown string
- Regex: `/【([^】]+)】/g`
- Deduplicates by slug — first occurrence wins the number
- `label` = the longest run of non-whitespace characters immediately before `【` in the original text
- Injects `<sup data-slug="{slug}" data-n="{N}">[N]</sup>` at each match position
- Returns ordered `citations` array (order = first appearance)

### `citation-panel.tsx`

Slide-out drawer anchored to the right side of the chat column (~480px wide):

- **Props:** `slug: string | null`, `onClose: () => void`
- **Visibility:** rendered when `slug !== null`; animated slide-in/out
- **Header:** slug displayed as breadcrumb path (e.g. `entity / gim`) + close `×` button
- **Body:** fetches `GET /api/wiki/pages/{encodeURIComponent(slug)}` on `slug` change; renders `content_md` with ReactMarkdown + remarkGfm; no editing chrome
- **States:** loading skeleton, content, "Page not found or not accessible" fallback (HTTP 403/404)
- **Auth:** uses the same `api()` helper as the rest of the app (JWT from localStorage)

### `CitationSources` (inline in `message-bubble.tsx`)

Rendered below the ReactMarkdown block when `citations.length > 0`:

```
Sources
[1] GIM  ← clickable, opens panel for entity/gim
[2] MAU
[3] MAU limit structure
[4] GIM MAU Spec
```

- Each entry: `[N]` number chip + label text as a `<button>`
- Subtle separator line above the list
- Same `onCitationClick(slug)` handler as inline superscripts

### `MessageBubble` changes

For `part.type === "text"` in assistant messages:

```tsx
const { processed, citations } = extractCitations(part.text);

<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  rehypePlugins={[rehypeRaw]}
  components={{
    sup({ node, children, ...props }) {
      const slug = (node as Element).properties?.['data-slug'] as string;
      if (slug) {
        return (
          <sup>
            <button onClick={() => onCitationClick(slug)} ...>
              {children}
            </button>
          </sup>
        );
      }
      return <sup {...props}>{children}</sup>;
    },
  }}
>
  {processed}
</ReactMarkdown>

{citations.length > 0 && (
  <CitationSources citations={citations} onCitationClick={onCitationClick} />
)}
```

### `ChatArea` changes

```tsx
const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

// Pass down:
<MessageList ... onCitationClick={setSelectedSlug} />

// Render alongside chat column:
<CitationPanel slug={selectedSlug} onClose={() => setSelectedSlug(null)} />
```

### System Prompt Update (`chat_agent.py`)

Replace:
```
"Always cite page slugs when referencing wiki pages."
```

With:
```
"When citing wiki pages or sources, format citations inline as: label【slug】
Examples: GIM【entity/gim】, the MAU spec【source/gim-mau-spec-150426-083136】
Always use this exact 【】 bracket style — never bare slugs or Markdown links."
```

## Edge Cases

| Case | Behavior |
|---|---|
| Same slug cited multiple times | Deduplicated — always the same `[N]` |
| No citations in response | `extractCitations` returns empty array; `CitationSources` renders nothing; no `rehype-raw` overhead |
| `source/...` slug vs `entity/...` slug | All slugs treated identically — all are wiki page slugs, one code path |
| Wiki page not found / out of scope | Panel shows "Page not accessible" message; no error thrown |
| Citation numbers shift mid-stream | Acceptable — numbers stabilize when stream ends |
| LLM outputs bare slug without label | `label` falls back to the slug itself |

## Dependencies

- `rehype-raw` — needs to be added to frontend (`pnpm add rehype-raw`)
- All other packages already present (`react-markdown`, `remark-gfm`, `hast` types)
