"use client";

import { useRef, useState } from "react";
import { LoadingVideo } from "@/components/shared/LoadingVideo";

export interface MediaAsset {
  id: string;
  url: string;
  name: string;
  type: "video" | "audio";
}

export const ASSET_MIME = "application/x-rexgent-asset";

/** A media bin: import external video + audio, then drag them onto the timeline. */
export function MediaBin({
  media,
  onImport,
  onAdd,
  uploading,
}: {
  media: MediaAsset[];
  onImport: (file: File) => void;
  onAdd: (asset: MediaAsset) => void;
  uploading: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const importFiles = (files: FileList | null) => {
    if (!files) return;
    Array.from(files)
      .filter((f) => f.type.startsWith("video/") || f.type.startsWith("audio/"))
      .forEach(onImport);
  };

  return (
    <div
      className={`rounded-xl border bg-card p-4 transition-colors ${
        dragOver ? "border-primary ring-1 ring-primary" : "hairline"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        importFiles(e.dataTransfer.files);
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-sm font-medium">Media</h2>
          <p className="text-[11px] text-muted-foreground">
            Drop your own video / audio here, then drag items onto the timeline
          </p>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          className="rounded-md bg-primary/15 text-primary px-3 py-1.5 text-xs font-medium hover:bg-primary/25"
        >
          {uploading ? "Importing…" : "+ Import media"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="video/*,audio/*"
          multiple
          className="hidden"
          onChange={(e) => importFiles(e.target.files)}
        />
      </div>

      {media.length === 0 ? (
        <div className="h-20 rounded-lg border border-dashed border-border flex items-center justify-center text-[11px] text-muted-foreground">
          Drop video (mp4 / mov / webm) or audio (mp3 / wav) files here
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {media.map((asset) => (
            <div
              key={asset.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData(ASSET_MIME, JSON.stringify(asset));
                e.dataTransfer.effectAllowed = "copy";
              }}
              className="rounded-lg border hairline bg-background/40 overflow-hidden cursor-grab active:cursor-grabbing"
            >
              {asset.type === "video" ? (
                <LoadingVideo
                  src={`${asset.url}#t=0.1`}
                  muted
                  loop
                  playsInline
                  preload="metadata"
                  onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
                  onMouseLeave={(e) => e.currentTarget.pause()}
                  className="aspect-video w-full bg-black pointer-events-none"
                />
              ) : (
                <div className="aspect-video w-full bg-hh/20 flex items-center justify-center text-2xl">
                  🎵
                </div>
              )}
              <div className="p-1.5">
                <p className="text-[10px] truncate" title={asset.name}>
                  {asset.name}
                </p>
                <button
                  onClick={() => onAdd(asset)}
                  className="mt-1 w-full rounded bg-primary/15 text-primary px-1.5 py-0.5 text-[10px] font-medium hover:bg-primary/25"
                >
                  {asset.type === "video" ? "+ add to cut" : "+ set as music"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
