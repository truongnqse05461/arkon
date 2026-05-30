import React from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Source } from "./types";

const LANGS: { value: string; label: string }[] = [
  { value: "vi", label: "Vietnamese" },
  { value: "en", label: "English" },
  { value: "zh", label: "Chinese" },
  { value: "ja", label: "Japanese" },
];

export function RetranslateDialog({
  source,
  onClose,
  onDone,
}: {
  source: Source;
  onClose: () => void;
  onDone: () => void;
}) {
  const [target, setTarget] = React.useState(source.target_language || "");
  const [sourceOverride, setSourceOverride] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState("");

  const detected = source.source_language || null;
  const detectedLabel = `Auto-detected${detected ? ` (${detected.toUpperCase()})` : ""}`;
  const effectiveSource = sourceOverride || detected;
  const sameLang = !!target && !!effectiveSource && target === effectiveSource;

  const submit = async () => {
    if (sameLang) {
      setError("Source and target language must differ.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api(`/api/sources/${source.id}/retranslate`, {
        method: "POST",
        body: {
          target_language: target || null,
          source_language: sourceOverride || null,
        },
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start re-translation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl">Re-translate Document</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 mt-2">
          <p className="text-xs text-muted-foreground">
            Use this if the wrong language was chosen at upload, to add a missing
            translation, or to replace or remove the current one. Re-translation
            reruns on this document&apos;s wiki pages.
          </p>

          {/* Target language */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="retranslate-target">Translate to</Label>
            <Select value={target} onValueChange={(v) => setTarget(v ?? "")}>
              <SelectTrigger id="retranslate-target" className="bg-background w-full">
                <SelectValue placeholder="No translation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">No translation</SelectItem>
                {LANGS.map((l) => (
                  <SelectItem key={l.value} value={l.value}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Source language override */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="retranslate-source">Source language</Label>
            <Select value={sourceOverride} onValueChange={(v) => setSourceOverride(v ?? "")}>
              <SelectTrigger id="retranslate-source" className="bg-background w-full">
                <SelectValue placeholder={detectedLabel} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">{detectedLabel}</SelectItem>
                {LANGS.map((l) => (
                  <SelectItem key={l.value} value={l.value}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Override only if the detected source language is wrong.
            </p>
          </div>

          {(error || sameLang) && (
            <p className="text-destructive text-sm bg-destructive/10 px-3 py-2 rounded-lg">
              {error || "Source and target language must differ."}
            </p>
          )}

          <div className="flex justify-end gap-2 mt-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={submitting || sameLang}
              onClick={submit}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <span className="material-symbols-outlined animate-spin text-sm">
                    progress_activity
                  </span>
                  Starting…
                </span>
              ) : (
                "Re-translate"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
