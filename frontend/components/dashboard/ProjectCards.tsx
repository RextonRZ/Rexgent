"use client";

import { useState } from "react";
import { Loader2, MoreVertical, Plus, Sparkles } from "lucide-react";
import { genreDef, posterGradient } from "@/lib/genres";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { BTN_PRIMARY } from "@/components/ui/cta";
import { FIELD } from "@/components/auth/AuthShell";
import { GRAIN } from "@/components/landing/CtaBackdrop";
import { cn } from "@/lib/utils";
import { relTime } from "@/components/dashboard/format";
import { useSuggestTitle, useUpdateProject } from "@/hooks/useProjects";
import type { ProjectOverviewItem } from "@/lib/types";

/** Titles that are really the raw prompt: long, screenplay-ish, or trailing off. */
export function isPromptLikeTitle(title: string): boolean {
  return (
    title.split(/\s+/).length > 8 ||
    /\b(INT|EXT)\./.test(title) ||
    title.trimEnd().endsWith("...")
  );
}

export type ProjectAction = "open" | "poster" | "rename" | "duplicate" | "delete";

export function statusOf(p: ProjectOverviewItem): string {
  if (p.is_generating) return "generating";
  if (p.status === "complete") return "complete";
  return "draft";
}

export function StatusPill({ project }: { project: ProjectOverviewItem }) {
  const s = statusOf(project);
  if (s === "generating") {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-violet-500/10 px-2 py-0.5 text-[11px] text-violet-300">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
        Generating
      </span>
    );
  }
  if (s === "complete") {
    return (
      <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-400">
        Complete
      </span>
    );
  }
  return (
    <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-zinc-400">
      Draft
    </span>
  );
}

function KebabMenu({
  project,
  onAction,
  className,
}: {
  project: ProjectOverviewItem;
  onAction: (action: ProjectAction, project: ProjectOverviewItem) => void;
  className?: string;
}) {
  return (
    <div className={className} onClick={(e) => e.stopPropagation()}>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`Actions for ${project.title}`}
          className="flex h-7 w-7 items-center justify-center rounded-md bg-black/50 text-zinc-300 outline-none backdrop-blur-sm transition-colors hover:bg-black/70 hover:text-white focus-visible:ring-2 focus-visible:ring-violet-400/60"
        >
          <MoreVertical className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44 glass">
          <DropdownMenuItem
            className="cursor-pointer"
            onClick={() => onAction("open", project)}
          >
            Open
          </DropdownMenuItem>
          <DropdownMenuItem
            className="cursor-pointer"
            disabled={project.clip_count === 0}
            onClick={() => onAction("poster", project)}
          >
            Change poster
          </DropdownMenuItem>
          <DropdownMenuItem
            className="cursor-pointer"
            onClick={() => onAction("rename", project)}
          >
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            className="cursor-pointer"
            onClick={() => onAction("duplicate", project)}
          >
            Duplicate
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="cursor-pointer text-destructive focus:text-destructive"
            onClick={() => onAction("delete", project)}
          >
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export function PosterImage({
  project,
  className,
  detailed = false,
}: {
  project: ProjectOverviewItem;
  className?: string;
  /** full teaser treatment (ghost title, grain, sprockets, shimmer) — for
   * card-sized posters only; tiny thumbnails stay clean */
  detailed?: boolean;
}) {
  // a generating drama's poster carries a light sweep — work in progress
  const shimmer = detailed && statusOf(project) === "generating" && (
    <span
      aria-hidden
      className="pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/[0.09] to-transparent motion-safe:animate-[poster-shimmer_2.4s_ease-in-out_infinite]"
    />
  );

  if (project.poster_url) {
    return (
      <div className={cn("relative h-full w-full overflow-hidden", className)}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={project.poster_url}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
        />
        {shimmer}
      </div>
    );
  }

  // Teaser one-sheet, not a broken image: genre duotone, ghosted title
  // typography clipped by the edges, film grain, a whisper of sprockets.
  const def = genreDef(project.genre);
  return (
    <div
      className={cn("relative h-full w-full overflow-hidden", className)}
      style={{ background: posterGradient(project.genre) }}
    >
      {detailed && (
        <span
          aria-hidden
          className="absolute -left-1 top-1.5 select-none break-words pr-8 text-[1.9rem] font-bold uppercase leading-[0.95] tracking-tight text-white/[0.09] line-clamp-3"
        >
          {project.title}
        </span>
      )}
      <def.icon
        aria-hidden
        className="absolute -bottom-3 -right-3 size-16 rotate-[-8deg] text-white opacity-20"
        strokeWidth={1.25}
      />
      {detailed && (
        <>
          <span
            aria-hidden
            className="absolute inset-0 opacity-[0.06] mix-blend-overlay"
            style={{ backgroundImage: GRAIN }}
          />
          <span
            aria-hidden
            className="absolute inset-x-0 bottom-1 flex justify-center gap-2 opacity-20"
          >
            {Array.from({ length: 12 }).map((_, i) => (
              <span key={i} className="h-[4px] w-[5px] rounded-[1px] bg-white" />
            ))}
          </span>
        </>
      )}
      {shimmer}
    </div>
  );
}

function GenreTag({ genre }: { genre: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-zinc-400">
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: genreDef(genre).dot }}
      />
      {genre}
    </span>
  );
}

export function ProjectCard({
  project,
  previewing,
  onPreview,
  onAction,
  className,
  style,
  hero = false,
}: {
  project: ProjectOverviewItem;
  previewing: boolean;
  onPreview: (id: string | null) => void;
  onAction: (action: ProjectAction, project: ProjectOverviewItem) => void;
  className?: string;
  style?: React.CSSProperties;
  /** the featured 2x2 card: bigger poster, premise line, hover quick actions */
  hero?: boolean;
}) {
  // Prompt-like titles get a sparkle: one click asks the LLM for a clean
  // title, offered inline with Accept / Keep. Never renames on its own.
  const promptLike = isPromptLikeTitle(project.title);
  const suggest = useSuggestTitle();
  const update = useUpdateProject();
  const [suggestion, setSuggestion] = useState<string | null>(null);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onAction("open", project)}
      onKeyDown={(e) => e.key === "Enter" && onAction("open", project)}
      style={style}
      className={cn(
        "group relative flex h-full cursor-pointer flex-col overflow-hidden rounded-xl border border-white/[0.08] bg-zinc-900/60 outline-none transition-all duration-300 hover:-translate-y-0.5 hover:border-violet-500/30 hover:shadow-[0_10px_36px_-12px_rgba(139,92,246,0.4)] focus-visible:ring-2 focus-visible:ring-violet-400/60",
        className
      )}
    >
      <div
        className={cn(
          "relative min-h-0 overflow-hidden bg-zinc-950",
          // the poster is the star: taller than 16:9 on standard cards, and
          // the hero card lets it flex-fill the doubled cell
          hero ? "flex-1" : "aspect-[16/10]"
        )}
        onMouseEnter={() =>
          project.preview_clip_url && onPreview(project.id)
        }
        onMouseLeave={() => onPreview(null)}
      >
        <PosterImage project={project} detailed className={hero ? "absolute inset-0" : undefined} />
        {/* poster gradient scrim so the title area reads on busy stills */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/50 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        {previewing && project.preview_clip_url && (
          <video
            src={project.preview_clip_url}
            muted
            loop
            playsInline
            autoPlay
            preload="metadata"
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}
        {hero && (
          <div className="absolute bottom-3 right-3 z-10 flex gap-1.5 opacity-0 transition-opacity duration-200 focus-within:opacity-100 group-hover:opacity-100">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAction("open", project);
              }}
              className="rounded-lg bg-black/60 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm transition-colors hover:bg-violet-600/80"
            >
              Open
            </button>
            {project.clip_count > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAction("poster", project);
                }}
                className="rounded-lg bg-black/60 px-3 py-1.5 text-xs text-zinc-200 backdrop-blur-sm transition-colors hover:bg-black/80 hover:text-white"
              >
                Change poster
              </button>
            )}
          </div>
        )}
      </div>

      <div className={cn("flex flex-col", hero ? "gap-1.5 p-4" : "gap-1.5 p-3.5")}>
        <div className="flex items-center gap-1.5">
          <p
            title={project.title}
            className={cn(
              "min-w-0 flex-1 truncate font-medium",
              hero ? "text-lg font-semibold" : "text-[15px]"
            )}
          >
            {project.title}
          </p>
          {promptLike && !suggestion && (
            <button
              title="Suggest a title"
              aria-label="Suggest a title"
              disabled={suggest.isPending}
              onClick={(e) => {
                e.stopPropagation();
                suggest
                  .mutateAsync(project.premise?.trim() || project.title)
                  .then(setSuggestion)
                  .catch(() => {});
              }}
              className="shrink-0 rounded text-violet-300/70 outline-none transition-colors hover:text-violet-300 focus-visible:ring-2 focus-visible:ring-violet-400/60"
            >
              {suggest.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Sparkles className="size-3.5" />
              )}
            </button>
          )}
        </div>
        {suggestion && (
          <div
            className="flex items-center gap-2 rounded-lg border border-violet-500/30 bg-violet-500/10 px-2 py-1.5"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="min-w-0 flex-1 truncate text-xs text-violet-200">
              {suggestion}
            </span>
            <button
              className="text-xs font-medium text-violet-300 transition-colors hover:text-violet-200"
              disabled={update.isPending}
              onClick={async () => {
                await update.mutateAsync({
                  projectId: project.id,
                  title: suggestion,
                });
                setSuggestion(null);
              }}
            >
              {update.isPending ? "Saving..." : "Accept"}
            </button>
            <button
              className="text-xs text-zinc-500 transition-colors hover:text-zinc-300"
              onClick={() => setSuggestion(null)}
            >
              Keep
            </button>
          </div>
        )}
        {hero && project.premise && (
          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {project.premise}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          {project.genre && <GenreTag genre={project.genre} />}
          <StatusPill project={project} />
          <span className="ml-auto text-muted-foreground">
            Edited {relTime(project.updated_at)}
          </span>
        </div>
      </div>

      <KebabMenu
        project={project}
        onAction={onAction}
        className="absolute right-2 top-2 z-10 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100"
      />
    </div>
  );
}

export function ProjectRow({
  project,
  onAction,
  className,
  style,
}: {
  project: ProjectOverviewItem;
  onAction: (action: ProjectAction, project: ProjectOverviewItem) => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onAction("open", project)}
      onKeyDown={(e) => e.key === "Enter" && onAction("open", project)}
      style={style}
      className={cn(
        "group flex cursor-pointer items-center gap-4 rounded-xl border border-white/[0.08] bg-zinc-900/60 p-3 outline-none transition-colors hover:border-white/15 focus-visible:ring-2 focus-visible:ring-violet-400/60",
        className
      )}
    >
      <div className="h-16 w-28 shrink-0 overflow-hidden rounded-md bg-zinc-950">
        <PosterImage project={project} />
      </div>
      <p title={project.title} className="min-w-0 flex-1 truncate text-sm font-medium">
        {project.title}
      </p>
      {project.genre && (
        <span className="hidden sm:inline">
          <GenreTag genre={project.genre} />
        </span>
      )}
      <StatusPill project={project} />
      <span className="hidden w-24 text-right text-[11px] text-muted-foreground md:inline">
        {relTime(project.updated_at)}
      </span>
      <span className="hidden w-16 text-right font-mono text-[11px] text-muted-foreground sm:inline">
        ${project.spent_usd.toFixed(2)}
      </span>
      <KebabMenu
        project={project}
        onAction={onAction}
        className="opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100"
      />
    </div>
  );
}

export function NewProjectTile({
  onClick,
  className,
  style,
}: {
  onClick: () => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <button
      onClick={onClick}
      style={style}
      className={cn(
        "group flex h-full min-h-[200px] w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-muted-foreground transition-all duration-300 hover:-translate-y-1 hover:border-violet-500/60 hover:bg-violet-500/5 hover:text-foreground",
        className
      )}
    >
      <span className="flex size-11 items-center justify-center rounded-full border border-dashed border-violet-500/40 transition-colors group-hover:border-violet-500/70 group-hover:bg-violet-500/10">
        <Plus className="size-5" />
      </span>
      <span className="text-sm font-medium">Start new drama</span>
    </button>
  );
}

export function RenameDialog({
  project,
  onOpenChange,
}: {
  project: ProjectOverviewItem | null;
  onOpenChange: (v: boolean) => void;
}) {
  const update = useUpdateProject();
  const [title, setTitle] = useState("");

  // seed the input when a new target opens
  const [seededFor, setSeededFor] = useState<string | null>(null);
  if (project && seededFor !== project.id) {
    setSeededFor(project.id);
    setTitle(project.title);
  }

  const save = async () => {
    if (!project || !title.trim()) return;
    await update.mutateAsync({ projectId: project.id, title: title.trim() });
    onOpenChange(false);
  };

  return (
    <Dialog open={Boolean(project)} onOpenChange={onOpenChange}>
      <DialogContent className="glass sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Rename drama</DialogTitle>
        </DialogHeader>
        <form
          className="space-y-4 pt-2"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            className={FIELD}
            placeholder="Drama title"
          />
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={update.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!title.trim() || update.isPending}
              className={cn("px-5", BTN_PRIMARY)}
            >
              {update.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
