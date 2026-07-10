"""Mindmap Service - AI generation of wiki topic trees."""

import json
import re
import uuid
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import ProviderRegistry
from app.database.models import Source, WikiMindmap, WikiPage

SMALL_WIKI_THRESHOLD = 150
EXCERPT_CHARS = 600
MIN_MEANINGFUL_CHARS = 40
INTERNAL_PAGE_SLUGS = {"_index", "_log"}

_SUMMARY_BATCH_SIZE = 15
_SUMMARY_MAX_CHARS = 150

_SYSTEM = (
    "You are a knowledge architect. Return ONLY valid JSON - no markdown, no explanation. "
    'Return an object with "title" (string, 3-8 words) and "tree" (the concept map object).'
)

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
  "title": "<short descriptive title - 3-8 words>",
  "tree": {{
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
}}

Rules:
- "title" should be a concise, descriptive name for this mindmap.
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
    """Build normalized_title -> list of page metadata dicts.

    Indexes both translated and original titles so the LLM's English node
    names can match even when pages have translated display titles.
    """
    lookup: dict[str, list[dict]] = {}
    for page in pages:
        display_title = _page_display_title(page)
        original_title = _first_text(getattr(page, "title", ""))
        if not display_title and not original_title:
            continue
        summary_raw = _first_text(
            getattr(page, "summary_translated", None),
            getattr(page, "summary", None),
        )
        entry = {
            "slug": getattr(page, "slug", ""),
            "page_type": getattr(page, "page_type", "concept"),
            "title": display_title or original_title,
            "summary": summary_raw[:_SUMMARY_MAX_LEN] if summary_raw else "",
        }
        # Index by translated title (primary)
        if display_title:
            key = _normalize_name(display_title)
            if key:
                lookup.setdefault(key, []).append(entry)
        # Also index by original title (for LLM English node name matching)
        if original_title:
            orig_key = _normalize_name(original_title)
            if orig_key and orig_key not in lookup:
                lookup.setdefault(orig_key, []).append(entry)
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
            # Add to sources array for multi-source support
            source_entry = {
                "slug": match["slug"],
                "type": match["page_type"],
                "title": match.get("title", match["slug"]),
            }
            node.setdefault("sources", []).append(source_entry)
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


_SOURCE_DOC_TEXT_LIMIT = 8000


def _build_source_doc_payload(sources: list) -> str:
    """Build payload from source documents."""
    lines = []
    for src in sources:
        title = _first_text(getattr(src, "title", None), "Untitled")
        text = _first_text(getattr(src, "full_text", None), "")
        if text:
            text = text[:_SOURCE_DOC_TEXT_LIMIT]
        lines.append(f"- {title}: {text}")
    return "\n".join(lines)


def _enrich_tree_nodes_from_sources(tree: dict, sources: list) -> dict:
    """Enrich nodes with source document metadata."""
    lookup: dict[str, list[dict]] = {}
    for src in sources:
        title = _first_text(getattr(src, "title", None))
        if not title:
            continue
        key = _normalize_name(title)
        entry = {
            "id": str(getattr(src, "id", "")),
            "title": title,
            "source_type": getattr(src, "source_type", "file"),
        }
        lookup.setdefault(key, []).append(entry)

    def enrich_node(node: dict) -> dict:
        match = _match_node(node.get("name", ""), lookup)
        if match:
            node["page_slug"] = f"source:{match['id']}"
            node["page_type"] = "document"
            node["summary"] = match["title"][:_SUMMARY_MAX_LEN]
            # Add to sources array for multi-source support
            source_entry = {
                "slug": f"source:{match['id']}",
                "type": "source_doc",
                "title": match["title"],
            }
            node.setdefault("sources", []).append(source_entry)
        for child in node.get("children", []):
            enrich_node(child)
        return node

    return enrich_node(tree)


_SUMMARY_PROMPT = """\
Given the following node names from a knowledge map, generate a concise
1-2 sentence summary for each node. The summary should explain what this
concept/topic means in the context of the knowledge base.

Node names:
{node_names}

Return JSON array:
[
  {{"name": "Node Name", "summary": "Brief explanation of the concept."}},
  ...
]

Rules:
- Summary must be max 150 characters
- Use plain language, no jargon
- If the node name is unclear, make a reasonable assumption based on context
"""


def _collect_unmatched_nodes(tree: dict) -> list[str]:
    """Collect node names that have no page_slug, no sources, and no summary."""
    unmatched = []

    def walk(node: dict):
        has_sources = bool(node.get("sources"))
        if not node.get("page_slug") and not has_sources and not node.get("summary"):
            name = node.get("name", "")
            if name:
                unmatched.append(name)
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return unmatched


def _apply_summaries(tree: dict, summaries: dict[str, str]) -> dict:
    """Apply generated summaries to tree nodes."""

    def walk(node: dict):
        name = node.get("name", "")
        if name in summaries and not node.get("summary"):
            node["summary"] = summaries[name][:_SUMMARY_MAX_CHARS]
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return tree


async def _generate_node_summaries(
    nodes: list[str],
    llm,
) -> dict[str, str]:
    """Generate summaries for unmatched nodes in batches."""
    summaries: dict[str, str] = {}

    for i in range(0, len(nodes), _SUMMARY_BATCH_SIZE):
        batch = nodes[i : i + _SUMMARY_BATCH_SIZE]
        prompt = _SUMMARY_PROMPT.format(node_names="\n".join(batch))

        try:
            result = await llm.generate(prompt, temperature=0.3, max_tokens=1024)
            cleaned = (
                result.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "name" in item and "summary" in item:
                        summaries[item["name"]] = item["summary"]
        except Exception:
            pass  # Skip summaries for this batch

    return summaries


async def list_mindmaps(
    db: AsyncSession,
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
) -> list[WikiMindmap]:
    """List all mindmaps, optionally filtered by scope."""
    stmt = select(WikiMindmap)
    if scope_type:
        stmt = stmt.where(WikiMindmap.scope_type == scope_type)
    if scope_id:
        stmt = stmt.where(WikiMindmap.scope_id == scope_id)
    stmt = stmt.order_by(WikiMindmap.generated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_mindmap(
    db: AsyncSession,
    scope_type: str,
    scope_id: Optional[uuid.UUID],
    source_type: str = "wiki",
) -> Optional[WikiMindmap]:
    stmt = select(WikiMindmap).where(
        WikiMindmap.scope_type == scope_type,
        WikiMindmap.scope_id == scope_id,
        WikiMindmap.source_type == source_type,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_mindmap_by_id(
    db: AsyncSession,
    mindmap_id: uuid.UUID,
) -> Optional[WikiMindmap]:
    stmt = select(WikiMindmap).where(WikiMindmap.id == mindmap_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def generate_mindmap(
    db: AsyncSession,
    scope_type: str,
    scope_id: Optional[uuid.UUID],
    source_type: str = "wiki",
    source_ids: Optional[list[uuid.UUID]] = None,
    instruction: Optional[str] = None,
) -> WikiMindmap:
    if source_type == "source_docs" and source_ids:
        # Fetch source documents
        stmt = select(Source).where(Source.id.in_(source_ids))
        result = await db.execute(stmt)
        sources = list(result.scalars().all())
        if not sources:
            raise ValueError("No source documents found for the given IDs.")
        payload = _build_source_doc_payload(sources)
        page_count = len(sources)
    else:
        # Wiki mode (existing behavior)
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
        page_count = len(pages)

    # Build prompt with optional instruction
    prompt = _PROMPT_TEMPLATE.format(pages=payload)
    if instruction:
        prompt += f"\n\nAdditional instructions: {instruction}"

    registry = ProviderRegistry(db)
    llm = await registry.get_llm()
    raw = await llm.generate(prompt, system=_SYSTEM, temperature=0.3, max_tokens=4096)

    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"LLM returned unexpected JSON shape: {type(parsed).__name__}")

    # Extract title and tree from wrapped response
    title = str(parsed.get("title", "")).strip() or "Untitled Mindmap"
    tree = parsed.get("tree", parsed)
    if not isinstance(tree, dict) or "name" not in tree:
        # Fallback: maybe LLM returned tree directly without wrapper
        tree = parsed
        title = str(tree.get("name", "Untitled Mindmap"))

    # Enrich nodes based on source type
    if source_type == "source_docs" and source_ids:
        tree = _enrich_tree_nodes_from_sources(tree, sources)
    else:
        tree = _enrich_tree_nodes(tree, pages)

    # Generate LLM summaries for unmatched nodes
    unmatched = _collect_unmatched_nodes(tree)
    if unmatched:
        summaries = await _generate_node_summaries(unmatched, llm)
        tree = _apply_summaries(tree, summaries)

    mindmap = WikiMindmap(
        scope_type=scope_type,
        scope_id=scope_id,
        title=title,
        tree_json=tree,
        wiki_page_count=page_count,
        source_type=source_type,
        source_ids=[str(sid) for sid in source_ids] if source_ids else None,
        instruction=instruction,
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
