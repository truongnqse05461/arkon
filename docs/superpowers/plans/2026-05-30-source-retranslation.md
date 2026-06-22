# Source Re-translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-source "Re-translate" action that lets a user fix a wrong target language, add a missing translation, or remove one — re-running only the TRANSLATE step over that document's wiki pages.

**Architecture:** A new `POST /sources/{id}/retranslate` endpoint validates input, flips the source to a new `translating` status, and enqueues `retranslate_source_task`. That task resolves the source's `WikiPage` rows and calls a new shared helper `retranslate_page()` (in `app/services/retranslation.py`) once per page. The same helper is refactored out of the existing admin `backfill_translate_pages_task`, so add/change/remove + embedding cleanup live in one tested place. The frontend gets a dialog + dropdown action + a `translating` status indicator.

**Tech Stack:** Python (FastAPI, SQLAlchemy async, arq, loguru, pytest), TypeScript/React (custom Next.js, shadcn-style UI components).

**Spec:** `docs/superpowers/specs/2026-05-30-source-retranslation-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `app/services/embedding_storage.py` *(modify)* | Add `delete_page_embedding()` — drop a page's target-language vector across all per-dimension tables. |
| `app/services/retranslation.py` *(create)* | The per-page `retranslate_page()` helper (add / change / remove / skip / fail), shared by the new task and the admin backfill. |
| `app/worker.py` *(modify)* | New `retranslate_source_task`; register it; refactor `backfill_translate_pages_task` onto the shared helper. |
| `app/routers/sources.py` *(modify)* | `RetranslateRequest` model + `POST /sources/{id}/retranslate`. |
| `frontend/.../knowledge-table/retranslate-dialog.tsx` *(create)* | The re-translate dialog (target + optional source override). |
| `frontend/.../knowledge-table/index.tsx` *(modify)* | "Re-translate" dropdown item + dialog slot. |
| `frontend/.../knowledge-table/status-dot.tsx` *(modify)* | Render the new `translating` status. |
| `frontend/.../app/(portal)/knowledge/page.tsx` *(modify)* | Keep polling while a source is `translating`. |
| `tests/test_embedding_storage_language.py` *(modify)* | Test `delete_page_embedding`. |
| `tests/test_retranslation.py` *(create)* | Decision-table tests for `retranslate_page` + worker-task registration. |
| `tests/test_retranslate_endpoint.py` *(create)* | Endpoint request-model + signature tests. |

**Build order:** Task 1 → 2 → 3 → 4 → 5 (backend), then 6 → 7 → 8 (frontend). Tasks 2–4 depend on Task 1; Task 3 and 4 depend on Task 2.

---

## Task 1: `delete_page_embedding` helper

**Files:**
- Modify: `app/services/embedding_storage.py`
- Test: `tests/test_embedding_storage_language.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_embedding_storage_language.py`:

```python
@pytest.mark.asyncio
async def test_delete_page_embedding_targets_language_across_dims():
    """Deletes the (page, language) row from every per-dimension table."""
    from app.services.embedding_storage import delete_page_embedding

    session = AsyncMock()
    await delete_page_embedding(session, uuid.uuid4(), language="target")

    # One DELETE per per-dimension table (768 / 1024 / 1536 / 3072).
    assert session.execute.await_count == 4
    stmt = session.execute.await_args_list[0].args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "DELETE FROM" in compiled.upper()
    assert "'target'" in compiled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_embedding_storage_language.py::test_delete_page_embedding_targets_language_across_dims -v`
Expected: FAIL with `ImportError: cannot import name 'delete_page_embedding'`.

- [ ] **Step 3: Write minimal implementation**

Add to `app/services/embedding_storage.py` (after `cleanup_stale_embeddings`; `delete`, `AsyncSession`, and `uuid` are already imported at the top of the file):

```python
async def delete_page_embedding(
    session: AsyncSession,
    page_id: uuid.UUID,
    language: str = "target",
) -> None:
    """Delete a page's (language) embedding row from every per-dimension table.

    Used when a translation is removed or replaced so stale vectors don't
    linger. Re-translation only ever removes the ``"target"`` slot; the
    ``"source"`` row is left untouched.
    """
    from app.database.models import (
        WikiPageEmbedding768,
        WikiPageEmbedding1024,
        WikiPageEmbedding1536,
        WikiPageEmbedding3072,
    )

    for Model in (
        WikiPageEmbedding768,
        WikiPageEmbedding1024,
        WikiPageEmbedding1536,
        WikiPageEmbedding3072,
    ):
        await session.execute(
            delete(Model).where(Model.page_id == page_id, Model.language == language)
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_embedding_storage_language.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add app/services/embedding_storage.py tests/test_embedding_storage_language.py
git commit -m "feat(embeddings): add delete_page_embedding for language slot cleanup"
```

---

## Task 2: `retranslate_page` shared helper

**Files:**
- Create: `app/services/retranslation.py`
- Test: `tests/test_retranslation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_retranslation.py`:

```python
"""Decision-table tests for the per-page re-translation helper.

`retranslate_page` mutates a WikiPage in place and returns an outcome string.
We patch the translator + embedding helpers so these stay pure unit tests
(no LLM, no DB).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.database.models import WikiPage
from app.ai.mrp.translator import TranslationOutput
from app.services.retranslation import retranslate_page


def _page(**kw) -> WikiPage:
    defaults = dict(
        id=uuid.uuid4(),
        slug="concept/x",
        title="T",
        page_type="concept",
        content_md="some body content",
        summary="sum",
        source_language=None,
        target_language=None,
        translation_status="skipped",
        title_translated=None,
        summary_translated=None,
        content_md_translated=None,
    )
    defaults.update(kw)
    return WikiPage(**defaults)


@pytest.mark.asyncio
async def test_add_translates_and_embeds():
    page = _page(source_language="zh")
    out = TranslationOutput(title="Bình", summary="cong cu", content_md="Bình chữa cháy ...")
    embedder = AsyncMock()
    embedder.embed.return_value = [0.1] * 8
    spec = object()  # truthy active_spec
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=out)), \
         patch("app.services.retranslation.upsert_page_embedding", AsyncMock()) as up, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), embedder, spec)

    assert outcome == "done"
    assert page.target_language == "vi"
    assert page.source_language == "zh"
    assert page.content_md_translated == "Bình chữa cháy ..."
    assert page.translation_status == "done"
    up.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_overwrites_without_delete():
    page = _page(source_language="zh", target_language="en",
                 translation_status="done", content_md_translated="old english")
    out = TranslationOutput(title="t", summary="s", content_md="bản dịch mới")
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=out)), \
         patch("app.services.retranslation.upsert_page_embedding", AsyncMock()), \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()) as dp:
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), None, None)

    assert outcome == "done"
    assert page.target_language == "vi"
    assert page.content_md_translated == "bản dịch mới"
    dp.assert_not_awaited()  # in-place overwrite — no explicit delete


@pytest.mark.asyncio
async def test_remove_clears_fields_and_deletes_embedding():
    page = _page(source_language="zh", target_language="vi", translation_status="done",
                 title_translated="x", summary_translated="y", content_md_translated="z")
    with patch("app.services.retranslation.translate_page", AsyncMock()) as tp, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()) as dp:
        outcome = await retranslate_page(AsyncMock(), page, None, None, AsyncMock(), None, None)

    assert outcome == "removed"
    assert page.target_language is None
    assert page.content_md_translated is None
    assert page.translation_status == "skipped"
    dp.assert_awaited_once()
    tp.assert_not_awaited()  # never calls the LLM


@pytest.mark.asyncio
async def test_skip_when_source_equals_target():
    page = _page(source_language="vi")
    with patch("app.services.retranslation.translate_page", AsyncMock()) as tp, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), None, None)

    assert outcome == "skipped"
    assert page.target_language == "vi"
    assert page.translation_status == "skipped"
    tp.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_when_source_undetectable():
    page = _page(source_language=None)
    with patch("app.services.retranslation.detect_language", return_value=("en", 0.0)), \
         patch("app.services.retranslation.translate_page", AsyncMock()) as tp, \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", None, AsyncMock(), None, None)

    assert outcome == "skipped"
    tp.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_marks_failed_and_clears_stale():
    page = _page(source_language="zh", target_language="vi", content_md_translated="old")
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=None)), \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()) as dp:
        outcome = await retranslate_page(AsyncMock(), page, "en", None, AsyncMock(), None, None)

    assert outcome == "failed"
    assert page.translation_status == "failed"
    assert page.content_md_translated is None
    assert page.target_language == "en"
    dp.assert_awaited_once()


@pytest.mark.asyncio
async def test_source_override_propagates_to_page():
    page = _page(source_language=None)
    out = TranslationOutput(title="t", summary="s", content_md="dich")
    with patch("app.services.retranslation.translate_page", AsyncMock(return_value=out)), \
         patch("app.services.retranslation.delete_page_embedding", AsyncMock()):
        outcome = await retranslate_page(AsyncMock(), page, "vi", "zh", AsyncMock(), None, None)

    assert outcome == "done"
    assert page.source_language == "zh"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retranslation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.retranslation'`.

- [ ] **Step 3: Write minimal implementation**

Create `app/services/retranslation.py`:

```python
"""Per-page re-translation — shared by the per-source Re-translate flow and the
admin backfill task.

Given an already-committed WikiPage, (re)compute its target-language fields and
embedding for a requested target language. Three intents are supported:

  * add / change — translate into ``target_language`` (overwriting any prior
                   translation in place via the embedding upsert)
  * remove       — ``target_language is None``: clear the translated half and
                   delete its target embedding
  * skip         — source unknown or equal to target: no LLM call; clear any
                   now-stale translated half

The caller owns the transaction; this function mutates ``page`` and the
embedding tables but never commits.
"""

from typing import Optional

from loguru import logger

from app.ai.mrp.translator import translate_page
from app.ai.mrp.writer import PageWriteResult
from app.config import settings
from app.services.embedding_storage import (
    compute_content_hash,
    delete_page_embedding,
    embedding_input_text,
    upsert_page_embedding,
)
from app.services.language_detection import detect_language

# Outcome strings returned to callers for tallying.
DONE = "done"
SKIPPED = "skipped"
REMOVED = "removed"
FAILED = "failed"


def _effective_source(page, source_override: Optional[str]) -> Optional[str]:
    """Resolve the source language: explicit override → stored → detection."""
    if source_override:
        return source_override
    if page.source_language:
        return page.source_language
    code, conf = detect_language(page.content_md or "")
    if conf >= settings.language_detection_min_confidence:
        return code
    return None


async def _clear_target(session, page) -> None:
    """Drop the translated half + its target embedding so no stale or
    wrong-language remnant survives a remove / skip / failed re-translation."""
    page.title_translated = None
    page.summary_translated = None
    page.content_md_translated = None
    await delete_page_embedding(session, page.id, language="target")


async def retranslate_page(
    session,
    page,
    target_language: Optional[str],
    source_override: Optional[str],
    llm,
    embedder,
    active_spec,
) -> str:
    """(Re)translate one page. Mutates ``page``; returns an outcome string."""
    if source_override:
        page.source_language = source_override
    src_lang = _effective_source(page, source_override)

    # --- Remove: translation turned off ---
    if target_language is None:
        await _clear_target(session, page)
        page.target_language = None
        page.translation_status = "skipped"
        return REMOVED

    # --- Skip: nothing to translate from, or already in the target language ---
    if not src_lang or src_lang == target_language:
        await _clear_target(session, page)
        page.target_language = target_language
        page.translation_status = "skipped"
        return SKIPPED

    # --- Translate ---
    stub = PageWriteResult(
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        action="UPDATE",
        content_md=page.content_md or "",
        summary=page.summary or "",
    )
    try:
        output = await translate_page(llm, stub, src_lang, target_language)
    except Exception as exc:  # translator already guards; stay defensive
        logger.warning(f"retranslate: {page.slug} raised {exc}")
        output = None

    if output is None:
        await _clear_target(session, page)
        page.target_language = target_language
        page.translation_status = "failed"
        return FAILED

    page.source_language = src_lang
    page.target_language = target_language
    page.title_translated = output.title
    page.summary_translated = output.summary
    page.content_md_translated = output.content_md
    page.translation_status = "done"

    if embedder is not None and active_spec is not None:
        try:
            tgt_vec = await embedder.embed(
                embedding_input_text(output.title, output.summary, output.content_md)
            )
            await upsert_page_embedding(
                session,
                page.id,
                active_spec,
                tgt_vec,
                compute_content_hash(output.title, output.summary, output.content_md),
                language="target",
            )
        except Exception as exc:
            logger.warning(f"retranslate: target embed failed for {page.slug}: {exc}")

    return DONE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retranslation.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/retranslation.py tests/test_retranslation.py
git commit -m "feat(translate): add shared per-page retranslate_page helper"
```

---

## Task 3: Refactor `backfill_translate_pages_task` onto the helper

**Files:**
- Modify: `app/worker.py` (the `backfill_translate_pages_task` body, ~lines 1117–1225)

This is a pure refactor — the admin endpoint and behavior are unchanged; the per-page logic now comes from the shared helper.

- [ ] **Step 1: Replace the in-function imports**

In `backfill_translate_pages_task`, replace the import block (currently importing `translate_page`, `PageWriteResult`, the embedding helpers, and `detect_language`) so it reads:

```python
    from app.ai.embedding_catalog import get_spec
    from app.ai.registry import ProviderRegistry
    from app.database import async_session_factory
    from app.database.models import WikiPage
    from app.services.retranslation import DONE, FAILED, retranslate_page
```

(The `embedder` / `active_spec` setup below still uses `get_spec` and `ProviderRegistry`, so keep those.)

- [ ] **Step 2: Replace the per-page loop body**

Replace the entire `for page in pages:` body (from `src_lang = page.source_language` down to the `translated += 1` / `await session.commit()` at the end of the loop) with:

```python
        for page in pages:
            outcome = await retranslate_page(
                session, page, target_language, None, llm, embedder, active_spec
            )
            if outcome == DONE:
                translated += 1
            elif outcome == FAILED:
                failed += 1
            else:  # SKIPPED (REMOVED can't occur — target_language is non-null here)
                skipped += 1
            await session.commit()
```

Leave everything after the loop (the `if translated > 0: regenerate_index(...)` block and the final `logger.success(...)` / `return`) unchanged.

- [ ] **Step 3: Verify the module imports and existing tests still pass**

Run: `python -c "import app.worker"`
Expected: no output, exit 0 (no import/syntax error).

Run: `python -m pytest tests/test_retranslation.py tests/test_translator.py tests/test_pipeline_translate.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/worker.py
git commit -m "refactor(translate): back backfill task with shared retranslate_page helper"
```

---

## Task 4: `retranslate_source_task` worker task

**Files:**
- Modify: `app/worker.py` (new task + registration)
- Test: `tests/test_retranslation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_retranslation.py`:

```python
import inspect


def test_retranslate_source_task_registered():
    from app.worker import WorkerSettings, retranslate_source_task
    assert retranslate_source_task in WorkerSettings.functions


def test_retranslate_source_task_signature():
    from app.worker import retranslate_source_task
    assert inspect.iscoroutinefunction(retranslate_source_task)
    params = list(inspect.signature(retranslate_source_task).parameters)
    assert params[:2] == ["ctx", "source_id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retranslation.py::test_retranslate_source_task_registered -v`
Expected: FAIL with `ImportError: cannot import name 'retranslate_source_task'`.

- [ ] **Step 3: Add the task**

In `app/worker.py`, add this function immediately after `backfill_translate_pages_task` (before `class WorkerSettings`):

```python
async def retranslate_source_task(
    ctx: dict,
    source_id: str,
    target_language: Optional[str] = None,
    source_language: Optional[str] = None,
) -> dict:
    """Re-run translation for one source's wiki pages.

    Applies add / change / remove per page via the shared `retranslate_page`
    helper, reports progress through ProgressTracker, and restores the source to
    `ready` when done. Per-page failures are non-blocking.
    """
    from app.ai.embedding_catalog import get_spec
    from app.ai.registry import ProviderRegistry
    from app.database import async_session_factory
    from app.database.models import Source, WikiPage
    from app.services.retranslation import retranslate_page

    _ = ctx
    sid = uuid.UUID(source_id)
    tracker = ProgressTracker(sid)
    counts = {"done": 0, "skipped": 0, "removed": 0, "failed": 0}

    async with async_session_factory() as session:
        source = await session.get(Source, sid)
        if not source:
            logger.warning(f"retranslate: source {source_id} not found")
            return {"status": "error", "message": "source not found"}

        try:
            registry = ProviderRegistry(session)
            llm = await registry.get_llm()
            embedder = None
            active_spec = None
            try:
                spec_id = await registry.get_active_embedding_spec_id()
                if spec_id:
                    active_spec = get_spec(spec_id)
                    embedder = await registry.get_embedding(task="document", spec_id=spec_id)
            except Exception as exc:
                logger.warning(f"retranslate: no embedding provider: {exc}")

            pages = (
                await session.execute(
                    select(WikiPage).where(WikiPage.source_ids.any(sid))
                )
            ).scalars().all()
            total = len(pages)

            for i, page in enumerate(pages):
                outcome = await retranslate_page(
                    session, page, target_language, source_language, llm, embedder, active_spec
                )
                counts[outcome] = counts.get(outcome, 0) + 1
                await session.commit()
                await tracker.update(
                    int((i + 1) / max(total, 1) * 100),
                    f"Re-translating… {i + 1}/{total}",
                )

            source = await session.get(Source, sid)
            if source:
                source.target_language = target_language
                if source_language:
                    source.source_language = source_language
                source.status = "ready"
                source.progress = 100
                source.progress_message = (
                    f"Re-translation complete: {counts['done']} done, "
                    f"{counts['skipped']} skipped, {counts['removed']} removed, "
                    f"{counts['failed']} failed"
                )
                await session.commit()

            logger.success(f"Re-translation complete for {source_id}: {counts}")
            return {"status": "ok", **counts}

        except BaseException as e:
            logger.error(f"Re-translation failed for {source_id}: {e}")
            msg = f"Re-translation error: {str(e)[:200]}"

            async def _restore() -> None:
                from app.database import async_session_factory as _sf
                from app.database.models import Source as _Source
                async with _sf() as s2:
                    src = await s2.get(_Source, sid)
                    if src:
                        src.status = "ready"
                        src.progress_message = msg
                        await s2.commit()

            try:
                await asyncio.shield(_restore())
            except Exception:
                pass
            raise
```

- [ ] **Step 4: Register the task**

In `class WorkerSettings`, add `retranslate_source_task,` to the `functions` list, right after `backfill_translate_pages_task,`:

```python
    functions = [
        ingest_file_task,
        ingest_url_task,
        arq_func(caption_images_task, timeout=3600),
        ingest_map_reduce_task,
        ingest_refine_task,
        regenerate_plan_task,
        reembed_all_pages_task,
        ai_pre_review_draft_task,
        backfill_translate_pages_task,
        retranslate_source_task,
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_retranslation.py -v`
Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add app/worker.py tests/test_retranslation.py
git commit -m "feat(translate): add retranslate_source_task worker job"
```

---

## Task 5: `POST /sources/{id}/retranslate` endpoint

**Files:**
- Modify: `app/routers/sources.py`
- Test: `tests/test_retranslate_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_retranslate_endpoint.py`:

```python
"""Re-translate endpoint: request model + handler signature.

Mirrors test_sources_target_language.py — the codebase tests routers at the
model/signature level rather than via a live HTTP client.
"""

import inspect

from app.routers.sources import RetranslateRequest, retranslate_source


def test_request_defaults_to_none():
    m = RetranslateRequest()
    assert m.target_language is None
    assert m.source_language is None


def test_request_accepts_languages():
    m = RetranslateRequest(target_language="vi", source_language="zh")
    assert m.target_language == "vi"
    assert m.source_language == "zh"


def test_endpoint_signature():
    sig = inspect.signature(retranslate_source)
    assert "source_id" in sig.parameters
    assert "body" in sig.parameters
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retranslate_endpoint.py -v`
Expected: FAIL with `ImportError: cannot import name 'RetranslateRequest'`.

- [ ] **Step 3: Add the settings import**

At the top of `app/routers/sources.py`, add this import (next to the other `app.` imports):

```python
from app.config import settings
```

- [ ] **Step 4: Add the request model + allowed-language set**

In `app/routers/sources.py`, after the `SourceUpdate` class, add:

```python
class RetranslateRequest(BaseModel):
    target_language: Optional[str] = None   # ISO 639-1; null = remove translation
    source_language: Optional[str] = None   # null = keep stored/auto-detected


# Curated set the UI offers; keeps junk codes out of the translator.
_RETRANSLATE_LANGS = {"vi", "en", "zh", "ja"}
```

- [ ] **Step 5: Add the endpoint**

In `app/routers/sources.py`, add this handler immediately after `retry_source` (after its `return _to_response(source)`):

```python
@router.post("/sources/{source_id}/retranslate", response_model=SourceResponse)
async def retranslate_source(
    source_id: uuid.UUID,
    body: RetranslateRequest,
    db: AsyncSession = Depends(get_db),
    _user: Employee = require_permission("doc:edit"),
):
    """Re-run translation for a ready source: add, change, or remove its target
    language (optionally correcting the detected source language)."""
    if not settings.translation_enabled:
        raise HTTPException(status_code=400, detail="Translation is disabled")

    source = (await db.execute(
        select(Source)
        .options(*_source_load_options())
        .where(Source.id == source_id)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status != "ready":
        raise HTTPException(
            status_code=400,
            detail="Re-translation is only allowed for sources in 'ready' status",
        )
    if await _wiki_page_count(db, source_id) == 0:
        raise HTTPException(status_code=400, detail="Source has no wiki pages to translate")

    target = (body.target_language or "").strip().lower() or None
    override = (body.source_language or "").strip().lower() or None
    if target and target not in _RETRANSLATE_LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported target_language: {target}")
    if override and override not in _RETRANSLATE_LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported source_language: {override}")

    effective_source = override or source.source_language
    if target and effective_source and target == effective_source:
        raise HTTPException(status_code=400, detail="Source and target language must differ.")

    source.target_language = target
    if override:
        source.source_language = override
    source.status = "translating"
    source.progress = 0
    source.progress_message = "Re-translating…"
    source.error_message = None
    await db.flush()

    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        "retranslate_source_task", str(source_id), target, override
    )
    if job:
        source.job_id = job.job_id
    await db.commit()

    source = (await db.execute(
        select(Source)
        .options(*_source_load_options())
        .where(Source.id == source_id)
    )).scalar_one()
    logger.info(f"Queued retranslate job {job.job_id if job else 'N/A'} for source {source_id}")
    return _to_response(source, await _wiki_page_count(db, source_id))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_retranslate_endpoint.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add app/routers/sources.py tests/test_retranslate_endpoint.py
git commit -m "feat(api): add POST /sources/{id}/retranslate endpoint"
```

---

## Task 6: Frontend — RetranslateDialog component

**Files:**
- Create: `frontend/src/components/knowledge/knowledge-table/retranslate-dialog.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/knowledge/knowledge-table/retranslate-dialog.tsx`:

```tsx
import React from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Source } from "./types";

const LANGS: { value: string; label: string }[] = [
  { value: "vi", label: "Vietnamese" },
  { value: "en", label: "English" },
  { value: "zh", label: "Chinese" },
  { value: "ja", label: "Japanese" },
];

export function RetranslateDialog({
  source,
  onClose,
  onDone,
}: {
  source: Source;
  onClose: () => void;
  onDone: () => void;
}) {
  const [target, setTarget] = React.useState(source.target_language || "");
  const [sourceOverride, setSourceOverride] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState("");

  const detected = source.source_language || null;
  const detectedLabel = `Auto-detected${detected ? ` (${detected.toUpperCase()})` : ""}`;
  const effectiveSource = sourceOverride || detected;
  const sameLang = !!target && !!effectiveSource && target === effectiveSource;

  const submit = async () => {
    if (sameLang) {
      setError("Source and target language must differ.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api(`/api/sources/${source.id}/retranslate`, {
        method: "POST",
        body: {
          target_language: target || null,
          source_language: sourceOverride || null,
        },
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start re-translation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl">Re-translate Document</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 mt-2">
          <p className="text-xs text-muted-foreground">
            Use this if the wrong language was chosen at upload, to add a missing
            translation, or to replace or remove the current one. Re-translation
            reruns on this document&apos;s wiki pages.
          </p>

          {/* Target language */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="retranslate-target">Translate to</Label>
            <Select value={target} onValueChange={(v) => setTarget(v ?? "")}>
              <SelectTrigger id="retranslate-target" className="bg-background w-full">
                <SelectValue placeholder="No translation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">No translation</SelectItem>
                {LANGS.map((l) => (
                  <SelectItem key={l.value} value={l.value}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Source language override */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="retranslate-source">Source language</Label>
            <Select value={sourceOverride} onValueChange={(v) => setSourceOverride(v ?? "")}>
              <SelectTrigger id="retranslate-source" className="bg-background w-full">
                <SelectValue placeholder={detectedLabel} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">{detectedLabel}</SelectItem>
                {LANGS.map((l) => (
                  <SelectItem key={l.value} value={l.value}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Override only if the detected source language is wrong.
            </p>
          </div>

          {(error || sameLang) && (
            <p className="text-destructive text-sm bg-destructive/10 px-3 py-2 rounded-lg">
              {error || "Source and target language must differ."}
            </p>
          )}

          <div className="flex justify-end gap-2 mt-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={submitting || sameLang}
              onClick={submit}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <span className="material-symbols-outlined animate-spin text-sm">
                    progress_activity
                  </span>
                  Starting…
                </span>
              ) : (
                "Re-translate"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors referencing `retranslate-dialog.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/knowledge/knowledge-table/retranslate-dialog.tsx
git commit -m "feat(ui): add RetranslateDialog for per-source re-translation"
```

---

## Task 7: Frontend — wire the dropdown action

**Files:**
- Modify: `frontend/src/components/knowledge/knowledge-table/index.tsx`

- [ ] **Step 1: Import the dialog**

Add to the imports at the top of `index.tsx` (next to `EditSourceDialog`):

```tsx
import { RetranslateDialog } from "./retranslate-dialog";
```

- [ ] **Step 2: Add dialog state**

Next to `const [editSource, setEditSource] = React.useState<Source | null>(null);`, add:

```tsx
  const [retranslateSource, setRetranslateSource] = React.useState<Source | null>(null);
```

- [ ] **Step 3: Add the menu item**

In the `DropdownMenuContent`, immediately after the `Edit` `DropdownMenuItem`, add:

```tsx
                        {source.status === "ready" && (
                          <DropdownMenuItem onClick={() => setRetranslateSource(source)}>
                            <span className="material-symbols-outlined mr-2" style={{ fontSize: 16 }}>
                              translate
                            </span>
                            Re-translate
                          </DropdownMenuItem>
                        )}
```

- [ ] **Step 4: Render the dialog**

After the `{editSource && ( <EditSourceDialog ... /> )}` block, add:

```tsx
      {retranslateSource && (
        <RetranslateDialog
          source={retranslateSource}
          onClose={() => setRetranslateSource(null)}
          onDone={() => { setRetranslateSource(null); onRefresh(); }}
        />
      )}
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/knowledge/knowledge-table/index.tsx
git commit -m "feat(ui): add Re-translate action to knowledge table rows"
```

---

## Task 8: Frontend — `translating` status + live polling

**Files:**
- Modify: `frontend/src/components/knowledge/knowledge-table/status-dot.tsx`
- Modify: `frontend/src/app/(portal)/knowledge/page.tsx`

- [ ] **Step 1: Render the `translating` status**

In `status-dot.tsx`, add `translating` to the `colors` map:

```tsx
  const colors: Record<string, string> = {
    ready: "bg-green-500",
    processing: "bg-yellow-500",
    translating: "bg-indigo-500",
    error: "bg-destructive",
    pending: "bg-muted-foreground",
    plan_ready: "bg-blue-500",
  };
```

Then include `translating` wherever `processing` drives the progress UI — change the two conditionals to:

```tsx
        {(status === "processing" || status === "translating") && source.progress !== undefined && (
          <span className="text-xs text-muted-foreground">({source.progress}%)</span>
        )}
      </div>
      {(status === "processing" || status === "pending" || status === "translating") && source.progress_message && (
        <span className="text-[10px] text-muted-foreground truncate max-w-[150px]" title={source.progress_message}>
          {source.progress_message}
        </span>
      )}
```

(The existing `capitalize` class renders the status text as "Translating" automatically.)

- [ ] **Step 2: Keep polling while translating**

In `frontend/src/app/(portal)/knowledge/page.tsx`, update the poll predicate (~line 107) to include `translating`:

```tsx
    const hasPending = sources.some((s) => s.status === "pending" || s.status === "processing" || s.status === "plan_ready" || s.status === "translating");
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Manual verification**

1. Start the app. Upload a Chinese doc with **No translation**. After it reaches `ready`, open the row menu → **Re-translate** → choose **Vietnamese** → submit. The row shows **Translating** (indigo) with live progress, then returns to **ready** with a `ZH → VI` badge; the page view shows the Vietnamese half.
2. Re-translate the same doc to **English** → the badge becomes `ZH → EN` and the translated pane updates.
3. Re-translate with target **No translation** → the badge disappears and the page is source-only.
4. Upload a doc, pick a deliberately wrong source via the **Source language** override, submit, and confirm the translation reflects the override.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/knowledge/knowledge-table/status-dot.tsx "frontend/src/app/(portal)/knowledge/page.tsx"
git commit -m "feat(ui): show translating status and keep polling during re-translation"
```

---

## Done

All spec sections are covered: API + status model (Task 5, Task 8), worker task + per-page add/change/remove/skip/fail logic (Tasks 2–4), embedding cleanup (Task 1), and UI dialog + action + status (Tasks 6–8). After Task 8, run the full backend suite once more:

```bash
python -m pytest tests/test_retranslation.py tests/test_retranslate_endpoint.py tests/test_embedding_storage_language.py -v
```
Expected: PASS.
