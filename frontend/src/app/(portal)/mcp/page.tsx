"use client";

import { useState } from "react";
import { PageHeader } from "@/components/shared/page-header";
import { AuthTabs } from "@/components/mcp/auth-tabs";
import { TokenManagement } from "@/components/mcp/token-management";

export default function McpPage() {
  const [token, setToken] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <PageHeader title="MCP Integration" description="Connect AI agents to Arkon's knowledge base" />
      <AuthTabs token={token} />
      <TokenManagement onTokenGenerated={setToken} />
    </div>
  );
}
