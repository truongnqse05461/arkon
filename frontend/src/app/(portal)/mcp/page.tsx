"use client";

import { TokenManagement } from "@/components/mcp/token-management";

export default function McpPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          MCP Integration
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Connect AI agents to Arkon&apos;s knowledge base
        </p>
      </div>
      <TokenManagement />
    </div>
  );
}
