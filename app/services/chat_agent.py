"""Chat Agent — agentic loop with LiteLLM tool calling + Vercel AI SDK SSE streaming."""

import json
import uuid
from typing import Any, AsyncGenerator, Optional

import litellm
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_protocol import ToolCall, neutral_to_openai_messages, tool_results_message
from app.ai.registry import ProviderRegistry
from app.database.models import Employee

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

CHAT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "Semantic search over wiki pages in the user's accessible scope. Use this first to answer any question about the organization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "top_k": {"type": "integer", "description": "Max results (default 10, max 50)", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_wiki_page",
            "description": "Read a specific wiki page by slug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Page slug, e.g. 'hr/leave-policy'"},
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_wiki_index",
            "description": "Read the wiki catalog listing every page by type with summaries.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_wiki_pages",
            "description": "Browse wiki pages with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_type": {"type": "string", "description": "entity | concept | topic | source"},
                    "knowledge_type": {"type": "string", "description": "KnowledgeType slug"},
                    "limit": {"type": "integer", "default": 50},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sources",
            "description": "List raw source documents accessible to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "default": "ready"},
                    "knowledge_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_source",
            "description": "Metadata for a raw source document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "Source UUID"},
                },
                "required": ["source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_source_outline",
            "description": "Heading-based outline (table of contents) of a raw source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "Source UUID"},
                },
                "required": ["source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_source_pages",
            "description": "Read raw text of specific pages from a source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "Source UUID"},
                    "pages": {"type": "string", "description": "Page range e.g. '5-7', '3,8', '12'"},
                },
                "required": ["source_id", "pages"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_knowledge_types",
            "description": "List knowledge type categories accessible to the user.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_knowledge_type_docs",
            "description": "List documents in a specific knowledge type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_type_slug": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["knowledge_type_slug"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Scope resolution (mirrors MCP identity)
# ---------------------------------------------------------------------------

async def _get_scope(
    db: AsyncSession, employee: Employee
) -> dict:
    """Build scope dict from employee for tool filtering."""
    dept_id = str(employee.department_id) if employee.department_id else None

    from sqlalchemy import select as sa_select
    from app.database.models import ProjectMember
    stmt = sa_select(ProjectMember.project_id).where(
        ProjectMember.employee_id == employee.id
    )
    result = await db.execute(stmt)
    project_ids = [str(r[0]) for r in result.all()]

    allowed_kt: list[str] | None = None
    if employee.custom_role_id:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select as sa_select2
        from app.database.models import Employee as Emp
        emp = (await db.execute(
            sa_select2(Emp)
            .where(Emp.id == employee.id)
            .options(selectinload(Emp.custom_role))
        )).scalar_one_or_none()
        if emp and emp.custom_role and emp.custom_role.allowed_knowledge_types:
            allowed_kt = emp.custom_role.allowed_knowledge_types

    return {
        "is_admin": employee.role == "admin",
        "department_id": dept_id,
        "project_ids": project_ids,
        "allowed_knowledge_types": allowed_kt,
        "employee_id": str(employee.id),
        "allowed_source_ids": None,
    }


def _make_identity(scope: dict):
    """Build a minimal identity-like object for apply_scope_filter."""
    import uuid as _uuid

    class _Identity:
        is_admin = scope["is_admin"]
        department_id = _uuid.UUID(scope["department_id"]) if scope["department_id"] else None
        project_ids = scope["project_ids"]
        allowed_knowledge_types = scope["allowed_knowledge_types"]
        allowed_source_ids = scope["allowed_source_ids"]

    return _Identity()


# ---------------------------------------------------------------------------
# Tool executor — calls existing wiki/source service functions directly
# ---------------------------------------------------------------------------

async def execute_tool(
    tool_name: str,
    args: dict,
    employee: Any,
    db: AsyncSession,
) -> str:
    """Execute a Tier 1 KB tool and return its string result."""
    import uuid as _uuid
    from app.services import wiki_service
    from app.services.mcp_auth_service import apply_scope_filter

    if employee is None:
        return f"[error: no employee context for tool {tool_name}]"

    scope = await _get_scope(db, employee)
    dept_uuid = _uuid.UUID(scope["department_id"]) if scope["department_id"] else None
    proj_uuids = [_uuid.UUID(p) for p in scope["project_ids"]]
    allowed_kt = scope["allowed_knowledge_types"]
    is_admin = scope["is_admin"]

    try:
        if tool_name == "search_wiki":
            registry = ProviderRegistry(db)
            embedding_provider = await registry.get_embedding(task="search_query")
            query_embedding = await embedding_provider.embed(args["query"])
            top_k = min(max(1, args.get("top_k", 10)), 50)
            hits = await wiki_service.search_pages_semantic(
                db,
                query_embedding=query_embedding,
                top_k=top_k,
                allowed_kt_slugs=allowed_kt,
                department_id=dept_uuid,
                project_ids=proj_uuids or None,
                all_scopes=is_admin,
            )
            if not hits:
                return f'No wiki pages found for: "{args["query"]}"'
            lines = [f'Wiki search — {len(hits)} result(s) for: "{args["query"]}"\n']
            for page, sim in hits:
                lines.append(f"- `{page.slug}` ({page.page_type}) — {sim:.0%} — **{page.title}**")
            lines.append("\n_Use read_wiki_page(slug) to read the full page._")
            return "\n".join(lines)

        elif tool_name == "read_wiki_page":
            slug = args["slug"]
            page = await wiki_service.get_page_by_slug(db, slug, allowed_kt_slugs=allowed_kt)
            if not page and dept_uuid:
                page = await wiki_service.get_page_by_slug(
                    db, slug, allowed_kt_slugs=allowed_kt,
                    scope_type="department", scope_id=dept_uuid,
                )
            if not page and proj_uuids:
                for pid in proj_uuids:
                    page = await wiki_service.get_page_by_slug(
                        db, slug, allowed_kt_slugs=allowed_kt,
                        scope_type="project", scope_id=pid,
                    )
                    if page:
                        break
            if not page:
                return f"Wiki page not found or out of scope: `{slug}`"
            backlinks = await wiki_service.get_backlinks(db, slug, page.scope_type, page.scope_id)
            body = page.content_md or ""
            if backlinks:
                body = body.rstrip() + "\n\n## Backlinks\n" + "\n".join(f"- `{s}`" for s in sorted(backlinks))
            return body

        elif tool_name == "read_wiki_index":
            page = await wiki_service.get_page_by_slug(db, wiki_service.INDEX_SLUG)
            return page.content_md if page else "_(wiki index not initialized yet)_"

        elif tool_name == "list_wiki_pages":
            pages = await wiki_service.list_pages(
                db,
                page_type=args.get("page_type"),
                knowledge_type_slug=args.get("knowledge_type"),
                allowed_kt_slugs=allowed_kt,
                limit=args.get("limit", 50),
                offset=args.get("offset", 0),
                department_id=dept_uuid,
                project_ids=proj_uuids or None,
                all_scopes=is_admin,
            )
            if not pages:
                return "No wiki pages match the filters."
            lines = [f"**Wiki pages — {len(pages)} result(s)**\n"]
            for p in pages:
                lines.append(f"- `{p.slug}` ({p.page_type}) — **{p.title}**")
            return "\n".join(lines)

        elif tool_name == "list_sources":
            from sqlalchemy import select as sa_select
            from app.database.models import KnowledgeType, Source
            stmt = (
                sa_select(Source)
                .order_by(Source.created_at.desc())
            )
            if args.get("status", "ready") != "all":
                stmt = stmt.where(Source.status == args.get("status", "ready"))
            if args.get("knowledge_type"):
                kt_id = (await db.execute(
                    sa_select(KnowledgeType.id).where(KnowledgeType.slug == args["knowledge_type"])
                )).scalar()
                if kt_id:
                    stmt = stmt.where(Source.knowledge_type_id == kt_id)
            stmt = apply_scope_filter(stmt, _make_identity(scope)).limit(args.get("limit", 20)).offset(args.get("offset", 0))
            sources = (await db.execute(stmt)).scalars().all()
            if not sources:
                return "No documents found."
            lines = [f"**{len(sources)} document(s)**\n"]
            for s in sources:
                lines.append(f"- **{s.title or s.file_name or 'Untitled'}** (ID: `{s.id}`)")
            return "\n".join(lines)

        elif tool_name == "get_source":
            from sqlalchemy import select as sa_select
            from sqlalchemy.orm import selectinload
            from app.database.models import Source
            try:
                sid = _uuid.UUID(args["source_id"])
            except ValueError:
                return f"Invalid source ID: {args['source_id']}"
            source = (await db.execute(
                sa_select(Source).where(Source.id == sid)
                .options(selectinload(Source.knowledge_type), selectinload(Source.contributor))
            )).scalar_one_or_none()
            if not source:
                return f"Source not found: {args['source_id']}"
            kt_label = source.knowledge_type.name if source.knowledge_type else "Uncategorized"
            return f"# {source.title or source.file_name or 'Untitled'}\n- **ID:** `{source.id}`\n- **Knowledge type:** {kt_label}\n- **Status:** {source.status}"

        elif tool_name == "get_source_outline":
            from sqlalchemy import select as sa_select
            from app.database.models import Source
            try:
                sid = _uuid.UUID(args["source_id"])
            except ValueError:
                return f"Invalid source ID: {args['source_id']}"
            source = await db.get(Source, sid)
            if not source:
                return f"Source not found: {args['source_id']}"
            outline = source.outline_json or []
            if not outline:
                return "_(no outline)_"
            lines = ["# Outline\n"]
            def _walk(nodes: list[dict]):
                for n in nodes:
                    indent = "  " * max(0, n.get("level", 1) - 1)
                    page = n.get("page")
                    lines.append(f"{indent}- {n.get('title', '')}" + (f" (page {page})" if page else ""))
                    if n.get("children"):
                        _walk(n["children"])
            _walk(outline)
            return "\n".join(lines)

        elif tool_name == "get_source_pages":
            from app.database.models import Source
            from app.services.source_outline import parse_page_range, slice_pages_by_range
            try:
                sid = _uuid.UUID(args["source_id"])
            except ValueError:
                return f"Invalid source ID: {args['source_id']}"
            source = await db.get(Source, sid)
            if not source:
                return f"Source not found: {args['source_id']}"
            page_nums = parse_page_range(args["pages"])
            if not page_nums:
                return f"Invalid page range: {args['pages']!r}"
            slices = slice_pages_by_range(source.full_text or "", source.page_offsets or [], page_nums)
            if not slices:
                return f"No content for pages: {page_nums}"
            return "\n\n".join(f"--- page {s['page']} ---\n{s['content']}" for s in slices)

        elif tool_name == "list_knowledge_types":
            from sqlalchemy import func as sqfunc, select as sa_select
            from app.database.models import KnowledgeType, Source
            rows = (await db.execute(
                sa_select(KnowledgeType, sqfunc.count(Source.id).label("doc_count"))
                .outerjoin(Source, (Source.knowledge_type_id == KnowledgeType.id) & (Source.status == "ready"))
                .group_by(KnowledgeType.id)
                .order_by(KnowledgeType.sort_order, KnowledgeType.name)
            )).all()
            if not rows:
                return "No knowledge types defined."
            lines = ["**Knowledge Types**\n"]
            for kt, doc_count in rows:
                if allowed_kt and kt.slug not in allowed_kt:
                    continue
                lines.append(f"- **{kt.name}** (slug: `{kt.slug}`, {doc_count} doc(s))")
            return "\n".join(lines) if len(lines) > 1 else "No accessible knowledge types."

        elif tool_name == "get_knowledge_type_docs":
            from sqlalchemy import select as sa_select
            from app.database.models import KnowledgeType, Source
            kt = (await db.execute(
                sa_select(KnowledgeType).where(KnowledgeType.slug == args["knowledge_type_slug"])
            )).scalar_one_or_none()
            if not kt:
                return f"Knowledge type '{args['knowledge_type_slug']}' not found."
            stmt = (
                sa_select(Source)
                .where(Source.knowledge_type_id == kt.id, Source.status == "ready")
                .order_by(Source.created_at.desc())
            )
            stmt = apply_scope_filter(stmt, _make_identity(scope)).limit(args.get("limit", 10))
            sources = (await db.execute(stmt)).scalars().all()
            if not sources:
                return f"No documents for **{kt.name}**"
            lines = [f"**{kt.name}** — {len(sources)} document(s)\n"]
            for s in sources:
                lines.append(f"- **{s.title or s.file_name or 'Untitled'}** (ID: `{s.id}`)")
            return "\n".join(lines)

        else:
            return f"[error: unknown tool '{tool_name}']"

    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return f"[tool error: {e}]"


# ---------------------------------------------------------------------------
# Vercel AI SDK data stream protocol encoder
# ---------------------------------------------------------------------------

def _sse_text(token: str) -> str:
    return f"0:{json.dumps(token)}\n"


def _sse_tool_call(tool_call_id: str, tool_name: str, args: dict) -> str:
    return f"9:{json.dumps({'toolCallId': tool_call_id, 'toolName': tool_name, 'args': args})}\n"


def _sse_tool_result(tool_call_id: str, result: str) -> str:
    return f"a:{json.dumps({'toolCallId': tool_call_id, 'result': result})}\n"


def _sse_finish_step(finish_reason: str = "tool-calls", is_continued: bool = False) -> str:
    return f"e:{json.dumps({'finishReason': finish_reason, 'isContinued': is_continued})}\n"


def _sse_finish(finish_reason: str = "stop") -> str:
    return f"d:{json.dumps({'finishReason': finish_reason})}\n"


def _sse_error(message: str) -> str:
    return f"3:{json.dumps(message)}\n"


# ---------------------------------------------------------------------------
# Streaming agentic loop
# ---------------------------------------------------------------------------

def _build_system_prompt(
    scope: dict,
    attachments: list[dict],
) -> str:
    lines = [
        "You are a helpful knowledge base assistant for this organization.",
        "Answer questions by searching and reading the knowledge base.",
        "When citing wiki pages or sources, format citations inline as: label【slug】",
        "Examples: GIM【entity/gim】, the MAU spec【source/gim-mau-spec-150426-083136】",
        "Always use this exact 【】 bracket style — never bare slugs or Markdown links.",
        "For source citations use source/{id} as the slug and the source title as the label.",
        "When including math formulas, wrap them in a ```math code block (never bare LaTeX or $$).",
        "Your answers are scoped to the user's department and workspace access only.",
    ]
    if attachments:
        lines.append("\nThe user has pinned the following context items — read these first:")
        for a in attachments:
            if a["type"] == "wiki":
                lines.append(f'- Wiki page: call read_wiki_page("{a["slug"]}")')
            elif a["type"] == "source":
                title = a.get("title") or a["id"]
                lines.append(f'- Source document (title: "{title}"): call get_source("{a["id"]}")')
                lines.append(f'  Cite it as: {title}【source/{a["id"]}】')
        lines.append("Only call search_wiki if these items don't fully answer the question.")
    return "\n".join(lines)


async def _enrich_source_attachments(db: AsyncSession, attachments: list[dict]) -> list[dict]:
    """Fetch titles for source attachments so the agent can use them in citation labels."""
    from sqlalchemy import select
    from app.database.models import Source

    enriched = []
    for a in attachments:
        if a["type"] == "source" and "title" not in a:
            try:
                sid = uuid.UUID(a["id"])
                row = (await db.execute(select(Source.title, Source.file_name).where(Source.id == sid))).first()
                if row:
                    a = {**a, "title": row.title or row.file_name or a["id"]}
            except Exception:
                pass
        enriched.append(a)
    return enriched


async def stream_agent_response(
    db: AsyncSession,
    employee: Employee,
    history: list[dict],
    user_message: str,
    attachments: list[dict],
    max_steps: int = 8,
) -> AsyncGenerator[str, None]:
    """
    Run the agentic loop and yield Vercel AI SDK data stream protocol lines.
    History is the existing session messages in neutral format (role/content dicts).
    """
    registry = ProviderRegistry(db)
    llm = await registry.get_llm()

    scope = await _get_scope(db, employee)
    attachments = await _enrich_source_attachments(db, attachments)
    system_prompt = _build_system_prompt(scope, attachments)

    messages: list[dict] = list(history)
    messages.append({"role": "user", "content": user_message})

    from app.ai.providers.litellm_provider import LiteLLMLLM, _resolve_model, _bifrost_extra_body
    assert isinstance(llm, LiteLLMLLM), "Chat agent requires a LiteLLMLLM provider"
    model = _resolve_model(llm.config.provider, llm.config.model_id)
    base_kwargs: dict = {
        "model": model,
        "api_key": llm.config.api_key or None,
        "base_url": llm.config.base_url or None,
        "temperature": 0.2,
        "stream": True,
        "tools": CHAT_TOOLS,
    }
    extra_body = _bifrost_extra_body(llm.config)
    if extra_body:
        base_kwargs["extra_body"] = extra_body

    step = 0
    while step < max_steps:
        step += 1

        formatted = [{"role": "system", "content": system_prompt}] + neutral_to_openai_messages(messages)

        try:
            response = await litellm.acompletion(messages=formatted, **base_kwargs)
        except Exception as e:
            yield _sse_error(f"LLM error: {e}")
            return

        accumulated_text = ""
        pending_calls: dict[int, dict] = {}
        finish_reason: str | None = None

        async for chunk in response:
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta.content:
                accumulated_text += delta.content
                yield _sse_text(delta.content)

            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in pending_calls:
                        pending_calls[idx] = {"id": tc_delta.id or str(uuid.uuid4()), "name": "", "arguments_str": ""}
                    if tc_delta.id:
                        pending_calls[idx]["id"] = tc_delta.id
                    if getattr(tc_delta, "function", None):
                        if tc_delta.function.name:
                            pending_calls[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            pending_calls[idx]["arguments_str"] += tc_delta.function.arguments

        if finish_reason == "tool_calls" and pending_calls:
            tool_call_objs = []
            for idx in sorted(pending_calls.keys()):
                tc = pending_calls[idx]
                try:
                    args = json.loads(tc["arguments_str"]) if tc["arguments_str"] else {}
                except json.JSONDecodeError:
                    args = {}
                tool_call_objs.append(ToolCall(id=tc["id"], name=tc["name"], arguments=args))

            messages.append({
                "role": "assistant",
                "content": accumulated_text or None,
                "tool_calls": tool_call_objs,
            })

            tool_results = []
            for tc_obj in tool_call_objs:
                yield _sse_tool_call(tc_obj.id, tc_obj.name, tc_obj.arguments)
                result = await execute_tool(tc_obj.name, tc_obj.arguments, employee, db)
                yield _sse_tool_result(tc_obj.id, result)
                tool_results.append((tc_obj.id, tc_obj.name, result))

            yield _sse_finish_step("tool-calls")
            messages.append(tool_results_message(tool_results))

        else:
            yield _sse_finish("stop")
            return

    yield _sse_finish("stop")
