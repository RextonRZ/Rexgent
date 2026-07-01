"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { useUploadAudio } from "@/hooks/useExport";

export interface AudioSettings {
  url: string | null;
  name: string;
  volume: number; // 0..2 (1 = 100%)
  fadeIn: number; // seconds
}

export const EMPTY_AUDIO: AudioSettings = {
  url: null,
  name: "",
  volume: 1,
  fadeIn: 0,
};

function num(v: number | readonly number[]): number {
  return Array.isArray(v) ? v[0] : (v as number);
}

export function MusicPanel({
  projectId,
  audio,
  onChange,
}: {
  projectId: string;
  audio: AudioSettings;
  onChange: (a: AudioSettings) => void;
}) {
  const upload = useUploadAudio(projectId);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const res = await upload.mutateAsync(file);
    onChange({ ...audio, url: res.url, name: file.name });
  };

  return (
    <div className="rounded-xl border hairline bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium">🎵 Music</h2>
        {audio.url && (
          <button
            onClick={() => onChange({ ...EMPTY_AUDIO })}
            className="text-xs text-bad hover:underline"
          >
            Remove
          </button>
        )}
      </div>

      {!audio.url ? (
        <>
          <input
            ref={inputRef}
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={handleFile}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Uploading…" : "+ Add music"}
          </Button>
          <p className="text-[11px] text-muted-foreground mt-2">
            Mixed over your cut on export · mp3 / wav / m4a
          </p>
        </>
      ) : (
        <div className="space-y-4">
          <p className="text-xs truncate">🎵 {audio.name || "music"}</p>
          <div>
            <div className="flex justify-between text-[11px] text-muted-foreground mb-1.5">
              <span>Volume</span>
              <span>{Math.round(audio.volume * 100)}%</span>
            </div>
            <Slider
              value={audio.volume}
              min={0}
              max={2}
              step={0.05}
              onValueChange={(v) => onChange({ ...audio, volume: num(v) })}
            />
          </div>
          <div>
            <div className="flex justify-between text-[11px] text-muted-foreground mb-1.5">
              <span>Fade in</span>
              <span>{audio.fadeIn.toFixed(1)}s</span>
            </div>
            <Slider
              value={audio.fadeIn}
              min={0}
              max={5}
              step={0.5}
              onValueChange={(v) => onChange({ ...audio, fadeIn: num(v) })}
            />
          </div>
        </div>
      )}
    </div>
  );
}
