# Document Translation Pipeline Design

## Goal

Let departments upload foreign-language documents (initially Chinese client docs) and produce wiki pages that internal users can actually read — without losing the source-language fidelity that's needed for accurate citation.

The wiki today preserves source language end-to-end: a Chinese doc produces Chinese pages with Chinese titles in the UI list. Non-Chinese users can't browse, can't comprehend page contents, and only get partial value via LLM responses that mix English answers with Chinese excerpts.

This design adds an optional **TRANSLATE** phase to the MRP pipeline that produces **dual-pane pages** — each page stores both the source-language content and a target-language translation, side-by-side.

## Non-Goals

- **Cross-lingual KB unification.** If an EN doc and a ZH doc describe the same product, they still produce separate wiki pages. Solving cross-lingual entity dedup is deferred.
- **Multi-target translation per page.** One source + one target language per page in v1.
- **Manual translation editing.** Reviewers cannot hand-edit the translated half; they edit the source and retranslate.
- **Glossary / translation memory management.**
- **Translating skill packages or chat messages.** Scope is wiki pages produced by MRP.

## Architecture

The pipeline gains a new phase between REFINE and VERIFY:

```
Phase 0  Source Entry      — upload form gains target_language dropdown
Phase 1  Pre-Processing    — adds language detection on first ~2k chars
Phase 2  MAP               — unchanged (extracts in source language)
Phase 3  REDUCE            — unchanged (plan review still works as today)
Phase 4  REFINE            — unchanged (writer rule "never translate" stays)
Phase 4.5 TRANSLATE  [NEW] — per-page LLM call producing translated title/summary/body
Phase 5  VERIFY            — extended with translation-completeness check
Phase 6  COMMIT            — writes both halves; embeds both languages
```

**Why a dedicated phase rather than baking translation into the writer:**
- Writer prompt stays focused on compilation, which is already complex.
- Translation failures don't block COMMIT — page can ship monolingual and retry later.
- Same code path serves backfill: translating existing pages reuses the phase verbatim.
- Translation model is configurable independently (often a cheaper model than the writer).

## Data Model Changes

### `Source` table

```python
source_language: Mapped[str | None]    # auto-detected, ISO 639-1: "zh", "en", "vi", ...
target_language: Mapped[str | null]    # uploader choice; null means no translation
```

### `WikiPage` table

```python
source_language: Mapped[str | None]
target_language: Mapped[str | None]    # immutable after first set in v1
title_translated: Mapped[str | None]
summary_translated: Mapped[str | None]
content_md_translated: Mapped[str | None]
translation_status: Mapped[str]        # "pending" | "done" | "skipped" | "failed"
```

Dedicated columns rather than `translations: jsonb` because v1 caps at one target language per page. The schema is forward-compatible — adding `translations: jsonb` later doesn't conflict.

### `wiki_page_embeddings_<dim>` tables (per-dimension)

Add a `language` column (`"source"` or `"target"`). The composite key becomes `(page_id, model_spec_id, language)`. Existing rows backfill to `language='source'` during the migration.

## Phase 1 — Language Detection

Library-based detection on the first ~2 000 characters of `full_text`:
- Primary: `fasttext-langdetect` (or `langid` as a lighter alternative).
- Cost: ~10 ms, no API call.
- Output: ISO 639-1 code stored on `source.source_language`.

Detection runs once, after text extraction, before MAP. If detection confidence is low (`< 0.6`), `source_language` stays `null` and translation is skipped with `translation_status='skipped'` and a non-blocking warning.

## Phase 4.5 — TRANSLATE

### Skip conditions

Evaluated at phase entry; the LLM is never invoked when any of these holds:

1. `source.target_language` is null.
2. Detected `source_language == target_language`.
3. Detected `source_language` is null (low-confidence detection).

### Per-page translation call

For each page produced by REFINE, the translator receives `{title, summary, content_md}` and emits `{title, summary, content_md}` in the target language. Concurrency cap matches the writer (max 4).

**Prompt skeleton:**

```
You are a translator. Translate the following wiki page from {source_lang}
to {target_lang}. Rules:

- Preserve [[slug]] and [[slug|display]] wikilinks verbatim (slugs never translate).
- Preserve 【...】 citation brackets verbatim.
- Preserve fenced code blocks, math blocks (```math), and inline `code` verbatim.
- Preserve markdown structure: headings stay headings, lists stay lists,
  table rows stay table rows.
- Translate the visible heading text and prose.
- For named regulations, laws, product codes, model numbers, and proper nouns
  with no widely-known translated form: keep the original in parentheses after
  the translation on first mention only.
  Example: "Phòng cháy chữa cháy (灭火) is governed by..."
- Return JSON: {"title": "...", "summary": "...", "content_md": "..."}
```

### Output validation

Before persisting:
- JSON parses.
- All three keys present and non-empty.
- `content_md` length is between 50 % and 200 % of the source's length (catches truncation and runaway expansion).
- Wikilink count in source matches wikilink count in translation (preservation check).
- Citation bracket count (`【…】`) in source matches translation.

Failures mark the page `translation_status='failed'`, log a warning, and let COMMIT proceed without the translated half.

### LLM choice

Defaults to the same LLM the writer uses. Configurable via a new setting `settings.translation_model_spec_id` so admins can route translation to a cheaper model (e.g. Gemini Flash) since translation is more mechanical than compilation.

## UPDATE Behavior Across Different Target Languages

Each page's `target_language` is immutable after first set. The decision matrix for an UPDATE action with this design:

| Page's `target_language` | Source's `target_language` | Behavior |
|---|---|---|
| null | null | No translation; page stays monolingual. |
| null | `vi` | Page adopts `target_language=vi`. Translation runs on the new content; the carried-over older content is translated too (one-time backfill of the existing half) within the same TRANSLATE phase. |
| `vi` | `vi` | Translation runs normally. |
| `vi` | `en` | Source's `target_language` is overridden to `vi`. Translation runs in `vi`. A non-blocking warning is appended to `source.error_message`: `"Page concept/X is in VI; your EN target was overridden."` |
| `vi` | null | No new translation requested, but the writer regenerated source content — translator re-runs for the target to keep the two halves aligned. |

**Rationale for immutable target_language:** multi-target adds storage, dedup complexity, and UI weight. The current model leaves room to lift this constraint later (move to `translations: jsonb`) without re-migrating embeddings.

## Phase 5 — VERIFY Extensions

The existing verifier gains one non-blocking check:

- For every plan page with `translation_status='failed'`, append a warning to the source's audit log: `"Translation failed for page concept/X — page committed source-only. Retry via admin tool."`

Coverage and conflict checks are unchanged.

## Phase 6 — COMMIT Changes

For each page being created or updated:

1. Write both source-language and (if applicable) target-language fields in a single transaction.
2. Compute embeddings for both halves:
   - `content_hash_source = sha256(title + summary + content_md)`
   - `content_hash_target = sha256(title_translated + summary_translated + content_md_translated)`
3. Upsert two rows into `wiki_page_embeddings_<dim>`: one with `language='source'`, one with `language='target'`. The hash short-circuits re-embedding if content didn't change.
4. If `translation_status='failed'`, only the source row is written.

## Search Behavior

`wiki_service.search_pages_semantic()` is extended:

1. Embed the query once with the active model (task `RETRIEVAL_QUERY`).
2. Cosine-search against rows in `wiki_page_embeddings_<dim>` regardless of `language`.
3. Group results by `page_id`, keep the max-similarity hit per page.
4. Include `matched_language` in the result row so the UI can highlight the matched pane.

No translation of the query string; the multilingual embedding space does the bridging.

## UI / Rendering

| Surface | Change |
|---|---|
| Source upload form | Add `target_language` dropdown: `None / Vietnamese / English` (extensible). |
| Wiki page view | Header toggle: `Source` / `Translated` / `Side-by-side`. Default is `Side-by-side` for bilingual pages; user's last choice is remembered in `localStorage` (key `wiki.bilingual.mode`). Monolingual pages render as today (toggle hidden). |
| Wiki listing | Show both titles for bilingual pages: `title` with `title_translated` on a second line in muted color, plus a `ZH→VI` badge. Monolingual rows unchanged. |
| Search results | Show the snippet from `matched_language`; offer a "show other language" affordance when the page is bilingual. |
| Chat citations | Citation labels show `title` (source-language) by default to match the existing format. Bilingual pages display the translated title on a second line inside the citation panel when opened. |

v1 deliberately avoids introducing a per-user language preference — that's a larger product decision (account settings, persistence, defaults) and is not required for the comprehension use case. `localStorage` covers the immediate need; a real preference can be added later without rework.

A new React component `BilingualPageView` takes both halves and a `mode` prop (`source` | `target` | `side`). Existing single-language rendering becomes a special case (`mode='source'` enforced).

## Backfill — Translating Existing Pages

Admin tool: `POST /admin/translate-pages` with body:

```json
{
  "scope_type": "department",
  "scope_id": "<uuid>",
  "target_language": "vi",
  "page_ids": ["..."],          // optional; if omitted, all pages in scope
  "force": false                // re-translate already-translated pages
}
```

Enqueues a background job `backfill_translate_pages_task` that:

1. Iterates pages where `target_language IS NULL` (or all pages if `force=true`).
2. Runs the same Phase 4.5 translator per page.
3. Re-embeds the target half.
4. Updates `translation_status` and audit log.

Progress is reported via the existing source-progress tracking style so the admin UI can poll.

## File Structure

**New files:**
- `app/ai/mrp/translator.py` — TRANSLATE phase: per-page LLM call, validation, output assembly.
- `app/services/language_detection.py` — thin wrapper around the langdetect library.
- `app/routers/admin_translation.py` — new `POST /admin/translate-pages` endpoint + status polling.
- `frontend/src/components/wiki/bilingual-page-view.tsx` — dual-pane renderer with mode toggle.
- `alembic/versions/<NNN>_translation_fields.py` — schema migration for the new columns.

**Modified files:**
- `app/ai/mrp/pipeline.py` — wire TRANSLATE between REFINE and VERIFY; extend resume logic to handle the new phase.
- `app/ai/mrp/verifier.py` — add translation-completeness warning.
- `app/database/models.py` — new columns on `Source`, `WikiPage`, `wiki_page_embeddings_*`.
- `app/routers/sources.py` — accept `target_language` on upload; surface translation status in source detail.
- `app/worker.py` — register `backfill_translate_pages_task`.
- `app/services/wiki_service.py` — `search_pages_semantic()` returns `matched_language`; queries both language rows.
- `app/services/embedding_storage.py` — upserts keyed by `(page_id, model_spec_id, language)`.
- `app/config.py` — new translation-related settings (see Configuration section).
- `frontend/src/components/knowledge/upload-dialog.tsx` — add `target_language` dropdown.
- `frontend/src/components/wiki/wiki-content.tsx` — render via `BilingualPageView` for bilingual pages.
- `frontend/src/components/knowledge/knowledge-table/` — show language badge on source rows; show translation status.
- `frontend/src/components/chat/citation-panel.tsx` — show translated title for bilingual pages.

## Configuration

```python
# app/config.py additions
translation_enabled: bool = True
translation_model_spec_id: str | None = None  # fall back to writer model if null
translation_default_target_language: str | None = None  # optional UI hint only
language_detection_min_confidence: float = 0.6
```

No env-var changes required beyond the new settings.

## Testing Strategy

**Unit:**
- `translator.py`: prompt formatting; validation rules (length bounds, wikilink count, citation count); JSON parsing failure paths.
- `language_detection.py`: known-language fixtures (ZH/EN/VI), low-confidence inputs.

**Integration:**
- End-to-end MRP run on a small Chinese fixture doc with `target_language='vi'`:
  - asserts `WikiPage.source_language='zh'`, `target_language='vi'`, both content halves populated.
  - asserts two rows in `wiki_page_embeddings_<dim>` per page.
  - asserts `search_pages_semantic("bình chữa cháy")` returns the page with `matched_language='target'`.
- UPDATE path: re-upload a different ZH doc updating the same page; assert translation re-runs and both halves stay consistent.
- Skip path: ZH doc with `target_language=null` → no translation rows, no `translation_status` failure.
- Conflict path: VI page exists, upload requests EN translation → page stays VI, warning is logged.

**Manual:**
- UI toggle (`Source / Translated / Side-by-side`) renders correctly for bilingual and monolingual pages.
- Search results highlight the matched-language snippet.

## Migration / Rollout

1. Ship migration adding the new columns with safe defaults (`translation_status='skipped'` for existing pages).
2. Deploy backend with `translation_enabled=False` by default — the new code paths exist but are inactive.
3. Backfill embeddings: existing single-row embeddings get `language='source'` written in the migration.
4. Smoke-test in staging with a fixture Chinese doc.
5. Enable `translation_enabled=True` per tenant. Admin UI shows the `target_language` dropdown.
6. Backfill existing wiki pages on request via the admin tool.

## Open Risks

- **Translation quality on technical content.** The "keep original in parentheses on first mention" rule helps but doesn't guarantee correct technical terminology. A glossary mechanism is deferred; tenants needing tight terminology control will see translation errors until that ships.
- **Cost.** Translating every page doubles the per-source LLM spend. Mitigations: cheaper model via `translation_model_spec_id`; skip-when-same; per-upload opt-in.
- **Embedding storage doubles for translated pages.** With pgvector HNSW indexes, query latency grows sub-linearly, but storage planning should anticipate 1.5–2x growth for bilingual tenants.
- **Mid-pipeline target_language change races.** If two uploads race to set the same page's target_language for the first time, the second wins by last-write semantics. Acceptable since both writes would translate to the same language in practice; the SELECT FOR UPDATE pattern already used in plan transitions can be lifted here if needed.
