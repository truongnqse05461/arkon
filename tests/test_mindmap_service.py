import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_page(
    title: str,
    content: str = "content " * 10,
    scope_type: str = "global",
    scope_id=None,
    slug: str = "page",
    summary: str = "",
    page_type: str = "concept",
    title_translated=None,
    summary_translated=None,
    content_md_translated=None,
    source_ids=None,
):
    p = MagicMock()
    p.slug = slug
    p.title = title
    p.page_type = page_type
    p.summary = summary
    p.content_md = content
    p.title_translated = title_translated
    p.summary_translated = summary_translated
    p.content_md_translated = content_md_translated
    p.source_ids = source_ids or []
    p.scope_type = scope_type
    p.scope_id = scope_id
    p.orphaned = False
    return p


def make_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_build_payload_uses_excerpts_for_small_wiki():
    from app.services.mindmap_service import _build_payload
    pages = [make_page(f"Page {i}", "x" * 700) for i in range(10)]
    result = _build_payload(pages)
    assert "Page 0" in result
    # With excerpts: each line has content (the "x" * 600 excerpt)
    assert "x" in result


@pytest.mark.asyncio
async def test_build_payload_prefers_translated_title_and_summary():
    from app.services.mindmap_service import _build_payload

    pages = [
        make_page(
            "Original Title",
            content="Original content " * 20,
            title_translated="Tieu de dich",
            summary_translated="Tom tat da dich " * 10,
        )
    ]

    result = _build_payload(pages)

    assert "Tieu de dich" in result
    assert "Tom tat da dich" in result
    assert "Original Title" not in result


@pytest.mark.asyncio
async def test_build_payload_falls_back_to_original_content():
    from app.services.mindmap_service import _build_payload

    pages = [make_page("Architecture", content="Original architecture content " * 20)]

    result = _build_payload(pages)

    assert "Architecture" in result
    assert "Original architecture content" in result


@pytest.mark.asyncio
async def test_build_payload_uses_translated_content_when_summary_missing():
    from app.services.mindmap_service import _build_payload

    pages = [
        make_page(
            "Original Title",
            content="Original content " * 20,
            title_translated="Tieu de dich",
            content_md_translated="Noi dung da dich " * 20,
        )
    ]

    result = _build_payload(pages)

    assert "Tieu de dich" in result
    assert "Noi dung da dich" in result
    assert "Original content" not in result


@pytest.mark.asyncio
async def test_build_payload_titles_only_for_large_wiki():
    from app.services.mindmap_service import _build_payload
    pages = [make_page(f"Page {i}") for i in range(150)]
    result = _build_payload(pages)
    lines = result.splitlines()
    assert len(lines) == 150
    # Titles-only lines are shorter (just "- Page N")
    for line in lines:
        assert len(line) < 20


def test_filter_pages_excludes_wiki_index_and_log():
    from app.services.mindmap_service import _filter_pages_for_mindmap

    pages = [
        make_page("Wiki Index", content="Index content " * 20, slug="_index"),
        make_page("Wiki Log", content="Log content " * 20, slug="_log"),
        make_page("Policy", content="Policy learning content " * 20, slug="policy"),
    ]

    result = _filter_pages_for_mindmap(pages)

    assert [p.title for p in result] == ["Policy"]


def test_filter_pages_excludes_empty_or_short_content():
    from app.services.mindmap_service import _filter_pages_for_mindmap

    pages = [
        make_page("Stub", content="short", slug="stub"),
        make_page("Useful", content="Useful process content " * 20, slug="useful"),
    ]

    result = _filter_pages_for_mindmap(pages)

    assert [p.title for p in result] == ["Useful"]


def test_filter_pages_keeps_short_summary_with_meaningful_content():
    from app.services.mindmap_service import _filter_pages_for_mindmap

    pages = [
        make_page(
            "Useful",
            content="",
            slug="useful",
            summary_translated="OK",
            content_md_translated="Meaningful translated process content " * 20,
        )
    ]

    result = _filter_pages_for_mindmap(pages)

    assert [p.title for p in result] == ["Useful"]


@pytest.mark.asyncio
async def test_list_mindmaps_returns_all():
    from app.services.mindmap_service import list_mindmaps
    db = make_db()
    mindmaps = [MagicMock(), MagicMock()]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mindmaps
    db.execute = AsyncMock(return_value=mock_result)

    result = await list_mindmaps(db)
    assert len(result) == 2
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_generate_mindmap_calls_llm_and_upserts():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    pages = [make_page("Architecture"), make_page("Deployment")]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": [{"name": "Architecture", "children": []}]}
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=json.dumps(tree))

    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            result = await generate_mindmap(db, "global", None)
            db.add.assert_called_once()
            db.flush.assert_called()
            prompt = mock_llm.generate.call_args_list[0].args[0]
            assert "learner-facing concept map" in prompt
            assert "Wiki knowledge pages" in prompt


@pytest.mark.asyncio
async def test_generate_mindmap_raises_when_no_pages():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValueError, match="No wiki pages"):
        await generate_mindmap(db, "global", None)


@pytest.mark.asyncio
async def test_generate_mindmap_strips_markdown_fences():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    pages = [make_page("Arch")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": []}
    raw = f"```json\n{json.dumps(tree)}\n```"
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=raw)
    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            result = await generate_mindmap(db, "global", None)
            assert result is not None


@pytest.mark.asyncio
async def test_generate_mindmap_uses_only_filtered_pages_and_count():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    pages = [
        make_page("Wiki Index", content="Index content " * 20, slug="_index"),
        make_page("Architecture", content="Architecture content " * 20, slug="architecture"),
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": []}
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=json.dumps(tree))
    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            result = await generate_mindmap(db, "global", None)

    assert result.wiki_page_count == 1
    prompt = mock_llm.generate.call_args_list[0].args[0]
    assert "Architecture" in prompt
    payload = prompt.split("Wiki knowledge pages:", 1)[1]
    assert "Wiki Index" not in payload


@pytest.mark.asyncio
async def test_generate_mindmap_raises_when_only_internal_pages():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    pages = [make_page("Wiki Log", content="Log content " * 20, slug="_log")]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValueError, match="No wiki pages"):
        await generate_mindmap(db, "global", None)


@pytest.mark.asyncio
async def test_generate_mindmap_updates_existing():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    pages = [make_page("Architecture")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    tree = {"name": "KB", "children": []}
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=json.dumps(tree))
    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    existing = MagicMock()
    existing.title = "Old Title"
    existing.tree_json = {}
    existing.wiki_page_count = 0

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=existing):
            result = await generate_mindmap(db, "global", None)
            assert result is existing
            assert existing.title == "KB"
            assert existing.wiki_page_count == 1
            db.flush.assert_called()


@pytest.mark.asyncio
async def test_generate_mindmap_raises_on_non_dict_json():
    from app.services.mindmap_service import generate_mindmap
    db = make_db()
    pages = [make_page("Arch")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = pages
    db.execute = AsyncMock(return_value=mock_result)

    # LLM returns a JSON array instead of an object
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value='[{"name": "KB"}]')
    mock_registry = AsyncMock()
    mock_registry.get_llm = AsyncMock(return_value=mock_llm)

    with patch("app.services.mindmap_service.ProviderRegistry", return_value=mock_registry):
        with patch("app.services.mindmap_service.get_mindmap", return_value=None):
            with pytest.raises(ValueError, match="unexpected JSON shape"):
                await generate_mindmap(db, "global", None)


# --- _enrich_tree_nodes tests ---


def test_enrich_tree_exact_match():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [
        make_page("Authentication", slug="auth", summary="Auth methods", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    assert child["page_slug"] == "auth"
    assert child["page_type"] == "concept"
    assert child["summary"] == "Auth methods"


def test_enrich_tree_fuzzy_match():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [
        make_page("User Authentication Methods", slug="user-auth", summary="How users authenticate", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    assert child["page_slug"] == "user-auth"


def test_enrich_tree_no_match():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [
        make_page("Deployment Guide", slug="deploy", summary="Deploy steps", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    assert "page_slug" not in child


def test_enrich_tree_summary_truncated():
    from app.services.mindmap_service import _enrich_tree_nodes

    long_summary = "x" * 300
    pages = [
        make_page("Auth", slug="auth", summary=long_summary, content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Auth", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    assert len(result["children"][0]["summary"]) <= 200


def test_enrich_tree_nested_nodes():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [
        make_page("Auth", slug="auth", summary="Auth", content="x" * 60),
        make_page("OAuth", slug="oauth", summary="OAuth flow", content="x" * 60),
    ]
    tree = {
        "name": "KB",
        "children": [
            {"name": "Auth", "children": [
                {"name": "OAuth", "children": []}
            ]}
        ],
    }
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["page_slug"] == "auth"
    assert result["children"][0]["children"][0]["page_slug"] == "oauth"


def test_enrich_tree_prefers_longer_summary_on_ambiguous_match():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [
        make_page("API", slug="api-short", summary="Short", content="x" * 60),
        make_page("API", slug="api-long", summary="A much longer and more detailed summary about APIs", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "API", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["page_slug"] == "api-long"


def test_enrich_tree_preserves_existing_fields():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [make_page("Auth", slug="auth", summary="Auth", content="x" * 60)]
    tree = {"name": "KB", "children": [{"name": "Auth", "children": [], "custom": "value"}]}
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["custom"] == "value"
    assert result["children"][0]["page_slug"] == "auth"


def test_enrich_tree_page_type_propagation():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = [
        make_page("Users", slug="users", page_type="entity", summary="User model", content="x" * 60),
        make_page("Auth", slug="auth", page_type="concept", summary="Auth methods", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [
        {"name": "Users", "children": []},
        {"name": "Auth", "children": []},
    ]}
    result = _enrich_tree_nodes(tree, pages)
    assert result["children"][0]["page_type"] == "entity"
    assert result["children"][1]["page_type"] == "concept"


def test_enrich_tree_empty_children():
    from app.services.mindmap_service import _enrich_tree_nodes

    pages = []
    tree = {"name": "KB", "children": []}
    result = _enrich_tree_nodes(tree, pages)
    assert result == {"name": "KB", "children": []}


def test_enrich_tree_substring_match():
    """Substring match when one name contains the other and length ratio >= 50%."""
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("Authentication Methods", slug="auth-methods", summary="Auth methods guide", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    # "authentication" is a substring of "authentication methods", length ratio 14/24 = 0.58 >= 0.5
    assert result["children"][0]["page_slug"] == "auth-methods"


def test_enrich_tree_substring_rejected_when_too_short():
    """Short node name rejected by 50% length ratio guard."""
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("REST API Design Guide", slug="api-design", summary="API design patterns", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "API", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    # "api" length 3 vs "rest api design guide" length 20, ratio 3/20 = 0.15 < 0.5
    assert "page_slug" not in result["children"][0]


def test_enrich_tree_fuzzy_match_via_sequence_matcher():
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page("Authentication Service", slug="auth-svc", summary="Auth service docs", content="x" * 60),
    ]
    tree = {"name": "KB", "children": [{"name": "Authentication System", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    # "authentication system" vs "authentication service" — not substrings, but SequenceMatcher ratio ~0.79
    assert child["page_slug"] == "auth-svc"


def test_enrich_tree_matches_original_title_when_translated():
    """LLM generates English node names; pages have translated titles. Match via original title."""
    from app.services.mindmap_service import _enrich_tree_nodes
    pages = [
        make_page(
            "Highly Scalable Architecture",
            slug="concept/hsa",
            summary="Scalable patterns",
            content="x" * 60,
            title_translated="Kiến trúc có khả năng mở rộng cao",
        ),
    ]
    tree = {"name": "KB", "children": [{"name": "Highly Scalable Architecture", "children": []}]}
    result = _enrich_tree_nodes(tree, pages)
    child = result["children"][0]
    assert child["page_slug"] == "concept/hsa"
    assert child["page_type"] == "concept"
    assert child["summary"] == "Scalable patterns"


# --- Source document support tests ---


def make_source(title: str, full_text: str = "content " * 100, source_type: str = "file"):
    src = MagicMock()
    src.id = uuid.uuid4()
    src.title = title
    src.full_text = full_text
    src.source_type = source_type
    return src


def test_build_source_doc_payload_basic():
    from app.services.mindmap_service import _build_source_doc_payload
    sources = [make_source("Doc A", "Content A " * 100), make_source("Doc B", "Content B " * 100)]
    result = _build_source_doc_payload(sources)
    assert "Doc A" in result
    assert "Doc B" in result
    assert "Content A" in result


def test_build_source_doc_payload_truncates_large_text():
    from app.services.mindmap_service import _build_source_doc_payload
    sources = [make_source("Big Doc", "x" * 20000)]
    result = _build_source_doc_payload(sources)
    assert len(result) < 10000


def test_enrich_tree_nodes_from_sources():
    from app.services.mindmap_service import _enrich_tree_nodes_from_sources
    sources = [make_source("Architecture Guide", "arch content")]
    tree = {"name": "KB", "children": [{"name": "Architecture Guide", "children": []}]}
    result = _enrich_tree_nodes_from_sources(tree, sources)
    child = result["children"][0]
    assert child["page_slug"].startswith("source:")
    assert child["page_type"] == "document"


# --- LLM summary generation tests ---


def test_collect_unmatched_nodes():
    from app.services.mindmap_service import _collect_unmatched_nodes
    tree = {
        "name": "KB",
        "children": [
            {"name": "Auth", "page_slug": "auth", "children": []},
            {"name": "Unmatched Topic", "children": []},
            {"name": "Another", "summary": "has summary", "children": []},
        ],
    }
    result = _collect_unmatched_nodes(tree)
    assert "Unmatched Topic" in result
    assert "Auth" not in result
    assert "Another" not in result


def test_apply_summaries():
    from app.services.mindmap_service import _apply_summaries
    tree = {
        "name": "KB",
        "children": [
            {"name": "Auth", "children": []},
            {"name": "Topic B", "children": []},
        ],
    }
    summaries = {"Topic B": "This is about topic B"}
    result = _apply_summaries(tree, summaries)
    assert result["children"][1]["summary"] == "This is about topic B"
    assert "summary" not in result["children"][0]


@pytest.mark.asyncio
async def test_generate_node_summaries_batches():
    from app.services.mindmap_service import _generate_node_summaries
    nodes = [f"Node {i}" for i in range(20)]
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=json.dumps([
        {"name": f"Node {i}", "summary": f"Summary {i}"} for i in range(15)
    ]))
    result = await _generate_node_summaries(nodes[:15], mock_llm)
    assert len(result) == 15
    assert result["Node 0"] == "Summary 0"
