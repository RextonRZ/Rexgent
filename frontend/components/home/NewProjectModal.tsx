"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { GENRES } from "@/lib/genres";
import {
  useBudgetEstimate,
  useCreateProject,
  useSuggestTitle,
} from "@/hooks/useProjects";

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

export function NewProjectModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const createProject = useCreateProject();
  const suggestTitle = useSuggestTitle();
  const [premise, setPremise] = useState("");
  const [genre, setGenre] = useState("sci-fi");
  const [mode, setMode] = useState<"auto" | "guided">("auto");
  const [ratio, setRatio] = useState<"9:16" | "16:9">("9:16");
  const [episodes, setEpisodes] = useState(1);
  const [length, setLength] = useState(30);
  const [budgetOverride, setBudgetOverride] = useState<number | null>(null);

  const { data: estimate } = useBudgetEstimate({
    episode_count: episodes,
    target_length: length,
  });

  // The spend cap defaults to the projection plus ~20% headroom (rounded up to
  // a clean number), but the user can set their own.
  const suggestedBudget = estimate
    ? Math.max(5, Math.ceil((estimate.credit_usd * 1.2) / 5) * 5)
    : 40;
  const budget = budgetOverride ?? suggestedBudget;
  const overBudget = Boolean(estimate && estimate.credit_usd > budget);

  const pending = createProject.isPending || suggestTitle.isPending;

  const handleCreate = async () => {
    // The card never wears the raw prompt: derive a short evocative title,
    // keep the premise stored separately on the project.
    const p = premise.trim();
    let title = "Untitled Drama";
    if (p) {
      try {
        title = await suggestTitle.mutateAsync(p);
      } catch {
        title = p.slice(0, 60);
      }
    }
    const project = await createProject.mutateAsync({
      title,
      genre,
      premise,
      credit_budget: budget,
      token_budget: estimate?.llm_tokens,
      video_ratio: ratio,
    });
    router.push(
      `/projects/${project.id}/script?mode=${mode}&ep=${episodes}&len=${length}`
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl">New drama</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <Label className="text-xs text-muted-foreground">Premise</Label>
            <Textarea
              value={premise}
              onChange={(e) => setPremise(e.target.value.slice(0, 300))}
              placeholder="A detective in 2047 Tokyo discovers her partner is an AI."
              rows={3}
              className="mt-1 bg-background/50"
              autoFocus
            />
            <p className="text-[11px] text-muted-foreground mt-1">
              {premise.length}/300
            </p>
          </div>

          <div>
            <Label className="text-xs text-muted-foreground">Genre</Label>
            <Select value={genre} onValueChange={(v) => v && setGenre(v)}>
              <SelectTrigger className="mt-1 bg-background/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GENRES.map((g) => (
                  <SelectItem key={g.value} value={g.value}>
                    <g.icon className="size-3.5 text-muted-foreground" />
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* delivery format: drives generation ratio, export canvas, player */}
          <div>
            <Label className="text-xs text-muted-foreground">Format</Label>
            <div className="mt-1 grid grid-cols-2 gap-2">
              <FormatCard
                active={ratio === "9:16"}
                onClick={() => setRatio("9:16")}
                title="9:16 Vertical"
                desc="Short drama for phones. Recommended."
                frameClass="h-7 w-4"
              />
              <FormatCard
                active={ratio === "16:9"}
                onClick={() => setRatio("16:9")}
                title="16:9 Landscape"
                desc="Widescreen for desktop and TV."
                frameClass="h-4 w-7"
              />
            </div>
          </div>

          {/* scope */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs text-muted-foreground">Episodes</Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={episodes}
                onChange={(e) =>
                  setEpisodes(Math.max(1, Number(e.target.value) || 1))
                }
                className="mt-1 bg-background/50"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">
                Length (sec/ep)
              </Label>
              <Input
                type="number"
                min={10}
                max={600}
                step={5}
                value={length}
                onChange={(e) =>
                  setLength(Math.max(10, Number(e.target.value) || 10))
                }
                className="mt-1 bg-background/50"
              />
            </div>
          </div>

          {/* budget projection for this drama */}
          <div className="rounded-lg border hairline bg-background/40 p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Budget for this drama</span>
              {estimate && (
                <span className="text-[11px] text-muted-foreground">
                  ≈ {estimate.scope.scenes} scenes · {estimate.scope.shots} shots
                  · {estimate.scope.video_seconds}s
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Tokens (LLM)
                </p>
                <p className="font-mono text-sm">
                  {estimate ? fmtTokens(estimate.llm_tokens) : "—"}
                </p>
              </div>
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Generation
                </p>
                <p className="font-mono text-sm">
                  {estimate ? `$${estimate.credit_usd.toFixed(2)}` : "—"}
                </p>
              </div>
            </div>

            {estimate && (
              <p className="text-[10px] text-muted-foreground">
                Video ${estimate.credit_breakdown.video.toFixed(2)} · Images $
                {estimate.credit_breakdown.image.toFixed(2)} · Voice $
                {estimate.credit_breakdown.tts.toFixed(2)}
              </p>
            )}

            <div className="flex items-center gap-2 pt-0.5">
              <Label className="text-[11px] text-muted-foreground shrink-0">
                Spend cap
              </Label>
              <div className="relative">
                <span className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                  $
                </span>
                <Input
                  type="number"
                  min={5}
                  step={5}
                  value={budget}
                  onChange={(e) =>
                    setBudgetOverride(Math.max(5, Number(e.target.value) || 5))
                  }
                  className="h-8 w-24 bg-background/50 pl-5 text-sm"
                />
              </div>
              <span className="text-[11px] text-muted-foreground">
                the agent fits generation under this
              </span>
            </div>

            {overBudget && (
              <p className="text-[11px] text-warn">
                Projected spend is above your cap — the agent will render fewer
                or shorter shots to fit.
              </p>
            )}
          </div>

          <div>
            <Label className="text-xs text-muted-foreground">How should we build it?</Label>
            <div className="mt-1 grid grid-cols-2 gap-2">
              <ModeCard
                active={mode === "auto"}
                onClick={() => setMode("auto")}
                title="⚡ Full Auto"
                desc="The agent runs every stage. You watch."
              />
              <ModeCard
                active={mode === "guided"}
                onClick={() => setMode("guided")}
                title="Guided"
                desc="Review and approve each stage."
              />
            </div>
          </div>

          <Button
            onClick={handleCreate}
            disabled={pending}
            className="w-full glow"
            size="lg"
          >
            {pending ? "Creating…" : "Create drama →"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FormatCard({
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

function ModeCard({
  active,
  onClick,
  title,
  desc,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  desc: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "text-left rounded-lg border p-3 transition-all",
        active
          ? "border-primary bg-primary/10"
          : "border-border hover:border-primary/40"
      )}
    >
      <div className="text-sm font-semibold">{title}</div>
      <div className="text-[11px] text-muted-foreground mt-0.5">{desc}</div>
    </button>
  );
}
