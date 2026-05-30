"""Mindmap Service — AI generation of wiki topic trees."""

import json
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import ProviderRegistry
from app.database.models import WikiMindmap, WikiPage

SMALL_WIKI_THRESHOLD = 150
EXCERPT_CHARS = 300

_SYSTEM = "You are a knowledge architect. Return ONLY valid JSON — no markdown, no explanation."

_PROMPT_TEMPLATE = """\
Given the following wiki pages from an organization's knowledge base, group them into \
a meaningful topic hierarchy that reflects the knowledge structure.

Return valid JSON matching this schema exactly:
{{
  "name": "<root topic name — 2-4 words summarising the whole KB>",
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
- Depth should match the natural complexity — no fixed level limit.
- Every node must have a "children" key (empty array for leaves).
- Return ONLY the JSON object, nothing else.

Wiki pages:
{pages}
"""


def _build_payload(pages: list) -> str:
    if len(pages) < SMALL_WIKI_THRESHOLD:
        lines = [f"- {p.title}: {p.content_md[:EXCERPT_CHARS].strip()}" for p in pages]
    else:
        lines = [f"- {p.title}" for p in pages]
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
    pages = list(result.scalars().all())

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
