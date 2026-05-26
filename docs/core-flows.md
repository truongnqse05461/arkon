# Arkon Core Flows

This document explains the main data flows in Arkon: how documents become wiki pages, how retrieval finds relevant knowledge, what worker-skills are, and how embeddings tie everything together.

---

## 1. Wiki Ingestion Pipeline (MRP)

MRP (Map-Reduce Pipeline) transforms raw documents into structured, interlinked wiki pages. The pipeline has 5 phases, each checkpointed for crash recovery.

### Phase 0: Source Entry

**Entry points:**
- `POST /sources/upload` — file upload (PDF, DOCX, etc.)
- `POST /sources/url` — URL-based source

A `Source` record is created with status `pending`, then an arq job is enqueued (`ingest_file_task` or `ingest_url_task`).

### Phase 1: Pre-Processing

**Files:** `app/worker.py`, `app/services/source_outline.py`, `app/services/image_service.py`

1. Extract text per page from the uploaded file
2. Extract images → store as `SourceImage` rows
3. Build document outline from headings/structure
4. Assemble `full_text` with inline image markers
5. If images exist → enqueue `caption_images_task` (Vision LLM captions each image, then chains to MAP)
6. If no images → enqueue `ingest_map_reduce_task` directly

### Phase 2: MAP (Parallel Chunk Extraction)

**File:** `app/ai/mrp/mapper.py`

1. **Triage** — classify document by length:
   - `< 30k chars` → single_pass
   - `30k–200k` → standard (chunked)
   - `> 200k` → hierarchical

2. **Chunking** (`build_chunks()`) — splits text into ~20k-char chunks along outline section boundaries with 1k-char overlap for context.

3. **Extraction** (`extract_chunk()`) — parallel LLM calls (max 6 concurrent) extract structured JSON from each chunk:
   - `entities[]` — named entities with type, aliases, text offset
   - `concepts[]` — terms with definition excerpts
   - `claims[]` — factual statements with confidence scores and evidence
   - `relations[]` — connections between entities
   - `topics[]` — topic tags

4. Each chunk result is persisted to `SourceChunkExtract` immediately (crash-safe).

### Phase 3: REDUCE (Deduplication & Planning)

**File:** `app/ai/mrp/reducer.py`

1. **Collect** — flatten all entities/concepts/claims from chunk extracts
2. **Exact dedup** — group by normalized name, merge aliases
3. **Embedding dedup** — embed entity names, auto-merge if cosine similarity ≥ 0.90, send ambiguous pairs (0.75–0.90) to LLM for disambiguation
4. **KB Reconciliation** — for each canonical entity, search existing wiki pages:
   - Similarity ≥ 0.85 → UPDATE existing page
   - 0.60–0.85 → LLM confirms (CREATE or UPDATE)
   - < 0.60 → CREATE new page
5. **Planning call** — single LLM call produces a Compilation Plan:
   - List of pages to create/update with slugs, titles, page types, priorities
   - Persisted to `SourceCompilationPlan`

**Approval gate:**
- If `mrp_auto_approve_plan=True` → immediately enqueue refine
- Otherwise → source status becomes `plan_ready`, user reviews in UI, then approves or requests regeneration

### Phase 4: REFINE (Wiki Page Writing)

**File:** `app/ai/mrp/writer.py`

1. **Evidence assembly** — for each planned page, collect matching claims and extract source excerpts
2. **Page writing** (max 4 concurrent):
   - **Simple writer** (< 8 evidence items): single LLM call
   - **Complex writer** (≥ 8 items): mini agent loop with tools (search_kb, read_section, generate), max 10 steps
3. Each page produces: `content_md`, `summary`, `citations`, `entity_names`
4. Drafts persisted to plan JSON for resume capability

### Phase 5: VERIFY & COMMIT

**Files:** `app/ai/mrp/verifier.py`, `app/ai/mrp/pipeline.py`

1. **Verify** — coverage check (entities mentioned ≥3 times but uncovered) and conflict check (contradictions with existing pages). Non-blocking warnings.
2. **Merge** — for UPDATE actions, LLM merges new content with existing page content (must retain ≥70% of longest input)
3. **Atomic write** — per scope (global/department/project):
   - Advisory lock per (slug, scope)
   - `wiki_service.apply_create()` or `wiki_service.apply_update()`
   - Embed page content immediately
4. **Finalize** — regenerate wiki index, append audit log, mark source as `ready`

### Pipeline Status Flow

```
pending → processing (pre-process)
       → processing (MAP + REDUCE)
       → plan_ready (awaiting approval)
       → processing (REFINE + VERIFY + COMMIT)
       → ready ✓
```

---

## 2. Retrieval (Semantic Search)

Arkon uses **pure semantic vector search** — no keyword fallback. Search operates over compiled wiki pages, not raw source chunks.

### Entry Points

| Interface | Location | Purpose |
|-----------|----------|---------|
| MCP tool `search_wiki` | `app/mcp/tools.py:228` | Claude Desktop queries the KB |
| Agent tool `search_wiki` | `app/ai/wiki_agent_tools.py:345` | LLM agent searches during compilation |
| REST `GET /wiki/pages` | `app/routers/wiki.py:195` | Frontend listing (no vector search) |

### Search Flow

```
Query string
  → Embed with active model (task="search_query")
  → Cosine similarity search in pgvector
  → Filter by scope (global/department/project) + knowledge type RBAC
  → Return top-K results ranked by similarity
```

**Core function:** `wiki_service.search_pages_semantic()` in `app/services/wiki_service.py:357`

### Scope & Access Control

Scope filtering is pushed to the SQL WHERE clause (not post-filtering):
- **Global** pages — visible to all authenticated users
- **Department** pages — visible to department members only
- **Project** pages — visible to workspace members only

The MCP tool also runs an **out-of-scope hint** query: finds top-5 results the user can't access and reports the count + scope name (never leaks titles).

### Wikilink Graph (Secondary Retrieval)

Wiki pages link to each other via `[[slug]]` syntax. The `wiki_links` table maintains a directed graph:
- `get_backlinks(slug)` — pages that reference a given page
- `get_neighborhood(slug, hops=3)` — recursive CTE for graph visualization

---

## 3. Worker-Skills

Skills are **versioned AI prompt packages** — reusable collections of files (SKILL.md + supporting content) that can be deployed globally or to specific departments. They are NOT wiki pages and are NOT embedded for search.

### How Skills Differ from Documents

| Aspect | Documents (Sources) | Skills |
|--------|-------------------|--------|
| Entry | File/URL upload | ZIP package upload |
| Processing | MRP pipeline → wiki pages | Unzip → store in MinIO |
| Output | Searchable wiki pages | Versioned file packages |
| Worker queue | Default queue | `skills_queue` (separate) |
| Embedding | Yes (wiki pages are embedded) | No |

### Skill Lifecycle

1. **Upload** — `POST /skills/upload` with ZIP containing `SKILL.md`
2. **Validation** — check for SKILL.md, Zip Slip protection, bomb detection
3. **Ingestion** (`ingest_skill_task`) — unzip, upload files to MinIO at `skills/{id}/versions/{n}/content/`, compute SHA256 hash
4. **Versioning** — each upload creates a `SkillVersion` record; hash comparison skips no-op re-uploads
5. **Deletion** (`delete_skill_task`) — soft-delete (status → `deleting`), then background cleanup of MinIO prefix + DB rows

### Contribution Workflow

Skills support a PR-style contribution flow:
- Contributors submit changes via `SkillContribution` (status: draft → pending → approved/rejected)
- Editors review and approve → merges as new version
- Supports forking from a base version

### SkillWorkerSettings

```python
class SkillWorkerSettings:
    functions = [ingest_skill_task, delete_skill_task]
    queue_name = "skills_queue"  # Isolated from document ingestion
    max_jobs = 3
    job_timeout = 1800
```

The separate queue ensures skill operations don't compete with heavy MRP pipeline jobs.

---

## 4. Embeddings

Embeddings are the bridge between human-readable wiki content and machine-searchable vectors. They enable semantic retrieval — finding pages by meaning rather than keywords.

### What Gets Embedded

**Only wiki pages.** Not raw sources, not skills, not chunks. Each page is embedded as a single vector from:

```
"{title}\n\n{summary}\n\n{content_md}"[:8000]
```

### When Embeddings Are Created

1. **During COMMIT phase** — immediately after a wiki page is created/updated by MRP
2. **During re-embed job** — when admin switches to a new embedding model

### Storage

PostgreSQL pgvector with per-dimension tables:

| Table | Dimension | Vector Type |
|-------|-----------|-------------|
| `wiki_page_embeddings_768` | 768 | Vector |
| `wiki_page_embeddings_1024` | 1024 | Vector |
| `wiki_page_embeddings_1536` | 1536 | Vector |
| `wiki_page_embeddings_3072` | 3072 | HALFVEC (HNSW compatible) |

Each row stores: `page_id`, `model_spec_id`, `embedding`, `content_hash` (SHA256 for change detection), `embedded_at`.

### Supported Models

- Google Gemini Embedding 001/002 (3072d)
- OpenAI text-embedding-3-small (1536d) / large (3072d)
- Custom OpenAI-compatible endpoints (768/1024/1536/3072d)

### Embeddings in the MRP Pipeline

Beyond search, embeddings are used during REDUCE phase:
- **Entity deduplication** — embed entity names, merge if cosine similarity ≥ 0.90
- **KB reconciliation** — embed entity/concept names, search existing wiki to decide CREATE vs UPDATE

### Re-Embed Flow

When admin switches embedding models (`reembed_all_pages_task`):
1. Process all pages in batches of 50 with the NEW model
2. Store vectors in the new dimension table (old model still active)
3. **Atomic flip** — update `active_embedding_model_spec_id` in one transaction
4. Clean up stale embeddings from old model
5. Zero-downtime: search uses old model until flip completes

### Why Page-Level (Not Chunk-Level)

Arkon embeds entire wiki pages rather than source chunks because:
- Wiki pages are **compiled knowledge** — deduplicated, structured, and interlinked
- Each page is a coherent unit (concept, process, reference) rather than an arbitrary text window
- The wikilink graph provides navigation that chunk-based RAG lacks
- Retrieval returns complete, readable pages — no reassembly needed
