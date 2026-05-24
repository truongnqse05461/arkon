# Bifrost Gateway Provider — Design Spec
Date: 2026-05-25

## Overview

Add Bifrost Gateway as a first-class provider for **LLM and Vision** capabilities.
Bifrost is a self-hosted, OpenAI-compatible AI gateway that supports automatic
failover via a `fallbacks` array in the request body. It is separate from the
existing `custom_openai` and `custom_anthropic` providers.

Embedding via Bifrost is **not** a new provider — admins use the existing
`Custom OpenAI-Compatible` embedding option with Bifrost's base URL and Virtual Key.

---

## Scope

| Capability | Bifrost provider added? | Fallbacks field? |
|------------|------------------------|-----------------|
| LLM        | Yes (`custom/bifrost`)  | Yes             |
| Vision     | Yes (`custom/bifrost`)  | Yes             |
| Embedding  | No — use `custom_openai` | N/A            |

---

## Backend

### 1. `app/ai/providers/base.py`
- Add `BIFROST = "bifrost"` to `ProviderType`.

### 2. `app/ai/llm_catalog.py`
Add catalog entry:
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
)
```

### 3. `app/ai/vision_catalog.py`
Add `custom/bifrost` entry with `provider="bifrost"` following the existing
`custom/openai` vision entry pattern.

### 4. `app/services/config_service.py`

New keys added to `ALL_CONFIG_KEYS`:

| Key | Type | Notes |
|-----|------|-------|
| `llm_api_key__bifrost` | sensitive | Virtual Key — encrypted at rest |
| `llm_bifrost_base_url` | plain | e.g. `https://gateway.mycompany.com` |
| `llm_bifrost_model_id` | plain | e.g. `openai/gpt-4o-mini` |
| `llm_bifrost_fallbacks` | plain | JSON array string, e.g. `["anthropic/claude-3-5-sonnet"]` |
| `vision_api_key__bifrost` | sensitive | Virtual Key for vision calls |
| `vision_bifrost_base_url` | plain | |
| `vision_bifrost_model_id` | plain | |
| `vision_bifrost_fallbacks` | plain | JSON array string |

Bifrost uses its own scoped keys (not the shared `llm_base_url` /
`llm_custom_model_id`) so switching between `custom/openai` and `custom/bifrost`
does not overwrite each other's settings.

### 5. `app/ai/registry.py`

In `_load_llm_config()` and `_load_vision_config()`, add a Bifrost branch before
the generic `custom/` branch:

```python
if spec_id == "custom/bifrost":
    base_url = await svc.get(f"{cap}_bifrost_base_url")
    model_id = await svc.get(f"{cap}_bifrost_model_id") or "custom"
    fallbacks_raw = await svc.get(f"{cap}_bifrost_fallbacks")
    fallbacks = json.loads(fallbacks_raw) if fallbacks_raw else []
    extra = {"spec_id": spec.id, "fallbacks": fallbacks}
```

Where `cap` is `"llm"` or `"vision"`. The existing `startswith("custom/")` branch
handles all other custom providers unchanged.

### 6. `app/ai/providers/litellm_provider.py`

- Add `ProviderType.BIFROST: "openai"` to `_PROVIDER_PREFIX`.
  Bifrost is OpenAI-compatible — LiteLLM routes it via the OpenAI path using the
  custom `api_base`.
- In `LiteLLMLLM.generate()`, `generate_with_tools()`, and
  `LiteLLMVision.analyze_image()`: when `self.config.provider == ProviderType.BIFROST`
  and `self.config.extra.get("fallbacks")` is non-empty, add to kwargs:
  ```python
  extra_body = {"fallbacks": self.config.extra["fallbacks"]}
  kwargs["extra_body"] = extra_body
  ```
  LiteLLM passes `extra_body` fields through to the raw request body.

### 7. `app/routers/admin_settings.py`

In `update_settings()`, add a Bifrost validation block (parallel to existing
custom LLM/Vision validation):

```python
if active_spec == "custom/bifrost":
    # require llm_bifrost_base_url and llm_bifrost_model_id
    # llm_bifrost_fallbacks is optional
```

Same pattern repeated for vision (`active_vis_spec == "custom/bifrost"`).

---

## Frontend

### New file: `frontend/src/components/settings/bifrost-extra-fields.tsx`

Controlled component (~80 lines). Receives:
```typescript
{
  capability: "llm" | "vision"
  baseUrl: string
  modelId: string
  fallbacks: string[]
  onChange: (patch: Partial<BifrostFields>) => void
}
```

Renders:
1. **Base URL** — text input, placeholder `https://gateway.mycompany.com`
2. **Primary Model** — text input, placeholder `openai/gpt-4o-mini`
3. **Fallback Models** — dynamic rows:
   - Each row: text input (placeholder `anthropic/claude-3-5-sonnet`) + remove (×) button
   - **Add fallback** button appends an empty string to the `fallbacks` array
   - Minimum 0 fallback rows (optional field)

### Updated: `frontend/src/components/settings/model-catalog-card.tsx`

**State additions:**
```typescript
const [bifrostBaseUrl, setBifrostBaseUrl] = useState("");
const [bifrostModelId, setBifrostModelId] = useState("");
const [bifrostFallbacks, setBifrostFallbacks] = useState<string[]>([]);
```

**Detection:**
```typescript
const isBifrost = selectedSpec?.id === "custom/bifrost";
const isCustom = !!selectedSpec?.id.startsWith("custom/") && !isBifrost;
```

**Config keys (computed):**
```typescript
const bifrostBaseUrlKey = `${capability}_bifrost_base_url`;
const bifrostModelIdKey = `${capability}_bifrost_model_id`;
const bifrostFallbacksKey = `${capability}_bifrost_fallbacks`;
```

**On load (`refresh()`):**
- Read `bifrostBaseUrlKey`, `bifrostModelIdKey` from settings
- Parse `bifrostFallbacksKey` as JSON array (default `[]`)

**On save (`handleSave()`):**
- When `isBifrost`: save `bifrostBaseUrlKey`, `bifrostModelIdKey`; serialize
  `bifrostFallbacks` (filter empty strings) as JSON to `bifrostFallbacksKey`

**`canSave` update — full expression:**
```typescript
const canSave =
  !!selectedSpec &&
  (!isCustom || (customModelId.trim().length > 0 && customBaseUrl.trim().length > 0)) &&
  (!isBifrost || (bifrostModelId.trim().length > 0 && bifrostBaseUrl.trim().length > 0)) &&
  (hasNewKey || (willSwitch && selectedSpec.api_key_configured) || isCustom || isBifrost);
```

**Render:** When `isBifrost`, render `<BifrostExtraFields>` in place of the
generic `isCustom` block.

---

## Data Flow

```
Admin UI
  → selects "Bifrost Gateway" radio
  → fills Base URL, Primary Model, optional Fallbacks rows
  → clicks Save

model-catalog-card.tsx
  → PUT /api/settings  { llm_bifrost_base_url, llm_bifrost_model_id, llm_bifrost_fallbacks, llm_api_key__bifrost }
  → POST /api/settings/llm/switch  { model_spec_id: "custom/bifrost" }

ProviderRegistry._load_llm_config()
  → loads Bifrost-scoped keys
  → parses fallbacks JSON → ProviderConfig.extra["fallbacks"]

LiteLLMLLM.generate_with_tools()
  → model = "openai/<bifrost_model_id>" via _PROVIDER_PREFIX
  → api_base = bifrost_base_url
  → extra_body = { "fallbacks": [...] }   ← injected only when non-empty
  → litellm.acompletion(...)              ← forwards extra_body to raw request
```

---

## Out of Scope

- Embedding Bifrost provider (use existing `custom_openai`)
- Bifrost-specific response metadata (`extra_fields.provider`, `extra_fields.latency`)
- Per-fallback retry budget configuration
- UI validation that fallback model strings follow `provider/model` format
