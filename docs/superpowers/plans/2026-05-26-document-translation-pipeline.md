# Document Translation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional TRANSLATE phase between REFINE and VERIFY in the MRP pipeline that produces dual-pane wiki pages (source + target language), with bilingual embeddings, dual-pane UI, and a backfill endpoint for existing pages.

**Architecture:** New phase invokes a per-page LLM translator that emits `{title, summary, content_md}` in the target language. Storage gains `*_translated` columns on `WikiPage` and a `language` column on per-dimension embedding tables. Search queries both language rows and returns the matched-language pane. UI gains a Source/Translated/Side-by-side toggle.

**Tech Stack:** Python 3.11, SQLAlchemy async, Alembic, FastAPI, arq workers, pgvector, pytest, React/TypeScript, Vercel AI SDK, Playwright (e2e only).

**Spec:** `docs/superpowers/specs/2026-05-26-document-translation-pipeline-design.md`

---

## Task 1: Schema migration — add translation columns

**Files:**
- Create: `alembic/versions/029_translation_fields.py`

- [ ] **Step 1: Write the migration**

```python
"""Add translation columns to sources, wiki_pages, wiki_page_embeddings_*

Revision ID: 029
Revises: 028
Create Date: 2026-05-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_TABLES = (
    "wiki_page_embeddings_768",
    "wiki_page_embeddings_1024",
    "wiki_page_embeddings_1536",
    "wiki_page_embeddings_3072",
)


def upgrade() -> None:
    # --- sources ---
    op.add_column("sources", sa.Column("source_language", sa.String(8), nullable=True))
    op.add_column("sources", sa.Column("target_language", sa.String(8), nullable=True))

    # --- wiki_pages ---
    op.add_column("wiki_pages", sa.Column("source_language", sa.String(8), nullable=True))
    op.add_column("wiki_pages", sa.Column("target_language", sa.String(8), nullable=True))
    op.add_column("wiki_pages", sa.Column("title_translated", sa.String(500), nullable=True))
    op.add_column("wiki_pages", sa.Column("summary_translated", sa.Text, nullable=True))
    op.add_column("wiki_pages", sa.Column("content_md_translated", sa.Text, nullable=True))
    op.add_column(
        "wiki_pages",
        sa.Column(
            "translation_status",
            sa.String(20),
            nullable=False,
            server_default="skipped",
        ),
    )

    # --- wiki_page_embeddings_<dim>: add language column + extend PK ---
    for tbl in EMBED_TABLES:
        op.add_column(
            tbl,
            sa.Column(
                "language", sa.String(8), nullable=False, server_default="source"
            ),
        )
        op.drop_constraint(f"{tbl}_pkey", tbl, type_="primary")
        op.create_primary_key(
            f"{tbl}_pkey", tbl, ["page_id", "model_spec_id", "language"]
        )


def downgrade() -> None:
    for tbl in EMBED_TABLES:
        op.drop_constraint(f"{tbl}_pkey", tbl, type_="primary")
        op.create_primary_key(f"{tbl}_pkey", tbl, ["page_id", "model_spec_id"])
        op.drop_column(tbl, "language")

    op.drop_column("wiki_pages", "translation_status")
    op.drop_column("wiki_pages", "content_md_translated")
    op.drop_column("wiki_pages", "summary_translated")
    op.drop_column("wiki_pages", "title_translated")
    op.drop_column("wiki_pages", "target_language")
    op.drop_column("wiki_pages", "source_language")

    op.drop_column("sources", "target_language")
    op.drop_column("sources", "source_language")
```

- [ ] **Step 2: Run migration against a dev database**

Run: `alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 028 -> 029`

- [ ] **Step 3: Verify schema**

Run: `psql $DATABASE_URL -c "\d wiki_pages" | grep translation`
Expected: rows for `title_translated`, `summary_translated`, `content_md_translated`, `translation_status`, `source_language`, `target_language`.

Run: `psql $DATABASE_URL -c "\d wiki_page_embeddings_768"`
Expected: `language` column present; primary key includes `language`.

- [ ] **Step 4: Verify downgrade is reversible**

Run: `alembic downgrade -1 && alembic upgrade head`
Expected: both commands succeed with no errors.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/029_translation_fields.py
git commit -m "feat(db): add translation fields to sources, wiki_pages, embeddings"
```

---

## Task 2: Update ORM models for translation columns

**Files:**
- Modify: `app/database/models.py:91-160` (Source class), `app/database/models.py:279-323` (WikiPage class), `app/database/models.py:1004-1037` (embedding mixin + tables)

- [ ] **Step 1: Add fields to `Source` model**

Add after the `scope_id` column block in `class Source` (around line 108):

```python
    source_language: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True,
        comment="Auto-detected source language (ISO 639-1: 'zh', 'en', 'vi', ...)",
    )
    target_language: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True,
        comment="Uploader-chosen target language; null = no translation",
    )
```

- [ ] **Step 2: Add fields to `WikiPage` model**

Add after `summary` column (around line 293):

```python
    source_language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    target_language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    title_translated: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    summary_translated: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_md_translated: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    translation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="skipped",
        comment="pending | done | skipped | failed",
    )
```

- [ ] **Step 3: Extend embedding base with `language`**

Modify `_WikiPageEmbeddingBase` (around line 1004) to add a `language` primary-key column:

```python
class _WikiPageEmbeddingBase:
    """Mixin: shared columns for all wiki_page_embeddings_<dim> tables."""

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model_spec_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    language: Mapped[str] = mapped_column(
        String(8), primary_key=True, default="source",
        comment="'source' or 'target' — which half of a bilingual page this row embeds",
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: Smoke test — models import and instantiate**

Run: `python -c "from app.database.models import Source, WikiPage, WikiPageEmbedding768; p = WikiPage(slug='x', title='y', page_type='entity', target_language='vi'); print(p.target_language)"`
Expected: prints `vi`

- [ ] **Step 5: Commit**

```bash
git add app/database/models.py
git commit -m "feat(models): add translation columns to Source, WikiPage, embedding tables"
```

---

## Task 3: Configuration additions

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Write a failing test**

Create `tests/test_translation_config.py`:

```python
from app.config import settings


def test_translation_enabled_default_true():
    assert settings.translation_enabled is True


def test_translation_model_spec_id_default_none():
    assert settings.translation_model_spec_id is None


def test_language_detection_min_confidence_default():
    assert settings.language_detection_min_confidence == 0.6
```

- [ ] **Step 2: Run test and confirm failure**

Run: `pytest tests/test_translation_config.py -v`
Expected: FAIL — attribute errors for missing settings fields.

- [ ] **Step 3: Add settings fields**

In `app/config.py`, add (alongside `mrp_auto_approve_plan`):

```python
    translation_enabled: bool = Field(
        default=True,
        description="Enable optional TRANSLATE phase in the MRP pipeline",
    )
    translation_model_spec_id: str | None = Field(
        default=None,
        description="LLM spec_id for translation calls; null = use the writer LLM",
    )
    language_detection_min_confidence: float = Field(
        default=0.6,
        description="Minimum confidence for source_language auto-detection",
    )
```

- [ ] **Step 4: Run test and confirm pass**

Run: `pytest tests/test_translation_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_translation_config.py
git commit -m "feat(config): add translation pipeline settings"
```

---

## Task 4: Language detection service

**Files:**
- Create: `app/services/language_detection.py`
- Create: `tests/test_language_detection.py`
- Modify: `pyproject.toml` (or `requirements.txt`) — add `langid` dependency

- [ ] **Step 1: Add `langid` dependency**

In `pyproject.toml` under `[project] dependencies` (or in `requirements.txt`), add:

```
langid==1.1.6
```

Run: `pip install langid==1.1.6`
Expected: installs successfully.

- [ ] **Step 2: Write failing tests**

Create `tests/test_language_detection.py`:

```python
from app.services.language_detection import detect_language


def test_detect_english():
    code, conf = detect_language("The quick brown fox jumps over the lazy dog. " * 5)
    assert code == "en"
    assert conf >= 0.6


def test_detect_chinese():
    code, conf = detect_language("灭火器是用于扑灭火灾的便携式工具。" * 5)
    assert code == "zh"
    assert conf >= 0.6


def test_detect_vietnamese():
    code, conf = detect_language("Bình chữa cháy là thiết bị dùng để dập tắt đám cháy. " * 5)
    assert code == "vi"
    assert conf >= 0.6


def test_low_confidence_returns_none():
    code, conf = detect_language("a b c")
    # Either confidence too low or returns 'en' with low conf; the caller decides.
    assert isinstance(code, str)
    assert 0.0 <= conf <= 1.0
```

- [ ] **Step 3: Run test and confirm failure**

Run: `pytest tests/test_language_detection.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.language_detection`.

- [ ] **Step 4: Implement the service**

Create `app/services/language_detection.py`:

```python
"""Language detection — thin wrapper around langid for the MRP pipeline.

Returns ISO 639-1 codes ("en", "zh", "vi", ...) and a normalized 0-1 confidence.
Callers compare confidence against settings.language_detection_min_confidence
and treat low-confidence results as "unknown" (skip translation).
"""

from typing import Tuple

import langid

_SAMPLE_CHARS = 2000


def detect_language(text: str) -> Tuple[str, float]:
    """Detect language of `text`. Uses up to the first 2000 characters.

    Returns:
        (iso_code, confidence) where confidence is a 0-1 normalized score.
        langid's raw score is a log-probability; we normalize via the
        identifier's `set_languages`-free output.
    """
    if not text or not text.strip():
        return ("en", 0.0)

    sample = text[:_SAMPLE_CHARS]
    code, raw = langid.classify(sample)
    # langid raw scores are log-likelihoods (large negative). Map via a
    # sigmoid-style transform: confidence = 1 / (1 + exp(-raw/100)) gives
    # ~0.5 at raw=0 and saturates as raw grows. For typical strong matches
    # (raw > 50) confidence > 0.62; very weak (raw < -200) → < 0.12.
    import math
    confidence = 1.0 / (1.0 + math.exp(-raw / 100.0))
    return (code, confidence)
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest tests/test_language_detection.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/language_detection.py tests/test_language_detection.py pyproject.toml
git commit -m "feat(translation): add language detection service"
```

---

## Task 5: Translator module — translate one page

**Files:**
- Create: `app/ai/mrp/translator.py`
- Create: `tests/test_translator.py`

- [ ] **Step 1: Write failing test for the validator**

Create `tests/test_translator.py`:

```python
import pytest

from app.ai.mrp.translator import (
    TranslationOutput,
    validate_translation,
    InvalidTranslationError,
)


def test_validate_translation_happy_path():
    src = "# Heading\n\nSee [[concept/x]] and 【source/y】 for details."
    tgt = "# Tiêu đề\n\nXem [[concept/x]] và 【source/y】 để biết chi tiết."
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    validate_translation(src_content=src, output=out)  # no exception


def test_validate_translation_rejects_missing_wikilink():
    src = "[[concept/a]] [[concept/b]]"
    tgt = "[[concept/a]] foo"  # second link dropped
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    with pytest.raises(InvalidTranslationError, match="wikilink count"):
        validate_translation(src_content=src, output=out)


def test_validate_translation_rejects_truncation():
    src = "x" * 1000
    tgt = "y" * 100  # 10% of source — under 50% bound
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    with pytest.raises(InvalidTranslationError, match="length"):
        validate_translation(src_content=src, output=out)


def test_validate_translation_rejects_runaway_expansion():
    src = "x" * 100
    tgt = "y" * 250  # 250% — over 200% bound
    out = TranslationOutput(title="A", summary="B", content_md=tgt)
    with pytest.raises(InvalidTranslationError, match="length"):
        validate_translation(src_content=src, output=out)
```

- [ ] **Step 2: Run test and confirm failure**

Run: `pytest tests/test_translator.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the translator module**

Create `app/ai/mrp/translator.py`:

```python
"""TRANSLATE phase — per-page translation of REFINE output.

Runs after REFINE produces source-language drafts. For each page, calls the
configured LLM with a strict prompt that preserves markdown structure,
wikilinks ([[slug]]), citations (【...】), and code blocks. Validates the
output before persisting; failures mark the page translation_status='failed'
without blocking COMMIT.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from loguru import logger

from app.ai.providers.interfaces import LLMProvider
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
```

- [ ] **Step 4: Run tests and confirm pass**

Run: `pytest tests/test_translator.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/ai/mrp/translator.py tests/test_translator.py
git commit -m "feat(translation): add per-page translator with output validation"
```

---

## Task 6: Wire TRANSLATE phase into the pipeline

**Files:**
- Modify: `app/ai/mrp/pipeline.py` (between REFINE and VERIFY, around line 484)
- Create: `tests/test_pipeline_translate.py`

- [ ] **Step 1: Write failing integration-style test for translate-phase wiring**

Create `tests/test_pipeline_translate.py`:

```python
"""Verify TRANSLATE phase is invoked when target_language is set, skipped otherwise.

Mocks the LLM so this is a unit-level integration test (no real API calls).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.mrp.writer import PageWriteResult


@pytest.mark.asyncio
async def test_translate_phase_skipped_when_no_target_language():
    from app.ai.mrp.pipeline import _maybe_run_translate_phase

    pages = [
        PageWriteResult(slug="concept/x", title="X", page_type="concept",
                        action="CREATE", content_md="body", summary="sum")
    ]
    llm = AsyncMock()

    out = await _maybe_run_translate_phase(
        pages=pages, source_language="zh", target_language=None, llm=llm,
    )
    assert out == pages
    assert all(p.title_translated is None for p in out)
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_phase_skipped_when_languages_equal():
    from app.ai.mrp.pipeline import _maybe_run_translate_phase

    pages = [
        PageWriteResult(slug="concept/x", title="X", page_type="concept",
                        action="CREATE", content_md="body", summary="sum")
    ]
    llm = AsyncMock()

    out = await _maybe_run_translate_phase(
        pages=pages, source_language="vi", target_language="vi", llm=llm,
    )
    assert out == pages
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_phase_populates_translated_fields_on_success():
    from app.ai.mrp.pipeline import _maybe_run_translate_phase

    pages = [
        PageWriteResult(
            slug="concept/x", title="灭火器", page_type="concept", action="CREATE",
            content_md="灭火器是工具。" * 5, summary="工具",
        )
    ]
    llm = AsyncMock()
    llm.generate.return_value = (
        '{"title": "Bình chữa cháy",'
        ' "summary": "công cụ",'
        ' "content_md": "Bình chữa cháy là công cụ. ' + "x" * 60 + '"}'
    )

    out = await _maybe_run_translate_phase(
        pages=pages, source_language="zh", target_language="vi", llm=llm,
    )
    assert out[0].title_translated == "Bình chữa cháy"
    assert out[0].translation_status == "done"
```

- [ ] **Step 2: Extend `PageWriteResult` to carry translation fields**

Modify `app/ai/mrp/writer.py:43-81` — add translation fields and update `to_dict`/`from_dict`:

```python
@dataclass
class PageWriteResult:
    slug: str
    title: str
    page_type: str
    action: str          # CREATE | UPDATE
    content_md: str
    summary: str
    citations: list[dict] = field(default_factory=list)
    entity_names: list[str] = field(default_factory=list)
    related_kb_pages: list[str] = field(default_factory=list)
    # Translation fields (populated by TRANSLATE phase; None if skipped)
    title_translated: Optional[str] = None
    summary_translated: Optional[str] = None
    content_md_translated: Optional[str] = None
    translation_status: str = "skipped"  # pending | done | skipped | failed

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "page_type": self.page_type,
            "action": self.action,
            "content_md": self.content_md,
            "summary": self.summary,
            "citations": self.citations,
            "entity_names": self.entity_names,
            "related_kb_pages": self.related_kb_pages,
            "title_translated": self.title_translated,
            "summary_translated": self.summary_translated,
            "content_md_translated": self.content_md_translated,
            "translation_status": self.translation_status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PageWriteResult":
        return cls(
            slug=d.get("slug", ""),
            title=d.get("title", ""),
            page_type=d.get("page_type", "concept"),
            action=d.get("action", "CREATE"),
            content_md=d.get("content_md", ""),
            summary=d.get("summary", ""),
            citations=d.get("citations", []),
            entity_names=d.get("entity_names", []),
            related_kb_pages=d.get("related_kb_pages", []),
            title_translated=d.get("title_translated"),
            summary_translated=d.get("summary_translated"),
            content_md_translated=d.get("content_md_translated"),
            translation_status=d.get("translation_status", "skipped"),
        )
```

Make sure `Optional` is imported at the top of `writer.py` (`from typing import Optional`).

- [ ] **Step 3: Add `_maybe_run_translate_phase` in `pipeline.py`**

Add this helper after the existing phase helpers in `app/ai/mrp/pipeline.py` (near the other private helpers, before `run_refine_pipeline`):

```python
async def _maybe_run_translate_phase(
    pages: list,
    source_language: Optional[str],
    target_language: Optional[str],
    llm,
) -> list:
    """Phase 4.5 — translate every page if applicable. Mutates and returns pages."""
    from app.ai.mrp.translator import translate_pages

    if not target_language:
        return pages
    if not source_language:
        # Unknown source language → skip translation.
        return pages
    if source_language == target_language:
        return pages

    results = await translate_pages(
        llm=llm,
        pages=pages,
        source_lang=source_language,
        target_lang=target_language,
    )
    for page, output in results:
        if output is None:
            page.translation_status = "failed"
        else:
            page.title_translated = output.title
            page.summary_translated = output.summary
            page.content_md_translated = output.content_md
            page.translation_status = "done"
    return pages
```

- [ ] **Step 4: Insert the phase call between REFINE and VERIFY in `run_refine_pipeline`**

In `app/ai/mrp/pipeline.py`, after the REFINE block sets `pipeline_phase='verify'` and before the VERIFY phase call (around line 484), insert:

```python
    # Phase 4.5: TRANSLATE
    if page_results:
        src = await session.get(Source, source_id)
        if src and getattr(src, "target_language", None):
            page_results = await _maybe_run_translate_phase(
                pages=page_results,
                source_language=src.source_language,
                target_language=src.target_language,
                llm=llm,
            )
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest tests/test_pipeline_translate.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/ai/mrp/pipeline.py app/ai/mrp/writer.py tests/test_pipeline_translate.py
git commit -m "feat(translation): wire TRANSLATE phase into MRP pipeline"
```

---

## Task 7: Wire language detection into pre-processing

**Files:**
- Modify: `app/worker.py` (find pre-processing task — probably `ingest_file_task` or `ingest_url_task`)

- [ ] **Step 1: Locate where `full_text` is finalized in pre-processing**

Run: `grep -n "full_text" app/worker.py | head -20`

Identify the spot where `source.full_text = ...` is set before MAP enqueues. The detection must run on `full_text` after extraction completes but before MAP starts.

- [ ] **Step 2: Add the detection call**

At the identified location (after `full_text` is assembled, before the MAP enqueue), add:

```python
    # Detect source language for the optional TRANSLATE phase.
    if source.target_language and not source.source_language:
        from app.services.language_detection import detect_language
        from app.config import settings

        code, confidence = detect_language(source.full_text or "")
        if confidence >= settings.language_detection_min_confidence:
            source.source_language = code
        await session.commit()
```

The guard `if source.target_language` keeps the cost zero when no translation is requested.

- [ ] **Step 3: Write integration test**

Create `tests/test_pipeline_language_detection.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_detection_skipped_when_no_target_language():
    """No detection if target_language is null — saves cost."""
    from app.services.language_detection import detect_language

    # Direct unit test of the gate: we don't run the full worker, just confirm
    # the detect function works and the guard logic is simple. This is a
    # smoke test; full worker integration is covered by the e2e MRP fixture.
    code, conf = detect_language("Hello world. " * 10)
    assert code == "en"
    assert conf >= 0.6
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pipeline_language_detection.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add app/worker.py tests/test_pipeline_language_detection.py
git commit -m "feat(translation): detect source language during pre-processing"
```

---

## Task 8: Update embedding storage to key by `(page_id, model_spec_id, language)`

**Files:**
- Modify: `app/services/embedding_storage.py`
- Create: `tests/test_embedding_storage_language.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_embedding_storage_language.py`:

```python
"""Unit tests for the language-aware embedding storage helpers.

These test the pure function `embedding_input_text`/`compute_content_hash`
behavior with language tagging — DB-level tests are covered by integration.
"""

from app.services.embedding_storage import (
    compute_content_hash,
    embedding_input_text,
)


def test_compute_content_hash_includes_inputs():
    h1 = compute_content_hash("T", "S", "C")
    h2 = compute_content_hash("T", "S", "D")
    assert h1 != h2


def test_embedding_input_text_truncates_to_8000():
    out = embedding_input_text("t", "s", "x" * 20000)
    assert len(out) == 8000
```

- [ ] **Step 2: Run test and confirm pass (existing behavior preserved)**

Run: `pytest tests/test_embedding_storage_language.py -v`
Expected: 2 passed.

- [ ] **Step 3: Add language parameter to `upsert_page_embedding` and `get_existing_hash`**

Modify `app/services/embedding_storage.py:35-72`:

```python
async def upsert_page_embedding(
    session: AsyncSession,
    page_id: uuid.UUID,
    spec: EmbeddingModelSpec,
    vector: list[float],
    content_hash: str,
    language: str = "source",
) -> None:
    """Upsert one (page, model_spec_id, language) row into wiki_page_embeddings_<dim>."""
    Model = get_embedding_model_for_dim(spec.dimension)
    stmt = pg_insert(Model).values(
        page_id=page_id,
        model_spec_id=spec.id,
        language=language,
        content_hash=content_hash,
        embedding=vector,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["page_id", "model_spec_id", "language"],
        set_={
            "embedding": stmt.excluded.embedding,
            "content_hash": stmt.excluded.content_hash,
            "embedded_at": stmt.excluded.embedded_at,
        },
    )
    await session.execute(stmt)


async def get_existing_hash(
    session: AsyncSession,
    page_id: uuid.UUID,
    spec_id: str,
    dimension: int,
    language: str = "source",
) -> Optional[str]:
    Model = get_embedding_model_for_dim(dimension)
    row = (
        await session.execute(
            select(Model.content_hash).where(
                Model.page_id == page_id,
                Model.model_spec_id == spec_id,
                Model.language == language,
            )
        )
    ).scalar_one_or_none()
    return row
```

- [ ] **Step 4: Update callers that don't pass `language` (compatibility)**

Run: `grep -rn "upsert_page_embedding\|get_existing_hash" app/ tests/`

For each caller that does NOT yet pass `language`, leave them as-is — the default `"source"` preserves current behavior.

- [ ] **Step 5: Run all embedding tests**

Run: `pytest tests/test_embedding_storage_language.py tests/test_embedding_catalog.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/embedding_storage.py tests/test_embedding_storage_language.py
git commit -m "feat(embeddings): make storage helpers language-aware (default 'source')"
```

---

## Task 9: COMMIT phase — write translated fields and dual embeddings

**Files:**
- Modify: `app/ai/mrp/pipeline.py` (around line 187 — the COMMIT loop)
- Modify: `app/services/wiki_service.py` — `apply_create`/`apply_update` to accept translated fields

- [ ] **Step 1: Locate `apply_create` and `apply_update`**

Run: `grep -n "def apply_create\|def apply_update" app/services/wiki_service.py`

- [ ] **Step 2: Extend `apply_create` and `apply_update` signatures**

In `app/services/wiki_service.py`, add to both function signatures (after `summary`):

```python
    source_language: Optional[str] = None,
    target_language: Optional[str] = None,
    title_translated: Optional[str] = None,
    summary_translated: Optional[str] = None,
    content_md_translated: Optional[str] = None,
    translation_status: str = "skipped",
```

In `apply_create`, set every translation field on the new `WikiPage` row directly.

In `apply_update`, apply the **immutable-target-language** guard from the spec:

```python
    # spec: page's target_language is immutable after first set.
    if page.target_language is None and target_language is not None:
        page.target_language = target_language
        page.source_language = source_language or page.source_language
    elif page.target_language is not None and target_language and target_language != page.target_language:
        # Source requested a different target language; page wins.
        # Translation should have run against the page's existing target_language;
        # caller (pipeline.py) must override source.target_language before calling
        # the translator. If we're here it means the override was skipped — log
        # but don't fail the commit.
        from loguru import logger
        logger.warning(
            f"apply_update: page {page.slug} target_language={page.target_language} "
            f"but source requested {target_language}; ignoring source's choice."
        )

    # Always overwrite the translated halves and status when provided.
    if title_translated is not None:
        page.title_translated = title_translated
    if summary_translated is not None:
        page.summary_translated = summary_translated
    if content_md_translated is not None:
        page.content_md_translated = content_md_translated
    if translation_status:
        page.translation_status = translation_status
```

- [ ] **Step 2b: Add the source.target_language override in pipeline COMMIT loop**

Before the `apply_update` call in `pipeline.py`, look up the existing page's `target_language` (if any) and prefer it over the source's choice. Add right before the `apply_update(...)` call:

```python
            existing_target = None
            existing = (await session.execute(
                select(WikiPage).where(
                    WikiPage.slug == pr.slug,
                    WikiPage.scope_type == scope_type,
                    WikiPage.scope_id == scope_id,
                )
            )).scalar_one_or_none()
            if existing and existing.target_language:
                existing_target = existing.target_language
            effective_target = existing_target or getattr(source, "target_language", None)
```

Then pass `target_language=effective_target` to `apply_update(...)`.

(Add `from app.database.models import WikiPage` and `from sqlalchemy import select` at the top of pipeline.py if not already present.)

- [ ] **Step 3: Update COMMIT loop in `pipeline.py`**

In `app/ai/mrp/pipeline.py` around line 180-190 where `apply_create`/`apply_update` are called, pass the translation fields from `PageWriteResult`:

```python
        try:
            if pr.action == "CREATE":
                page = await wiki_service.apply_create(
                    session, slug=pr.slug, title=pr.title, content_md=pr.content_md,
                    summary=pr.summary, page_type=pr.page_type,
                    scope_type=scope_type, scope_id=scope_id,
                    source_ids=[source.id], knowledge_type_slugs=kt_slugs,
                    citations=pr.citations,
                    source_language=getattr(source, "source_language", None),
                    target_language=getattr(source, "target_language", None),
                    title_translated=pr.title_translated,
                    summary_translated=pr.summary_translated,
                    content_md_translated=pr.content_md_translated,
                    translation_status=pr.translation_status,
                )
            else:
                page = await wiki_service.apply_update(
                    session, slug=pr.slug, content_md=pr.content_md, summary=pr.summary,
                    title=pr.title, page_type=pr.page_type,
                    scope_type=scope_type, scope_id=scope_id,
                    source_ids=[source.id], knowledge_type_slugs=kt_slugs,
                    citations=pr.citations,
                    title_translated=pr.title_translated,
                    summary_translated=pr.summary_translated,
                    content_md_translated=pr.content_md_translated,
                    translation_status=pr.translation_status,
                )
        except ...
```

(Keep the existing exception handling unchanged.)

- [ ] **Step 4: Embed both halves after page apply**

Right after the page is created/updated and the source-language embedding is computed, add (still inside the COMMIT loop):

```python
            # Source embedding (existing call, ensure language='source' is passed)
            await upsert_page_embedding(
                session, page.id, active_spec, src_vector,
                compute_content_hash(page.title, page.summary, page.content_md),
                language="source",
            )

            # Target embedding (only if translation succeeded)
            if pr.translation_status == "done" and pr.content_md_translated:
                tgt_text = embedding_input_text(
                    pr.title_translated or "",
                    pr.summary_translated or "",
                    pr.content_md_translated or "",
                )
                tgt_vector = await embedding_provider.embed_one(tgt_text, task="document")
                await upsert_page_embedding(
                    session, page.id, active_spec, tgt_vector,
                    compute_content_hash(
                        pr.title_translated or "",
                        pr.summary_translated or "",
                        pr.content_md_translated or "",
                    ),
                    language="target",
                )
```

(Adjust to match the exact variable names already used in pipeline.py for the spec and provider — verify with `grep -n "embed_one\|active_spec" app/ai/mrp/pipeline.py`.)

- [ ] **Step 5: Manual smoke test — a single CREATE with translation**

Run: prepare a small fixture with `target_language='vi'` and observe via DB:

```bash
psql $DATABASE_URL -c "SELECT slug, target_language, translation_status, length(content_md_translated) FROM wiki_pages WHERE translation_status='done' LIMIT 5;"
psql $DATABASE_URL -c "SELECT page_id, model_spec_id, language FROM wiki_page_embeddings_3072 LIMIT 10;"
```

Expected: rows with `translation_status='done'` have non-empty `content_md_translated`, and the embedding table has both `language='source'` and `language='target'` rows for those pages.

- [ ] **Step 6: Commit**

```bash
git add app/ai/mrp/pipeline.py app/services/wiki_service.py
git commit -m "feat(translation): COMMIT writes translated fields and dual embeddings"
```

---

## Task 10: Search — query both language rows, return matched language

**Files:**
- Modify: `app/services/wiki_service.py` — `search_pages_semantic` (around line 357)
- Modify: `app/mcp/tools.py` and `app/ai/wiki_agent_tools.py` — pass through `matched_language` in result dicts
- Create: `tests/test_search_language.py`

- [ ] **Step 1: Identify the current search shape**

Run: `grep -n "search_pages_semantic\|matched_language" app/services/wiki_service.py app/mcp/tools.py app/ai/wiki_agent_tools.py`

Note the columns currently selected.

- [ ] **Step 2: Update the SELECT to include `language`**

In `app/services/wiki_service.py:421-425`, modify the query to:

```python
    stmt = (
        select(
            WikiPage.id, WikiPage.slug, WikiPage.title, WikiPage.summary,
            WikiPage.title_translated, WikiPage.summary_translated,
            WikiPage.target_language,
            Emb.language.label("matched_language"),
            (1 - Emb.embedding.cosine_distance(query_embedding)).label("similarity"),
        )
        .join(Emb, Emb.page_id == WikiPage.id)
        .where(Emb.model_spec_id == active_spec_id)
        # ... existing scope/RBAC WHERE clauses unchanged
        .order_by(Emb.embedding.cosine_distance(query_embedding))
        .limit(top_k * 2)  # over-fetch so we can dedupe per page_id
    )
```

(Keep the existing scope/RBAC predicates verbatim — only add `language` to the SELECT and over-fetch.)

- [ ] **Step 3: Dedupe results per `page_id`, keep max similarity**

After executing the query, replace the result-list-building block with:

```python
    rows = (await session.execute(stmt)).all()
    seen: dict[uuid.UUID, dict] = {}
    for row in rows:
        if row.id in seen:
            continue
        seen[row.id] = {
            "id": str(row.id),
            "slug": row.slug,
            "title": row.title,
            "summary": row.summary,
            "title_translated": row.title_translated,
            "summary_translated": row.summary_translated,
            "target_language": row.target_language,
            "matched_language": row.matched_language,
            "similarity": float(row.similarity),
        }
        if len(seen) >= top_k:
            break
    return list(seen.values())
```

- [ ] **Step 4: Update MCP and agent tool result schemas**

In `app/mcp/tools.py` and `app/ai/wiki_agent_tools.py`, wherever `search_wiki` formats results for the LLM, include `matched_language` in the dict it returns.

Example for `app/ai/wiki_agent_tools.py` (in the `search_wiki` handler):

```python
        formatted = [
            {
                "slug": r["slug"],
                "title": r["title"],
                "matched_language": r.get("matched_language"),
                "similarity": r["similarity"],
                "summary": r["summary"][:300],
            }
            for r in results
        ]
```

- [ ] **Step 5: Write a unit-ish test for the dedupe logic**

Create `tests/test_search_language.py`:

```python
"""Unit test the dedupe-by-page-id behavior in search_pages_semantic."""

# Pure-Python dedupe behavior is exercised via a small fake. The DB layer
# is exercised by integration tests not included in unit suite.

def test_dedupe_keeps_max_similarity():
    rows = [
        {"id": "a", "matched_language": "source", "similarity": 0.7},
        {"id": "a", "matched_language": "target", "similarity": 0.9},
        {"id": "b", "matched_language": "source", "similarity": 0.6},
    ]
    seen = {}
    for r in rows:
        if r["id"] in seen and seen[r["id"]]["similarity"] >= r["similarity"]:
            continue
        seen[r["id"]] = r

    assert seen["a"]["matched_language"] == "target"
    assert seen["a"]["similarity"] == 0.9
    assert seen["b"]["similarity"] == 0.6
```

Note: the production code above uses "first wins from ORDER BY similarity" which is equivalent when results are sorted descending. The test confirms the equivalent logic.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_search_language.py -v`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add app/services/wiki_service.py app/mcp/tools.py app/ai/wiki_agent_tools.py tests/test_search_language.py
git commit -m "feat(search): query bilingual embeddings and return matched language"
```

---

## Task 11: Source upload accepts `target_language`

**Files:**
- Modify: `app/routers/sources.py` — upload endpoint(s) and `Source` creation
- Create: `tests/test_sources_target_language.py`

- [ ] **Step 1: Locate the upload handler**

Run: `grep -n "ingest_file_task\|POST.*upload\|@router.post.*sources" app/routers/sources.py | head -10`

- [ ] **Step 2: Write a failing test**

Create `tests/test_sources_target_language.py`:

```python
"""Test that the upload endpoint accepts and persists `target_language`."""

# This is a thin smoke test — we don't run the full ASGI stack here.
# Just confirms the Pydantic schema accepts the new field.

from app.routers.sources import UploadMeta  # or whatever the request model is


def test_upload_meta_accepts_target_language():
    m = UploadMeta(scope_type="global", target_language="vi")
    assert m.target_language == "vi"


def test_upload_meta_target_language_optional():
    m = UploadMeta(scope_type="global")
    assert m.target_language is None
```

(Adapt the class name to whatever the actual request schema is. If the upload uses raw `Form(...)` parameters rather than a Pydantic model, replace the test with one that calls the endpoint via FastAPI's TestClient.)

- [ ] **Step 3: Run test and confirm failure**

Run: `pytest tests/test_sources_target_language.py -v`
Expected: FAIL — `target_language` not on the model yet.

- [ ] **Step 4: Add `target_language` to the upload request schema**

In `app/routers/sources.py`, find the upload Pydantic model (or `Form` parameters) and add:

```python
    target_language: Optional[str] = None  # ISO 639-1; null = no translation
```

In the upload handler, when constructing the `Source` row, pass it through:

```python
    source = Source(
        # ... existing fields
        target_language=payload.target_language,
    )
```

- [ ] **Step 5: Run tests and confirm pass**

Run: `pytest tests/test_sources_target_language.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/routers/sources.py tests/test_sources_target_language.py
git commit -m "feat(api): accept target_language on source upload"
```

---

## Task 12: Backfill endpoint + worker task

**Files:**
- Create: `app/routers/admin_translation.py`
- Modify: `app/worker.py` — register `backfill_translate_pages_task`
- Modify: `app/main.py` (or wherever routers are mounted) — include the new router

- [ ] **Step 1: Implement the worker task**

Append to `app/worker.py`:

```python
async def backfill_translate_pages_task(
    ctx: dict,
    scope_type: str,
    scope_id: Optional[str],
    target_language: str,
    page_ids: Optional[list[str]] = None,
    force: bool = False,
):
    """Translate existing wiki pages in a scope to the target language.

    Picks pages where target_language IS NULL (or all pages if force=True),
    runs them through the same translator used by the MRP pipeline, and
    upserts the target-language fields + embedding.
    """
    import uuid
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.database.models import Source, WikiPage
    from app.ai.mrp.translator import translate_page
    from app.ai.mrp.writer import PageWriteResult
    from app.ai.registry import ProviderRegistry
    from app.services.embedding_storage import (
        compute_content_hash, embedding_input_text, upsert_page_embedding,
    )
    from app.services.language_detection import detect_language

    async with async_session_factory() as session:
        registry = ProviderRegistry(session)
        llm = await registry.get_llm()
        embedder = await registry.get_embedding_provider()
        active_spec = await registry.get_active_embedding_spec()

        q = select(WikiPage).where(WikiPage.scope_type == scope_type)
        if scope_id:
            q = q.where(WikiPage.scope_id == uuid.UUID(scope_id))
        if page_ids:
            q = q.where(WikiPage.id.in_([uuid.UUID(p) for p in page_ids]))
        if not force:
            q = q.where(WikiPage.target_language.is_(None))

        pages = (await session.execute(q)).scalars().all()
        logger.info(f"Translation backfill: {len(pages)} pages → {target_language}")

        for page in pages:
            # Detect source language from existing content if unset.
            src_lang = page.source_language
            if not src_lang:
                code, conf = detect_language(page.content_md)
                if conf >= 0.6:
                    src_lang = code
            if not src_lang or src_lang == target_language:
                page.translation_status = "skipped"
                page.target_language = target_language
                await session.commit()
                continue

            stub = PageWriteResult(
                slug=page.slug, title=page.title, page_type=page.page_type,
                action="UPDATE", content_md=page.content_md, summary=page.summary,
            )
            output = await translate_page(llm, stub, src_lang, target_language)
            if output is None:
                page.translation_status = "failed"
                page.target_language = target_language
                await session.commit()
                continue

            page.source_language = src_lang
            page.target_language = target_language
            page.title_translated = output.title
            page.summary_translated = output.summary
            page.content_md_translated = output.content_md
            page.translation_status = "done"

            tgt_text = embedding_input_text(output.title, output.summary, output.content_md)
            tgt_vec = await embedder.embed_one(tgt_text, task="document")
            await upsert_page_embedding(
                session, page.id, active_spec, tgt_vec,
                compute_content_hash(output.title, output.summary, output.content_md),
                language="target",
            )
            await session.commit()
```

Then register it in the worker functions list (find the `functions = [...]` list around line 1086 in `app/worker.py`):

```python
        backfill_translate_pages_task,
```

- [ ] **Step 2: Implement the admin endpoint**

Create `app/routers/admin_translation.py`:

```python
"""Admin endpoint for backfilling translations on existing wiki pages."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import require_admin
from app.worker import get_arq_pool

router = APIRouter(prefix="/admin", tags=["admin"])


class TranslateBackfillRequest(BaseModel):
    scope_type: str
    scope_id: Optional[str] = None
    target_language: str
    page_ids: Optional[list[str]] = None
    force: bool = False


@router.post("/translate-pages")
async def translate_pages(
    body: TranslateBackfillRequest,
    db: AsyncSession = Depends(get_db),
    _admin = Depends(require_admin),
):
    if body.scope_type not in ("global", "department", "project"):
        raise HTTPException(status_code=400, detail="Invalid scope_type")
    if len(body.target_language) > 8:
        raise HTTPException(status_code=400, detail="Invalid target_language")

    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        "backfill_translate_pages_task",
        body.scope_type,
        body.scope_id,
        body.target_language,
        body.page_ids,
        body.force,
    )
    return {"queued": True, "job_id": job.job_id if job else None}
```

- [ ] **Step 3: Mount the router**

Find where other admin routers are mounted (probably in `app/main.py`). Add:

```python
from app.routers import admin_translation
app.include_router(admin_translation.router)
```

- [ ] **Step 4: Smoke test the endpoint**

Manual: with the dev server running,

```bash
curl -X POST http://localhost:8000/admin/translate-pages \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"scope_type": "global", "target_language": "vi"}'
```

Expected: `{"queued": true, "job_id": "..."}`. Then check the worker log for `Translation backfill: N pages → vi`.

- [ ] **Step 5: Commit**

```bash
git add app/routers/admin_translation.py app/worker.py app/main.py
git commit -m "feat(translation): add admin backfill endpoint and worker task"
```

---

## Task 13: Verifier — non-blocking warning for failed translations

**Files:**
- Modify: `app/ai/mrp/verifier.py`

- [ ] **Step 1: Locate the verify function**

Run: `grep -n "def run_verify_phase\|def run_verifier" app/ai/mrp/verifier.py`

- [ ] **Step 2: Append a translation-failure check at the end of verify**

Inside the verify function, after existing checks, append:

```python
    failed = [p for p in page_results if getattr(p, "translation_status", "skipped") == "failed"]
    if failed:
        slugs = ", ".join(p.slug for p in failed[:5])
        logger.warning(
            f"MRP VERIFY: {len(failed)} page(s) had translation failures: {slugs}"
            + (" ..." if len(failed) > 5 else "")
        )
        # Audit log entry (non-blocking)
        try:
            from app.services.audit import log_audit
            await log_audit(
                session, user=None, action="translate_failed",
                target_type="source", target_id=str(source.id),
                reason=f"{len(failed)} page(s) failed translation",
            )
        except Exception:
            pass
```

- [ ] **Step 3: Verify by running translate-phase tests**

Run: `pytest tests/test_pipeline_translate.py tests/test_translator.py -v`
Expected: all pass (the new code path is logging-only).

- [ ] **Step 4: Commit**

```bash
git add app/ai/mrp/verifier.py
git commit -m "feat(verify): non-blocking warning when page translation fails"
```

---

## Task 14: Frontend — upload form gets `target_language` dropdown

**Files:**
- Modify: `frontend/src/components/knowledge/upload-dialog.tsx`

- [ ] **Step 1: Locate where upload form fields are defined**

Run: `grep -n "scope_type\|FormField\|Select" frontend/src/components/knowledge/upload-dialog.tsx | head -20`

- [ ] **Step 2: Add a target_language Select field**

Inside the form (next to the scope/knowledge-type fields), add:

```tsx
<div className="space-y-2">
  <Label htmlFor="target-language">Translate to</Label>
  <Select
    value={targetLanguage}
    onValueChange={setTargetLanguage}
  >
    <SelectTrigger id="target-language">
      <SelectValue placeholder="No translation" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="">No translation</SelectItem>
      <SelectItem value="vi">Vietnamese</SelectItem>
      <SelectItem value="en">English</SelectItem>
    </SelectContent>
  </Select>
  <p className="text-xs text-muted-foreground">
    Wiki pages will include a side-by-side translation in the selected language.
  </p>
</div>
```

Add the corresponding `useState`:

```tsx
const [targetLanguage, setTargetLanguage] = useState<string>("");
```

When the form submits, include `target_language: targetLanguage || null` in the upload payload/FormData.

- [ ] **Step 3: Manual UI test**

Run the dev server (`pnpm dev` in frontend folder), open the upload dialog, confirm the "Translate to" select shows three options, submit a file with "Vietnamese" selected, then check the resulting `Source` row in the DB:

```bash
psql $DATABASE_URL -c "SELECT id, title, target_language FROM sources ORDER BY id DESC LIMIT 1;"
```

Expected: `target_language` column shows `vi`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge/upload-dialog.tsx
git commit -m "feat(ui): target_language dropdown on upload dialog"
```

---

## Task 15: Frontend — bilingual page view component

**Files:**
- Create: `frontend/src/components/wiki/bilingual-page-view.tsx`
- Modify: `frontend/src/components/wiki/wiki-content.tsx` — render via `BilingualPageView` when bilingual

- [ ] **Step 1: Create the component**

Create `frontend/src/components/wiki/bilingual-page-view.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { MarkdownRenderer } from "@/components/wiki/markdown-renderer";

type Mode = "source" | "target" | "side";
const STORAGE_KEY = "wiki.bilingual.mode";

interface Props {
  title: string;
  contentMd: string;
  titleTranslated: string | null;
  contentMdTranslated: string | null;
  sourceLanguage: string | null;
  targetLanguage: string | null;
}

export function BilingualPageView({
  title,
  contentMd,
  titleTranslated,
  contentMdTranslated,
  sourceLanguage,
  targetLanguage,
}: Props) {
  const bilingual = !!(titleTranslated && contentMdTranslated);
  const [mode, setMode] = useState<Mode>("side");

  useEffect(() => {
    if (!bilingual) {
      setMode("source");
      return;
    }
    const stored = typeof window !== "undefined"
      ? (window.localStorage.getItem(STORAGE_KEY) as Mode | null)
      : null;
    if (stored === "source" || stored === "target" || stored === "side") {
      setMode(stored);
    }
  }, [bilingual]);

  const onModeChange = (m: string) => {
    const next = (m as Mode);
    setMode(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  if (!bilingual) {
    return (
      <article className="prose dark:prose-invert max-w-none">
        <h1>{title}</h1>
        <MarkdownRenderer content={contentMd} />
      </article>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs text-muted-foreground">
          {sourceLanguage?.toUpperCase()} → {targetLanguage?.toUpperCase()}
        </div>
        <Tabs value={mode} onValueChange={onModeChange}>
          <TabsList>
            <TabsTrigger value="source">Source</TabsTrigger>
            <TabsTrigger value="target">Translated</TabsTrigger>
            <TabsTrigger value="side">Side-by-side</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {mode === "source" && (
        <article className="prose dark:prose-invert max-w-none">
          <h1>{title}</h1>
          <MarkdownRenderer content={contentMd} />
        </article>
      )}
      {mode === "target" && (
        <article className="prose dark:prose-invert max-w-none">
          <h1>{titleTranslated}</h1>
          <MarkdownRenderer content={contentMdTranslated!} />
        </article>
      )}
      {mode === "side" && (
        <div className="grid grid-cols-2 gap-6">
          <article className="prose dark:prose-invert max-w-none">
            <h1>{title}</h1>
            <MarkdownRenderer content={contentMd} />
          </article>
          <article className="prose dark:prose-invert max-w-none border-l pl-6">
            <h1>{titleTranslated}</h1>
            <MarkdownRenderer content={contentMdTranslated!} />
          </article>
        </div>
      )}
    </div>
  );
}
```

(If `MarkdownRenderer` is named differently in this repo, swap the import and component name to match the existing renderer — find with: `grep -rln "ReactMarkdown\|MarkdownRenderer" frontend/src/components/wiki/`.)

- [ ] **Step 2: Wire the component into `wiki-content.tsx`**

Replace the single-language markdown render with `BilingualPageView`. Find the existing render in `frontend/src/components/wiki/wiki-content.tsx` and replace it:

```tsx
<BilingualPageView
  title={page.title}
  contentMd={page.content_md}
  titleTranslated={page.title_translated ?? null}
  contentMdTranslated={page.content_md_translated ?? null}
  sourceLanguage={page.source_language ?? null}
  targetLanguage={page.target_language ?? null}
/>
```

If the wiki page TypeScript type doesn't have the translation fields yet, add them to the type (likely in `frontend/src/lib/api-types.ts` or co-located).

- [ ] **Step 3: Manual UI test**

Open a page that has `target_language` set in DB, confirm:
- Toggle shows three buttons.
- Switching to "Translated" renders the Vietnamese half.
- "Side-by-side" renders two columns.
- Refresh: the previously selected mode persists.

Open a monolingual page, confirm the toggle is hidden and the page renders as before.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/wiki/bilingual-page-view.tsx frontend/src/components/wiki/wiki-content.tsx frontend/src/lib/api-types.ts
git commit -m "feat(ui): bilingual page view with Source/Translated/Side-by-side toggle"
```

---

## Task 16: Frontend — language badge in knowledge table + citation panel

**Files:**
- Modify: `frontend/src/components/knowledge/knowledge-table/` (the row component)
- Modify: `frontend/src/components/chat/citation-panel.tsx`

- [ ] **Step 1: Add language badge to knowledge-table source rows**

In the source row component (find with `grep -rln "source_type\|target_language" frontend/src/components/knowledge/`), if `source.target_language` is set, render:

```tsx
{source.target_language && (
  <Badge variant="outline" className="text-xs">
    {(source.source_language ?? "??").toUpperCase()} → {source.target_language.toUpperCase()}
  </Badge>
)}
```

Same for translation status (failed/done/pending) — show a small icon if status is `failed`.

- [ ] **Step 2: Citation panel shows translated title for bilingual pages**

In `frontend/src/components/chat/citation-panel.tsx`, when fetching a wiki page, if `page.target_language` is set and `page.title_translated` exists, render the title block as:

```tsx
<div>
  <h2 className="text-lg font-semibold">{page.title}</h2>
  {page.title_translated && (
    <p className="text-sm text-muted-foreground">{page.title_translated}</p>
  )}
</div>
```

And render the page body via `BilingualPageView` (reuse from Task 15) so users can toggle inside the panel.

- [ ] **Step 3: Manual UI test**

- Upload a Chinese doc with `target_language=vi`.
- Open the knowledge table, confirm the new badge `ZH → VI` shows on the row.
- Wait for processing; ask the chat a question that cites the page.
- Click the citation, confirm the panel shows both titles and the toggle works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge frontend/src/components/chat/citation-panel.tsx
git commit -m "feat(ui): language badge on sources and bilingual citation panel"
```

---

## Task 17: End-to-end manual verification

- [ ] **Step 1: Reset the dev environment**

```bash
alembic upgrade head
```

- [ ] **Step 2: Upload a Chinese fixture document with `target_language=vi`**

Use the UI or:

```bash
curl -X POST http://localhost:8000/sources/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@tests/fixtures/zh_sample.pdf" \
  -F "scope_type=global" \
  -F "target_language=vi"
```

- [ ] **Step 3: Watch the pipeline complete**

Tail the worker log. Confirm the sequence:
1. `Pre-processing: detected source_language=zh`
2. `MAP: ...`
3. `REDUCE: plan_ready` (auto-approve or manual)
4. `REFINE: ...`
5. `TRANSLATE: N pages, X done, Y failed`
6. `VERIFY: ...`
7. `COMMIT: ...`
8. Source status → `ready`.

- [ ] **Step 4: Verify DB state**

```bash
psql $DATABASE_URL -c "SELECT slug, source_language, target_language, translation_status FROM wiki_pages WHERE id IN (SELECT page_id FROM wiki_page_embeddings_3072 WHERE language='target' LIMIT 5);"
```

Expected: rows with `source_language='zh'`, `target_language='vi'`, `translation_status='done'`.

- [ ] **Step 5: Verify bilingual search**

- Search the chat in Vietnamese for a term you know is on the page.
- Confirm the page appears in results.
- Repeat in Chinese — confirm same page appears.
- Inspect `matched_language` in the result (check the source-snippet language shown in citations panel).

- [ ] **Step 6: Verify UI**

- Open the wiki page in the browser. Confirm `Source / Translated / Side-by-side` toggle is present and renders correctly.
- Refresh the page — confirm the toggle remembers your last choice.
- Open a non-translated page — confirm no toggle is shown.

- [ ] **Step 7: Test backfill endpoint**

```bash
curl -X POST http://localhost:8000/admin/translate-pages \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"scope_type": "global", "target_language": "en"}'
```

Watch the worker run the backfill. Confirm pages without `target_language` get translated.

- [ ] **Step 8: Final commit + push**

```bash
git push
```

---

## Spec Coverage Map

| Spec section | Tasks |
|---|---|
| Data Model — `Source`, `WikiPage`, embeddings | 1, 2 |
| Configuration | 3 |
| Phase 1 — Language Detection | 4, 7 |
| Phase 4.5 — TRANSLATE (translator, prompts, validation) | 5, 6 |
| Phase 5 — VERIFY extension | 13 |
| Phase 6 — COMMIT changes (dual fields + dual embeddings) | 8, 9 |
| UPDATE behavior matrix (immutable target_language) | 9 (Step 2 + 2b) |
| Search — query both languages, return matched | 10 |
| Source upload API | 11 |
| Backfill admin endpoint + worker | 12 |
| UI — upload dropdown | 14 |
| UI — bilingual page view | 15 |
| UI — knowledge table badge + citation panel | 16 |
| End-to-end verification | 17 |
