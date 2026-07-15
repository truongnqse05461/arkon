"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { AgentConfigCard } from "./agent-config-card";
import { QuickStart } from "./quick-start";

type Agent = {
  id: string;
  label: string;
  config: string;
  description: string;
};

const MCP_URL = typeof window !== "undefined"
  ? `${window.location.origin}/mcp`
  : "http://localhost:8000/mcp";

function buildAgents(token: string): Agent[] {
  const bearer = `Bearer ${token}`;

  return [
    {
      id: "claude-code",
      label: "Claude Code",
      config: JSON.stringify(
        {
          mcpServers: {
            arkon: {
              type: "url",
              url: MCP_URL,
              headers: { Authorization: bearer },
            },
          },
        },
        null,
        2
      ),
      description: "Claude Code CLI — uses url type with headers",
    },
    {
      id: "claude-desktop",
      label: "Claude Desktop",
      config: JSON.stringify(
        {
          mcpServers: {
            arkon: {
              url: MCP_URL,
              headers: { Authorization: bearer },
            },
          },
        },
        null,
        2
      ),
      description: "Claude Desktop app — standard MCP config",
    },
    {
      id: "cursor",
      label: "Cursor",
      config: JSON.stringify(
        {
          mcpServers: {
            arkon: {
              url: MCP_URL,
              headers: { Authorization: bearer },
            },
          },
        },
        null,
        2
      ),
      description: "Cursor IDE — MCP settings in project config",
    },
    {
      id: "generic",
      label: "Generic",
      config: `URL:    ${MCP_URL}\nHeader: ${bearer}`,
      description: "Any MCP-compatible client — use URL and header directly",
    },
  ];
}

interface TokenAuthTabProps {
  token: string | null;
}

export function TokenAuthTab({ token }: TokenAuthTabProps) {
  const [selectedAgent, setSelectedAgent] = useState("claude-code");
  const agents = buildAgents(token || "ark_xxxxxxxxxxxx");
  const activeAgent = agents.find((a) => a.id === selectedAgent) || agents[0];

  return (
    <div className="space-y-6">
      {/* Agent selector */}
      <div>
        <p className="text-sm text-muted-foreground mb-3">Select your agent:</p>
        <div className="flex flex-wrap gap-2">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent.id)}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-colors border",
                selectedAgent === agent.id
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background text-muted-foreground border-border hover:text-foreground hover:border-foreground/20"
              )}
            >
              {agent.label}
            </button>
          ))}
        </div>
      </div>

      {/* Config display */}
      <AgentConfigCard
        label={activeAgent.label}
        config={activeAgent.config}
        description={activeAgent.description}
      />

      {/* No token warning */}
      {!token && (
        <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
          Generate a token in the Token Management section below to get a real config.
        </p>
      )}

      {/* Quick start */}
      <QuickStart />
    </div>
  );
}
