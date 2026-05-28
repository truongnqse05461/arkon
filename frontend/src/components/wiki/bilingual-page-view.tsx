"use client";

import { useEffect, useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WikiContent } from "@/components/wiki/wiki-content";

type Mode = "source" | "target" | "side";
const STORAGE_KEY = "wiki.bilingual.mode";

interface Props {
  title: string;
  contentMd: string;
  titleTranslated: string | null;
  contentMdTranslated: string | null;
  sourceLanguage: string | null;
  targetLanguage: string | null;
  linkSuffix?: string;
  hideSideBySide?: boolean;
}

export function BilingualPageView({
  title,
  contentMd,
  titleTranslated,
  contentMdTranslated,
  sourceLanguage,
  targetLanguage,
  linkSuffix = "",
  hideSideBySide = false,
}: Props) {
  const bilingual = !!(titleTranslated && contentMdTranslated);
  const [mode, setMode] = useState<Mode>(hideSideBySide ? "target" : "side");

  useEffect(() => {
    if (!bilingual) {
      setMode("source");
      return;
    }
    const stored =
      typeof window !== "undefined"
        ? (window.localStorage.getItem(STORAGE_KEY) as Mode | null)
        : null;
    if (stored === "source" || stored === "target" || (stored === "side" && !hideSideBySide)) {
      setMode(stored);
    } else if (stored === "side" && hideSideBySide) {
      setMode("target");
    }
  }, [bilingual, hideSideBySide]);

  const onModeChange = (m: string) => {
    const next = m as Mode;
    setMode(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
  };

  if (!bilingual) {
    return <WikiContent markdown={contentMd} linkSuffix={linkSuffix} />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="text-xs text-muted-foreground">
          {(sourceLanguage ?? "??").toUpperCase()} → {(targetLanguage ?? "??").toUpperCase()}
        </div>
        <Tabs value={mode} onValueChange={onModeChange}>
          <TabsList>
            <TabsTrigger value="source">Source</TabsTrigger>
            <TabsTrigger value="target">Translated</TabsTrigger>
            {!hideSideBySide && (
              <TabsTrigger value="side">Side-by-side</TabsTrigger>
            )}
          </TabsList>
        </Tabs>
      </div>

      {mode === "source" && (
        <WikiContent markdown={contentMd} linkSuffix={linkSuffix} />
      )}
      {mode === "target" && (
        <div>
          {titleTranslated && titleTranslated !== title && (
            <h1 className="text-2xl font-semibold mb-4">{titleTranslated}</h1>
          )}
          <WikiContent markdown={contentMdTranslated!} linkSuffix={linkSuffix} />
        </div>
      )}
      {mode === "side" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground mb-2">
              {(sourceLanguage ?? "Source").toUpperCase()}
            </div>
            <WikiContent markdown={contentMd} linkSuffix={linkSuffix} />
          </div>
          <div className="xl:border-l xl:pl-6">
            <div className="text-xs font-medium uppercase text-muted-foreground mb-2">
              {(targetLanguage ?? "Translated").toUpperCase()}
            </div>
            {titleTranslated && titleTranslated !== title && (
              <h1 className="text-2xl font-semibold mb-4">{titleTranslated}</h1>
            )}
            <WikiContent markdown={contentMdTranslated!} linkSuffix={linkSuffix} />
          </div>
        </div>
      )}
    </div>
  );
}
