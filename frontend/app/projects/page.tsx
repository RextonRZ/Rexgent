"use client";

import { useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { NewProjectModal } from "@/components/home/NewProjectModal";
import { AuthGate } from "@/components/auth/AuthGate";
import { UserMenu } from "@/components/auth/UserMenu";
import { Skeleton } from "@/components/shared/Skeleton";
import { useProjects, useDeleteProject } from "@/hooks/useProjects";
import { useAuth } from "@/hooks/useAuth";
import type { Project } from "@/lib/types";

const STATUS_TONE: Record<string, string> = {
  draft: "text-muted-foreground",
  complete: "text-ok",
};

export default function ProjectsPage() {
  return (
    <AuthGate>
      <ProjectsHub />
    </AuthGate>
  );
}

function ProjectsHub() {
  const { data, isLoading } = useProjects();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const projects = data?.projects || [];
  const firstName = user?.full_name?.split(" ")[0];

  return (
    <main className="min-h-screen">
      {/* top nav */}
      <header className="sticky top-0 z-40 glass border-b hairline">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <Link href="/" className="font-bold tracking-tight">
            Rexgent
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-xs text-muted-foreground hidden sm:inline">
              AI Showrunner · Qwen Cloud
            </span>
            <UserMenu />
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="mx-auto max-w-6xl px-6 pt-16 pb-10 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-primary/80 mb-3">
          {firstName ? `Welcome back, ${firstName}` : "One premise. A whole drama."}
        </p>
        <h1 className="text-4xl sm:text-6xl font-bold tracking-tight">
          Direct films with a <span className="text-primary">crew of agents</span>.
        </h1>
        <p className="mt-4 text-muted-foreground max-w-xl mx-auto">
          Type a story idea. Rexgent writes it, casts it, storyboards it,
          generates it, and hands you back a finished short drama — on budget.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Button size="lg" onClick={() => setOpen(true)}>
            ⚡ Start a new drama
          </Button>
        </div>
      </section>

      {/* projects */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <h2 className="text-sm font-medium text-muted-foreground mb-4">
          Your dramas
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <button
            onClick={() => setOpen(true)}
            className="group rounded-xl border border-dashed border-border hover:border-primary/50 hover:bg-primary/5 transition-all min-h-[160px] flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-foreground"
          >
            <span className="text-3xl">+</span>
            <span className="text-sm font-medium">Start new project</span>
            <span className="text-[11px]">Initialize AI Showrunner</span>
          </button>

          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="min-h-[160px] rounded-xl" />
              ))
            : projects.map((p) => (
                <ProjectCard
                  key={p.id}
                  project={p}
                  onDelete={() => setDeleteTarget(p)}
                />
              ))}
        </div>

        {!isLoading && projects.length === 0 && (
          <p className="text-center text-sm text-muted-foreground mt-10">
            Your first drama is one idea away.
          </p>
        )}
      </section>

      <NewProjectModal open={open} onOpenChange={setOpen} />
      <DeleteProjectModal
        project={deleteTarget}
        onOpenChange={(v) => {
          if (!v) setDeleteTarget(null);
        }}
      />
    </main>
  );
}

function ProjectCard({
  project,
  onDelete,
}: {
  project: Project;
  onDelete: () => void;
}) {
  return (
    <Link href={`/projects/${project.id}/script`}>
      <div className="group relative rounded-xl border hairline bg-card hover:border-primary/40 transition-all overflow-hidden min-h-[160px] flex flex-col">
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDelete();
          }}
          title="Delete drama"
          aria-label={`Delete ${project.title}`}
          className="absolute top-2 right-2 z-10 rounded-md p-1.5 text-muted-foreground/70 opacity-0 group-hover:opacity-100 hover:text-destructive hover:bg-destructive/10 transition-all"
        >
          <Trash2 className="h-4 w-4" />
        </button>
        <div className="relative h-24 bg-gradient-to-br from-primary/20 via-secondary to-hh/10 flex items-center justify-center">
          <span className="text-[10px] uppercase tracking-widest text-foreground/70">
            {project.genre || "drama"}
          </span>
        </div>
        <div className="p-4 flex-1 flex flex-col justify-between">
          <p className="font-medium line-clamp-2 text-sm">{project.title}</p>
          <div className="flex items-center gap-1.5 mt-2">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                project.status === "complete" ? "bg-ok" : "bg-warn"
              }`}
            />
            <span
              className={`text-[11px] capitalize ${
                STATUS_TONE[project.status] || "text-muted-foreground"
              }`}
            >
              {project.status}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

function DeleteProjectModal({
  project,
  onOpenChange,
}: {
  project: Project | null;
  onOpenChange: (v: boolean) => void;
}) {
  const deleteProject = useDeleteProject();

  const handleDelete = async () => {
    if (!project) return;
    await deleteProject.mutateAsync(project.id);
    onOpenChange(false);
  };

  return (
    <Dialog open={Boolean(project)} onOpenChange={onOpenChange}>
      <DialogContent className="glass sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl">Delete this drama?</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <p className="text-sm text-muted-foreground">
            <span className="text-foreground font-medium">
              “{project?.title}”
            </span>{" "}
            and everything inside it — script, characters, storyboard, and
            generated clips — will be permanently deleted. This cannot be
            undone.
          </p>
          {deleteProject.isError && (
            <p className="text-sm text-destructive">
              Delete failed: {(deleteProject.error as Error).message}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={deleteProject.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteProject.isPending}
            >
              {deleteProject.isPending ? (
                "Deleting…"
              ) : (
                <>
                  <Trash2 className="h-4 w-4" />
                  Delete drama
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
