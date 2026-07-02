"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const STATUS_LABEL: Record<string, string> = {
  ai_generated: "AI generated",
  ai_pending: "Pending",
  user_override: "User override",
};

const STATUS_COLOR: Record<string, string> = {
  ai_generated: "bg-ok/15 text-ok",
  ai_pending: "bg-warn/15 text-warn",
  user_override: "bg-primary/15 text-primary",
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

  return (
    <Card className="hover:border-primary/40 transition-colors">
      <div className="relative aspect-video w-full bg-background/40">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={label}
            className="h-full w-full object-cover"
          />
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
      </div>
      <CardContent className="space-y-2 pt-3">
        <div>
          <p className="text-sm font-medium leading-snug">{label}</p>
          {description && (
            <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
              {description}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onRegenerate}
            disabled={!onRegenerate}
            className="flex-1"
          >
            ↻ Regenerate
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => fileInputRef.current?.click()}
            disabled={!onUpload}
            className="flex-1"
          >
            ⬆ Upload
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      </CardContent>
    </Card>
  );
}
