# Enhancement Roadmap: Chat, Wiki, Mindmap, Document Ingestion

> Verified against local `stdev` at `8618433` on 2026-07-02. Scope excludes Workspace-only feedback (homepage, nested workspace, view modes, pinning).

## Objective

Turn document ingestion into a trustworthy intake flow, make Wiki review easier to control, make Mindmap actionable, and let Chat use fresh external knowledge without bypassing Arkon scope and provenance controls.

## Feedback verification

| Feedback | Verified state | Decision | Priority |
|---|---|---|---|
| Required metadata when uploading documents | **Valid gap.** Upload requires only one file. Knowledge type, departments, target workspace, and translation are optional; title defaults to filename. | Add configurable metadata policy by scope/knowledge type. Require at minimum title, knowledge type, and explicit visibility confirmation. | P0 |
| Upload multiple documents | **Valid gap.** Both global and workspace dialogs keep one `File`; API accepts one `UploadFile`. | Add batch intake with per-file validation, shared defaults, per-file override, bounded concurrency, and partial-failure results. | P0 |
| Online source / Google Drive / crawl URL | **Partially implemented.** URL ingestion endpoints and `Source.url` exist, but primary upload UI exposes file only. No Drive sync connector found. | Ship one-shot URL import first. Build versioned connector sync separately; do not label URL import as a connector. | P1 |
| Link back to uploaded original | **Mostly implemented.** Source detail API emits a presigned `download_url`; Chat citation panel shows **Download original**. Documents list/detail does not expose it consistently. | Reuse the existing API. Add View original / Open source actions to all document surfaces, with permission and expiry handling. | P0 quick win |
| Approve/reject each concept in compilation plan | **Valid gap.** Review UI is read-only per planned page and supports whole-plan approve/reject/regenerate. API approval accepts only a note. | Use page-level decisions (`include`, `exclude`, `edit`) rather than concept-level state. Persist reviewed plan snapshot and compile only included pages. | P1 |
| Native Jira/Confluence/GitLab connectors and browser extension for Chat | **Valid gap, oversized proposal.** Chat tools currently query Arkon Wiki/Documents only. | Connect external systems through ingestion/sync first; Chat remains retrieval over authorized Arkon data. Add live connector tools only for use cases requiring real-time data. Browser extension stays later and read-only first. | P2/P3 |
| Mindmap “Suggest link” creates backlink task and map reflects it | **Valid gap.** Mindmap is a cached AI-generated name tree. Clicking a node only seeds `Explain about "…"` in Chat. No durable page identity, suggestion, or backlink task exists. | Add page-backed nodes, link candidates with evidence, human approval, Wiki draft creation, then invalidate/regenerate affected map. Never auto-write backlinks. | P1 |
| Tooltips explaining Document vs Wiki and Entity/Concept/Topic | **Valid UX gap.** Type labels and filters exist, but no shared in-product glossary was found. | Add contextual glossary/tooltips in upload, plan review, Wiki filters, create page, and Mindmap. | P0 quick win |

## Product principles

- **One knowledge path:** external source -> Document -> reviewed compilation -> Wiki -> Mindmap/Chat.
- **Provenance stays visible:** every Chat answer and Wiki claim can reach its source or original file.
- **Human approval for structural changes:** connector sync, plan exclusions, and suggested links are reviewable and auditable.
- **Partial failure, not batch failure:** one bad upload or connector item must not discard successful items.
- **Scope first:** permissions applied before retrieval, sync, preview, download, and link suggestions.

## Delivery roadmap

### Phase 0 — Baseline and contracts (P0, 1 sprint)

**Outcome:** measurable flows and stable contracts before UI expansion.

- Define ingestion batch states: queued, extracting, awaiting approval, plan review, compiling, ready, failed.
- Define required metadata policy and defaults per global/workspace scope.
- Add events and metrics: upload success, time-to-ready, plan rejection/exclusion rate, source-open rate, Chat citation-open rate, Mindmap suggestion acceptance.
- Add a shared glossary contract for Document, Wiki, Entity, Concept, Topic, Source page, and Mindmap.

**Exit criteria**

- Product owner approves metadata policy and glossary.
- Existing single-file and URL API behavior remains backward compatible.
- Metrics distinguish file, URL, and connector sources.

### Phase 1 — Document intake and provenance (P0, 2–3 sprints)

**Outcome:** users can submit many well-described sources and always return to originals.

- Add multi-file drag/drop and picker with a batch review table.
- Apply shared metadata defaults, then allow per-file title/type/scope override.
- Validate type, size, duplicate fingerprint, metadata, and scope before enqueue.
- Upload with bounded parallelism; return per-file progress, retry, cancel, and error.
- Add one-shot URL import to the same intake surface with SSRF protection, redirect limits, content-size/type limits, timeout, and canonical URL deduplication.
- Add **View original** for file sources and **Open source URL** for URL sources in Documents table/detail, workspace sources, review plan, and Chat citation panel.
- Preserve source filename, URL, checksum, connector identity, sync version, and ingestion timestamp.

**Exit criteria**

- A 20-file batch reports success/failure independently and retries only failed items.
- Required metadata cannot be bypassed through UI or API.
- Users with access can open the original from every source-bearing surface; unauthorized users cannot obtain a presigned URL.
- URL importer blocks private/link-local targets and records final canonical URL.

### Phase 2 — Wiki comprehension and compilation control (P0/P1, 2 sprints)

**Outcome:** reviewers understand the knowledge model and control what compilation writes.

- Ship shared glossary tooltips and first-use guidance across Document/Wiki flows.
- Replace read-only compilation cards with page decisions: include, exclude with reason, edit title/slug/type/action, reorder.
- Persist original AI plan plus reviewer-approved immutable snapshot for audit/resume.
- Validate duplicate slugs, empty plans, invalid types, scope changes, and concurrent review.
- Show source evidence/entity coverage before exclusion.
- Compile included pages only; regenerate index/log and record skipped coverage warnings.

**Exit criteria**

- Reviewer can exclude one planned page without regenerating or rejecting the whole plan.
- Resume after worker restart uses the exact approved snapshot.
- Audit log identifies AI proposal, reviewer edits, exclusions, and compiled result.

### Phase 3 — Actionable Mindmap (P1, 2–3 sprints)

**Outcome:** Mindmap becomes a reviewed navigation and knowledge-quality surface, not only an AI picture.

- Change tree nodes from display names to stable Wiki references: slug, page type, scope, label, confidence.
- Add node preview and navigation while preserving “Ask Chat about this node”.
- Generate **Suggest link** candidates using graph distance, semantic similarity, shared sources, and textual evidence.
- Show why a link is suggested and its direction; deduplicate existing wikilinks.
- Accepting a suggestion creates a Wiki draft/task, not a direct edit. Rejection stores feedback to reduce repeat suggestions.
- On draft approval, refresh Wiki links and invalidate/regenerate only affected scoped Mindmap cache.

**Exit criteria**

- Every actionable node resolves to an authorized Wiki page.
- No suggestion directly changes published Wiki content.
- Approved backlink appears in Wiki graph and the regenerated Mindmap; rejected suggestions do not immediately recur.

### Phase 4 — Connector ingestion and Chat freshness (P2, 3–5 sprints per connector family)

**Outcome:** Chat answers from synchronized enterprise sources while retaining Arkon authorization and citations.

- Build a generic connector contract: account, cursor, item identity, revision, ACL mapping, tombstone, retry, rate-limit, and health state.
- Start with one connector family based on customer evidence; recommended order: Google Drive, Confluence, then Jira/GitLab.
- Support initial import, incremental sync, deletion/tombstone handling, conflict policy, and manual re-sync.
- Normalize connector items into `Source`; reuse extraction, plan review, Wiki compilation, and provenance.
- Extend Chat citations with connector name, source revision, last synced time, and stale-data warning.
- Add live Chat tools only when synchronized data cannot meet freshness requirements; enforce the same scope and audit layer.

**Exit criteria**

- Incremental sync is idempotent and does not duplicate Wiki pages for unchanged items.
- Removed access propagates before subsequent Chat retrieval.
- Every connector-backed answer exposes source revision and sync freshness.
- Connector outage degrades to last known indexed data with an explicit stale warning.

### Phase 5 — Browser capture extension (P3, after connector model stabilizes)

**Outcome:** users can deliberately capture web knowledge into Arkon without turning the extension into a second Chat platform.

- Read-only capture first: page URL, title, selected text/full article, workspace, knowledge type.
- Preview and redact before upload; never capture credentials, hidden DOM, or unrelated tabs.
- Route captures through the same URL/document ingestion and review pipeline.
- Defer in-extension Chat until capture adoption and security posture are proven.

## Dependencies and sequencing

1. Metadata/provenance contracts precede batch upload and connectors.
2. Reviewed plan snapshots precede fine-grained approval and reliable resume.
3. Stable Wiki page identity precedes actionable Mindmap suggestions.
4. Connector ingestion precedes connector-aware Chat; Browser extension reuses connector/source contracts.

## Suggested ownership boundaries

| Stream | Primary areas |
|---|---|
| Document ingestion | `app/routers/sources.py`, worker/ingestion services, storage, upload dialogs, source tables |
| Wiki review | compilation plan schema/router, MRP reducer/writer/pipeline, plan review UI, audit |
| Mindmap | `mindmap_service`, router/schema, Mindmap tree/panel, Wiki draft/link services |
| Chat/connectors | connector adapters/sync jobs, `chat_agent`, citation UI, permission engine |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Bulk uploads overload workers/LLM budget | Admission limits, bounded concurrency, queue visibility, per-tenant quotas |
| URL ingestion enables SSRF or oversized downloads | DNS/IP validation before and after redirects, allowlisted schemes, byte/time limits |
| Fine-grained plan edits break resume determinism | Immutable approved snapshot with version and checksum |
| Suggested links pollute Wiki structure | Evidence threshold, human-reviewed draft, rejection memory, audit trail |
| Connector ACL drift leaks data | Deny by default, ACL sync before content availability, periodic reconciliation |
| Chat mixes stale and current facts | Source revision/freshness metadata and visible stale warnings |

## Success metrics

- >= 95% valid files in a batch reach queued state without re-entry.
- >= 99% source previews/downloads resolve for authorized users during URL lifetime.
- Median reviewer time per compilation plan decreases by 30%.
- >= 80% of published Chat factual answers contain at least one resolvable citation.
- >= 30% acceptance for surfaced Mindmap link suggestions after tuning; < 5% repeated rejected suggestions.
- >= 99% connector sync jobs are idempotent across retry; zero confirmed cross-scope retrieval incidents.

## Evidence in current code

- Single-file upload and optional metadata: [`upload-dialog.tsx`](../frontend/src/components/knowledge/upload-dialog.tsx), [`sources.py`](../app/routers/sources.py)
- URL ingestion backend: [`sources.py`](../app/routers/sources.py), [`projects.py`](../app/routers/projects.py)
- Original-file presigned URL: [`storage_service.py`](../app/services/storage_service.py), [`citation-panel.tsx`](../frontend/src/components/chat/citation-panel.tsx)
- Whole-plan review flow: [`plan-review-dialog.tsx`](../frontend/src/components/knowledge/knowledge-table/plan-review-dialog.tsx), [`sources.py`](../app/routers/sources.py)
- Arkon-only Chat tools and attachments: [`chat_agent.py`](../app/services/chat_agent.py), [`attachment-picker.tsx`](../frontend/src/components/chat/attachment-picker.tsx)
- Generated Mindmap and node-to-Chat behavior: [`mindmap_service.py`](../app/services/mindmap_service.py), [`mindmap-panel.tsx`](../frontend/src/components/chat/mindmap-panel.tsx), [`chat-area.tsx`](../frontend/src/components/chat/chat-area.tsx)

## Unresolved questions

- Which metadata fields are mandatory globally versus configurable per knowledge type?
- Which connector has the first committed customer and required freshness SLA?
- Should plan exclusions suppress a page only for this source, or also flag existing related Wiki pages for follow-up?
- Who reviews Mindmap-generated Wiki drafts: existing Wiki editors or a dedicated knowledge steward role?
