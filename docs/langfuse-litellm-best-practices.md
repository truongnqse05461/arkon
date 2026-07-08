# Langfuse + LiteLLM Integration — Best Practice Reference

Built from real production code (Agentic RAG — LlamaIndex-based multi-agent chatbot).

---

## 1. Architecture Overview

```
LLM calls (gemini-2.5-flash via LiteLLM)
  └─> OpenInference auto-instrumentor (LlamaIndexInstrumentor)
       └─> OpenTelemetry TracerProvider + BatchSpanProcessor
            └─> OTLPSpanExporter (HTTP)
                 └─> Langfuse OTLP endpoint: {LANGFUSE_HOST}/api/public/otel/v1/traces
                      └─> Langfuse Web UI (v3)

No Langfuse Python SDK required. Traces flow via standard OTLP.
```

**Key insight**: This project does NOT install `langfuse` Python package. It uses Langfuse's public OTLP ingestion endpoint with Basic auth. This avoids vendor lock-in to the Langfuse SDK and keeps the dependency graph minimal.

---

## 2. Library Versions

From `backend/requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| `litellm` | >=1.67.0 | Unified LLM API (direct SDK + LlamaIndex wrapper) |
| `llama-index` | >=0.10.0 | Agent framework (FunctionAgent, tools, memory) |
| `llama-index-llms-litellm` | >=0.1.0 | LlamaIndex LLM wrapper around LiteLLM |
| `llama-index-embeddings-litellm` | >=0.1.0 | LlamaIndex embedding wrapper around LiteLLM |
| `opentelemetry-sdk` | >=1.24.0 | OTEL tracer + span processor |
| `opentelemetry-exporter-otlp-proto-http` | >=1.24.0 | OTLP HTTP span exporter |
| `openinference-instrumentation-llama-index` | >=3.0.0 | Auto-instrumentation for LlamaIndex |

**Notably absent**: `langfuse` Python package. No `langfuse` dependency needed.

---

## 3. Core Setup Code

### 3.1 Tracing Initialization

```python
# backend/infra/tracing.py
import os
import base64
import logging

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace

_log = logging.getLogger(__name__)

def setup_tracing() -> None:
    host = os.environ.get("LANGFUSE_HOST", "").rstrip("/")
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sec = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if not (host and pub and sec):
        _log.warning("Langfuse tracing disabled — missing env vars")
        return

    # Basic auth: public_key:secret_key → base64
    auth = base64.b64encode(f"{pub}:{sec}".encode()).decode()
    endpoint = f"{host}/api/public/otel/v1/traces"

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"Authorization": f"Basic {auth}"},
    )

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument LlamaIndex
    from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
    LlamaIndexInstrumentor().instrument(tracer_provider=provider)

    # Suppress noisy instrumentor logs
    logging.getLogger("openinference.instrumentation.llama_index._handler").setLevel(logging.ERROR)

    _log.info("Langfuse tracing enabled: endpoint=%s", endpoint)
```

**Startup sequence** (in `main.py` lifespan):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_llm_stack()   # register models, set embeddings
    setup_tracing()          # initialize OTel + instrument LlamaIndex
    yield
    await engine.dispose()
```

### 3.2 LiteLLM LLM Configuration

```python
# backend/infra/llm_config.py
import litellm
from llama_index.core import Settings
from llama_index.embeddings.litellm import LiteLLMEmbedding

def configure_llm_stack():
    # Register custom model capabilities for GLM models (optional)
    litellm.register_model({
        "glm-4.6": {
            "mode": "chat",
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_system_messages": True,
            "supports_tool_choice_strict": True,
            "max_tokens": 4096,
            "max_input_tokens": 32768,
        },
        # ... more models
    })

    # Embedding model via LlamaIndex global settings
    Settings.embed_model = LiteLLMEmbedding(
        model_name="gemini/gemini-embedding-001",
        api_key=os.environ.get("GEMINI_API_KEY"),
    )
```

### 3.3 LLM Provider Registry

```python
# backend/domain/agent/registry.py
from functools import lru_cache
from llama_index.llms.litellm import LiteLLM
from llama_index.postprocessor.cohere_rerank import CohereRerank

@lru_cache(maxsize=32)
def get_llm(model: str, temperature: float = 0, max_tokens: int | None = None) -> LiteLLM:
    kwargs = {"model": model, "temperature": temperature}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    # Custom provider routing: zai/ prefix → OpenAI-compatible API
    if model.startswith("zai/"):
        kwargs["model"] = "openai/" + model.removeprefix("zai/")
        kwargs["api_base"] = os.environ["ZAI_BASE_URL"]
        kwargs["api_key"] = os.environ["ZAI_API_KEY"]

    return LiteLLM(**kwargs)

@lru_cache(maxsize=4)
def get_reranker():
    return CohereRerank(api_key=os.environ.get("COHERE_API_KEY", ""), top_n=5)
```

### 3.4 Direct LiteLLM SDK Usage (outside LlamaIndex)

```python
# backend/services/gemini.py
from litellm import acompletion, aembedding

async def embed_texts(texts: list[str], model: str = "gemini/gemini-embedding-001"):
    resp = await aembedding(model=model, input=texts, api_key=os.environ["GEMINI_API_KEY"])
    return [d["embedding"] for d in resp["data"]]

async def generate(messages, model="gemini/gemini-2.5-flash", stream=False):
    kwargs = {
        "model": model,
        "messages": messages,
        "api_key": os.environ["GEMINI_API_KEY"],
    }
    if stream:
        resp = await acompletion(**kwargs, stream=True)
        # iterate chunks...
    else:
        resp = await acompletion(**kwargs)
        return resp.choices[0].message.content
```

---

## 4. Environment Variables

```bash
# LLM
GEMINI_API_KEY=
COHERE_API_KEY=

# Embeddings (optional override)
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Langfuse / Observability
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**OTLP endpoint construction**: `{LANGFUSE_HOST}/api/public/otel/v1/traces` with Basic auth (`public_key:secret_key` base64-encoded).

---

## 5. Docker / Infrastructure

Langfuse v3 services in `docker-compose.yml`:

| Service | Image | Port | Purpose |
|---|---|---|---|
| `langfuse_db` | `postgres:16` | — | Postgres for traces/metadata |
| `langfuse_clickhouse` | `clickhouse/clickhouse-server:24.3` | — | Analytics store |
| `langfuse_redis` | `redis:7` | — | Queue/cache |
| `langfuse_minio` | `minio/minio` | — | S3-compatible blob storage |
| `langfuse-worker` | `langfuse/langfuse-worker:3` | — | Background processor |
| `langfuse-web` | `langfuse/langfuse:3` | 3001:3000 | Web UI + API |

**Auto-provisioning** via `LANGFUSE_INIT_*` env vars on `langfuse-web`:
```yaml
environment:
  LANGFUSE_INIT_PROJECT_NAME: "Agentic RAG"
  LANGFUSE_INIT_PROJECT_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
  LANGFUSE_INIT_PROJECT_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
  LANGFUSE_INIT_ORG_NAME: "My Org"
  LANGFUSE_INIT_USER_EMAIL: admin@example.com
  LANGFUSE_INIT_USER_NAME: Admin
```

The init vars seed the project and user on first boot, ensuring the public/secret keys in `.env` match the Langfuse project.

---

## 6. Notes & Best Practices

### 6.1 OTLP vs Langfuse SDK

| | OTLP approach (this project) | Langfuse SDK |
|---|---|---|
| Dependency | `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http` | `langfuse` |
| Vendor lock-in | None — standard OTLP | Langfuse-specific |
| Setup | Manual: TracerProvider + exporter + auth | `Langfuse(...)` + decorators |
| Custom traces | Need `@trace` decorator equivalent | Built-in |
| Cost | Free (self-hosted) | Free tier / self-hosted |

**When to use OTLP**: You're already using OpenTelemetry for other services, or want to avoid vendor lock-in. Langfuse accepts OTLP natively.

**When to use Langfuse SDK**: You need SDK-specific features (score tracking, dataset management, session tracking) that aren't covered by OTLP spans.

### 6.2 `TracerProvider` Must Be Set Once

```python
trace.set_tracer_provider(provider)  # GLOBAL — can only be called once
```

If you call it twice (e.g., in tests that reload modules), you'll get a runtime error. Guard with a check or use it only in app startup (lifespan).

### 6.3 OpenInference Suppresses Noisy Logs

```python
logging.getLogger("openinference.instrumentation.llama_index._handler").setLevel(logging.ERROR)
```

Without this, the instrumentor logs every span at INFO level, flooding your application logs.

### 6.4 LiteLLM `register_model` for Non-Standard Models

LiteLLM has built-in support for OpenAI, Anthropic, Google, etc. For custom providers (like Z.ai's GLM models), you must register capabilities:

```python
litellm.register_model({
    "glm-4.6": {
        "mode": "chat",
        "supports_function_calling": True,
        "supports_tool_choice": True,
        "supports_system_messages": True,
        "max_tokens": 4096,
        "max_input_tokens": 32768,
    },
})
```

Without this, LiteLLM won't know how to route the request or what features the model supports.

### 6.5 Custom Provider Routing

For providers that use OpenAI-compatible API but different base URLs:

```python
if model.startswith("zai/"):
    kwargs["model"] = "openai/" + model.removeprefix("zai/")
    kwargs["api_base"] = os.environ["ZAI_BASE_URL"]
    kwargs["api_key"] = os.environ["ZAI_API_KEY"]
```

The `openai/` prefix tells LiteLLM to use the OpenAI-compatible client with the overridden `api_base`.

### 6.6 Embedding Task Types

Gemini embeddings accept `task_type` metadata for optimized vector generation:

```python
await aembedding(
    model="gemini/gemini-embedding-001",
    input=texts,
    metadata={"task_type": "retrieval_document"},  # or "retrieval_query"
)
```

`retrieval_document` for document chunks, `retrieval_query` for search queries. This can improve retrieval quality.

### 6.7 LLM Instance Caching

Use `@lru_cache` for LLM instances. LiteLLM maintains internal connection pools; creating a new instance per request wastes resources.

```python
@lru_cache(maxsize=32)
def get_llm(model, temperature, max_tokens):
    return LiteLLM(model=model, temperature=temperature, max_tokens=max_tokens)
```

### 6.8 Graceful Degradation

```python
try:
    from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
    LlamaIndexInstrumentor().instrument(tracer_provider=provider)
except ImportError:
    _log.warning("openinference-instrumentation-llama-index not installed")
```

If the instrumentation package isn't installed, the app still runs — just without tracing. This is useful for dev environments that don't need observability.

### 6.9 What OpenInference Captures Automatically

When `LlamaIndexInstrumentor` is active, these are traced without any manual instrumentation:
- LLM calls (model, prompt, response, token counts, latency)
- Retrieval operations (query, top-k, results)
- Tool calls (tool name, arguments, outputs)
- Agent steps (reasoning, tool use loop)
- Reranking (input, output, scores)
- Embedding calls

All visible in Langfuse's trace viewer, including the full call tree.

### 6.10 OTLP Endpoint Path

The path `/api/public/otel/v1/traces` is Langfuse's **public** OTLP endpoint. It differs from the standard OTLP path (`/v1/traces`) in that it accepts Basic auth with Langfuse project keys.

If using Langfuse Cloud (`https://cloud.langfuse.com`), the endpoint would be:
```
https://cloud.langfuse.com/api/public/otel/v1/traces
```

---

## 7. Dependency Graph

```
User Chat Request
  ├── FastAPI endpoint
  │   └── orchestrator.stream_response()
  │       └── factory.build_agent()
  │           └── FunctionAgent(llm=LiteLLM, tools=[file_search])
  │               └── agent.run(memory=..., user_msg=...)
  │                   ├── LiteLLM → gemini-2.5-flash  ←─ traced by OpenInference
  │                   └── file_search tool
  │                       ├── Qdrant retrieve           ←─ traced by OpenInference
  │                       └── Cohere rerank             ←─ traced by OpenInference
  │
  └── OpenTelemetry spans
      └── BatchSpanProcessor
          └── OTLPSpanExporter → Langfuse OTLP endpoint
```

Separate ingestion path (not traced by default):
```
File Upload
  └── ingest.run_ingestion()
      ├── PyMuPDF / marker-pdf parse
      └── litellm.aembedding()       ←─ NOT auto-traced (direct SDK call)
          └── Qdrant upsert
```

---

## 8. Common Pitfalls

### 8.1 Missing `supports_function_calling` Registration
If you register a model in `litellm.register_model()` but omit `supports_function_calling: True`, LiteLLM will silently skip tool use and the agent will return garbage.

### 8.2 Embedding Dimension Mismatch
Gemini-embedding-001 outputs 3072-dimensional vectors. If your Qdrant collection was created with a different dimension, upserts will fail:
```python
VECTOR_SIZE = 3072  # gemini-embedding-001 output dimension
```

### 8.3 OTLP Exporter Fails Silently in Batch Mode
`BatchSpanProcessor` buffers spans. If the endpoint is wrong or auth fails, you won't see errors immediately. Check Langfuse UI for incoming traces, or switch to `SimpleSpanProcessor` during debugging.

### 8.4 Langfuse Init Keys Must Match `.env`
`LANGFUSE_INIT_PROJECT_PUBLIC_KEY` and `LANGFUSE_INIT_PROJECT_SECRET_KEY` in docker-compose must match `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`. Mismatch = traces go to a different project or get rejected.

### 8.5 `trace.set_tracer_provider()` Is Global and Idempotent
Calling it twice raises `ValueError`. This happens in test suites that import the tracing module multiple times. Guard with a flag or only call in app lifespan.

---

## 9. Quick Start for New Project

```bash
# 1. Install dependencies
pip install litellm llama-index llama-index-llms-litellm \
    llama-index-embeddings-litellm \
    opentelemetry-sdk opentelemetry-exporter-otlp-proto-http \
    openinference-instrumentation-llama-index

# 2. Set env vars
export LANGFUSE_HOST=http://localhost:3000
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export GEMINI_API_KEY=AIza...

# 3. In your app startup:
from infra.tracing import setup_tracing
from infra.llm_config import configure_llm_stack

configure_llm_stack()
setup_tracing()

# 4. All LlamaIndex LLM/embedding calls are now auto-traced in Langfuse
```
