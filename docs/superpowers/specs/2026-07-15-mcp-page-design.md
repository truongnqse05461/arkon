# MCP Integration Page

**Date:** 2026-07-15
**Status:** Draft

## Problem

MCP token management lives on `/profile`, connection config lives on the Dashboard, and there's no dedicated place for users to set up MCP integrations with AI agents. Users have to visit two different pages to get connected, and the Dashboard card is easy to miss.

## Goal

Create a standalone `/mcp` page that consolidates everything a user needs to connect AI agents to Arkon: auth method selection, per-agent config snippets with copy buttons, and token lifecycle management — all in one place.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Page location | Standalone `/mcp` route under System sidebar | Clean separation, discoverable, deep-linkable |
| Auth methods | Side-by-side tabs (Token + OAuth) | Token is universal, OAuth is Claude Desktop-optimized |
| Agent config | Per-agent tabs under Token Auth | Each agent has slightly different config format |
| Token management | Moved from `/profile` to `/mcp` | Consolidate all MCP concerns in one page |
| OAuth page | Dedicated tab, simpler config (no headers) | OAuth handles auth automatically |

## Scope

### Included

- Standalone `/mcp` page with sidebar nav
- Token Auth tab with per-agent config cards + copy buttons
- OAuth tab with Claude Desktop config + authorize button
- Token Management section (generate, show, copy, revoke, regenerate)
- Quick Start instructions
- Cleanup: remove `McpTokenCard` from `/profile`, `McpConnectionCard` from Dashboard

### Out of Scope

- No new backend endpoints (everything already exists)
- No token usage analytics or audit logging changes
- No multi-token support (one token per user, as-is)
- No team/org-level MCP config sharing
- No MCP server health monitoring UI

## Architecture

### Page Layout

```
┌─────────────────────────────────────────────────────┐
│  MCP Integration                                    │
│  Connect AI agents to Arkon's knowledge base        │
│                                                     │
│  ┌─────────────────────────────────────────────────┐│
│  │ [Token Auth]          [OAuth (Claude Desktop)]  ││
│  ├─────────────────────────────────────────────────┤│
│  │                                                 ││
│  │  (tab content here)                             ││
│  │                                                 ││
│  └─────────────────────────────────────────────────┘│
│                                                     │
│  ── Token Management ──────────────────────────────│
│  Status / Token / Actions                           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Token Auth Tab

Agent selector (pill buttons) + per-agent config JSON + copy button + Quick Start.

```
┌─────────────────────────────────────────────────────┐
│  Select your agent:                                 │
│  [Claude Code] [Claude Desktop] [Cursor] [Generic] │
│                                                     │
│  ┌─────────────────────────────────────────────────┐│
│  │  Config JSON                                    ││
│  │  ┌─────────────────────────────────────────┐   ││
│  │  │ {                                      │   ││
│  │  │   "mcpServers": {                      │   ││
│  │  │     "arkon": {                         │   ││
│  │  │       "url": "http://localhost:8000/mcp"│  ││
│  │  │       "headers": {                     │   ││
│  │  │         "Authorization": "Bearer ark_..."│ ││
│  │  │       }                                │   ││
│  │  │     }                                  │   ││
│  │  │   }                                    │   ││
│  │  │ }                                      │   ││
│  │  └─────────────────────────────────────────┘   ││
│  │  Server URL: http://localhost:8000/mcp [Copy]  ││
│  │                                      [Copy]   ││
│  └─────────────────────────────────────────────────┘│
│                                                     │
│  Quick Start                                        │
│  1. Generate a token in the section below           │
│  2. Copy the config above                           │
│  3. Add it to your agent's MCP settings file        │
│  4. Restart your agent                              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### OAuth Tab

Claude Desktop-specific. Simpler config (no headers — OAuth handles auth).

```
┌─────────────────────────────────────────────────────┐
│  Claude Desktop — OAuth 2.1 + PKCE                  │
│  No token copying needed. Authorize once and        │
│  Claude Desktop manages credentials automatically.  │
│                                                     │
│  ┌─────────────────────────────────────────────────┐│
│  │  Config JSON                                    ││
│  │  { "mcpServers": { "arkon": { "url": "..." }}} ││
│  │                                      [Copy]    ││
│  │                                                 ││
│  │  Status: Not connected  [Authorize with Claude] ││
│  └─────────────────────────────────────────────────┘│
│                                                     │
│  How it works                                       │
│  1. Copy the config above into Claude Desktop       │
│  2. Click "Authorize" — a browser window opens      │
│  3. Log in with your Arkon credentials              │
│  4. Claude Desktop receives an access token         │
│     automatically (no manual copy needed)           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Token Management

Always visible below the tabs. Both auth methods depend on having a token (OAuth resolves to one internally).

**Active state**:
```
Status: ● Active
Created: 2026-07-12
Token:   ark_••••••••••••••••  [Show] [Copy]

[Revoke Token]        [Regenerate Token]

⚠️ Regenerating invalidates all existing connections using this token.
```

**Empty state**:
```
Status: ○ No token
Generate a token to connect AI agents to Arkon.

[Generate Token]
```

## Agent Config Formats

Each agent option in the Token Auth tab renders a different JSON shape:

**Claude Code**:
```json
{
  "mcpServers": {
    "arkon": {
      "type": "url",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer ark_xxxxxxxxxxxx"
      }
    }
  }
}
```

**Claude Desktop** (token variant):
```json
{
  "mcpServers": {
    "arkon": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer ark_xxxxxxxxxxxx"
      }
    }
  }
}
```

**Cursor**:
```json
{
  "mcpServers": {
    "arkon": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer ark_xxxxxxxxxxxx"
      }
    }
  }
}
```

**Generic**:
```
URL:    http://localhost:8000/mcp
Header: Authorization: Bearer ark_xxxxxxxxxxxx
```

## API Endpoints (Existing)

No new endpoints. All functionality exists:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/my/mcp-token` | GET | Get token status (masked) |
| `/api/my/mcp-token` | POST | Generate/regenerate token |
| `/api/my/mcp-token` | DELETE | Revoke token |
| `/.well-known/oauth-authorization-server` | GET | OAuth metadata |
| `/oauth/register` | POST | Dynamic client registration |
| `/oauth/authorize` | GET | OAuth login form |
| `/oauth/token` | POST | Token exchange |

## Component Architecture

```
frontend/src/app/(portal)/mcp/page.tsx          ← page route
frontend/src/components/mcp/
├── mcp-page.tsx                                  ← main orchestrator
├── auth-tabs.tsx                                 ← Token Auth | OAuth tabs
├── token-auth-tab.tsx                            ← agent selector + config
├── oauth-tab.tsx                                 ← OAuth config + authorize
├── agent-config-card.tsx                         ← per-agent config JSON + copy
├── token-management.tsx                          ← generate/revoke/regenerate
└── quick-start.tsx                               ← step-by-step instructions
```

### Sidebar Change

Add entry in `sidebar.tsx` under the System section:

```tsx
{
  title: "MCP Integration",
  url: "/mcp",
  icon: "hub",
  requiredPermission: null,  // any authenticated user
}
```

## Error Handling

| Scenario | Handling |
|----------|----------|
| No token generated yet | Config shows placeholder `ark_xxxx` with note to generate first |
| Token revoked while viewing | "Token revoked" banner appears, prompt to generate new one |
| OAuth authorization fails | Error toast + "Try again" button; status stays "Not connected" |
| Copy to clipboard blocked | Fallback: select-all text; toast with manual copy instruction |
| Backend unreachable | Config still renders (static); status indicator shows "Offline" |

## Files to Create

- `frontend/src/app/(portal)/mcp/page.tsx`
- `frontend/src/components/mcp/mcp-page.tsx`
- `frontend/src/components/mcp/auth-tabs.tsx`
- `frontend/src/components/mcp/token-auth-tab.tsx`
- `frontend/src/components/mcp/oauth-tab.tsx`
- `frontend/src/components/mcp/agent-config-card.tsx`
- `frontend/src/components/mcp/token-management.tsx`
- `frontend/src/components/mcp/quick-start.tsx`

## Files to Modify

- `frontend/src/components/sidebar.tsx` — add "MCP Integration" nav item
- `frontend/src/app/(portal)/profile/page.tsx` — remove McpTokenCard
- `frontend/src/app/(portal)/page.tsx` — remove McpConnectionCard
