# Langfuse Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in Langfuse LLM observability to Arkon by registering LiteLLM's built-in Langfuse callback on startup, activated via environment variables.

**Architecture:** A small `app/ai/tracing.py` module exposes `configure_langfuse_tracing()` which sets `litellm.success_callbacks` and `litellm.failure_callbacks` to `["langfuse"]` when `LANGFUSE_PUBLIC_KEY` is present in the environment. This is called from the `lifespan` startup block in `app/main.py`. LiteLLM then automatically sends every `acompletion` and `aembedding` call to Langfuse.

**Tech Stack:** `langfuse>=2.0.0` Python SDK, LiteLLM callback registry.

---

### Task 1: Add `langfuse` dependency and env file documentation

**Files:**
- Modify: `pyproject.toml` (add dep after `litellm` line)
- Modify: `.env.docker.example` (add Langfuse section at end)
- Modify: `.env.local.example` (same section, keep in sync)
- Modify: `docker-compose.yml` (add comment near `env_file` line)
- Test: `tests/test_langfuse_tracing.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_langfuse_tracing.py`:

```python
def test_langfuse_importable():
    import langfuse
    assert langfuse is not None
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m pytest tests/test_langfuse_tracing.py::test_langfuse_importable -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'langfuse'`

- [ ] **Step 3: Add `langfuse` to `pyproject.toml`**

In `pyproject.toml`, find the `litellm` line and add `langfuse` immediately after:

```toml
    # AI / LLM (provider-agnostic — user picks at runtime)
    "litellm>=1.60.0",
    "langfuse>=2.0.0",
```

- [ ] **Step 4: Install the dependency**

```bash
pip install -e ".[dev]"
```

Expected: output includes `Successfully installed langfuse-...`

- [ ] **Step 5: Run the test to verify it passes**

```bash
python -m pytest tests/test_langfuse_tracing.py::test_langfuse_importable -v
```

Expected: `PASSED`

- [ ] **Step 6: Add Langfuse section to `.env.docker.example`**

Append to the end of `.env.docker.example`:

```
# --- Observability (optional) ---
# Langfuse LLM tracing — set all three to enable. Leave blank to disable.
# Cloud: https://cloud.langfuse.com  |  Self-hosted: your Langfuse URL
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_HOST=https://cloud.langfuse.com
```

- [ ] **Step 7: Add the same section to `.env.local.example`**

Append the identical block to the end of `.env.local.example`:

```
# --- Observability (optional) ---
# Langfuse LLM tracing — set all three to enable. Leave blank to disable.
# Cloud: https://cloud.langfuse.com  |  Self-hosted: your Langfuse URL
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_HOST=https://cloud.langfuse.com
```

- [ ] **Step 8: Add a comment to `docker-compose.yml`**

In `docker-compose.yml`, find the `x-backend` anchor block. The current `env_file` line is:

```yaml
  env_file: [.env.docker]
```

Replace it with:

```yaml
  # Langfuse tracing: add LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST to .env.docker to enable
  env_file: [.env.docker]
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .env.docker.example .env.local.example docker-compose.yml tests/test_langfuse_tracing.py
git commit -m "feat(tracing): add langfuse dependency and env documentation"
```

---

### Task 2: Implement tracing module and wire into app startup

**Files:**
- Create: `app/ai/tracing.py`
- Modify: `app/main.py` (add import + call in `lifespan`, after MinIO check block)
- Modify: `tests/test_langfuse_tracing.py` (add 2 tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_langfuse_tracing.py`:

```python
import litellm


def test_tracing_enabled_when_key_set(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    litellm.success_callbacks = []
    litellm.failure_callbacks = []

    from app.ai.tracing import configure_langfuse_tracing
    result = configure_langfuse_tracing()

    assert result is True
    assert "langfuse" in litellm.success_callbacks
    assert "langfuse" in litellm.failure_callbacks


def test_tracing_disabled_when_key_absent(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    litellm.success_callbacks = []
    litellm.failure_callbacks = []

    from app.ai.tracing import configure_langfuse_tracing
    result = configure_langfuse_tracing()

    assert result is False
    assert "langfuse" not in litellm.success_callbacks
    assert "langfuse" not in litellm.failure_callbacks
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_langfuse_tracing.py -v -k "not importable"
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'app.ai.tracing'`

- [ ] **Step 3: Create `app/ai/tracing.py`**

```python
import os

import litellm


def configure_langfuse_tracing() -> bool:
    """Register Langfuse LiteLLM callbacks if LANGFUSE_PUBLIC_KEY is set. Returns True if enabled."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return False
    litellm.success_callbacks = ["langfuse"]
    litellm.failure_callbacks = ["langfuse"]
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_langfuse_tracing.py -v
```

Expected: all 3 tests `PASSED`

- [ ] **Step 5: Wire into `app/main.py` lifespan**

At the top of `app/main.py`, the existing imports include `from app.config import settings`. Add the tracing import on the next line:

```python
from app.config import settings
from app.ai.tracing import configure_langfuse_tracing
```

In the `lifespan` function, after the MinIO bucket block and before `await seed_default_admin()`, add:

```python
        # Configure Langfuse tracing if env vars are set
        if configure_langfuse_tracing():
            logger.success("Langfuse tracing enabled")
        else:
            logger.info("Langfuse tracing not configured (LANGFUSE_PUBLIC_KEY not set)")
```

Full context for placement — the lifespan block should look like this after the change:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown logic (composed with FastMCP lifespan)."""
    async with mcp_http_app.lifespan(app):
        logger.info("Starting Arkon API...")

        # Ensure MinIO bucket exists
        try:
            from app.services.storage_service import storage_service
            await storage_service.ensure_bucket()
            logger.success("MinIO bucket ready")
        except Exception as e:
            logger.warning(f"MinIO not available yet: {e}")

        # Configure Langfuse tracing if env vars are set
        if configure_langfuse_tracing():
            logger.success("Langfuse tracing enabled")
        else:
            logger.info("Langfuse tracing not configured (LANGFUSE_PUBLIC_KEY not set)")

        # Seed default admin if no admin exists yet
        await seed_default_admin()
        ...
```

- [ ] **Step 6: Verify the import is clean**

```bash
python -c "from app.ai.tracing import configure_langfuse_tracing; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Run the full test suite to check for regressions**

```bash
python -m pytest tests/ -q
```

Expected: all tests pass, no new failures.

- [ ] **Step 8: Commit**

```bash
git add app/ai/tracing.py app/main.py tests/test_langfuse_tracing.py
git commit -m "feat(tracing): register Langfuse callback on startup via LiteLLM"
```
