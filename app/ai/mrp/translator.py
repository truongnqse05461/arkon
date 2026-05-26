"""TRANSLATE phase — per-page translation of REFINE output.

Runs after REFINE produces source-language drafts. For each page, calls the
configured LLM with a strict prompt that preserves markdown structure,
wikilinks ([[slug]]), citations (【...】), and code blocks. Validates the
output before persisting; failures mark the page translation_status='failed'
without blocking COMMIT.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from loguru import logger

from app.ai.providers.base import LLMProvider
from app.ai.mrp.writer import PageWriteResult
from app.utils.text import parse_json_loose

TRANSLATOR_TIMEOUT = 120
TRANSLATOR_MAX_CONCURRENCY = 4
_LENGTH_MIN_RATIO = 0.5
_LENGTH_MAX_RATIO = 2.0

WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
CITATION_RE = re.compile(r"【[^】]+】")


@dataclass
class TranslationOutput:
    title: str
    summary: str
    content_md: str


class InvalidTranslationError(ValueError):
    pass


TRANSLATOR_SYSTEM = (
    "You are a precise technical translator. Return ONLY valid JSON. "
    "Preserve markdown structure, wikilinks, citation brackets, and code blocks verbatim."
)

TRANSLATOR_PROMPT = """\
Translate the following wiki page from {source_lang} to {target_lang}.

Rules:
- Preserve [[slug]] and [[slug|display]] wikilinks verbatim (slugs never translate).
- Preserve 【...】 citation brackets verbatim.
- Preserve fenced code blocks, math blocks (```math), and inline `code` verbatim.
- Preserve markdown structure: headings stay headings, lists stay lists, tables stay tables.
- Translate visible heading text and prose.
- For named regulations, laws, product codes, model numbers, and proper nouns
  with no widely-known translated form, keep the original in parentheses after
  the translation on first mention only. Example: "Bình chữa cháy (灭火器) là..."

## Source page
Title: {title}

Summary: {summary}

Content:
{content_md}

Return JSON with this exact shape and nothing else:
{{
  "title": "<translated title>",
  "summary": "<translated summary>",
  "content_md": "<translated content_md>"
}}
"""


def validate_translation(src_content: str, output: TranslationOutput) -> None:
    """Raise InvalidTranslationError if the translation looks broken."""
    if not output.title or not output.summary or not output.content_md:
        raise InvalidTranslationError("Empty title, summary, or content_md")

    src_len = max(len(src_content), 1)
    tgt_len = len(output.content_md)
    ratio = tgt_len / src_len
    if ratio < _LENGTH_MIN_RATIO or ratio > _LENGTH_MAX_RATIO:
        raise InvalidTranslationError(
            f"content_md length ratio {ratio:.2f} outside [{_LENGTH_MIN_RATIO}, {_LENGTH_MAX_RATIO}]"
        )

    src_links = len(WIKILINK_RE.findall(src_content))
    tgt_links = len(WIKILINK_RE.findall(output.content_md))
    if src_links != tgt_links:
        raise InvalidTranslationError(
            f"wikilink count mismatch: source={src_links} target={tgt_links}"
        )

    src_cites = len(CITATION_RE.findall(src_content))
    tgt_cites = len(CITATION_RE.findall(output.content_md))
    if src_cites != tgt_cites:
        raise InvalidTranslationError(
            f"citation count mismatch: source={src_cites} target={tgt_cites}"
        )


async def translate_page(
    llm: LLMProvider,
    page: PageWriteResult,
    source_lang: str,
    target_lang: str,
) -> Optional[TranslationOutput]:
    """Translate one page. Returns None on failure (caller marks failed)."""
    prompt = TRANSLATOR_PROMPT.format(
        source_lang=source_lang,
        target_lang=target_lang,
        title=page.title,
        summary=page.summary,
        content_md=page.content_md,
    )
    try:
        raw = await asyncio.wait_for(
            llm.generate(prompt, system=TRANSLATOR_SYSTEM, temperature=0.1),
            timeout=TRANSLATOR_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Translate timeout for page slug={page.slug}")
        return None

    try:
        data = parse_json_loose(raw)
        output = TranslationOutput(
            title=data["title"],
            summary=data["summary"],
            content_md=data["content_md"],
        )
    except Exception as exc:
        logger.warning(f"Translate JSON parse failed for slug={page.slug}: {exc}")
        return None

    try:
        validate_translation(page.content_md, output)
    except InvalidTranslationError as exc:
        logger.warning(f"Translate validation failed for slug={page.slug}: {exc}")
        return None

    return output


async def translate_pages(
    llm: LLMProvider,
    pages: Iterable[PageWriteResult],
    source_lang: str,
    target_lang: str,
) -> List[tuple[PageWriteResult, Optional[TranslationOutput]]]:
    """Translate every page concurrently with TRANSLATOR_MAX_CONCURRENCY cap."""
    sem = asyncio.Semaphore(TRANSLATOR_MAX_CONCURRENCY)
    pages_list = list(pages)

    async def one(p: PageWriteResult):
        async with sem:
            return (p, await translate_page(llm, p, source_lang, target_lang))

    return await asyncio.gather(*(one(p) for p in pages_list))
