"""
Provider-agnostic types for multi-turn LLM agent loops with tool calling.

Used by wiki_agent.py to drive agent loops without importing any provider SDK.
Providers convert between these neutral types and their native API formats.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    id: str        # provider-assigned id, echoed back in tool result
    name: str
    arguments: dict


@dataclass
class AssistantTurn:
    text: Optional[str]                        # narration text (may be None)
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "end_turn"            # "tool_use" | "end_turn" | "max_tokens"
    # Provider-specific raw content for replay (e.g. Gemini Content with thought_signature).
    # Stored in the neutral message as "_raw_content" and used by the originating provider
    # to avoid reconstructing content that may lose internal metadata.
    raw_provider_content: Any = field(default=None)


# ---------------------------------------------------------------------------
# Neutral message builders — used by the agent loop
# ---------------------------------------------------------------------------

def assistant_message_from_turn(turn: AssistantTurn) -> dict:
    """Build neutral assistant message dict to append to message history."""
    msg: dict = {
        "role": "assistant",
        "content": turn.text,
        "tool_calls": turn.tool_calls,
    }
    if turn.raw_provider_content is not None:
        msg["_raw_content"] = turn.raw_provider_content
    return msg


def tool_results_message(results: list[tuple[str, str, Any]]) -> dict:
    """
    Build neutral tool-results message from (call_id, call_name, result) tuples.
    Result is JSON-serialized if not already a string.
    """
    return {
        "role": "user",
        "tool_results": [
            {
                "id": cid,
                "name": cname,
                "content": (
                    json.dumps(r, ensure_ascii=False, default=str)
                    if not isinstance(r, str) else r
                ),
            }
            for cid, cname, r in results
        ],
    }


# ---------------------------------------------------------------------------
# Neutral → provider-specific message converters (used inside providers)
# ---------------------------------------------------------------------------

def neutral_to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Convert neutral messages to Anthropic API format."""
    result = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            if "tool_results" in msg:
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r["id"],
                            "content": r["content"],
                        }
                        for r in msg["tool_results"]
                    ],
                })
            else:
                result.append({"role": "user", "content": msg.get("content") or ""})
        elif role == "assistant":
            blocks: list[dict] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls", []):
                blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            result.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
    return result


def neutral_to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert neutral messages to OpenAI API format."""
    result = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            if "tool_results" in msg:
                for r in msg["tool_results"]:
                    result.append({
                        "role": "tool",
                        "tool_call_id": r["id"],
                        "content": r["content"],
                    })
            else:
                result.append({"role": "user", "content": msg.get("content") or ""})
        elif role == "assistant":
            m: dict = {"role": "assistant", "content": msg.get("content")}
            if msg.get("tool_calls"):
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg["tool_calls"]
                ]
            result.append(m)
    return result



