# Project Roadmap

This document outlines the completed features and the upcoming roadmap for Arkon.

---

## ✅ Completed Features

### 1. Ingestion & Core Compilation (MRP Pipeline)
* **Status:** Completed
* **Implementation:** [pipeline.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/mrp/pipeline.py)
* **Details:** Implemented the Map-Reduce-Plan-Refine-Verify-Commit pipeline with support for crash resume, image captioning, and human compilation plan reviews.

### 2. Model Context Protocol Integration (MCP Server)
* **Status:** Completed
* **Implementation:** [server.py](file:///d:/workspace/src/truongnqse05461/arkon/app/mcp/server.py)
* **Details:** Scoped tools for searching, reading, proposing edits, and reviewing wiki pages. Support for OAuth 2.1 with PKCE and manual Bearer authentication.

### 3. Workspaces & Access Control
* **Status:** Completed
* **Implementation:** [permission_engine.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/permission_engine.py)
* **Details:** Isolation of documents and wiki pages based on department scopes and workspace project memberships. Hierarchical RBAC for Viewer, Contributor, Editor, and Admin.

### 4. Review Console & Draft State Machine
* **Status:** Completed
* **Implementation:** [page.tsx](file:///d:/workspace/src/truongnqse05461/arkon/frontend/src/app/(portal)/wiki/review/page.tsx)
* **Details:** Dedicated side-by-side review panel supporting draft status loops (`pending`, `needs_revision`, `withdrawn`, `rejected`, `approved`), advisory lock guards, and keyboard shortcuts.

### 5. Multi-Model Support & Active Migrations
* **Status:** Completed
* **Implementation:** [llm_catalog.py](file:///d:/workspace/src/truongnqse05461/arkon/app/ai/llm_catalog.py)
* **Details:** Pluggable AI integration for Google Gemini, OpenAI, and Anthropic Claude. Online database embedding migration backfill support.

### 6. Audit Logging & Analytics
* **Status:** Completed
* **Implementation:** [audit.py](file:///d:/workspace/src/truongnqse05461/arkon/app/routers/audit.py)
* **Details:** Immutable activity log tracking all privileged actions. Usage analytics dashboard displaying workspace and token metrics.

---

## 📋 Upcoming Roadmap & TODOs

### 1. Rich Media & Bulk Spreadsheet Ingestion
* **Goal:** Extend the pipeline to swallow complete folders containing images, videos, and complex tables/Excel spreadsheets, stitching the visual context automatically.
* **Target:** Next minor release (`v0.8.0`).

### 2. External Cloud Data Connectors
* **Goal:** Build automated import scripts and integration connectors for SharePoint, Google Drive, Notion, and Confluence to keep Arkon's wiki in sync with legacy wikis.
* **Target:** Major release (`v1.0.0`).

### 3. Arkon CLI Utility
* **Goal:** A simplified, single-command command-line tool for employees to install and configure Arkon connectors locally (e.g. configuring Claude Desktop JSON configs).
* **Target:** Future enhancement.

### 4. In-App & Email Notification Dispatcher
* **Goal:** Complete email/webhooks integration to alert authors when edits require revision, and alert editors when plans or drafts are queued.
* **Under Development:** [notification_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/notification_service.py).
