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
