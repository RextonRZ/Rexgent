"use client";

import { useState } from "react";
import { Clock, Users, Pencil, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ShotEditor } from "./ShotEditor";
import { useDeleteShot } from "@/hooks/useStoryboard";
import { explainFilmTerm, fullShotType } from "@/lib/filmTerms";
import { tierLabel, isFullTier, modelLabel } from "@/lib/qualityTier";
import type { Shot, ShotPromptEngineering } from "@/lib/types";

/** The beat expander's paper trail: what the model was actually told, what it
 * was told to avoid, and which world-graph rule shaped the environment. */
function PromptEngineering({ pe }: { pe: ShotPromptEngineering }) {
  const [open, setOpen] = useState(false);
  const env = pe.environment;
  const overridden = env?.source && env.source !== "location default";
  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-2.5 py-1.5 text-[10px] uppercase tracking-widest text-zinc-400 hover:text-zinc-200"
      >
        <span>prompt engineering</span>
        <span className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`}>
          ▸
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-white/[0.07] px-2.5 py-2 text-[11px] leading-relaxed">
          <div>
            <p className="text-[9px] uppercase tracking-widest text-zinc-500">
              sent to the video model
            </p>
            <p className="text-zinc-300">{pe.prompt}</p>
          </div>
          {pe.negative_prompt && (
            <div>
              <p className="text-[9px] uppercase tracking-widest text-zinc-500">
                negative prompt (what it must NOT render)
              </p>
              <p className="text-zinc-400">{pe.negative_prompt}</p>
            </div>
          )}
          {env?.behavior && (
            <div>
              <p className="text-[9px] uppercase tracking-widest text-zinc-500">
                environment (world graph)
              </p>
              <p className="text-zinc-300">
                {overridden ? (
                  <>
                    The event{" "}
                    <span className="font-medium text-primary">{env.source}</span>{" "}
                    (priority {env.priority}) overrides the{" "}
                    {(env.location ?? "location").replace(/_/g, " ")} default:{" "}
                    {env.behavior}.
                  </>
                ) : (
                  <>
                    {(env.location ?? "location").replace(/_/g, " ")} default
                    behavior: {env.behavior}.
                  </>
                )}
                {env.suppressed && (
                  <span className="text-zinc-500">
                    {" "}
                    Suppressed into the negative: {env.suppressed}.
                  </span>
                )}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Meta({
  icon: Icon,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <Icon className="h-3 w-3 opacity-70" />
      {children}
    </span>
  );
}

export function ShotCard({ shot }: { shot: Shot }) {
  const [editing, setEditing] = useState(false);
  const deleteShot = useDeleteShot();

  if (editing) {
    return <ShotEditor shot={shot} onClose={() => setEditing(false)} />;
  }

  const handleDelete = () => {
    if (window.confirm(`Delete shot ${shot.number}? This can't be undone.`)) {
      deleteShot.mutate(shot.id);
    }
  };

  // Under wan_primary routing each shot names the MODEL it renders on (Wan for
  // visuals, HappyHorse for characters). When there is no model split the tag
  // falls back to the quality LEVEL the Producer assigned (full vs fast).
  const renderPlan = shot.render_plan;
  const tier = shot.quality_tier;
  const isFull = isFullTier(tier);
  const model = renderPlan?.model ? modelLabel(renderPlan.model) : null;
  const showTierTag = Boolean(tier);

  return (
    <Card className="group">
      <CardContent className="px-5 py-1.5 space-y-3 text-sm">
        {/* header: shot id + technicals left, model + hover actions right */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs flex items-center gap-2">
            <span className="rounded bg-primary/15 text-primary px-1.5 py-0.5 font-semibold">
              Shot {shot.number}
            </span>
            {shot.shot_type && (
              <span
                className="text-muted-foreground cursor-help underline decoration-dotted decoration-white/20 underline-offset-2"
                title={explainFilmTerm(shot.shot_type)}
              >
                {fullShotType(shot.shot_type)}
              </span>
            )}
            {shot.camera_movement && (
              <span className="text-muted-foreground">
                {shot.camera_movement.toLowerCase().replace(/_/g, " ")}
              </span>
            )}
          </p>
          <div className="flex items-center gap-1.5 shrink-0">
            <div className="flex opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
              <button
                onClick={() => setEditing(true)}
                title="Edit shot"
                className="h-7 w-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteShot.isPending}
                title="Delete shot"
                className="h-7 w-7 rounded-md text-muted-foreground hover:text-bad hover:bg-bad/10 flex items-center justify-center disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            {model ? (
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  model === "Wan" ? "bg-wan/15 text-wan" : "bg-hh/15 text-hh"
                }`}
                title={
                  model === "Wan"
                    ? "Wan · visuals / continuity"
                    : "HappyHorse · face + dialogue"
                }
              >
                {model}
              </span>
            ) : (
              showTierTag && (
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    tier === "deferred"
                      ? "bg-warn/15 text-warn"
                      : isFull
                        ? "bg-wan/15 text-wan"
                        : "bg-hh/15 text-hh"
                  }`}
                >
                  {tierLabel(tier)}
                </span>
              )
            )}
            {renderPlan?.lipsync && (
              <span className="rounded-full bg-primary/10 text-primary/90 px-2 py-0.5 text-[10px] font-medium">
                Lipsync
              </span>
            )}
          </div>
        </div>

        {/* the description is the hero */}
        {shot.action && <p className="leading-relaxed">{shot.action}</p>}
        {shot.dialogue && (
          <p className="border-l-2 border-primary/40 pl-3 py-0.5 text-xs italic text-muted-foreground">
            &ldquo;{shot.dialogue}&rdquo;
          </p>
        )}

        {/* one quiet metadata row — lighting + colour_mood are scene-wide, so
            they live once on the SceneSection header, not on every shot */}
        <div className="flex items-center gap-3 pt-1 pb-1 text-[11px] text-muted-foreground flex-wrap">
          <Meta icon={Clock}>{shot.estimated_duration_seconds}s</Meta>
          {shot.characters_in_frame && shot.characters_in_frame.length > 0 && (
            <Meta icon={Users}>{shot.characters_in_frame.join(", ")}</Meta>
          )}
          {shot.emotional_beat && (
            <span className="ml-auto rounded bg-primary/10 text-primary/90 px-1.5 py-0.5 text-[10px]">
              Beat · {shot.emotional_beat}
            </span>
          )}
        </div>

        {/* the script to prompt transformation, once this shot has rendered */}
        {shot.prompt_json?.prompt && <PromptEngineering pe={shot.prompt_json} />}
      </CardContent>
    </Card>
  );
}
