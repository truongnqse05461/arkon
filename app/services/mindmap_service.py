"""Mindmap Service - AI generation of wiki topic trees."""

import json
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import ProviderRegistry
from app.database.models import WikiMindmap, WikiPage

SMALL_WIKI_THRESHOLD = 150
EXCERPT_CHARS = 600
MIN_MEANINGFUL_CHARS = 40
INTERNAL_PAGE_SLUGS = {"_index", "_log"}

_SYSTEM = "You are a knowledge architect. Return ONLY valid JSON - no markdown, no explanation."

_PROMPT_TEMPLATE = """\
You are given wiki knowledge pages from an organization's knowledge base.
Create a learner-facing concept map that helps a user understand the actual
knowledge content.

Do not mirror wiki navigation or maintenance structure. Ignore administrative,
index, log, changelog, navigation, and metadata pages if they appear in the
input. Prefer concepts, processes, systems, entities, policies, decisions,
relationships, and dependencies.

Return valid JSON matching this schema exactly:
{{
  "name": "<root topic name - 2-4 words summarising the whole KB>",
  "children": [
    {{
      "name": "<subtopic>",
      "children": [
        {{"name": "<leaf>", "children": []}}
      ]
    }}
  ]
}}

Rules:
- Depth should match the natural complexity - no fixed level limit.
- Every node must have a "children" key (empty array for leaves).
- Node names must be concise, user-facing concepts.
- Avoid node names like "Wiki Index", "Wiki Log", "Administrative Pages", "Metadata", or "Source List".
- Do not include duplicate sibling names.
- Return ONLY the JSON object, nothing else.

Wiki knowledge pages:
{pages}
"""


def _first_text(*values: Optional[str]) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _page_display_title(page: WikiPage) -> str:
    return _first_text(getattr(page, "title_translated", None), getattr(page, "title", ""))


def _page_display_text(page: WikiPage) -> str:
    return _first_text(
        getattr(page, "summary_translated", None),
        getattr(page, "content_md_translated", None),
        getattr(page, "summary", None),
        getattr(page, "content_md", ""),
    )


def _page_meaningful_text(page: WikiPage) -> str:
    return " ".join(
        text
        for text in (
            _first_text(getattr(page, "summary_translated", None)),
            _first_text(getattr(page, "content_md_translated", None)),
            _first_text(getattr(page, "summary", None)),
            _first_text(getattr(page, "content_md", "")),
        )
        if text
    )


def _is_internal_page(page: WikiPage) -> bool:
    slug = _first_text(getattr(page, "slug", ""))
    return slug in INTERNAL_PAGE_SLUGS


def _is_meaningful_page(page: WikiPage) -> bool:
    return bool(_page_display_title(page)) and len(_page_meaningful_text(page)) >= MIN_MEANINGFUL_CHARS


def _filter_pages_for_mindmap(pages: list[WikiPage]) -> list[WikiPage]:
    return [
        page
        for page in pages
        if not _is_internal_page(page) and _is_meaningful_page(page)
    ]


def _build_payload(pages: list) -> str:
    if len(pages) < SMALL_WIKI_THRESHOLD:
        lines = [
            f"- {_page_display_title(p)}: {_page_display_text(p)[:EXCERPT_CHARS].strip()}"
            for p in pages
        ]
    else:
        lines = [f"- {_page_display_title(p)}" for p in pages]
    return "\n".join(lines)


async def get_mindmap(
    db: AsyncSession,
    scope_type: str,
    scope_id: Optional[uuid.UUID],
) -> Optional[WikiMindmap]:
    stmt = select(WikiMindmap).where(
        WikiMindmap.scope_type == scope_type,
        WikiMindmap.scope_id == scope_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def generate_mindmap(
    db: AsyncSession,
    scope_type: str,
    scope_id: Optional[uuid.UUID],
) -> WikiMindmap:
    stmt = select(WikiPage).where(
        WikiPage.scope_type == scope_type,
        WikiPage.scope_id == scope_id,
        WikiPage.orphaned.is_(False),
    )
    result = await db.execute(stmt)
    pages = _filter_pages_for_mindmap(list(result.scalars().all()))

    if not pages:
        raise ValueError("No wiki pages found for this scope.")

    payload = _build_payload(pages)
    prompt = _PROMPT_TEMPLATE.format(pages=payload)

    registry = ProviderRegistry(db)
    llm = await registry.get_llm()
    raw = await llm.generate(prompt, system=_SYSTEM, temperature=0.3, max_tokens=4096)

    try:
        tree = json.loads(raw.strip())
    except json.JSONDecodeError:
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            tree = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc

    if not isinstance(tree, dict):
        raise ValueError(f"LLM returned unexpected JSON shape: {type(tree).__name__}")
    title = str(tree.get("name", "Knowledge Base"))

    existing = await get_mindmap(db, scope_type, scope_id)
    if existing:
        existing.title = title
        existing.tree_json = tree
        existing.wiki_page_count = len(pages)
        await db.flush()
        await db.refresh(existing)
        return existing

    mindmap = WikiMindmap(
        scope_type=scope_type,
        scope_id=scope_id,
        title=title,
        tree_json=tree,
        wiki_page_count=len(pages),
    )
    db.add(mindmap)
    await db.flush()
    await db.refresh(mindmap)
    return mindmap


async def delete_mindmap(db: AsyncSession, mindmap_id: uuid.UUID) -> bool:
    stmt = select(WikiMindmap).where(WikiMindmap.id == mindmap_id)
    result = await db.execute(stmt)
    mindmap = result.scalar_one_or_none()
    if not mindmap:
        return False
    await db.delete(mindmap)
    await db.flush()
    return True
