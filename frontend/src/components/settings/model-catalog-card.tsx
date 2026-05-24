"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { BifrostExtraFields } from "@/components/settings/bifrost-extra-fields";

// Shape shared by LLMSpecOut and VisionSpecOut on the backend. Cards pick which
// fields to display via the `renderMeta` prop so this component stays generic.
export type ModelSpec = {
  id: string;
  provider: string;
  model_id: string;
  label: string;
  notes: string | null;
  api_key_configured: boolean;
  // LLM-specific
  context_window_tokens?: number;
  max_output_tokens?: number;
  supports_tools?: boolean;
  supports_vision?: boolean;
  cost_per_1m_input_tokens?: number | null;
  cost_per_1m_output_tokens?: number | null;
  // Vision-specific
  max_image_size_mb?: number;
  cost_per_image?: number | null;
};

type CatalogResp = {
  active_spec_id: string | null;
  specs: ModelSpec[];
};

export function ModelCatalogCard({
  title,
  description,
  icon,
  catalogUrl,
  switchUrl,
  capability,
  renderMeta,
}: {
  title: string;
  description: string;
  icon: string;
  catalogUrl: string;
  switchUrl: string;
  /** "llm" | "vision" — determines which config keys to read/write */
  capability: "llm" | "vision";
  renderMeta?: (spec: ModelSpec) => React.ReactNode;
}) {
  const [catalog, setCatalog] = useState<CatalogResp | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  // Per-provider masked keys, e.g. {"google": "••••••••P258"}.
  const [maskedKeys, setMaskedKeys] = useState<Record<string, string>>({});
  const [apiKey, setApiKey] = useState<string>("");
  const [customModelId, setCustomModelId] = useState<string>("");
  const [customBaseUrl, setCustomBaseUrl] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [bifrostBaseUrl, setBifrostBaseUrl] = useState<string>("");
  const [bifrostModelId, setBifrostModelId] = useState<string>("");
  const [bifrostFallbacks, setBifrostFallbacks] = useState<string[]>([]);

  const customModelKey = `${capability}_custom_model_id`;
  const customBaseUrlKey = `${capability}_base_url`;
  const bifrostBaseUrlKey = `${capability}_bifrost_base_url`;
  const bifrostModelIdKey = `${capability}_bifrost_model_id`;
  const bifrostFallbacksKey = `${capability}_bifrost_fallbacks`;

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When the user picks a different model, prefill the input with that
  // provider's masked key (or empty if none saved).
  useEffect(() => {
    const provider = catalog?.specs.find((s) => s.id === selected)?.provider;
    setApiKey(provider ? maskedKeys[provider] ?? "" : "");
  }, [selected, maskedKeys, catalog]);

  async function refresh() {
    try {
      const [c, settings] = await Promise.all([
        api<CatalogResp>(catalogUrl),
        api<Record<string, unknown>>("/api/settings"),
      ]);
      setCatalog(c);

      const masked: Record<string, string> = {};
      for (const provider of new Set(c.specs.map((sp) => sp.provider))) {
        const v = settings[`${capability}_api_key__${provider}`];
        if (typeof v === "string" && v.length > 0) masked[provider] = v;
      }
      setMaskedKeys(masked);

      const cId = settings[customModelKey];
      const bUrl = settings[customBaseUrlKey];
      setCustomModelId(typeof cId === "string" ? cId : "");
      setCustomBaseUrl(typeof bUrl === "string" ? bUrl : "");

      const bBase = settings[bifrostBaseUrlKey];
      const bModel = settings[bifrostModelIdKey];
      const bFallbacksRaw = settings[bifrostFallbacksKey];
      setBifrostBaseUrl(typeof bBase === "string" ? bBase : "");
      setBifrostModelId(typeof bModel === "string" ? bModel : "");
      try {
        setBifrostFallbacks(
          typeof bFallbacksRaw === "string" && bFallbacksRaw
            ? (JSON.parse(bFallbacksRaw) as string[])
            : []
        );
      } catch (_e) {
        setBifrostFallbacks([]);
      }

      setSelected((prev) => prev ?? c.active_spec_id ?? c.specs[0]?.id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : `Failed to load ${title}`);
    }
  }

  const selectedSpec = catalog?.specs.find((s) => s.id === selected) ?? null;
  const isActiveSelected = selectedSpec?.id === catalog?.active_spec_id;
  const willSwitch = !!selectedSpec && !isActiveSelected;
  const isMaskedKey = apiKey.includes("•");
  const hasNewKey = apiKey.trim().length > 0 && !isMaskedKey;
  const isBifrost = selectedSpec?.id === "custom/bifrost";
  const isCustom = !!selectedSpec?.id.startsWith("custom/") && !isBifrost;
  const canSave =
    !!selectedSpec &&
    (!isCustom || (customModelId.trim().length > 0 && customBaseUrl.trim().length > 0)) &&
    (!isBifrost || (bifrostModelId.trim().length > 0 && bifrostBaseUrl.trim().length > 0)) &&
    (
      hasNewKey ||
      (willSwitch && selectedSpec.api_key_configured) ||
      isCustom ||
      isBifrost
    );

  async function handleSave() {
    if (!selectedSpec) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const settingsUpdates: Record<string, string> = {};
      if (hasNewKey) {
        settingsUpdates[`${capability}_api_key__${selectedSpec.provider}`] = apiKey.trim();
      }
      if (isCustom) {
        settingsUpdates[customModelKey] = customModelId.trim();
        settingsUpdates[customBaseUrlKey] = customBaseUrl.trim();
      }
      if (isBifrost) {
        settingsUpdates[bifrostBaseUrlKey] = bifrostBaseUrl.trim();
        settingsUpdates[bifrostModelIdKey] = bifrostModelId.trim();
        settingsUpdates[bifrostFallbacksKey] = JSON.stringify(
          bifrostFallbacks.filter((f) => f.trim().length > 0)
        );
      }

      if (Object.keys(settingsUpdates).length > 0) {
        await api("/api/settings", {
          method: "PUT",
          body: { settings: settingsUpdates },
        });
      }

      if (willSwitch) {
        await api(switchUrl, {
          method: "POST",
          body: { model_spec_id: selectedSpec.id },
        });
      }
      await refresh();
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!catalog) {
    return (
      <div className="bg-card rounded-xl p-6 border border-border shadow-sahara">
        <p className="text-sm text-muted-foreground">Loading {title.toLowerCase()}…</p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl p-6 border border-border shadow-sahara">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-base">{icon}</span>
        </div>
        <div className="flex-1">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>

      {/* Model list */}
      <div className="flex flex-col gap-2 mb-4">
        {catalog.specs.map((spec) => {
          const isActive = spec.id === catalog.active_spec_id;
          const isChecked = spec.id === selected;
          return (
            <label
              key={spec.id}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                isChecked ? "border-primary bg-primary/5" : "border-border hover:bg-accent/30"
              }`}
            >
              <input
                type="radio"
                name={`${title}-spec`}
                value={spec.id}
                checked={isChecked}
                onChange={() => setSelected(spec.id)}
                className="mt-1"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium">{spec.label}</span>
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground bg-secondary/40 px-1.5 py-0.5 rounded">
                    {spec.provider}
                  </span>
                  {isActive && (
                    <span className="text-[10px] uppercase tracking-wide bg-green-500/15 text-green-700 dark:text-green-400 px-1.5 py-0.5 rounded">
                      Active
                    </span>
                  )}
                </div>
                {renderMeta && (
                  <div className="text-[11px] text-muted-foreground mt-1">
                    {renderMeta(spec)}
                  </div>
                )}
                {spec.notes && (
                  <p className="text-[11px] text-muted-foreground/80 mt-1 italic">{spec.notes}</p>
                )}
              </div>
            </label>
          );
        })}
      </div>

      {selectedSpec && (
        <>
          {isCustom && (
            <>
              <div className="mb-4 flex flex-col gap-1.5">
                <Label className="text-xs">Custom Model ID / Name</Label>
                <Input
                  type="text"
                  value={customModelId}
                  onChange={(e) => setCustomModelId(e.target.value)}
                  placeholder={capability === "llm" ? "e.g. meta-llama/Llama-3-8B-Instruct" : "e.g. llava-v1.6"}
                  className="bg-background"
                />
              </div>
              <div className="mb-4 flex flex-col gap-1.5">
                <Label className="text-xs">API Base URL</Label>
                <Input
                  type="text"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  placeholder="e.g. http://localhost:8080/v1"
                  className="bg-background"
                />
              </div>
            </>
          )}

          {isBifrost && (
            <BifrostExtraFields
              capability={capability}
              baseUrl={bifrostBaseUrl}
              modelId={bifrostModelId}
              fallbacks={bifrostFallbacks}
              onChange={(patch) => {
                if (patch.baseUrl !== undefined) setBifrostBaseUrl(patch.baseUrl);
                if (patch.modelId !== undefined) setBifrostModelId(patch.modelId);
                if (patch.fallbacks !== undefined) setBifrostFallbacks(patch.fallbacks);
              }}
            />
          )}

          <div className="mb-4 flex flex-col gap-1.5">
            <Label className="text-xs">
              API key for {selectedSpec.provider}
              {selectedSpec.api_key_configured && (
                <span className="ml-2 text-green-600 dark:text-green-400">✓ saved</span>
              )}
            </Label>
            <Input
              type={isMaskedKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onFocus={() => {
                if (isMaskedKey) setApiKey("");
              }}
              placeholder={
                selectedSpec.api_key_configured ? "Replace existing key…" : "Paste API key"
              }
              className="bg-background"
            />
          </div>
        </>
      )}

      <div className="flex items-center gap-3">
        <button
          disabled={!canSave || saving}
          onClick={handleSave}
          className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? "Saving…" : willSwitch ? "Switch & Save" : "Save"}
        </button>
        {saved && (
          <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
            <span className="material-symbols-outlined text-sm">check_circle</span>
            Saved
          </span>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    </div>
  );
}
