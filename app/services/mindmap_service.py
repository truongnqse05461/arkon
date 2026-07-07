"""Mindmap Service - AI generation of wiki topic trees."""

import json
import re
import uuid
from difflib import SequenceMatcher
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


# --- Tree node enrichment ---

_SUMMARY_MAX_LEN = 200
_FUZZY_THRESHOLD = 0.75


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", name.lower())).strip()


def _build_page_lookup(pages: list[WikiPage]) -> dict[str, list[dict]]:
    """Build normalized_title -> list of page metadata dicts."""
    lookup: dict[str, list[dict]] = {}
    for page in pages:
        title = _page_display_title(page)
        if not title:
            continue
        key = _normalize_name(title)
        summary_raw = _first_text(
            getattr(page, "summary_translated", None),
            getattr(page, "summary", None),
        )
        entry = {
            "slug": getattr(page, "slug", ""),
            "page_type": getattr(page, "page_type", "concept"),
            "summary": summary_raw[:_SUMMARY_MAX_LEN] if summary_raw else "",
        }
        lookup.setdefault(key, []).append(entry)
    return lookup


def _match_node(node_name: str, lookup: dict[str, list[dict]]) -> Optional[dict]:
    """Find best matching page for a node name. Returns metadata dict or None."""
    normalized = _normalize_name(node_name)
    if not normalized:
        return None

    # Exact match
    if normalized in lookup:
        candidates = lookup[normalized]
        return max(candidates, key=lambda c: len(c.get("summary", "")))

    # Substring match — pragmatic middle tier between exact and fuzzy.
    # Heuristic: the shorter name must be at least 50% of the longer name's
    # length to avoid false positives like "API" matching "REST API Design".
    norm_len = len(normalized)
    best_sub_entry = None
    best_sub_len_diff = float("inf")
    for page_key, entries in lookup.items():
        shorter = min(norm_len, len(page_key))
        longer = max(norm_len, len(page_key))
        if shorter < longer * 0.5:
            continue
        if normalized in page_key or page_key in normalized:
            len_diff = abs(norm_len - len(page_key))
            if len_diff < best_sub_len_diff:
                best_sub_len_diff = len_diff
                best_sub_entry = max(entries, key=lambda c: len(c.get("summary", "")))
    if best_sub_entry:
        return best_sub_entry

    # Fuzzy match
    best_score = 0.0
    best_entry = None
    for page_key, entries in lookup.items():
        score = SequenceMatcher(None, normalized, page_key).ratio()
        if score > best_score:
            best_score = score
            best_entry = max(entries, key=lambda c: len(c.get("summary", "")))

    if best_score >= _FUZZY_THRESHOLD and best_entry:
        return best_entry
    return None


def _enrich_tree_nodes(tree: dict, pages: list[WikiPage]) -> dict:
    """Enrich tree nodes with wiki page metadata (slug, type, summary)."""
    lookup = _build_page_lookup(pages)

    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = match["slug"]
            node["page_type"] = match["page_type"]
            if match["summary"]:
                node["summary"] = match["summary"]
        for child in node.get("children", []):
            enrich_node(child)
        return node

    return enrich_node(tree)


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

    tree = _enrich_tree_nodes(tree, pages)

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
