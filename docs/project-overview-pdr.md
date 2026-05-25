# Project Overview & Product Requirements (PDR)

Arkon is a self-hosted, enterprise-grade knowledge management layer that bridges organizational data and AI clients. It runs as a centralized Model Context Protocol (MCP) server, compiling standard operating procedures (SOPs), policies, and internal docs into a structured, traceable knowledge wiki - then serving that wiki to Claude and other LLMs through a single permission-scoped endpoint.

---

## 🎯 Product Goals & Problem Statement

In most organizations, AI adoption is fragmented. Employees copy-paste sensitive documents into external chat interfaces, leading to:
1. **Security & Compliance Risks:** Leaking internal IPs or private data.
2. **Inconsistent Context:** Different bots receiving outdated or inconsistent information.
3. **Duplicated Work:** Employees separately compiling context for the same tasks.
4. **Lack of Scope Enforcement:** No mechanism to prevent low-privileged employees from feeding restricted company documents (e.g. HR files, financial forecasts) to public LLMs.

**Arkon treats AI as a managed organizational resource.** It guarantees that every employee gets the correct context automatically and securely—filtered by their department, project membership, and role.

---

## 👥 Target Audiences

1. **System Administrators:** Who configure corporate AI providers, manage workspaces, and oversee RBAC settings.
2. **Knowledge Editors:** Who review and approve compilation plans and write/edit wiki pages.
3. **General Employees (Viewers/Contributors):** Who consume the compiled knowledge through their AI chat client (e.g. Claude Desktop) or propose edits directly via the wiki.

---

## ✨ Key Features & Capabilities

### 1. The MRP Ingestion Pipeline
Unlike traditional Retrieval-Augmented Generation (RAG) that simply chunks and indexes text, Arkon's Map-Reduce-Plan-Refine-Verify (**MRP**) pipeline compiles documents into a coherent wiki of interlinked pages.
* **Map Phase:** Parallelized LLM chunk extraction.
* **Reduce Phase:** Entity deduplication and KB reconciliation.
* **Plan Review:** Editors review and approve compile plans.
* **Refine Phase:** Page content generation with mini-agent writers.
* **Verify Phase:** Citation checks, coverage analysis, and conflict verification.
* **Commit Phase:** Atomic database persistence with pgvector updates.

This pipeline is defined in [pipeline.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/pipeline.py).

### 2. Scoped Workspaces (Departments & Projects)
Provides workspace isolation for department-level data (e.g., HR, Engineering, Legal) or cross-functional projects.
* **Scope Isolation:** Members can only query or search documents/wiki pages within their authorized scopes.
* **Hard Enforcement:** Enforced across REST API, pgvector search, and MCP endpoints.

### 3. Fine-Grained Role-Based Access Control (RBAC)
Dual-realm permission system managing system-wide roles (Viewer, Contributor, Admin) and project-specific roles (Viewer, Contributor, Editor, Admin).
* RBAC logic is located in [permission_engine.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/permission_engine.py).
* Permissions are defined in [permissions.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/permissions.py).

### 4. Scoped MCP Server
Integrates directly with Claude Desktop and Claude.ai via Model Context Protocol, exposing wiki search, page readings, draft proposals, and review tools.
* Auth uses **OAuth 2.1 + PKCE** or Bearer tokens.
* Server is created in [server.py](file:///d:/workspace/src/truongnqse05461/arkon/app/mcp/server.py).
* Scoped tools are defined in [tools.py](file:///d:/workspace/src/truongnqse05461/arkon/app/mcp/tools.py).

### 5. Custom AI Skills Distribution
Upload and distribute custom agent packages (.zip format containing `SKILL.md`) scoped to specific departments or workspaces.
* Defined in [skill_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/skill_service.py).

---

## 🔒 Security & Privacy Requirements

* **Self-Hosted Deployment:** Fully run on-premise or inside private clouds (AWS, GCP, etc.) via Docker Compose.
* **Zero Telemetry:** No data leaves the organization except for direct API calls to selected AI providers.
* **Encryption at Rest:** Sensitive credentials (like API keys) are Fernet-encrypted inside PostgreSQL.
* **OAuth 2.1 + PKCE:** Secure authentication for employees connecting Claude without sharing plaintext database tokens.
* **Token Hashing at Rest:** Plaintext MCP tokens are hashed using HMAC-SHA256 in the database [models.py](file:///d:/workspace/src/truongnqse05461/arkon/app/database/models.py).
