"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useDesignVoice, useCloneVoice, previewVoice } from "@/hooks/useCasting";

/** Per-character voice casting: design a voice from text, clone from a sample, or preview. */
export function VoiceRow({ characterId }: { characterId: string }) {
  const [mode, setMode] = useState<"design" | "clone">("design");
  const [description, setDescription] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const designVoice = useDesignVoice();
  const cloneVoice = useCloneVoice();

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const url = await previewVoice(characterId);
      setPreviewUrl(url);
    } catch {
      /* no voice yet / preview failed — silently ignore */
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="rounded-lg border hairline bg-background/40 p-2.5 space-y-2">
      <div className="flex items-center gap-2 text-[11px]">
        <span className="text-muted-foreground">Voice:</span>
        <button
          onClick={() => setMode("design")}
          className={`rounded px-1.5 py-0.5 ${
            mode === "design" ? "bg-primary/20 text-primary" : "text-muted-foreground"
          }`}
        >
          Design
        </button>
        <button
          onClick={() => setMode("clone")}
          className={`rounded px-1.5 py-0.5 ${
            mode === "clone" ? "bg-primary/20 text-primary" : "text-muted-foreground"
          }`}
        >
          Clone
        </button>
        <button
          onClick={handlePreview}
          disabled={previewing}
          className="ml-auto rounded px-1.5 py-0.5 text-primary hover:bg-primary/15 disabled:opacity-50"
        >
          {previewing ? "…" : "▶ Preview"}
        </button>
      </div>

      {mode === "design" ? (
        <div className="flex items-center gap-2">
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. warm low female voice, calm"
            className="flex-1 rounded border border-border bg-background/60 px-2 py-1 text-[11px]"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={designVoice.isPending || !description.trim()}
            onClick={() => designVoice.mutate({ characterId, description })}
          >
            {designVoice.isPending ? "…" : "Design"}
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) cloneVoice.mutate({ characterId, file: f });
            }}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={cloneVoice.isPending}
            onClick={() => fileRef.current?.click()}
          >
            {cloneVoice.isPending ? "Cloning…" : "Upload 5–20s sample"}
          </Button>
        </div>
      )}

      {previewUrl && (
        <audio src={previewUrl} controls autoPlay className="w-full h-7" />
      )}
    </div>
  );
}
