"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface AgentConfigCardProps {
  label: string;
  config: string;
  description?: string;
}

export function AgentConfigCard({ label, config, description }: AgentConfigCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(config);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-2">
      {label && (
        <p className="text-sm font-medium text-foreground">{label}</p>
      )}
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <div className="relative">
        <div className="bg-[#3a302a] rounded-lg p-4 font-mono text-xs text-[#faf5ee] overflow-x-auto whitespace-pre">
          {config}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="absolute top-2 right-2 text-[#faf5ee]/70 hover:text-[#faf5ee] hover:bg-white/10"
        >
          <span className="material-symbols-outlined text-sm mr-1">
            {copied ? "check" : "content_copy"}
          </span>
          {copied ? "Copied!" : "Copy"}
        </Button>
      </div>
    </div>
  );
}
