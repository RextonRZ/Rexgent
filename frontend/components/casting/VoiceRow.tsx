"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  useSetPresetVoice,
  useCloneVoice,
  previewVoice,
  PRESET_VOICES,
} from "@/hooks/useCasting";

/** Per-character voice: pick a preset timbre, or clone a custom voice from a
 *  short sample. Reflects the character's current voice + previews it. */
export function VoiceRow({
  characterId,
  voiceId,
  voiceSource,
}: {
  characterId: string;
  voiceId?: string | null;
  voiceSource?: string | null;
}) {
  const cloned = voiceSource === "cloned";
  const [mode, setMode] = useState<"preset" | "clone">(cloned ? "clone" : "preset");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const setPreset = useSetPresetVoice();
  const cloneVoice = useCloneVoice();

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      setPreviewUrl(await previewVoice(characterId));
    } catch {
      /* no voice yet / preview failed — silently ignore */
    } finally {
      setPreviewing(false);
    }
  };

  const currentLabel = cloned
    ? "Cloned voice"
    : voiceId
    ? `Preset: ${voiceId}`
    : "No voice set";

  return (
    <div className="rounded-lg border hairline bg-background/40 p-2.5 space-y-2">
      <div className="flex items-center gap-2 text-[11px]">
        <span className="text-muted-foreground">Voice</span>
        <span className={`rounded px-1.5 py-0.5 ${cloned ? "bg-primary/20 text-primary" : "text-muted-foreground"}`}>
          {currentLabel}
        </span>
        <button
          onClick={() => setMode("preset")}
          className={`ml-auto rounded px-1.5 py-0.5 ${
            mode === "preset" ? "bg-primary/20 text-primary" : "text-muted-foreground"
          }`}
        >
          Preset
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
          disabled={previewing || !voiceId}
          className="rounded px-1.5 py-0.5 text-primary hover:bg-primary/15 disabled:opacity-40"
        >
          {previewing ? "…" : "▶ Preview"}
        </button>
      </div>

      {mode === "preset" ? (
        <select
          value={cloned ? "" : voiceId ?? ""}
          onChange={(e) => e.target.value && setPreset.mutate({ characterId, voice: e.target.value })}
          disabled={setPreset.isPending}
          className="w-full rounded border border-border bg-background/60 px-2 py-1 text-[11px]"
        >
          <option value="" disabled>
            {setPreset.isPending ? "Setting…" : "Choose a preset voice…"}
          </option>
          {PRESET_VOICES.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      ) : (
        <div className="space-y-1">
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
            className="w-full"
          >
            {cloneVoice.isPending
              ? "Cloning…"
              : cloned
              ? "Re-clone (upload new sample)"
              : "Upload 5–20s sample to clone"}
          </Button>
          {cloneVoice.isError && (
            <p className="text-[10px] text-bad">
              {(cloneVoice.error as Error).message}
            </p>
          )}
        </div>
      )}

      {previewUrl && <audio src={previewUrl} controls autoPlay className="w-full h-7" />}
    </div>
  );
}
