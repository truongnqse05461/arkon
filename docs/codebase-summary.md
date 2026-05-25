# Codebase Summary

This document provides a structured index of directories and files in the Arkon project, based on the codebase LOC report.

---

## 📊 Project Statistics Overview

* **Grand Total:** 277 files, 70,500 lines of code (LOC).
* **Backend (`app` + `alembic` + `skills`):** ~81 files, ~21,400 LOC.
* **Frontend (`frontend` excluding package-lock):** ~185 files, ~37,300 LOC.
* **Documentation (`docs` + root markdown files):** 18 files, ~4,126 LOC.

---

## 📁 Directory Structure & File Index

### 1. Backend Application (`app/`)
The FastAPI server is organized into logical layers: database schemas, API routers, business services, AI orchestration (MRP pipeline), and MCP endpoints.

* **Main App Config & Execution:**
  * [app/main.py](file:///d:/workspace/src/truongnqse05461/arkon/app/main.py) (267 LOC) — Entry point. Configures CORS, mounts routers, lifespan, and handles system health checks.
  * [app/config.py](file:///d:/workspace/src/truongnqse05461/arkon/app/config.py) (88 LOC) — Configuration engine using `pydantic-settings`.
  * [app/worker.py](file:///d:/workspace/src/truongnqse05461/arkon/app/worker.py) (1,135 LOC) — Background job definitions (ARQ workers) for ingestion and cron tasks.

* **Database Layer (`app/database/`):**
  * [app/database/models.py](file:///d:/workspace/src/truongnqse05461/arkon/app/database/models.py) (1,243 LOC) — Core database entities (SQLAlchemy ORM) including `sources`, `wiki_pages`, `employees`, and `projects`.
  * [app/database/repository.py](file:///d:/workspace/src/truongnqse05461/arkon/app/database/repository.py) (72 LOC) — Base repository methods.
  * [app/database/oauth_models.py](file:///d:/workspace/src/truongnqse05461/arkon/app/database/oauth_models.py) (58 LOC) — OAuth clients, grants, and codes.

* **API Routers (`app/routers/`):**
  * [app/routers/wiki_drafts.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/wiki_drafts.py) (1,159 LOC) — Draft workflow routing.
  * [app/routers/projects.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/projects.py) (1,001 LOC) — Workspace CRUD and member/source associations.
  * [app/routers/sources.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/sources.py) (799 LOC) — Ingestion upload triggers.
  * [app/routers/wiki.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/wiki.py) (714 LOC) — Page viewing and history routes.
  * [app/routers/skills.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/skills.py) (502 LOC) — AI Skills package upload.
  * [app/routers/rbac.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/rbac.py) (411 LOC) — Department and employee listings.

* **Business Services (`app/services/`):**
  * [app/services/wiki_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/wiki_service.py) (1,053 LOC) — Page modification, draft approvals, advisory locks.
  * [app/services/skill_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/skill_service.py) (1,013 LOC) — Processing and storage of custom skill packages.
  * [app/services/mcp_auth_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/mcp_auth_service.py) (405 LOC) — Token validation.
  * [app/services/permission_engine.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/permission_engine.py) (300 LOC) — Checks RBAC scope levels.
  * [app/services/storage_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/storage_service.py) (257 LOC) — S3/MinIO upload wrapper.

* **AI & Ingestion (`app/ai/`):**
  * [app/ai/wiki_compiler.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/wiki_compiler.py) (712 LOC) — Compiler wrappers.
  * [app/ai/llm_catalog.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/llm_catalog.py) (214 LOC) — Supported model providers definitions.
  * **MRP Pipeline (`app/ai/mrp/`):**
    * [app/ai/mrp/writer.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/writer.py) (876 LOC) — Mini-agent writing page routines (Phase 3).
    * [app/ai/mrp/reducer.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/reducer.py) (688 LOC) — Entity deduplication and KB reconciliation (Phase 2).
    * [app/ai/mrp/pipeline.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/pipeline.py) (508 LOC) — Ingestion sequence orchestrator.
    * [app/ai/mrp/mapper.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/mapper.py) (459 LOC) — Document triage and parallel LLM extraction (Phase 0-1).
    * [app/ai/mrp/verifier.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/verifier.py) (175 LOC) — Coverage and conflict checks (Phase 4).

* **Model Context Protocol (`app/mcp/`):**
  * [app/mcp/tools.py](file:///d:/workspace/src/truongnqse05461/arkon/app/mcp/tools.py) (1,834 LOC) — Exposed MCP tools.
  * [app/mcp/server.py](file:///d:/workspace/src/truongnqse05461/arkon/app/mcp/server.py) (70 LOC) — FastMCP instantiation.

---

### 2. Frontend (`frontend/src/`)
Next.js 16 (App Router) using React 19, Tailwind CSS v4, and Shadcn UI components.

* **Pages (`frontend/src/app/(portal)/`):**
  * `wiki/review/page.tsx` (938 LOC) — Three-panel wiki review dashboard.
  * `wiki/[...slug]/page.tsx` (550 LOC) — Wiki page content viewer with sidebars.
  * `audit/page.tsx` (102 LOC) — Scopes and policy decision logger.
  * `workspaces/[id]/page.tsx` (88 LOC) — Workspace details viewer.

* **UI Components (`frontend/src/components/`):**
  * **Wiki Components (`wiki/`):** Tree navigations, markdown editor, backlinks viewer, and scope switcher.
  * **Skills Components (`skills/`):** Skill table lists, file explorers, uploads, and tag dialogs.
  * **Workspace details (`projects/project-detail/`):** Member roster tabs, source document tabs, and candidate selectors.
  * **UI primitives (`ui/`):** Standard components including cards, buttons, dropdowns, tables, and tabs.

---

### 3. Database Schema Migrations (`alembic/`)
Contains Alembic configuration and versions tracking schema evolution.
* Main migrations are under `alembic/versions/` (versions `001_initial_schema.py` to `027_hash_mcp_tokens.py`).

---

### 4. Custom AI Skills Packages (`skills/`)
Pre-bundled capabilities loaded into the database:
* `skills/arkon-edit/` (153 LOC) — Propose/edit wiki scripts.
* `skills/arkon-review/` (136 LOC) — Draft review controls.
* `skills/arkon-query/` (96 LOC) — Search-focused script wrapper.
