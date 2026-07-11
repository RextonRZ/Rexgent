"use client";

import { useRef, useState } from "react";
import { Loader2, Shirt, ZoomIn } from "lucide-react";
import { Lightbox } from "@/components/shared/Lightbox";

const STATUS_LABEL: Record<string, string> = {
  ai_generated: "AI generated",
  ai_pending: "Pending",
  user_override: "User override",
};

const STATUS_COLOR: Record<string, string> = {
  ai_generated: "bg-ok/15 text-ok",
  ai_pending: "bg-warn/15 text-warn",
  user_override: "bg-secondary text-muted-foreground",
};

export interface PlateCardProps {
  imageUrl?: string;
  label: string;
  description?: string;
  status?: string;
  onRegenerate?: () => void;
  onUpload?: (file: File) => void;
  /** re-dress from ANY outfit photo: the clothing is read from the image and
   * the plate re-renders with this character's own face wearing it */
  onSwapOutfit?: (file: File) => void;
  /** an action on THIS plate is running — show it working, block re-clicks */
  busy?: boolean;
}

export function PlateCard({
  imageUrl,
  label,
  description,
  status,
  onRegenerate,
  onUpload,
  onSwapOutfit,
  busy,
}: PlateCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const outfitInputRef = useRef<HTMLInputElement>(null);
  const [zoom, setZoom] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onUpload) onUpload(file);
    e.target.value = "";
  };

  const handleOutfitChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onSwapOutfit) onSwapOutfit(file);
    e.target.value = "";
  };

  const hasActions = Boolean(onRegenerate || onUpload || onSwapOutfit);

  return (
    <div className="group relative overflow-hidden rounded-lg border border-border bg-card">
      {/* square + contain so the whole plate is visible (plates are 1:1; uploads letterbox) */}
      <div className="relative aspect-square w-full bg-background/40">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={label}
            onClick={() => setZoom(true)}
            className="h-full w-full cursor-zoom-in object-contain"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[11px] text-muted-foreground">
            no plate yet
          </div>
        )}
        {/* view-larger affordance, top-left so it clears the status badge */}
        {imageUrl && !busy && (
          <button
            onClick={() => setZoom(true)}
            title="View larger"
            className="absolute top-1.5 left-1.5 z-20 flex h-7 w-7 items-center justify-center rounded-full bg-black/50 text-white/80 opacity-0 transition-opacity hover:bg-black/70 hover:text-white group-hover:opacity-100 focus-visible:opacity-100"
          >
            <ZoomIn className="size-3.5" />
          </button>
        )}
        {status && (
          <span
            className={`absolute top-1.5 right-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
              STATUS_COLOR[status] || "bg-secondary text-muted-foreground"
            }`}
          >
            {STATUS_LABEL[status] || status}
          </span>
        )}
        {/* a running action owns the plate: spinner, no competing buttons */}
        {busy && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-1.5 bg-black/60">
            <Loader2 className="size-5 animate-spin text-white/90" />
            <span className="text-[10px] text-white/80">working on it…</span>
          </div>
        )}
        {/* actions appear on hover as icon buttons over the image */}
        {hasActions && !busy && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/50 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                title="Regenerate plate"
                className="h-8 w-8 rounded-full bg-background/90 hover:bg-background flex items-center justify-center text-sm"
              >
                ↻
              </button>
            )}
            {onUpload && (
              <button
                onClick={() => fileInputRef.current?.click()}
                title="Upload replacement image"
                className="h-8 w-8 rounded-full bg-background/90 hover:bg-background flex items-center justify-center text-sm"
              >
                ⬆
              </button>
            )}
            {onSwapOutfit && (
              <button
                onClick={() => outfitInputRef.current?.click()}
                title="Swap outfit from a photo: the clothing is copied, the person in your photo is ignored"
                className="h-8 w-8 rounded-full bg-background/90 hover:bg-background flex items-center justify-center"
              >
                <Shirt className="size-3.5" />
              </button>
            )}
          </div>
        )}
      </div>

      <div className="px-2.5 py-2 min-w-0">
        <p className="text-xs font-medium leading-snug">{label}</p>
        {description && (
          <p className="text-[11px] text-muted-foreground leading-snug mt-0.5">
            {description}
          </p>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />
      <input
        ref={outfitInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleOutfitChange}
      />

      <Lightbox
        src={imageUrl}
        alt={label}
        open={zoom}
        onClose={() => setZoom(false)}
      />
    </div>
  );
}
