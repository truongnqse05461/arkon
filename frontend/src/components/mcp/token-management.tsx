"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function TokenManagement() {
  const [hasToken, setHasToken] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showToken, setShowToken] = useState(false);

  useEffect(() => {
    api<{ has_token: boolean }>("/api/my/mcp-token/status")
      .then((data) => setHasToken(data.has_token))
      .catch((err) => console.warn("Failed to check MCP token status:", err));
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const data = await api<{ token: string }>("/api/my/mcp-token", {
        method: "POST",
      });
      setToken(data.token);
      setHasToken(true);
      setShowToken(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to generate token");
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!confirm("Revoke your MCP token? All agent connections using this token will stop working.")) return;
    try {
      await api("/api/my/mcp-token", { method: "DELETE" });
      setToken(null);
      setHasToken(false);
      setShowToken(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to revoke token");
    }
  };

  const handleCopy = () => {
    if (!token) return;
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-card rounded-xl p-6 border border-border shadow-sahara">
      <h3 className="text-lg font-semibold text-foreground mb-1">
        Token Management
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        Your MCP token authorizes agents to access Arkon&apos;s knowledge base on your behalf.
      </p>

      {hasToken ? (
        <div className="space-y-4">
          {/* Status */}
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-foreground font-medium">Active</span>
          </div>

          {/* Token display (only if just generated or show toggled) */}
          {token && showToken ? (
            <div className="space-y-2">
              <div className="bg-[#3a302a] rounded-lg p-3 font-mono text-xs text-[#faf5ee] break-all">
                {token}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleCopy}>
                  <span className="material-symbols-outlined text-sm mr-1">
                    {copied ? "check" : "content_copy"}
                  </span>
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setShowToken(false)}>
                  <span className="material-symbols-outlined text-sm mr-1">visibility_off</span>
                  Hide
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Your token was shown when generated — it cannot be retrieved again for security.
              Regenerate to get a new one.
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleGenerate} disabled={loading} variant="outline" size="sm">
              <span className="material-symbols-outlined text-sm mr-1">refresh</span>
              {loading ? "Regenerating..." : "Regenerate Token"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRevoke}
              className="text-destructive hover:text-destructive"
            >
              <span className="material-symbols-outlined text-sm mr-1">vpn_key_off</span>
              Revoke Token
            </Button>
          </div>

          <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
            Regenerating invalidates all existing connections using this token.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-muted-foreground/30" />
            <span className="text-muted-foreground">No token</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Generate a token to connect AI agents to Arkon.
          </p>
          <Button onClick={handleGenerate} disabled={loading}>
            <span className="material-symbols-outlined text-sm mr-1">vpn_key</span>
            {loading ? "Generating..." : "Generate Token"}
          </Button>
        </div>
      )}
    </div>
  );
}
