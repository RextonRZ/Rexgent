"use client";

import { useEffect, useRef, useState } from "react";
import { SpendConfirm, type SpendRequest } from "@/components/shared/SpendConfirm";
import { Button } from "@/components/ui/button";
import {
  useSetPresetVoice,
  useCloneVoice,
  useVoices,
  previewVoice,
} from "@/hooks/useCasting";
import { errText } from "@/lib/errText";

/** A short neutral passage to read for a clean voice sample. */
const CLONE_PASSAGE =
  "The morning light spilled across the quiet street as I walked, thinking about everything and nothing at once.";

/** Per-character voice: pick a preset timbre, or clone a custom voice by recording
 *  a passage live (or uploading a sample). Reflects + previews the current voice. */
export function VoiceRow({
  characterId,
  voiceId,
  voiceSource,
  voiceDesign,
}: {
  characterId: string;
  voiceId?: string | null;
  voiceSource?: string | null;
  /** the written description casting gave the voice designer (designed voices only) */
  voiceDesign?: string | null;
}) {
  const cloned = voiceSource === "cloned";
  const designed = voiceSource === "designed";
  const [mode, setMode] = useState<"designed" | "preset" | "clone">(
    cloned ? "clone" : designed ? "designed" : "preset"
  );
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [spend, setSpend] = useState<SpendRequest | null>(null);

  // both clone paths (recording and file) confirm before enrolling
  const confirmClone = (file: File) =>
    setSpend({
      title: "Clone this voice",
      costLine:
        "Cloning enrolls your recording with the speech service, and every line spoken with a cloned voice bills at a higher rate than the presets.",
      note: "The cloned voice then reads all of this character's dialogue.",
      confirmLabel: "Clone voice",
      run: () => cloneVoice.mutate({ characterId, file }),
    });

  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const setPreset = useSetPresetVoice();
  const cloneVoice = useCloneVoice();
  const { data: voices } = useVoices();

  const femaleVoices = (voices ?? []).filter((v) => v.gender === "female");
  const maleVoices = (voices ?? []).filter((v) => v.gender === "male");

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const [previewError, setPreviewError] = useState<string | null>(null);

  const handlePreview = async () => {
    setPreviewing(true);
    setPreviewError(null);
    try {
      setPreviewUrl(await previewVoice(characterId));
    } catch (e) {
      setPreviewError(errText(e) || "Preview failed, try again in a moment.");
    } finally {
      setPreviewing(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ["audio/webm", "audio/mp4", "audio/ogg"].find(
        (m) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)
      );
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const type = mr.mimeType || "audio/webm";
        const ext = type.includes("mp4") ? "mp4" : type.includes("ogg") ? "ogg" : "webm";
        const file = new File(chunksRef.current, `sample.${ext}`, { type });
        confirmClone(file);
      };
      mr.start();
      recorderRef.current = mr;
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      /* mic denied / unavailable — the file upload path still works */
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    setRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const currentLabel = cloned
    ? "Cloned voice"
    : designed
    ? "Designed voice"
    : voiceId
    ? `Preset: ${voiceId}`
    : "No voice set";

  return (
    <div className="rounded-lg border hairline bg-background/40 p-2.5 space-y-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
        <span className="text-muted-foreground">Voice</span>
        <span
          className={`max-w-[10rem] truncate whitespace-nowrap rounded px-1.5 py-0.5 ${cloned || designed ? "bg-primary/20 text-primary" : "text-muted-foreground"}`}
          title={designed ? "A bespoke voice designed from this character's age and personality" : undefined}
        >
          {currentLabel}
        </span>
        {designed && (
          <button
            onClick={() => setMode("designed")}
            className={`ml-auto whitespace-nowrap rounded px-1.5 py-0.5 ${
              mode === "designed" ? "bg-primary/20 text-primary" : "text-muted-foreground"
            }`}
          >
            Designed
          </button>
        )}
        <button
          onClick={() => setMode("preset")}
          className={`${designed ? "" : "ml-auto "}whitespace-nowrap rounded px-1.5 py-0.5 ${
            mode === "preset" ? "bg-primary/20 text-primary" : "text-muted-foreground"
          }`}
        >
          Preset
        </button>
        <button
          onClick={() => setMode("clone")}
          className={`whitespace-nowrap rounded px-1.5 py-0.5 ${
            mode === "clone" ? "bg-primary/20 text-primary" : "text-muted-foreground"
          }`}
        >
          Clone
        </button>
        <button
          onClick={handlePreview}
          disabled={previewing || !voiceId}
          className="whitespace-nowrap rounded px-1.5 py-0.5 text-primary hover:bg-primary/15 disabled:opacity-40"
        >
          {previewing ? "…" : "▶ Preview"}
        </button>
      </div>

      {mode === "designed" ? (
        <div className="rounded border border-primary/30 bg-primary/5 p-2 text-[11px] leading-snug">
          <p className="font-medium text-primary/90">
            Casting designed this voice for the character
          </p>
          <p className="mt-1 text-muted-foreground">
            {voiceDesign ||
              "A bespoke voice built from this character's age, gender and personality. Hit Preview to hear it."}
          </p>
          <p className="mt-1 text-[10px] text-muted-foreground/70">
            Picking a preset or cloning below replaces it.
          </p>
        </div>
      ) : mode === "preset" ? (
        <select
          value={cloned || designed ? "" : voiceId ?? ""}
          onChange={(e) => e.target.value && setPreset.mutate({ characterId, voice: e.target.value })}
          disabled={setPreset.isPending}
          className="w-full rounded border border-border bg-background/60 px-2 py-1 text-[11px]"
        >
          <option value="" disabled>
            {setPreset.isPending ? "Setting…" : "Choose a preset voice…"}
          </option>
          <optgroup label="Female">
            {femaleVoices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.id} — {v.desc}
              </option>
            ))}
          </optgroup>
          <optgroup label="Male">
            {maleVoices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.id} — {v.desc}
              </option>
            ))}
          </optgroup>
        </select>
      ) : (
        <div className="space-y-2">
          <div className="rounded border border-border bg-background/60 p-2 text-[11px] leading-snug text-muted-foreground">
            <span className="font-medium text-foreground/80">Read this aloud (~15s):</span>{" "}
            “{CLONE_PASSAGE}”
          </div>
          <div className="flex items-center gap-2">
            {!recording ? (
              <Button
                size="sm"
                variant="outline"
                onClick={startRecording}
                disabled={cloneVoice.isPending}
              >
                🎙 Record
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={stopRecording} className="text-bad">
                ■ Stop ({seconds}s)
              </Button>
            )}
            <span className="text-[10px] text-muted-foreground">or</span>
            <input
              ref={fileRef}
              type="file"
              accept="audio/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) confirmClone(f);
              }}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => fileRef.current?.click()}
              disabled={cloneVoice.isPending}
            >
              Upload file
            </Button>
          </div>
          {recording && (
            <p className="text-[10px] text-primary">● Recording… read the passage, then Stop.</p>
          )}
          {cloneVoice.isPending && (
            <p className="text-[10px] text-muted-foreground">Enrolling clone…</p>
          )}
          {cloned && !cloneVoice.isPending && (
            <p className="text-[10px] text-ok">✓ Cloned voice active.</p>
          )}
          {cloneVoice.isError && (
            <p className="text-[10px] text-bad">{errText(cloneVoice.error)}</p>
          )}
        </div>
      )}

      {previewing && (
        <p className="text-[10px] text-muted-foreground">
          Synthesizing a sample line in this voice…
        </p>
      )}
      {previewError && <p className="text-[10px] text-bad">{previewError}</p>}
      {previewUrl && <audio src={previewUrl} controls autoPlay className="w-full h-7" />}
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
    </div>
  );
}
