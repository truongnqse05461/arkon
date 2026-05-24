"""
LiteLLM provider integration — unified interface for all AI models (LLM, Embedding, Vision).
Supports Google Gemini, OpenAI, Anthropic Claude, Ollama, etc. via LiteLLM SDK.
"""

import asyncio
import base64
import json
from typing import Optional
from loguru import logger
import litellm

from app.ai.agent_protocol import AssistantTurn, ToolCall, neutral_to_openai_messages
from app.ai.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    ProviderConfig,
    ProviderType,
    VisionProvider,
)

# LiteLLM model prefix per provider.
_PROVIDER_PREFIX: dict[ProviderType, str] = {
    ProviderType.GOOGLE: "gemini",
    ProviderType.OPENAI: "openai",
    ProviderType.CUSTOM_OPENAI: "openai",
    ProviderType.ANTHROPIC: "anthropic",
    ProviderType.CUSTOM_ANTHROPIC: "anthropic",
    ProviderType.OLLAMA: "ollama",
    ProviderType.VOYAGE: "voyage",
    ProviderType.COHERE: "cohere",
    ProviderType.BIFROST: "openai",
}

# Internal task names → Google Gemini task_type enum values passed to LiteLLM.
# LiteLLM forwards task_type to the underlying Google Generative AI SDK.
_GOOGLE_TASK_MAP: dict[str, str] = {
    "document":           "RETRIEVAL_DOCUMENT",
    "search_query":       "RETRIEVAL_QUERY",
    "question_answering": "QUESTION_ANSWERING",
    "classification":     "CLASSIFICATION",
    "clustering":         "CLUSTERING",
    "similarity":         "SEMANTIC_SIMILARITY",
}


def _resolve_model(provider: ProviderType, model_id: str) -> str:
    """Map the catalog provider + model_id to the string syntax expected by LiteLLM."""
    prefix = _PROVIDER_PREFIX.get(provider, provider.value)
    return f"{prefix}/{model_id}"


def _bifrost_extra_body(config: ProviderConfig) -> dict:
    """Return extra_body dict for Bifrost fallbacks, or empty dict."""
    if config.provider != ProviderType.BIFROST:
        return {}
    fallbacks = config.extra.get("fallbacks", [])
    if not fallbacks:
        return {}
    return {"fallbacks": fallbacks}


class LiteLLMEmbedding(EmbeddingProvider):
    """LiteLLM embedding provider."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    def _base_embed_kwargs(self) -> dict:
        kwargs: dict = {
            "model": _resolve_model(self.config.provider, self.config.model_id),
            "api_key": self.config.api_key or None,
            "api_base": self.config.base_url or None,
        }
        if self.config.provider == ProviderType.GOOGLE:
            task = self.config.extra.get("task", "document")
            litellm_task = _GOOGLE_TASK_MAP.get(task)
            if litellm_task:
                kwargs["task_type"] = litellm_task
        elif self.config.provider == ProviderType.OPENAI:
            # `dimensions` is only supported by OpenAI text-embedding-3-* models.
            # Custom/proxy endpoints (OpenRouter, Ollama, etc.) reject this param.
            if self.config.dimensions and self.config.model_id.startswith("text-embedding-3"):
                kwargs["dimensions"] = self.config.dimensions
        return kwargs

    async def embed(self, text: str) -> list[float]:
        kwargs = {**self._base_embed_kwargs(), "input": [text]}
        for attempt in range(3):
            try:
                response = await litellm.aembedding(**kwargs)
                item = response.data[0]
                return item.embedding if hasattr(item, "embedding") else item["embedding"]
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"LiteLLM embed attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def embed_batch(
        self, texts: list[str], concurrency: int = 5
    ) -> list[list[float]]:
        base_kwargs = self._base_embed_kwargs()
        batch_size = 100
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        sem = asyncio.Semaphore(concurrency)

        async def _embed_one_batch(batch: list[str]) -> list[list[float]]:
            async with sem:
                for attempt in range(3):
                    try:
                        response = await litellm.aembedding(input=batch, **base_kwargs)
                        return [
                            d.embedding if hasattr(d, "embedding") else d["embedding"]
                            for d in sorted(
                                response.data,
                                key=lambda x: x.index if hasattr(x, "index") else x["index"],
                            )
                        ]
                    except Exception as e:
                        if attempt < 2:
                            logger.warning(
                                f"LiteLLM batch embed attempt {attempt + 1} failed: {e}"
                            )
                            await asyncio.sleep(2 ** attempt)
                        else:
                            raise
            return []  # unreachable — satisfies type checkers

        batch_results = await asyncio.gather(*[_embed_one_batch(b) for b in batches])
        all_embeddings: list[list[float]] = []
        for result in batch_results:
            all_embeddings.extend(result)
        logger.debug(
            f"LiteLLM: embedded {len(texts)} texts across {len(batches)} concurrent batches"
        )
        return all_embeddings

    async def test_connection(self) -> tuple[bool, str]:
        try:
            result = await self.embed("test connection")
            dim = len(result)
            return True, f"OK — model={self.config.model_id}, dimensions={dim}"
        except Exception as e:
            return False, f"LiteLLM embedding error: {e}"

    def with_task(self, task: str) -> "LiteLLMEmbedding":
        """Return a copy with a different task type for query vs document."""
        new_config = ProviderConfig(
            provider=self.config.provider,
            api_key=self.config.api_key,
            model_id=self.config.model_id,
            base_url=self.config.base_url,
            dimensions=self.config.dimensions,
            extra={**self.config.extra, "task": task},
        )
        return LiteLLMEmbedding(new_config)


class LiteLLMLLM(LLMProvider):
    """LiteLLM LLM provider."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": _resolve_model(self.config.provider, self.config.model_id),
            "messages": messages,
            "temperature": temperature,
            "api_key": self.config.api_key or None,
            "base_url": self.config.base_url or None,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        extra_body = _bifrost_extra_body(self.config)
        if extra_body:
            kwargs["extra_body"] = extra_body

        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
    ) -> AssistantTurn:
        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})
        formatted_messages.extend(neutral_to_openai_messages(messages))

        kwargs = {
            "model": _resolve_model(self.config.provider, self.config.model_id),
            "messages": formatted_messages,
            "tools": tools,
            "temperature": temperature,
            "api_key": self.config.api_key or None,
            "base_url": self.config.base_url or None,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        extra_body = _bifrost_extra_body(self.config)
        if extra_body:
            kwargs["extra_body"] = extra_body

        response = await litellm.acompletion(**kwargs)
        choice = response.choices[0]
        message = choice.message
        text = message.content

        tool_calls: list[ToolCall] = []
        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                args = {}
                if tc.function.arguments:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        pass
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        reason_map = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens"}
        finish_reason = reason_map.get(choice.finish_reason or "stop", "end_turn")

        return AssistantTurn(
            text=text or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

    async def test_connection(self) -> tuple[bool, str]:
        try:
            result = await self.generate("Say 'OK'", max_tokens=10, temperature=0)
            return True, f"OK — model={self.config.model_id}, response='{result[:50]}'"
        except Exception as e:
            return False, f"LiteLLM LLM error: {e}"


class LiteLLMVision(VisionProvider):
    """LiteLLM Vision provider."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    async def analyze_image(
        self,
        image_data: bytes,
        mime_type: str = "image/jpeg",
        prompt: Optional[str] = None,
        timeout: int = 90,
    ) -> str:
        if not prompt:
            prompt = (
                "Describe this image in detail. "
                "If it's a diagram, flowchart, or table, explain the meaning and steps. "
                "If it's a regular image, provide a concise description."
            )

        b64_image = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_image}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

        for attempt in range(3):
            try:
                call_kwargs = {
                    "model": _resolve_model(self.config.provider, self.config.model_id),
                    "messages": messages,
                    "temperature": 0.2,
                    "api_key": self.config.api_key or None,
                    "base_url": self.config.base_url or None,
                    "timeout": timeout,
                }
                extra_body = _bifrost_extra_body(self.config)
                if extra_body:
                    call_kwargs["extra_body"] = extra_body
                response = await litellm.acompletion(**call_kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning(f"LiteLLM Vision attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def test_connection(self) -> tuple[bool, str]:
        try:
            # Quick test with a tiny 1x1 PNG
            tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
                b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
                b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            await self.analyze_image(tiny_png, "image/png", "What is this?")
            return True, f"OK — model={self.config.model_id}"
        except Exception as e:
            return False, f"LiteLLM Vision error: {e}"
