# Langfuse Tracing Design

**Goal:** Add LLM observability to Arkon via LiteLLM's built-in Langfuse callback, configured entirely through environment variables.

**Architecture:** Register `"langfuse"` in LiteLLM's global `success_callbacks` and `failure_callbacks` on app startup. LiteLLM reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` from the environment automatically and sends every `acompletion` and `aembedding` call to Langfuse. Initialization is guarded by a `LANGFUSE_PUBLIC_KEY` presence check so the app starts normally when tracing is not configured.

**Tech Stack:** `langfuse>=2.0.0` (Python SDK), LiteLLM callback registry.

---

## What Gets Traced

Every LiteLLM call — LLM completions, vision completions, and embeddings — is captured automatically with no per-call code:

- Model name and provider
- Input messages and output content
- Token counts (prompt + completion)
- Latency
- Estimated cost
- Errors (failures are sent via `failure_callbacks`)

## Activation

Tracing is opt-in via environment variables. If `LANGFUSE_PUBLIC_KEY` is absent, the app behaves exactly as before. When all three vars are set, traces appear in the Langfuse project associated with the key.

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com   # or self-hosted URL
```

## Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | Add `langfuse>=2.0.0` to dependencies |
| `app/main.py` | Register callbacks in `lifespan` startup, guarded by env check |
| `docker-compose.yml` | Commented-out Langfuse env var block |
| `.env.docker.example` | Commented Langfuse section |
| `.env.local.example` | Commented Langfuse section (kept in sync with docker example) |

## Startup Block (`app/main.py`)

```python
import os
if os.getenv("LANGFUSE_PUBLIC_KEY"):
    import litellm
    litellm.success_callbacks = ["langfuse"]
    litellm.failure_callbacks = ["langfuse"]
    logger.success("Langfuse tracing enabled")
else:
    logger.info("Langfuse tracing not configured (LANGFUSE_PUBLIC_KEY not set)")
```

## Out of Scope

- Settings UI for Langfuse credentials (env vars are sufficient)
- Per-call metadata enrichment (user_id, session_id) — default trace info is sufficient for now
- Filtering embedding traces out — all LiteLLM calls are traced; embeddings can be filtered in the Langfuse UI
