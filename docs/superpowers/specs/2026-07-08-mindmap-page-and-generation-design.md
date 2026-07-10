# Mindmap Page & Generation Enhancement — Design Spec

> Extends mindmap with a dedicated management page, multi-source generation (Wiki + Source Documents), LLM-generated node summaries, and improved Chat ↔ Mindmap navigation.

## Problem Statement

The current mindmap feature is tightly coupled to the Chat page as a side panel. Users cannot manage mindmaps independently (list, delete, regenerate), generation is limited to Wiki pages only, node summaries are raw page excerpts, and there's no way to customize generation focus. After mindmap becomes a separate page, Chat ↔ Mindmap interaction needs explicit navigation support.

## Goals

1. **Dedicated Mindmap page** — Top-level nav item with list view, generation dialog, and full-screen viewer
2. **Multi-source generation** — Generate mindmaps from Wiki pages OR source documents
3. **Custom instructions** — User instruction appended to system prompt for focused generation
4. **LLM-generated summaries** — Concise, meaningful node summaries instead of raw excerpts
5. **Chat ↔ Mindmap navigation** — "Ask in Chat" from Mindmap page navigates to Chat with prefilled input

## Non-Goals

- Real-time mindmap collaboration
- Mindmap editing (manual node add/remove/rename)
- Source document selection UI for Wiki mode (already scope-based)
- Export mindmap to image/PDF
- Version history for mindmaps

---

## 1. Architecture

### Current Architecture
```
Chat Page
├── Chat Panel (messages, input)
└── MindMap Panel (side panel, scope-based)
    └── MindMap Tree (react-d3-tree)
```

### New Architecture
```
Chat Page
├── Chat Panel (messages, input)
└── MindMap Panel (side panel, unchanged)

MindMap Page (NEW - /mindmap)
├── Mindmap List View (table of all mindmaps)
├── Generation Dialog (scope, source, instruction)
└── Mindmap Viewer (full-screen tree view)
```

### Key Decisions

- **Chat panel preserved** — Existing side panel in Chat page remains unchanged
- **Separate page for management** — New `/mindmap` route for list/generate/delete/view
- **Extend existing model** — Add fields to `WikiMindmap` table (no new table)
- **Pre-generated summaries** — LLM summaries generated during mindmap creation, stored in DB

---

## 2. Data Model Changes

### Extend `WikiMindmap` Table

```python
# New fields added to existing WikiMindmap model
source_type: Mapped[str] = mapped_column(String(20), default="wiki")  # "wiki" | "source_docs"
source_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # UUIDs of source docs (NULL for wiki mode)
instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # User instruction (NULL if not provided)
```

**Field semantics:**
- `source_type`: "wiki" (default) or "source_docs"
- `source_ids`: NULL for wiki mode (scope-based), array of UUIDs for source_docs mode
- `instruction`: NULL if not provided, otherwise user's custom instruction text

### Migration Strategy

```sql
ALTER TABLE wiki_mindmaps ADD COLUMN source_type VARCHAR(20) DEFAULT 'wiki';
ALTER TABLE wiki_mindmaps ADD COLUMN source_ids JSONB;
ALTER TABLE wiki_mindmaps ADD COLUMN instruction TEXT;
```

Backward compatible: existing rows get `source_type='wiki'`, `source_ids=NULL`, `instruction=NULL`.

---

## 3. API Changes

### New Endpoints

```
GET /api/mindmaps
```
List all mindmaps for the current user's accessible scopes.

Response:
```json
[
  {
    "id": "uuid",
    "scope_type": "global",
    "scope_id": null,
    "title": "Knowledge Base",
    "source_type": "wiki",
    "wiki_page_count": 24,
    "generated_at": "2026-07-05T10:30:00Z"
  }
]
```

### Modified Endpoints

```
POST /api/mindmap/generate
```

Request:
```json
{
  "scope_type": "global",
  "scope_id": null,
  "source_type": "wiki",
  "source_ids": ["uuid1", "uuid2"],
  "instruction": "Focus on API architecture"
}
```

Validation:
- `source_type` must be "wiki" or "source_docs"
- If `source_type="source_docs"`, `source_ids` must be non-empty
- `instruction` max 500 characters
- `scope_type` and `scope_id` unchanged

---

## 4. Mindmap Page UI

### Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  🌳 Mindmaps                                    [+ Generate]    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Scope      │ Source    │ Pages │ Generated    │ Actions      ││
│  ├────────────┼───────────┼───────┼──────────────┼──────────────┤│
│  │ 🌐 Global  │ Wiki      │ 24    │ 3 days ago   │ 🔄 🗑️ 👁️    ││
│  │ 🏢 Eng     │ Wiki      │ 12    │ 1 day ago    │ 🔄 🗑️ 👁️    ││
│  │ 📁 Alpha   │ Source Doc│ 5     │ today        │ 🔄 🗑️ 👁️    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Table Columns

| Column | Content | Width |
|--------|---------|-------|
| Scope | Icon + scope name (🌐 Global, 🏢 Dept, 📁 Project) | 200px |
| Source | "Wiki" or "Source Doc" badge | 100px |
| Pages | Page/source count | 80px |
| Generated | Relative time (e.g., "3 days ago") | 120px |
| Actions | Regenerate, Delete, View buttons | 120px |

### Actions

| Action | Icon | Behavior |
|--------|------|----------|
| View | 👁️ | Open full-screen viewer |
| Regenerate | 🔄 | Confirm dialog → regenerate with same settings (source_type, source_ids, instruction) |
| Delete | 🗑️ | Confirm dialog → delete mindmap |

**Regenerate behavior:**
- Uses stored `source_type`, `source_ids`, and `instruction` from the mindmap record
- Shows confirmation: "Regenerate mindmap for {scope}? This will replace the current version."
- If source docs were used, verifies source documents still exist before regenerating

### Empty State

```
🌳
No mindmaps yet
Generate a knowledge map from Wiki pages or source documents.
[Generate Mindmap]
```

### Generation Dialog

```
┌─────────────────────────────────────────────────────────────┐
│  Generate Mindmap                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Scope *                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🌐 Global                                    ▼     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Source *                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Wiki Pages                                  ▼     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [If "Source Documents" selected:]                          │
│  Select Documents *                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ☐ doc-1.pdf (2.4 MB)                              │   │
│  │ ☑ doc-2.xlsx (156 KB)                             │   │
│  │ ☑ doc-3.docx (890 KB)                             │   │
│  └─────────────────────────────────────────────────────┘   │
│  Fetches from GET /api/sources?scope_type=X&scope_id=Y     │
│                                                             │
│  Instruction (optional)                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Focus on API architecture and integration patterns  │   │
│  └─────────────────────────────────────────────────────┘   │
│  Max 500 characters                                         │
│                                                             │
│                            [Cancel]  [Generate]            │
└─────────────────────────────────────────────────────────────┘
```

### Mindmap Viewer

Full-screen view when clicking "View" (👁️):

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back    🌳 Knowledge Base    [🔄 Regenerate] [🗑️ Delete]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Tree visualization with zoom/pan controls...]                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

- Reuses existing `MindMapTree` component
- Header: back button, mindmap title, actions
- Footer: scope info, source type, generated date

---

## 5. Backend — Generation Logic

### Current Flow (Wiki only)
```
1. Fetch WikiPages in scope
2. Build payload (title + excerpt per page)
3. Call LLM with prompt template
4. Parse JSON tree
5. Enrich nodes with wiki page metadata (fuzzy match)
6. Store in wiki_mindmaps
```

### New Flow (Wiki + Source Docs)
```
1. Determine source_type
   - "wiki" → Fetch WikiPages in scope (current behavior)
   - "source_docs" → Fetch Source records by source_ids

2. Build payload
   - Wiki: title + excerpt (current)
   - Source docs: title + full_text (truncated to 8k chars)

3. Call LLM with prompt template + user instruction (if provided)
   - System prompt stays the same
   - User instruction appended: "\n\nAdditional instructions: {instruction}"

4. Parse JSON tree (unchanged)

5. Enrich nodes
   - Wiki: fuzzy match to WikiPages (current)
   - Source docs: fuzzy match to Source titles (new)

6. Generate LLM summaries for unmatched nodes (new)

7. Store in wiki_mindmaps with source_type, source_ids, instruction
```

### Source Document Payload

```python
def _build_source_doc_payload(sources: list[Source]) -> str:
    """Build payload from source documents."""
    lines = []
    for src in sources:
        title = src.title or "Untitled"
        text = (src.full_text or "")[:8000]  # ~2k tokens
        lines.append(f"- {title}: {text}")
    return "\n".join(lines)
```

### Node Enrichment for Source Docs

```python
def _enrich_tree_nodes_from_sources(tree: dict, sources: list[Source]) -> dict:
    """Enrich nodes with source document metadata."""
    lookup = {}
    for src in sources:
        if src.title:
            key = _normalize_name(src.title)
            lookup[key] = {
                "id": str(src.id),
                "title": src.title,
                "source_type": src.source_type,
            }
    
    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = f"source:{match['id']}"
            node["page_type"] = "document"
            node["summary"] = match["title"]
        for child in node.get("children", []):
            enrich_node(child)
        return node
    
    return enrich_node(tree)
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| No Wiki pages in scope | 400: "No wiki pages found for this scope" |
| No source docs selected | 400: "No source documents selected" |
| Source doc too large (>100k chars) | Use first 8k chars only |
| LLM returns invalid JSON | Retry once, then 500 |
| Instruction too long (>500 chars) | 400: "Instruction too long" |

---

## 6. LLM-Generated Node Summaries

### When to Generate

After tree JSON is generated, before storing in DB.

### Strategy

```
1. Traverse tree, collect all node names
2. For each node:
   a. If matched to Wiki page → use existing summary (skip LLM)
   b. If matched to Source doc → use source title (skip LLM)
   c. If unmatched OR summary is empty → call LLM to generate
3. Batch LLM calls (group 15 nodes per call)
4. Store enriched tree with summaries
```

### LLM Prompt

```python
_SUMMARY_PROMPT = """\
Given the following node names from a knowledge map, generate a concise 
1-2 sentence summary for each node. The summary should explain what this 
concept/topic means in the context of the knowledge base.

Node names:
{node_names}

Return JSON array:
[
  {{"name": "Node Name", "summary": "Brief explanation of the concept."}},
  ...
]

Rules:
- Summary must be max 150 characters
- Use plain language, no jargon
- If the node name is unclear, make a reasonable assumption based on context
"""
```

### Batch Processing

```python
async def _generate_node_summaries(
    nodes: list[str], 
    llm: LLM
) -> dict[str, str]:
    """Generate summaries for unmatched nodes in batches."""
    summaries = {}
    batch_size = 15
    
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i + batch_size]
        prompt = _SUMMARY_PROMPT.format(node_names="\n".join(batch))
        
        try:
            result = await llm.generate(prompt, temperature=0.3, max_tokens=1024)
            parsed = json.loads(result)
            for item in parsed:
                summaries[item["name"]] = item["summary"]
        except Exception:
            pass  # Skip summaries for this batch
    
    return summaries
```

### Storage Impact

| Metric | Before | After |
|--------|--------|-------|
| Avg node size | ~100 bytes | ~200 bytes |
| 50-node tree | ~5 KB | ~10 KB |
| Generation time | ~5s | ~8-10s (+3-5s for summaries) |

---

## 7. Chat ↔ Mindmap Interaction

### Current State (Preserved)

- Mindmap panel in Chat page: click node → "Ask Chat" seeds input
- No changes to existing behavior

### New: Mindmap Page → Chat Navigation

**"Ask in Chat" button in node popover:**

```typescript
// In Mindmap page
const handleAskInChat = useCallback((nodeName: string) => {
  router.push(`/chat?input=${encodeURIComponent(`Explain about "${nodeName}"`)}`);
}, [router]);
```

**Chat page reads prefilled input:**

```typescript
// In Chat page
const searchParams = useSearchParams();
const prefilledInput = searchParams.get("input");

useEffect(() => {
  if (prefilledInput) {
    setInput(prefilledInput);
    router.replace("/chat");
  }
}, [prefilledInput]);
```

### Interaction Matrix

| From | To | Action | Behavior |
|------|-----|--------|----------|
| Chat Panel | Mindmap Panel | "Ask Chat" | Seeds input (current) |
| Mindmap Panel | Chat Panel | "Ask Chat" | Seeds input (current) |
| Mindmap Page | Chat Page | "Ask in Chat" | Navigate with prefilled input |
| Mindmap Page | Wiki Page | "Open Page" | Navigate to wiki page |

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User not logged in | Redirect to login, then to Chat with input |
| Chat session doesn't exist | Create new session, then set input |
| Input too long (>1000 chars) | Truncate with warning |
| User already on Chat page | Use `router.push` which triggers re-render, prefilled input still works |
| User has unsent input in Chat | Overwrite with prefilled input (user can undo with Ctrl+Z) |

---

## 8. Implementation Summary

### Files to Modify

| File | Changes |
|------|---------|
| `app/database/models.py` | Add `source_type`, `source_ids`, `instruction` to WikiMindmap |
| `app/routers/mindmap.py` | Add `GET /api/mindmaps`, modify `POST /api/mindmap/generate` |
| `app/services/mindmap_service.py` | Add source doc support, LLM summary generation |
| `frontend/src/app/mindmap/page.tsx` | New mindmap page component |
| `frontend/src/components/mindmap/mindmap-list.tsx` | List view component |
| `frontend/src/components/mindmap/generation-dialog.tsx` | Generation popup |
| `frontend/src/components/mindmap/mindmap-viewer.tsx` | Full-screen viewer |
| `frontend/src/components/chat/chat-area.tsx` | Read prefilled input from URL |

### Files to Create

| File | Purpose |
|------|---------|
| `frontend/src/app/mindmap/page.tsx` | Mindmap page route |
| `frontend/src/components/mindmap/mindmap-list.tsx` | List view |
| `frontend/src/components/mindmap/generation-dialog.tsx` | Generation popup |
| `frontend/src/components/mindmap/mindmap-viewer.tsx` | Full-screen viewer |
| `alembic/versions/031_extend_wiki_mindmaps.py` | DB migration |

### Backward Compatibility

- Existing mindmaps work without changes (source_type defaults to "wiki")
- Chat panel behavior unchanged
- API responses backward compatible (new fields optional)

### Testing Strategy

- **Backend:** Unit tests for source doc payload, node enrichment, summary generation
- **Frontend:** Component tests for list view, generation dialog, viewer
- **Integration:** Generate from Wiki → verify, generate from source docs → verify, Chat navigation → verify

---

## 9. Success Criteria

1. Mindmap page accessible from top-level nav with list of all mindmaps
2. Generation dialog supports Wiki and Source Documents with custom instruction
3. Node summaries are concise, meaningful (not raw excerpts)
4. "Ask in Chat" from Mindmap page navigates to Chat with prefilled input
5. Existing Chat panel behavior unchanged
6. Backward compatible with existing mindmaps

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Large source docs exceed LLM context | Truncate to 8k chars, use summary if available |
| LLM summary generation adds latency | Batch processing (15 nodes/batch), skip if matched |
| Source doc enrichment less accurate than Wiki | Fuzzy matching threshold 0.75, fallback to "unmatched" |
| Chat prefilled input lost on page refresh | Clear URL param after reading, store in sessionStorage |
| Multiple mindmaps per scope confusing | Show scope + source type in list, allow delete |

---

## 11. Implementation Phases

### Phase 1: Mindmap Page + List View (1 sprint)
- Create `/mindmap` route
- Implement list view with table
- Add View/Regenerate/Delete actions
- Reuse existing `MindMapTree` for viewer

### Phase 2: Generation Dialog (1 sprint)
- Build generation popup with scope/source/instruction fields
- Implement source document selector
- Extend backend API to accept new parameters

### Phase 3: Source Document Support (1 sprint)
- Implement source doc payload building
- Add node enrichment for source docs
- Test with various document types

### Phase 4: LLM Node Summaries (1 sprint)
- Implement summary generation prompt
- Add batch processing logic
- Integrate into generation flow

### Phase 5: Chat ↔ Mindmap Navigation (0.5 sprint)
- Add "Ask in Chat" button to node popover
- Implement URL-based prefilled input
- Handle edge cases (no session, long input)
