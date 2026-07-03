"use client";

import { useRef } from "react";

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
}

export function PlateCard({
  imageUrl,
  label,
  description,
  status,
  onRegenerate,
  onUpload,
}: PlateCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onUpload) onUpload(file);
    e.target.value = "";
  };

  const hasActions = Boolean(onRegenerate || onUpload);

  return (
    <div className="group relative overflow-hidden rounded-lg border border-border bg-card">
      <div className="relative aspect-video w-full bg-background/40">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt={label} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[11px] text-muted-foreground">
            no plate yet
          </div>
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
        {/* actions appear on hover as icon buttons over the image */}
        {hasActions && (
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
                title="Upload replacement"
                className="h-8 w-8 rounded-full bg-background/90 hover:bg-background flex items-center justify-center text-sm"
              >
                ⬆
              </button>
            )}
          </div>
        )}
      </div>

      <div className="px-2.5 py-2 min-w-0">
        <p className="text-xs font-medium truncate">{label}</p>
        {description && (
          <p className="text-[11px] text-muted-foreground truncate">{description}</p>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  );
}
