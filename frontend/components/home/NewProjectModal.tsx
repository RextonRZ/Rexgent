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
import { useCreateProject, useSuggestTitle } from "@/hooks/useProjects";

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
    const project = await createProject.mutateAsync({ title, genre, premise });
    router.push(`/projects/${project.id}/script?mode=${mode}`);
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
