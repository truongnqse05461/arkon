# Bifrost Gateway Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bifrost Gateway as a first-class LLM + Vision provider with dynamic fallback model routing, exposed in the Settings UI as a distinct option from `custom_openai` and `custom_anthropic`.

**Architecture:** `ProviderType.BIFROST` routes through LiteLLM's OpenAI-compatible path with a custom `api_base`, injecting a `fallbacks` array into the raw request body via LiteLLM's `extra_body` kwarg. Bifrost config uses provider-scoped keys (`llm_bifrost_*`, `vision_bifrost_*`) to avoid clobbering existing custom provider settings. The Settings UI extends `ModelCatalogCard` with a new `BifrostExtraFields` child component that renders base URL, primary model, and a dynamic add/remove fallback rows list.

**Tech Stack:** Python (FastAPI, LiteLLM, SQLAlchemy async), TypeScript/React (Next.js), pytest + pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/ai/providers/base.py` | Modify | Add `BIFROST = "bifrost"` to `ProviderType` enum |
| `app/ai/llm_catalog.py` | Modify | Add `"custom/bifrost"` to `LLM_CATALOG` |
| `app/ai/vision_catalog.py` | Modify | Add `"custom/bifrost"` to `VISION_CATALOG` |
| `app/services/config_service.py` | Modify | Add 8 new Bifrost config keys to `ALL_CONFIG_KEYS` |
| `app/ai/registry.py` | Modify | Bifrost-specific loading in `_load_llm_config()` and `_load_vision_config()` |
| `app/ai/providers/litellm_provider.py` | Modify | Add Bifrost prefix; inject `extra_body` fallbacks in all three provider classes |
| `app/routers/admin_settings.py` | Modify | Bifrost validation in `update_settings()` for LLM and Vision |
| `tests/test_custom_registry.py` | Modify | Add Bifrost registry resolution tests |
| `tests/test_bifrost_catalog.py` | Create | Catalog + config key smoke tests |
| `frontend/src/components/settings/bifrost-extra-fields.tsx` | Create | Controlled component: base URL, model ID, dynamic fallback rows |
| `frontend/src/components/settings/model-catalog-card.tsx` | Modify | Bifrost state, detection, load/save, render `<BifrostExtraFields>` |

---

## Task 1: Add `ProviderType.BIFROST` to the enum

**Files:**
- Modify: `app/ai/providers/base.py:21-29`

- [ ] **Write the failing test**

Create `tests/test_bifrost_catalog.py`:

```python
"""Smoke tests for Bifrost catalog entries and config keys."""

from app.ai.providers.base import ProviderType


def test_bifrost_provider_type_exists():
    assert ProviderType.BIFROST == "bifrost"
```

- [ ] **Run to confirm it fails**

```bash
pytest tests/test_bifrost_catalog.py::test_bifrost_provider_type_exists -v
```

Expected: `AttributeError: 'ProviderType' has no attribute 'BIFROST'`

- [ ] **Implement: add `BIFROST` to `ProviderType`**

In `app/ai/providers/base.py`, find the `ProviderType` class (lines 21-29) and add one line:

```python
class ProviderType(str, Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    VOYAGE = "voyage"
    COHERE = "cohere"
    CUSTOM_OPENAI = "custom_openai"
    CUSTOM_ANTHROPIC = "custom_anthropic"
    BIFROST = "bifrost"
```

- [ ] **Run to confirm it passes**

```bash
pytest tests/test_bifrost_catalog.py::test_bifrost_provider_type_exists -v
```

Expected: `PASSED`

- [ ] **Commit**

```bash
git add app/ai/providers/base.py tests/test_bifrost_catalog.py
git commit -m "feat(bifrost): add BIFROST to ProviderType enum"
```

---

## Task 2: Add `custom/bifrost` to LLM and Vision catalogs

**Files:**
- Modify: `app/ai/llm_catalog.py:179-205` (after the existing custom entries)
- Modify: `app/ai/vision_catalog.py:78-98` (after the existing custom entries)
- Modify: `tests/test_bifrost_catalog.py`

- [ ] **Write the failing tests** (append to `tests/test_bifrost_catalog.py`)

```python
from app.ai.llm_catalog import LLM_CATALOG, get_spec as get_llm_spec
from app.ai.vision_catalog import VISION_CATALOG, get_spec as get_vision_spec


def test_bifrost_in_llm_catalog():
    assert "custom/bifrost" in LLM_CATALOG
    spec = LLM_CATALOG["custom/bifrost"]
    assert spec.provider == "bifrost"
    assert spec.supports_tools is True
    assert spec.supports_vision is True


def test_bifrost_in_vision_catalog():
    assert "custom/bifrost" in VISION_CATALOG
    spec = VISION_CATALOG["custom/bifrost"]
    assert spec.provider == "bifrost"


def test_get_llm_spec_bifrost():
    spec = get_llm_spec("custom/bifrost")
    assert spec.id == "custom/bifrost"


def test_get_vision_spec_bifrost():
    spec = get_vision_spec("custom/bifrost")
    assert spec.id == "custom/bifrost"
```

- [ ] **Run to confirm they fail**

```bash
pytest tests/test_bifrost_catalog.py -v -k "catalog"
```

Expected: `FAILED` — `"custom/bifrost" not in LLM_CATALOG`

- [ ] **Implement: add to `LLM_CATALOG`**

In `app/ai/llm_catalog.py`, after the `"custom/anthropic"` entry (around line 205), add:

```python
    "custom/bifrost": LLMModelSpec(
        id="custom/bifrost",
        provider="bifrost",
        model_id="custom",
        context_window_tokens=128_000,
        max_output_tokens=4_096,
        supports_tools=True,
        supports_vision=True,
        label="Bifrost Gateway",
        cost_per_1m_input_tokens=None,
        cost_per_1m_output_tokens=None,
        notes="OpenAI-compatible AI gateway with fallback routing. Configure base URL, Virtual Key, primary model, and optional fallbacks below.",
    ),
```

- [ ] **Implement: add to `VISION_CATALOG`**

In `app/ai/vision_catalog.py`, after the `"custom/anthropic"` vision entry (around line 98), add:

```python
    "custom/bifrost": VisionModelSpec(
        id="custom/bifrost",
        provider="bifrost",
        model_id="custom",
        max_image_size_mb=20,
        label="Bifrost Gateway Vision",
        cost_per_1m_input_tokens=None,
        cost_per_image=None,
        notes="OpenAI-compatible AI gateway with fallback routing. Configure base URL, Virtual Key, primary model, and optional fallbacks below.",
    ),
```

- [ ] **Run to confirm tests pass**

```bash
pytest tests/test_bifrost_catalog.py -v
```

Expected: all `PASSED`

- [ ] **Commit**

```bash
git add app/ai/llm_catalog.py app/ai/vision_catalog.py tests/test_bifrost_catalog.py
git commit -m "feat(bifrost): add custom/bifrost to LLM and Vision catalogs"
```

---

## Task 3: Add Bifrost config keys to `ALL_CONFIG_KEYS`

**Files:**
- Modify: `app/services/config_service.py:68-112`
- Modify: `tests/test_bifrost_catalog.py`

- [ ] **Write the failing tests** (append to `tests/test_bifrost_catalog.py`)

```python
from app.services.config_service import ALL_CONFIG_KEYS, _is_sensitive


def test_bifrost_llm_keys_in_all_config_keys():
    for key in [
        "llm_api_key__bifrost",
        "llm_bifrost_base_url",
        "llm_bifrost_model_id",
        "llm_bifrost_fallbacks",
    ]:
        assert key in ALL_CONFIG_KEYS, f"{key!r} missing from ALL_CONFIG_KEYS"


def test_bifrost_vision_keys_in_all_config_keys():
    for key in [
        "vision_api_key__bifrost",
        "vision_bifrost_base_url",
        "vision_bifrost_model_id",
        "vision_bifrost_fallbacks",
    ]:
        assert key in ALL_CONFIG_KEYS, f"{key!r} missing from ALL_CONFIG_KEYS"


def test_bifrost_api_keys_are_sensitive():
    assert _is_sensitive("llm_api_key__bifrost")
    assert _is_sensitive("vision_api_key__bifrost")


def test_bifrost_non_key_fields_are_not_sensitive():
    assert not _is_sensitive("llm_bifrost_base_url")
    assert not _is_sensitive("llm_bifrost_model_id")
    assert not _is_sensitive("llm_bifrost_fallbacks")
```

- [ ] **Run to confirm they fail**

```bash
pytest tests/test_bifrost_catalog.py -v -k "config_keys or sensitive"
```

Expected: `FAILED` — keys not in `ALL_CONFIG_KEYS`

- [ ] **Implement: add keys to `ALL_CONFIG_KEYS`**

In `app/services/config_service.py`, find `ALL_CONFIG_KEYS` (line 68). After `"llm_api_key__custom_anthropic"` and before `"llm_base_url"`, add the Bifrost LLM keys. After `"vision_api_key__custom_anthropic"` and before `"vision_base_url"`, add the Bifrost Vision keys:

```python
ALL_CONFIG_KEYS = [
    # --- Embedding ---
    ACTIVE_EMBEDDING_MODEL_KEY,
    "embedding_api_key__google",
    "embedding_api_key__openai",
    "embedding_api_key__custom_openai",
    "embedding_base_url",
    "embedding_custom_model_id",

    # --- LLM ---
    ACTIVE_LLM_MODEL_KEY,
    "llm_api_key__google",
    "llm_api_key__openai",
    "llm_api_key__anthropic",
    "llm_api_key__custom_openai",
    "llm_api_key__custom_anthropic",
    "llm_api_key__bifrost",          # NEW
    "llm_base_url",
    "llm_custom_model_id",
    "llm_bifrost_base_url",          # NEW
    "llm_bifrost_model_id",          # NEW
    "llm_bifrost_fallbacks",         # NEW

    # --- Vision ---
    ACTIVE_VISION_MODEL_KEY,
    "vision_api_key__google",
    "vision_api_key__openai",
    "vision_api_key__custom_openai",
    "vision_api_key__custom_anthropic",
    "vision_api_key__bifrost",       # NEW
    "vision_base_url",
    "vision_custom_model_id",
    "vision_bifrost_base_url",       # NEW
    "vision_bifrost_model_id",       # NEW
    "vision_bifrost_fallbacks",      # NEW

    # --- Deprecated single-key fallbacks ---
    "llm_api_key",
    "vision_api_key",
    "llm_provider",
    "llm_model_id",
    "vision_provider",
    "vision_model_id",

    # --- System ---
    "session_timeout_minutes",

    # --- Deprecated embedding keys ---
    "embedding_provider",
    "embedding_model_id",
    "embedding_api_key",
    "embedding_dimensions",
]
```

- [ ] **Run to confirm tests pass**

```bash
pytest tests/test_bifrost_catalog.py -v
```

Expected: all `PASSED`

- [ ] **Commit**

```bash
git add app/services/config_service.py tests/test_bifrost_catalog.py
git commit -m "feat(bifrost): add Bifrost config keys to ALL_CONFIG_KEYS"
```

---

## Task 4: Update registry to load Bifrost-specific config

**Files:**
- Modify: `app/ai/registry.py:239-309` (`_load_llm_config` and `_load_vision_config`)
- Modify: `tests/test_custom_registry.py`

- [ ] **Write the failing tests** (append to `tests/test_custom_registry.py`)

```python
@pytest.mark.asyncio
async def test_bifrost_llm_resolution():
    """Registry loads Bifrost-scoped keys and parses fallbacks JSON."""
    db = AsyncMock()

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                "active_llm_model_spec_id": "custom/bifrost",
                "llm_api_key__bifrost": "bfk-virtual-key",
                "llm_bifrost_base_url": "https://bifrost.myco.com",
                "llm_bifrost_model_id": "gpt-4o-mini",
                "llm_bifrost_fallbacks": '["anthropic/claude-3-5-sonnet","bedrock/claude-3"]',
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()

        assert llm.config.provider == ProviderType.BIFROST
        assert llm.config.model_id == "gpt-4o-mini"
        assert llm.config.base_url == "https://bifrost.myco.com"
        assert llm.config.api_key == "bfk-virtual-key"
        assert llm.config.extra["fallbacks"] == [
            "anthropic/claude-3-5-sonnet",
            "bedrock/claude-3",
        ]


@pytest.mark.asyncio
async def test_bifrost_llm_empty_fallbacks():
    """Registry handles missing fallbacks key gracefully (returns empty list)."""
    db = AsyncMock()

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                "active_llm_model_spec_id": "custom/bifrost",
                "llm_api_key__bifrost": "bfk-key",
                "llm_bifrost_base_url": "https://bifrost.myco.com",
                "llm_bifrost_model_id": "openai/gpt-4o",
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()

        assert llm.config.extra["fallbacks"] == []


@pytest.mark.asyncio
async def test_bifrost_vision_resolution():
    """Registry loads Bifrost vision-scoped keys."""
    db = AsyncMock()
    from app.services.config_service import ACTIVE_VISION_MODEL_KEY

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                ACTIVE_VISION_MODEL_KEY: "custom/bifrost",
                "vision_api_key__bifrost": "bfk-vis-key",
                "vision_bifrost_base_url": "https://bifrost.myco.com",
                "vision_bifrost_model_id": "gpt-4o",
                "vision_bifrost_fallbacks": '["anthropic/claude-3-5-sonnet"]',
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        vis = await registry.get_vision()

        assert vis is not None
        assert vis.config.provider == ProviderType.BIFROST
        assert vis.config.model_id == "gpt-4o"
        assert vis.config.base_url == "https://bifrost.myco.com"
        assert vis.config.extra["fallbacks"] == ["anthropic/claude-3-5-sonnet"]


@pytest.mark.asyncio
async def test_custom_openai_unaffected_by_bifrost():
    """custom/openai still loads from llm_base_url / llm_custom_model_id."""
    db = AsyncMock()

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                "active_llm_model_spec_id": "custom/openai",
                "llm_api_key__custom_openai": "sk-openai",
                "llm_base_url": "http://localhost:8080/v1",
                "llm_custom_model_id": "llama-3-8b",
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()

        assert llm.config.provider == ProviderType.CUSTOM_OPENAI
        assert llm.config.base_url == "http://localhost:8080/v1"
        assert llm.config.model_id == "llama-3-8b"
        assert llm.config.extra.get("fallbacks") is None
```

- [ ] **Run to confirm they fail**

```bash
pytest tests/test_custom_registry.py -v -k "bifrost"
```

Expected: `FAILED` — `BIFROST` not resolved, or `extra["fallbacks"]` missing

- [ ] **Implement: update `_load_llm_config()`**

In `app/ai/registry.py`, add `import json` at the top of the file (after existing imports). Then replace lines 262–274 (the custom branch in `_load_llm_config`) with:

```python
        if spec_id == "custom/bifrost":
            base_url = await svc.get("llm_bifrost_base_url")
            model_id = await svc.get("llm_bifrost_model_id") or "custom"
            fallbacks_raw = await svc.get("llm_bifrost_fallbacks")
            fallbacks = json.loads(fallbacks_raw) if fallbacks_raw else []
            extra = {"spec_id": spec.id, "fallbacks": fallbacks}
        elif spec_id.startswith("custom/"):
            base_url = await svc.get("llm_base_url")
            model_id = await svc.get("llm_custom_model_id") or "custom"
            extra = {"spec_id": spec.id}
        else:
            base_url = None
            model_id = spec.model_id
            extra = {"spec_id": spec.id}

        return ProviderConfig(
            provider=ProviderType(spec.provider),
            api_key=api_key,
            model_id=model_id,
            base_url=base_url,
            extra=extra,
            spec=spec,
        )
```

- [ ] **Implement: update `_load_vision_config()`**

Replace lines 297–309 (the custom branch in `_load_vision_config`) with the same pattern:

```python
        if spec_id == "custom/bifrost":
            base_url = await svc.get("vision_bifrost_base_url")
            model_id = await svc.get("vision_bifrost_model_id") or "custom"
            fallbacks_raw = await svc.get("vision_bifrost_fallbacks")
            fallbacks = json.loads(fallbacks_raw) if fallbacks_raw else []
            extra = {"spec_id": spec.id, "fallbacks": fallbacks}
        elif spec_id.startswith("custom/"):
            base_url = await svc.get("vision_base_url")
            model_id = await svc.get("vision_custom_model_id") or "custom"
            extra = {"spec_id": spec.id}
        else:
            base_url = None
            model_id = spec.model_id
            extra = {"spec_id": spec.id}

        return ProviderConfig(
            provider=ProviderType(spec.provider),
            api_key=api_key,
            model_id=model_id,
            base_url=base_url,
            extra=extra,
            spec=spec,
        )
```

- [ ] **Run to confirm all registry tests pass**

```bash
pytest tests/test_custom_registry.py -v
```

Expected: all `PASSED` (including existing tests — confirm `custom_openai_unaffected` passes too)

- [ ] **Commit**

```bash
git add app/ai/registry.py tests/test_custom_registry.py
git commit -m "feat(bifrost): registry loads Bifrost-scoped config with fallbacks"
```

---

## Task 5: Inject Bifrost fallbacks in LiteLLM provider

**Files:**
- Modify: `app/ai/providers/litellm_provider.py`

- [ ] **Write the failing test** (append to `tests/test_bifrost_catalog.py`)

```python
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.providers.base import ProviderConfig, ProviderType
from app.ai.providers.litellm_provider import LiteLLMLLM, LiteLLMVision


@pytest.mark.asyncio
async def test_bifrost_llm_injects_extra_body():
    """LiteLLMLLM passes extra_body with fallbacks for Bifrost provider."""
    config = ProviderConfig(
        provider=ProviderType.BIFROST,
        api_key="bfk-key",
        model_id="gpt-4o-mini",
        base_url="https://bifrost.myco.com",
        extra={"fallbacks": ["anthropic/claude-3-5-sonnet"]},
    )
    llm = LiteLLMLLM(config)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "hello"

    with patch("litellm.acompletion", return_value=mock_response) as mock_call:
        await llm.generate("Say hi")
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs.get("extra_body") == {"fallbacks": ["anthropic/claude-3-5-sonnet"]}
        # _resolve_model(BIFROST, "gpt-4o-mini") → "openai/gpt-4o-mini"
        assert call_kwargs["model"] == "openai/gpt-4o-mini"
        assert call_kwargs["base_url"] == "https://bifrost.myco.com"


@pytest.mark.asyncio
async def test_bifrost_llm_no_extra_body_when_no_fallbacks():
    """LiteLLMLLM does not inject extra_body when fallbacks list is empty."""
    config = ProviderConfig(
        provider=ProviderType.BIFROST,
        api_key="bfk-key",
        model_id="gpt-4o-mini",
        base_url="https://bifrost.myco.com",
        extra={"fallbacks": []},
    )
    llm = LiteLLMLLM(config)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "hello"

    with patch("litellm.acompletion", return_value=mock_response) as mock_call:
        await llm.generate("Say hi")
        call_kwargs = mock_call.call_args.kwargs
        assert "extra_body" not in call_kwargs
```

- [ ] **Run to confirm they fail**

```bash
pytest tests/test_bifrost_catalog.py -v -k "extra_body"
```

Expected: `FAILED` — `extra_body` not in call kwargs

- [ ] **Implement: add `BIFROST` to `_PROVIDER_PREFIX`**

In `app/ai/providers/litellm_provider.py`, update `_PROVIDER_PREFIX` (lines 23–32):

```python
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
```

- [ ] **Implement: add `_bifrost_extra_body()` helper and inject in `LiteLLMLLM.generate()`**

Add a module-level helper function after `_resolve_model()`:

```python
def _bifrost_extra_body(config: ProviderConfig) -> dict:
    """Return extra_body dict for Bifrost fallbacks, or empty dict."""
    if config.provider != ProviderType.BIFROST:
        return {}
    fallbacks = config.extra.get("fallbacks", [])
    if not fallbacks:
        return {}
    return {"fallbacks": fallbacks}
```

Then update `LiteLLMLLM.generate()` — add the extra_body injection before the `litellm.acompletion` call. The full updated method body:

```python
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
```

- [ ] **Implement: inject in `LiteLLMLLM.generate_with_tools()`**

Same pattern — add after `if max_tokens is not None:` block and before `response = await litellm.acompletion(**kwargs)`:

```python
        extra_body = _bifrost_extra_body(self.config)
        if extra_body:
            kwargs["extra_body"] = extra_body
```

- [ ] **Implement: inject in `LiteLLMVision.analyze_image()`**

Same pattern — add after building the initial `litellm.acompletion(...)` kwargs dict inside the retry loop. Because `analyze_image` calls `litellm.acompletion` inline (not via a kwargs dict), refactor it to use a kwargs dict first. Replace the `response = await litellm.acompletion(...)` block inside the `for attempt` loop:

```python
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
```

- [ ] **Run to confirm all tests pass**

```bash
pytest tests/test_bifrost_catalog.py tests/test_custom_registry.py -v
```

Expected: all `PASSED`

- [ ] **Commit**

```bash
git add app/ai/providers/litellm_provider.py tests/test_bifrost_catalog.py
git commit -m "feat(bifrost): inject fallbacks via extra_body in LiteLLM provider"
```

---

## Task 6: Add Bifrost validation in `admin_settings.py`

**Files:**
- Modify: `app/routers/admin_settings.py:80-131`

- [ ] **Implement: update LLM validation block**

In `app/routers/admin_settings.py`, find the LLM custom validation (around line 84). Change the condition and add a Bifrost `elif`:

```python
    if active_spec and active_spec.startswith("custom/") and active_spec != "custom/bifrost":
        custom_model = body.settings.get("llm_custom_model_id")
        if custom_model is None:
            custom_model = await svc.get("llm_custom_model_id")
        custom_url = body.settings.get("llm_base_url")
        if custom_url is None:
            custom_url = await svc.get("llm_base_url")

        if not custom_model or not custom_model.strip():
            raise HTTPException(status_code=400, detail="Custom Model ID/Name cannot be empty.")
        if not custom_url or not custom_url.strip():
            raise HTTPException(status_code=400, detail="Custom Base URL cannot be empty.")
    elif active_spec == "custom/bifrost":
        bifrost_model = body.settings.get("llm_bifrost_model_id")
        if bifrost_model is None:
            bifrost_model = await svc.get("llm_bifrost_model_id")
        bifrost_url = body.settings.get("llm_bifrost_base_url")
        if bifrost_url is None:
            bifrost_url = await svc.get("llm_bifrost_base_url")

        if not bifrost_model or not bifrost_model.strip():
            raise HTTPException(status_code=400, detail="Bifrost Model ID cannot be empty.")
        if not bifrost_url or not bifrost_url.strip():
            raise HTTPException(status_code=400, detail="Bifrost Base URL cannot be empty.")
```

- [ ] **Implement: update Vision validation block**

Find the Vision custom validation (around line 115). Apply the same change:

```python
    if active_vis_spec and active_vis_spec.startswith("custom/") and active_vis_spec != "custom/bifrost":
        custom_vis_model = body.settings.get("vision_custom_model_id")
        if custom_vis_model is None:
            custom_vis_model = await svc.get("vision_custom_model_id")
        custom_vis_url = body.settings.get("vision_base_url")
        if custom_vis_url is None:
            custom_vis_url = await svc.get("vision_base_url")

        if not custom_vis_model or not custom_vis_model.strip():
            raise HTTPException(status_code=400, detail="Custom Vision Model ID/Name cannot be empty.")
        if not custom_vis_url or not custom_vis_url.strip():
            raise HTTPException(status_code=400, detail="Custom Vision Base URL cannot be empty.")
    elif active_vis_spec == "custom/bifrost":
        bifrost_vis_model = body.settings.get("vision_bifrost_model_id")
        if bifrost_vis_model is None:
            bifrost_vis_model = await svc.get("vision_bifrost_model_id")
        bifrost_vis_url = body.settings.get("vision_bifrost_base_url")
        if bifrost_vis_url is None:
            bifrost_vis_url = await svc.get("vision_bifrost_base_url")

        if not bifrost_vis_model or not bifrost_vis_model.strip():
            raise HTTPException(status_code=400, detail="Bifrost Vision Model ID cannot be empty.")
        if not bifrost_vis_url or not bifrost_vis_url.strip():
            raise HTTPException(status_code=400, detail="Bifrost Vision Base URL cannot be empty.")
```

- [ ] **Run full backend test suite**

```bash
pytest tests/ -v
```

Expected: all `PASSED`

- [ ] **Commit**

```bash
git add app/routers/admin_settings.py
git commit -m "feat(bifrost): add Bifrost validation in admin settings router"
```

---

## Task 7: Create `BifrostExtraFields` frontend component

**Files:**
- Create: `frontend/src/components/settings/bifrost-extra-fields.tsx`

- [ ] **Create the file**

```tsx
"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type BifrostFields = {
  baseUrl: string;
  modelId: string;
  fallbacks: string[];
};

export function BifrostExtraFields({
  capability,
  baseUrl,
  modelId,
  fallbacks,
  onChange,
}: {
  capability: "llm" | "vision";
  baseUrl: string;
  modelId: string;
  fallbacks: string[];
  onChange: (patch: Partial<BifrostFields>) => void;
}) {
  function updateFallback(index: number, value: string) {
    const next = [...fallbacks];
    next[index] = value;
    onChange({ fallbacks: next });
  }

  function removeFallback(index: number) {
    onChange({ fallbacks: fallbacks.filter((_, i) => i !== index) });
  }

  function addFallback() {
    onChange({ fallbacks: [...fallbacks, ""] });
  }

  return (
    <div className="flex flex-col gap-4 mb-4">
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Gateway Base URL</Label>
        <Input
          type="text"
          value={baseUrl}
          onChange={(e) => onChange({ baseUrl: e.target.value })}
          placeholder="https://gateway.mycompany.com"
          className="bg-background"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Primary Model</Label>
        <Input
          type="text"
          value={modelId}
          onChange={(e) => onChange({ modelId: e.target.value })}
          placeholder={capability === "llm" ? "gpt-4o-mini" : "gpt-4o"}
          className="bg-background"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Fallback Models <span className="text-muted-foreground">(optional)</span></Label>
        {fallbacks.map((fb, i) => (
          <div key={i} className="flex gap-2 items-center">
            <Input
              type="text"
              value={fb}
              onChange={(e) => updateFallback(i, e.target.value)}
              placeholder="anthropic/claude-3-5-sonnet"
              className="bg-background flex-1"
            />
            <button
              type="button"
              onClick={() => removeFallback(i)}
              className="text-muted-foreground hover:text-destructive px-2 text-base leading-none"
              aria-label="Remove fallback"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={addFallback}
          className="text-xs text-primary hover:underline self-start mt-0.5"
        >
          + Add fallback
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors related to `bifrost-extra-fields.tsx`

- [ ] **Commit**

```bash
git add frontend/src/components/settings/bifrost-extra-fields.tsx
git commit -m "feat(bifrost): add BifrostExtraFields settings component"
```

---

## Task 8: Update `ModelCatalogCard` for Bifrost

**Files:**
- Modify: `frontend/src/components/settings/model-catalog-card.tsx`

- [ ] **Add import** at the top of the file (after existing imports):

```tsx
import { BifrostExtraFields } from "@/components/settings/bifrost-extra-fields";
```

- [ ] **Add Bifrost state** after the existing `const [saved, setSaved] = useState(false);` line (line ~59):

```tsx
  const [bifrostBaseUrl, setBifrostBaseUrl] = useState<string>("");
  const [bifrostModelId, setBifrostModelId] = useState<string>("");
  const [bifrostFallbacks, setBifrostFallbacks] = useState<string[]>([]);
```

- [ ] **Add Bifrost config key constants** after `const customBaseUrlKey = ...` (line ~65):

```tsx
  const bifrostBaseUrlKey = `${capability}_bifrost_base_url`;
  const bifrostModelIdKey = `${capability}_bifrost_model_id`;
  const bifrostFallbacksKey = `${capability}_bifrost_fallbacks`;
```

- [ ] **Update `refresh()` to load Bifrost settings**

Inside the `refresh()` function, after the lines that call `setCustomModelId` and `setCustomBaseUrl` (around line 95), add:

```tsx
      const bBase = settings[bifrostBaseUrlKey];
      const bModel = settings[bifrostModelIdKey];
      const bFallbacksRaw = settings[bifrostFallbacksKey];
      setBifrostBaseUrl(typeof bBase === "string" ? bBase : "");
      setBifrostModelId(typeof bModel === "string" ? bModel : "");
      try {
        setBifrostFallbacks(
          typeof bFallbacksRaw === "string" && bFallbacksRaw
            ? (JSON.parse(bFallbacksRaw) as string[])
            : []
        );
      } catch {
        setBifrostFallbacks([]);
      }
```

- [ ] **Update detection constants** — replace lines ~104-109 (`selectedSpec`, `isActiveSelected`, `willSwitch`, `isMaskedKey`, `hasNewKey`, `isCustom`):

```tsx
  const selectedSpec = catalog?.specs.find((s) => s.id === selected) ?? null;
  const isActiveSelected = selectedSpec?.id === catalog?.active_spec_id;
  const willSwitch = !!selectedSpec && !isActiveSelected;
  const isMaskedKey = apiKey.includes("•");
  const hasNewKey = apiKey.trim().length > 0 && !isMaskedKey;
  const isBifrost = selectedSpec?.id === "custom/bifrost";
  const isCustom = !!selectedSpec?.id.startsWith("custom/") && !isBifrost;
```

- [ ] **Replace `canSave`** (lines ~110-117) with:

```tsx
  const canSave =
    !!selectedSpec &&
    (!isCustom || (customModelId.trim().length > 0 && customBaseUrl.trim().length > 0)) &&
    (!isBifrost || (bifrostModelId.trim().length > 0 && bifrostBaseUrl.trim().length > 0)) &&
    (
      hasNewKey ||
      (willSwitch && selectedSpec.api_key_configured) ||
      isCustom ||
      isBifrost
    );
```

- [ ] **Update `handleSave()`** — after the `if (isCustom) { ... }` block (around line 131), add:

```tsx
      if (isBifrost) {
        settingsUpdates[bifrostBaseUrlKey] = bifrostBaseUrl.trim();
        settingsUpdates[bifrostModelIdKey] = bifrostModelId.trim();
        settingsUpdates[bifrostFallbacksKey] = JSON.stringify(
          bifrostFallbacks.filter((f) => f.trim().length > 0)
        );
      }
```

- [ ] **Update the render** — in the JSX return, find the `{selectedSpec && ( ... )}` block. Replace the `{isCustom && ( ... )}` conditional with two consecutive conditionals:

```tsx
          {isCustom && (
            <>
              <div className="mb-4 flex flex-col gap-1.5">
                <Label className="text-xs">Custom Model ID / Name</Label>
                <Input
                  type="text"
                  value={customModelId}
                  onChange={(e) => setCustomModelId(e.target.value)}
                  placeholder={capability === "llm" ? "e.g. meta-llama/Llama-3-8B-Instruct" : "e.g. llava-v1.6"}
                  className="bg-background"
                />
              </div>
              <div className="mb-4 flex flex-col gap-1.5">
                <Label className="text-xs">API Base URL</Label>
                <Input
                  type="text"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  placeholder="e.g. http://localhost:8080/v1"
                  className="bg-background"
                />
              </div>
            </>
          )}

          {isBifrost && (
            <BifrostExtraFields
              capability={capability}
              baseUrl={bifrostBaseUrl}
              modelId={bifrostModelId}
              fallbacks={bifrostFallbacks}
              onChange={(patch) => {
                if (patch.baseUrl !== undefined) setBifrostBaseUrl(patch.baseUrl);
                if (patch.modelId !== undefined) setBifrostModelId(patch.modelId);
                if (patch.fallbacks !== undefined) setBifrostFallbacks(patch.fallbacks);
              }}
            />
          )}
```

- [ ] **Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Manual smoke test — start the dev server**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000` → Settings → LLM Model section:
1. Confirm "Bifrost Gateway" appears as a radio option
2. Select it — confirm Base URL, Primary Model, and Fallbacks rows appear (no generic Custom fields)
3. Click "+ Add fallback" — confirm a new row appears
4. Fill in Base URL + Primary Model — confirm Save button becomes enabled
5. Save — confirm the settings persist on page reload
6. Switch back to a standard model — confirm Bifrost fields disappear

Repeat the same checks in Vision Model section.

- [ ] **Commit**

```bash
git add frontend/src/components/settings/model-catalog-card.tsx
git commit -m "feat(bifrost): integrate BifrostExtraFields into ModelCatalogCard"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
pytest tests/ -v
```

Expected: all `PASSED`, no skips or failures

- [ ] **Run type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors
