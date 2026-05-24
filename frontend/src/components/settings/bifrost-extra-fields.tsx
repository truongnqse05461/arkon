"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type BifrostFields = {
  baseUrl: string;
  modelId: string;
  fallbacks: string[];
};

export function BifrostExtraFields({
  capability,
  baseUrl,
  modelId,
  fallbacks,
  onChange,
}: {
  capability: "llm" | "vision";
  baseUrl: string;
  modelId: string;
  fallbacks: string[];
  onChange: (patch: Partial<BifrostFields>) => void;
}) {
  function updateFallback(index: number, value: string) {
    const next = [...fallbacks];
    next[index] = value;
    onChange({ fallbacks: next });
  }

  function removeFallback(index: number) {
    onChange({ fallbacks: fallbacks.filter((_, i) => i !== index) });
  }

  function addFallback() {
    onChange({ fallbacks: [...fallbacks, ""] });
  }

  return (
    <div className="flex flex-col gap-4 mb-4">
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Gateway Base URL</Label>
        <Input
          type="text"
          value={baseUrl}
          onChange={(e) => onChange({ baseUrl: e.target.value })}
          placeholder="https://gateway.mycompany.com"
          className="bg-background"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Primary Model</Label>
        <Input
          type="text"
          value={modelId}
          onChange={(e) => onChange({ modelId: e.target.value })}
          placeholder={capability === "llm" ? "gpt-4o-mini" : "gpt-4o"}
          className="bg-background"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">
          Fallback Models{" "}
          <span className="text-muted-foreground">(optional)</span>
        </Label>
        {fallbacks.map((fb, i) => (
          <div key={i} className="flex gap-2 items-center">
            <Input
              type="text"
              value={fb}
              onChange={(e) => updateFallback(i, e.target.value)}
              placeholder="anthropic/claude-3-5-sonnet"
              className="bg-background flex-1"
            />
            <button
              type="button"
              onClick={() => removeFallback(i)}
              className="text-muted-foreground hover:text-destructive px-2 text-base leading-none"
              aria-label="Remove fallback"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={addFallback}
          className="text-xs text-primary hover:underline self-start mt-0.5"
        >
          + Add fallback
        </button>
      </div>
    </div>
  );
}
