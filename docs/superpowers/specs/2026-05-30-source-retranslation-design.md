# Source Re-translation — Fix Wrong or Missing Translations

## Goal

Let a user re-run translation on an already-ingested document when:

1. **The wrong language was chosen at upload** — e.g. the uploader picked English in the "Translate to" dropdown but meant Vietnamese, or the auto-detected *source* language was off, so the page was translated from/into the wrong language (or silently skipped).
2. **The document was uploaded with no translation** — `target_language` was left null, and the user now wants a translation added.

The fix is a per-source **Re-translate** action that lets the user (re)set the target language — and, when needed, correct the auto-detected source language — then reruns just the TRANSLATE step over that document's wiki pages. No re-ingestion, no re-compilation.

## Non-Goals

- **Re-running MAP/REDUCE/REFINE.** This feature touches only the already-committed `WikiPage` translation fields and their target-language embeddings. Source content compilation is untouched.
- **Per-page language choice.** One source language and one target language per document, applied to all of that document's pages (consistent with the existing one-target-per-page model).
- **Mixed-language documents.** A document with genuinely mixed source languages is not special-cased; the source override is document-wide.
- **Manual editing of the translated text.** Same as the base translation feature — users re-translate, they don't hand-edit.
- **Changing the admin bulk tool's contract.** `POST /admin/translate-pages` keeps its current behavior; it is only refactored internally to share the new per-page helper.

## Background — Current State

- **Upload** (`POST /sources/upload`, `app/routers/sources.py`) accepts a `target_language` form field, stored on `Source.target_language`. Pre-processing (`ingest_file_task` / `ingest_url_task` in `app/worker.py`) auto-detects `Source.source_language` from `full_text` when a target is set and source is still unknown.
- **TRANSLATE phase** (`app/ai/mrp/translator.py`, wired in `app/ai/mrp/pipeline.py`) translates each page when a target is set, source is detected, and the two differ. COMMIT writes both halves and dual embeddings (`language='source'` / `language='target'`) into the per-dimension `wiki_page_embeddings_<dim>` tables.
- `WikiPage.target_language` is documented as **immutable after first set**, and `WikiPage` carries `translation_status` ∈ `{pending, done, skipped, failed}`.
- A **`backfill_translate_pages_task`** (`app/worker.py:1103`) already exists behind admin-only `POST /admin/translate-pages` — scope-based (global/department/project), with a `force` flag to re-translate. It updates `WikiPage` rows but **not** the `Source`, has no per-source entry point, only logs progress, and does not handle "remove translation" or a source-language override.
- The per-source `POST /sources/{id}/retry` endpoint only handles `error`/`plan_ready` status and re-runs ingestion phases — it does not re-run translation alone.

## Decisions

Settled during brainstorming:

1. **Trigger model: per-source action.** A "Re-translate" item on each document row in the knowledge table, available to users who can edit the doc. The admin bulk tool stays as-is.
2. **Allowed target transitions: add, change, and remove.** `null → vi` (add), `vi → en` (change, replacing the translation + its embedding), and `vi → null` (remove, clearing translated fields + target embeddings). This fully relaxes the v1 immutability rule for the target language.
3. **Source language is correctable.** The dialog shows the detected source language and lets the user override it (default: keep detected). This covers translations that were skipped or wrong because detection was off.
4. **Backend approach: a dedicated endpoint + focused worker task, sharing one per-page helper.** The per-page translate+embed logic currently inlined in `backfill_translate_pages_task` is refactored into a shared helper so the admin tool and the new flow use one correct implementation, including the new remove/override/cleanup paths.

## Section 1 — API Contract & Status Model

**Endpoint:** `POST /sources/{source_id}/retranslate` (added to `app/routers/sources.py`, next to `/retry`).

- **Permission:** `doc:edit` (same as `/retry` and `update_source`); admins included via the permission engine.
- **Preconditions** (else `400`): source exists and is accessible; `source.status == "ready"`; the source has ≥ 1 wiki page; `settings.translation_enabled` is on.
- **Request body:**

  ```python
  class RetranslateRequest(BaseModel):
      target_language: Optional[str] = None   # ISO 639-1; null = remove translation
      source_language: Optional[str] = None   # null = keep stored/auto-detected; else override
  ```

- **Validation:** `target_language` and `source_language` (when present) are constrained to the curated UI set (`vi`, `en`, `zh`, `ja`; lowercased; len ≤ 8). If `target_language` is non-null and equals the effective source language — the `source_language` override when provided, else `source.source_language` → `400 "Source and target language must differ."`
- **Effect:** set `Source.target_language` to the requested value (and `Source.source_language` when an override is provided) immediately, so the row badge reflects intent; set `status="translating"`, `progress=0`, `progress_message="Re-translating…"`, clear `error_message`; enqueue `retranslate_source_task(source_id, target_language, source_language)`. Return `{"queued": True, "job_id": ..., "status": "translating"}`.

**Status model:** introduce a new `Source.status` value **`"translating"`**. The existing `GET /sources/{id}/progress` endpoint already returns `status/progress/progress_message`, so the frontend reuses its current polling. On completion the task sets status back to **`"ready"`** with a summary of outcomes in `progress_message` (translated / skipped / removed / failed counts; see Section 2). Per-page translation failures are **non-blocking** — recorded on `WikiPage.translation_status`, never flipping the source to `error`, so the action can simply be re-run. Search is unaffected throughout: it reads `WikiPage` embeddings, and rows are overwritten or deleted in place.

## Section 2 — Worker Task & Per-Page Logic

**New shared helper — `app/services/retranslation.py`.** The per-page translate+embed logic inlined in `backfill_translate_pages_task` moves here as `retranslate_page(...)`, and the admin task is refactored to call it. One implementation, used by both the admin bulk tool and the new per-source flow:

```python
async def retranslate_page(
    session,
    page: WikiPage,
    target_language: Optional[str],     # None = remove translation
    source_override: Optional[str],     # None = keep page.source_language / auto-detect
    llm,
    embedder,                           # may be None (embeddings best-effort)
    active_spec,                        # may be None
) -> str:                               # outcome: "done" | "skipped" | "failed" | "removed"
```

**Effective source language** = `source_override` → else `page.source_language` → else library detection on `page.content_md`, accepted only at/above `settings.language_detection_min_confidence`.

**Per-page decision table:**

| Condition | Action | `translation_status` | Outcome |
|---|---|---|---|
| **Remove** — `target_language is None` | Clear `title_translated`/`summary_translated`/`content_md_translated`; set `target_language=None`; `delete_page_embedding(language="target")` | `"skipped"` | `removed` |
| **Skip** — effective source unknown, or `source == target` | Set `target_language`; clear any now-stale translated fields + target embedding | `"skipped"` | `skipped` |
| **Translate success** | Write `*_translated`; set `source_language`, `target_language`; upsert target embedding (new content hash → re-embed) | `"done"` | `done` |
| **Translate failure** (`translate_page` → None / raises) | Clear stale translated fields + target embedding (no wrong-language remnant); set `target_language` | `"failed"` | `failed` |

When a `source_override` is supplied it is written to `page.source_language` in every branch where the page is otherwise updated.

**New task — `retranslate_source_task(ctx, source_id, target_language, source_language)`** (`app/worker.py`):

1. Open a session; load the source. If missing, return.
2. Resolve the source's pages: `WikiPage` where `source_ids.any(source.id)` (the same matcher `_wiki_page_count` uses).
3. Acquire `llm` + `embedder` + `active_spec` from `ProviderRegistry` (mirrors `backfill_translate_pages_task`); embedder/spec may be `None` (embeddings stay best-effort, non-blocking).
4. Iterate pages **sequentially**, calling `retranslate_page(...)`, committing per page, and pushing progress through the existing `ProgressTracker` (`ProgressTracker(source_id)` → `await tracker.update(pct, msg)`), scaling `pct` 0→100 across the page set so the existing poll shows live status. Sequential mirrors today's backfill; bounded per-page concurrency is a noted future optimization.
5. After the loop: persist `Source.target_language = target_language` and `Source.source_language = source_language or source.source_language`; set `status="ready"`, `progress=100`, `progress_message="Re-translation complete: {done} done, {skipped} skipped, {removed} removed, {failed} failed"`. Commit.
6. On unexpected exception: restore `status="ready"` (the document stays usable) with a short note in `progress_message`, using the `asyncio.shield` error-marking pattern the ingest tasks already use; log the error.
7. Register `retranslate_source_task` in the worker `functions` list (`app/worker.py:1247`).

**Embedding cleanup — `delete_page_embedding(session, page_id, language="target")`** added to `app/services/embedding_storage.py`. Removes the page's target-language row across the per-dimension embedding tables, so the remove/skip/failure paths leave no stale vectors. The **change** path (e.g. vi→en) needs no explicit delete — the `language="target"` slot is overwritten in place by `upsert_page_embedding`, since `language` is the abstract `"target"`, not the language code.

**Multi-source pages:** a page assembled from several sources is matched by `source_ids.any(source.id)` and re-translated too; the user's requested target wins (last-write). This is consistent with the existing one-target-per-page model and is documented in Risks rather than guarded.

## Section 3 — UI

**New dialog — `frontend/src/components/knowledge/knowledge-table/retranslate-dialog.tsx`** (co-located with `edit-source-dialog.tsx`), styled to match the existing dialogs (`Dialog` / `Select` / `Label` / `Button`):

- **Translate to** — `Select` prefilled from `source.target_language`: `No translation` / Vietnamese (`vi`) / English (`en`) / Chinese (`zh`) / Japanese (`ja`) — the same list as the upload dialog.
- **Source language** — a secondary ("advanced") `Select` defaulting to `Auto-detected (XX)` showing the current `source.source_language`; it sends an override only when the user changes it.
- Helper text: *"Use this if the wrong language was chosen at upload, to add a missing translation, or to replace/remove the current one. Re-translation reruns on this document's wiki pages."*
- Inline guard: if target ≠ "No translation" and target === effective source → *"Source and target language must differ."*
- Submit → `POST /api/sources/{id}/retranslate` with `{ target_language: target || null, source_language: override || null }`; on success call `onClose()` + `onRefresh()`.

**Table action — `frontend/src/components/knowledge/knowledge-table/index.tsx`:** add a **Re-translate** `DropdownMenuItem` (icon `translate`) shown when `source.status === "ready"`, opening the dialog via a `retranslateSource` state slot that mirrors `editSource` / `reviewPlanSource`. The existing `SRC → TGT` badge on the row already re-renders from the refreshed source, so adding/changing/removing a translation updates (or hides) the badge automatically.

**Status — `frontend/src/components/knowledge/knowledge-table/status-dot.tsx`:** add `translating` to the color map (a distinct hue — e.g. indigo — so it reads differently from yellow `processing`) with label **"Translating"**, and include `translating` wherever `processing` already shows `(progress%)` and the `progress_message` line.

**Live updates — `frontend/src/app/(portal)/knowledge/page.tsx:107`:** extend the existing poll predicate (`status === "pending" || "processing" || "plan_ready"`) to also include `"translating"`, so progress updates without a manual refresh.

## Section 4 — Testing

- **Endpoint** (`tests/test_retranslate_endpoint.py`): non-`ready` status → 400; `target == effective source` → 400; missing `doc:edit` → 403; `translation_enabled=False` → 400; happy path enqueues the task, flips `status="translating"`, and persists the requested `target_language`.
- **Helper** (`tests/test_retranslation.py`, stub LLM + embedder) — one case per decision-table row: add (`null→vi`) writes fields + upserts `language="target"`; change (`vi→en`) overwrites; remove (`→null`) clears fields + calls `delete_page_embedding`, status `"skipped"`; skip (`source==target` / unknown) clears stale fields; failure (`translate_page`→None) → `"failed"` + stale cleared; source override propagates to `page.source_language`.
- **Task**: resolves pages via the `source_ids` matcher; one page failing leaves the others `done` and the source `ready` (non-blocking); the final `progress_message` summary counts are correct.
- **Embedding storage**: `delete_page_embedding` removes target rows across dimensions and leaves the `source` row intact.
- **Frontend (manual)**: dialog renders and prefills; the same-language inline guard fires; the `translating` status and live progress render.

## Files

**New**

- `app/services/retranslation.py` — shared `retranslate_page(...)` helper + outcome constants.
- `frontend/src/components/knowledge/knowledge-table/retranslate-dialog.tsx` — the dialog.
- `tests/test_retranslation.py` — per-page helper tests.
- `tests/test_retranslate_endpoint.py` — endpoint tests.

**Modified**

- `app/routers/sources.py` — `RetranslateRequest` model + `POST /sources/{id}/retranslate`.
- `app/worker.py` — `retranslate_source_task` + registration in `functions`; refactor `backfill_translate_pages_task` onto the shared helper.
- `app/services/embedding_storage.py` — `delete_page_embedding(session, page_id, language)`.
- `frontend/src/components/knowledge/knowledge-table/index.tsx` — Re-translate menu item + dialog slot.
- `frontend/src/components/knowledge/knowledge-table/status-dot.tsx` — `translating` status.
- `frontend/src/app/(portal)/knowledge/page.tsx` — add `translating` to the poll predicate (line ~107).

## Configuration

None new. The endpoint reuses the existing `settings.translation_enabled` (`app/config.py:76`) and `settings.language_detection_min_confidence` (`app/config.py:93`). No database migration is required — `"translating"` is a new value for the existing `Source.status` string column, and all translation columns already exist.

## Risks / Known Behavior

- **Shared (multi-source) pages** are re-translated with last-write-wins on the target — consistent with the existing one-target-per-page model; documented, not guarded.
- **Cost & time:** one LLM call per page, run sequentially; long documents take proportionally longer (progress is shown). Bounded concurrency is a future optimization.
- **Source override is document-wide:** genuinely mixed-language documents aren't special-cased (out of scope; matches current single-source-language detection).
- **Best-effort embeddings:** if the embedding provider is unavailable mid-run, target vectors may lag until the next run — the same non-blocking behavior the backfill already has.
