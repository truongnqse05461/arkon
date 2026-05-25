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
