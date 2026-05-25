# System Architecture

Arkon is structured as a self-hosted, decoupled multi-service system. It coordinates file storage, relational and vector databases, background task queues, and LLM integrations.

---

## 🏗️ System Components Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        On-Premise Server                         │
│                                                                  │
│  ┌──────────────────┐        ┌───────────────────────────────┐  │
│  │   Admin Portal   │        │        Arkon API              │  │
│  │   (Next.js)      │──────▶ │        (FastAPI)              │  │
│  └──────────────────┘        │                               │  │
│                               │  /api/*   REST endpoints      │  │
│                               │  /mcp     MCP server          │  │
│                               │  /docs    Swagger UI          │  │
│                               └───────────────┬───────────────┘  │
│                                               │                  │
│  ┌────────────────┐  ┌──────────────┐        │                  │
│  │ Wiki Worker    │  │ Skill Worker │        │                  │
│  │ (arq)          │  │ (arq)        │        │                  │
│  │ · ingestion    │  │ · skill pkg  │        │                  │
│  │ · compilation  │  │   processing │        │                  │
│  └────────────────┘  └──────────────┘        │                  │
│                                               │                  │
│  ┌──────────────┐  ┌───────────┐  ┌────────┐│                  │
│  │  PostgreSQL  │  │   Redis   │  │ MinIO  ││                  │
│  │  + pgvector  │  │  (queue)  │  │(files) ││                  │
│  └──────────────┘  └───────────┘  └────────┘│                  │
└───────────────────────────────────────────────┼─────────────────┘
                                                │ MCP (HTTPS)
                               ┌────────────────┼────────────┐
                               │                │            │
                          Claude Desktop    Claude.ai    Any MCP
                          (employees)       (web)        client
```

---

## 📦 Component Breakdown

### 1. Admin Portal (`frontend/`)
A Next.js application that provides the web dashboard for administrators, editors, and viewers:
* Wiki content explorer and interactive knowledge graphs.
* Member and department directory.
* Workspace assignments and RBAC configuration.
* System configurations, AI providers settings, and API logs.

### 2. Arkon API Server (`app/`)
A FastAPI application that serves two primary pathways in parallel, defined in [main.py](file:///d:/workspace/src/truongnqse05461/arkon/app/main.py):
* **REST API (`/api/*`):** Used by the Admin Portal for authentication, metadata administration, document uploads, and draft workflow.
* **MCP Server (`/mcp`):** A FastMCP-based interface exposed to Claude. Exposes tools for reading and editing the wiki, drill-down into source documents, and executing custom AI Skills. Implements OAuth 2.1 + PKCE authentication.

### 3. Background Workers (`app/worker.py`)
Two Redis-based task queues run via `arq` to offload resource-intensive workloads:
* **Wiki Ingestion Worker:** Handles raw text/image extraction, triggers the parallel Map-Reduce compilation stages, generates pgvector embeddings, and executes automated AI checks on drafts. Defined in [worker.py](file:///d:/workspace/src/truongnqse05461/arkon/app/worker.py).
* **Skill Compilation Worker:** Builds and verifies custom AI skill packages.

### 4. Database & Storage Layer
* **PostgreSQL + pgvector:** Stores structured data (users, logs, drafts) and handles semantic text search via vector similarity checks.
* **Redis:** Coordinates the arq job queues.
* **MinIO:** An S3-compatible local bucket for storing source files (PDFs, images, docs) and uploaded skill zip packages.

---

## 🔄 Request Flow Diagrams

### 1. Document Upload and Wiki Ingestion
This shows how an uploaded file is parsed and compiled into the wiki:

```
[User Upload] ──► POST /api/sources/upload 
                        │
                        ▼
                Store raw file in MinIO
                Create DB Source entry (status=pending)
                Enqueue `ingest_file_task` in Redis
                        │
                        ▼
            [Worker: ingest_file_task]
                Extract text (pdfplumber/docx)
                Trigger Vision Model captioning for images
                Enqueue `ingest_map_reduce_task`
                        │
                        ▼
         [Worker: ingest_map_reduce_task]
             Phase 1 (MAP): Section chunking + extraction
             Phase 2 (REDUCE): Dedup entities + compile plan
                        │
                        ▼
               [Human Plan Review] (REST approval)
                        │
                        ▼
            [Worker: ingest_refine_task]
             Phase 3 (REFINE): Mini-agent page writing
             Phase 4 (VERIFY): Citation check & conflicts
             Phase 5 (COMMIT): Write to DB & Re-embed
```

### 2. Scoped MCP Queries
This details the pipeline when Claude queries Arkon:

```
[Claude Client] ──► POST /mcp (Bearer Token)
                          │
                          ▼
                Verify token & resolve identity
                (Check department + workspace access list)
                          │
                          ▼
                Execute tool (e.g., search_wiki)
                Apply pgvector search query
                Filter outputs to user scope list
                          │
                          ▼
                Return filtered matches to Claude
```

---

## 🔌 AI Provider Architecture
Arkon abstracts AI vendor specific API layouts via provider-agnostic wrappers located in [providers](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/providers/). Administrators can swap LLMs, Embedding models, or Vision tools directly through the UI settings.
* **Online Embedding Migration:** When changing embedding models (e.g. from Google to OpenAI), Arkon runs an online re-embedding routine that backfills the entire wiki database in the background, atomically swapping the active index only when 100% complete, preventing downtime.
