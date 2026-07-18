"use client";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { GENRES } from "@/lib/genres";
import { VISUAL_STYLES } from "@/lib/styles";
import { SampleCard } from "@/components/shared/SampleCard";
import type { VideoRatio } from "@/lib/types/project";

export type { VideoRatio };

/* The look of the whole drama: genre, visual style and delivery format.
   Shared by the create modal (local state until Create) and the Import tab
   (instant PATCH per pick), so the two surfaces never drift apart. */
export function DramaLookFields({
  genre,
  visualStyle,
  ratio,
  onGenre,
  onStyle,
  onRatio,
}: {
  genre: string;
  visualStyle: string;
  ratio: VideoRatio;
  onGenre: (v: string) => void;
  onStyle: (v: string) => void;
  onRatio: (v: VideoRatio) => void;
}) {
  return (
    <>
      <div>
        <div className="flex items-baseline justify-between">
          <Label className="text-xs text-muted-foreground">Genre</Label>
          <span className="text-[11px] font-medium text-primary">
            {GENRES.find((g) => g.value === genre)?.label}
          </span>
        </div>
        <div className="scroll-clean mt-1.5 flex snap-x gap-2 overflow-x-auto pb-1.5">
          {GENRES.map((g) => (
            <SampleCard
              key={g.value}
              active={genre === g.value}
              onClick={() => onGenre(g.value)}
              img={`/genres/${g.value.replace(/ /g, "-")}.jpg`}
              label={g.label}
            />
          ))}
        </div>
      </div>

      {/* visual style: seeds the style plate and every costume plate, so
          the whole drama renders in the chosen look. Every sample shows
          the SAME scene so the cards read as a pure style comparison. */}
      <div>
        <div className="flex items-baseline justify-between">
          <Label className="text-xs text-muted-foreground">Visual style</Label>
          <span className="text-[11px] font-medium text-primary">
            {VISUAL_STYLES.find((s) => s.value === visualStyle)?.label}
          </span>
        </div>
        <div className="scroll-clean mt-1.5 flex snap-x gap-2 overflow-x-auto pb-1.5">
          {VISUAL_STYLES.map((s) => (
            <SampleCard
              key={s.value}
              active={visualStyle === s.value}
              onClick={() => onStyle(s.value)}
              img={`/styles/${s.value}.jpg`}
              label={s.label}
            />
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground mt-1">
          Every card is the same scene in that style. Your whole drama renders
          in the look you pick.
        </p>
      </div>

      {/* delivery format: drives generation ratio, export canvas, player */}
      <div>
        <Label className="text-xs text-muted-foreground">Format</Label>
        <div className="mt-1 grid grid-cols-2 gap-2">
          <FormatCard
            active={ratio === "9:16"}
            onClick={() => onRatio("9:16")}
            title="9:16 Vertical"
            desc="Short drama for phones. Recommended."
            frameClass="h-7 w-4"
          />
          <FormatCard
            active={ratio === "16:9"}
            onClick={() => onRatio("16:9")}
            title="16:9 Landscape"
            desc="Widescreen for desktop and TV."
            frameClass="h-4 w-7"
          />
        </div>
      </div>
    </>
  );
}

export function FormatCard({
  active,
  onClick,
  title,
  desc,
  frameClass,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  desc: string;
  frameClass: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2.5 rounded-lg border p-2.5 text-left transition-all",
        active
          ? "border-primary bg-primary/10"
          : "border-border hover:border-primary/40"
      )}
    >
      <span
        className={cn(
          "shrink-0 rounded-[3px] border",
          frameClass,
          active ? "border-primary bg-primary/25" : "border-muted-foreground/50"
        )}
      />
      <span>
        <span className="block text-xs font-semibold">{title}</span>
        <span className="block text-[10px] text-muted-foreground">{desc}</span>
      </span>
    </button>
  );
}
