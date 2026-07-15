"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { AgentConfigCard } from "./agent-config-card";

const MCP_URL = typeof window !== "undefined"
  ? `${window.location.origin}/mcp`
  : "http://localhost:8000/mcp";

export function OAuthTab() {
  const [authStatus, setAuthStatus] = useState<"idle" | "authorizing">("idle");

  const oauthConfig = JSON.stringify(
    {
      mcpServers: {
        arkon: {
          url: MCP_URL,
        },
      },
    },
    null,
    2
  );

  const handleAuthorize = () => {
    setAuthStatus("authorizing");
    // Open the OAuth authorize endpoint in a new tab
    const authorizeUrl = `${window.location.origin}/oauth/authorize`;
    window.open(authorizeUrl, "_blank");
    // Reset status after a delay (the actual OAuth flow happens in the new tab)
    setTimeout(() => setAuthStatus("idle"), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-foreground">
          Claude Desktop — OAuth 2.1 + PKCE
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          No token copying needed. Authorize once and Claude Desktop manages
          credentials automatically.
        </p>
      </div>

      {/* Config */}
      <AgentConfigCard
        label="Claude Desktop OAuth"
        config={oauthConfig}
        description="Simpler config — OAuth handles authentication automatically"
      />

      {/* Authorize button */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full bg-muted-foreground/30" />
          <span className="text-muted-foreground">Not connected</span>
        </div>
        <Button onClick={handleAuthorize} disabled={authStatus === "authorizing"}>
          <span className="material-symbols-outlined text-sm mr-1">open_in_new</span>
          {authStatus === "authorizing" ? "Opening..." : "Authorize with Claude"}
        </Button>
      </div>

      {/* How it works */}
      <div className="bg-card rounded-xl p-6 border border-border shadow-sahara">
        <h4 className="text-sm font-semibold text-foreground mb-3">How it works</h4>
        <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
          <li>Copy the config above into Claude Desktop</li>
          <li>Click &quot;Authorize&quot; — a browser window opens</li>
          <li>Log in with your Arkon credentials</li>
          <li>
            Claude Desktop receives an access token automatically (no manual copy
            needed)
          </li>
        </ol>
      </div>
    </div>
  );
}
