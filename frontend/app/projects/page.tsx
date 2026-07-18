"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  LayoutGrid,
  List,
  Search,
  Trash2,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { BTN_PRIMARY, CtaArrow } from "@/components/ui/cta";
import { NewProjectModal } from "@/components/home/NewProjectModal";
import { AuthGate } from "@/components/auth/AuthGate";
import { UserMenu } from "@/components/auth/UserMenu";
import { RecapShelf } from "@/components/dashboard/RecapShelf";
import {
  NewProjectTile,
  ProjectCard,
  ProjectRow,
  RenameDialog,
  statusOf,
  type ProjectAction,
} from "@/components/dashboard/ProjectCards";
import { PosterPicker } from "@/components/dashboard/PosterPicker";
import { Skeleton } from "@/components/shared/Skeleton";
import { AmbientBackdrop } from "@/components/shared/AmbientBackdrop";
import { EmptyState } from "@/components/shared/EmptyState";
import { SiteFooter } from "@/components/shared/SiteFooter";
import { cn } from "@/lib/utils";
import { PHOTOREAL, VISUAL_STYLES } from "@/lib/styles";
import {
  useDeleteProject,
  useDuplicateProject,
  useProjectsOverview,
} from "@/hooks/useProjects";
import { useAuth } from "@/hooks/useAuth";
import type { ProjectOverviewItem } from "@/lib/types";
import { errText } from "@/lib/errText";
import { GoLink, useGo } from "@/components/shared/NavProgress";

const VIEW_KEY = "rx.dashboard.view";

const SORTS = [
  { value: "edited", label: "Recently edited" },
  { value: "newest", label: "Newest" },
  { value: "az", label: "A–Z" },
  { value: "spent", label: "Budget spent" },
  { value: "status", label: "Status" },
];

const STATUS_ORDER: Record<string, number> = {
  generating: 0,
  draft: 1,
  complete: 2,
};

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs capitalize transition-colors",
        active
          ? "border-violet-500 bg-violet-500/10 text-violet-300"
          : "border-white/10 text-zinc-400 hover:border-white/25 hover:text-zinc-300"
      )}
    >
      {children}
    </button>
  );
}

export default function ProjectsPage() {
  return (
    <AuthGate>
      <Dashboard />
    </AuthGate>
  );
}

function Dashboard() {
  const go = useGo();
  const { data, isLoading } = useProjectsOverview();
  const { user } = useAuth();
  const deleteProject = useDeleteProject();
  const duplicateProject = useDuplicateProject();

  const [newOpen, setNewOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectOverviewItem | null>(null);
  const [renameTarget, setRenameTarget] = useState<ProjectOverviewItem | null>(null);
  const [posterTarget, setPosterTarget] = useState<ProjectOverviewItem | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("edited");
  const [genres, setGenres] = useState<string[]>([]);
  const [looks, setLooks] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [view, setView] = useState<"grid" | "list">("grid");

  // view preference survives reloads; read after mount to match SSR
  useEffect(() => {
    const saved = window.localStorage.getItem(VIEW_KEY);
    if (saved === "grid" || saved === "list") setView(saved);
  }, []);
  const changeView = (v: "grid" | "list") => {
    setView(v);
    window.localStorage.setItem(VIEW_KEY, v);
  };

  const projects = useMemo(() => data?.projects ?? [], [data]);
  const firstName = user?.full_name?.split(" ")[0];

  const allGenres = useMemo(
    () =>
      Array.from(
        new Set(
          projects
            .map((p) => p.genre?.toLowerCase().trim())
            .filter((g): g is string => Boolean(g))
        )
      ).sort(),
    [projects]
  );
  const allStatuses = useMemo(
    () => Array.from(new Set(projects.map(statusOf))).sort(),
    [projects]
  );
  const allLooks = useMemo(
    () =>
      Array.from(new Set(projects.map((p) => p.visual_style ?? PHOTOREAL))).sort(),
    [projects]
  );
  const lookLabel = (v: string) =>
    VISUAL_STYLES.find((s) => s.value === v)?.label ?? v;

  const filtered = useMemo(() => {
    let list = projects;
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((p) => p.title.toLowerCase().includes(q));
    if (genres.length)
      list = list.filter((p) => genres.includes(p.genre?.toLowerCase() ?? ""));
    if (looks.length)
      list = list.filter((p) => looks.includes(p.visual_style ?? PHOTOREAL));
    if (statuses.length) list = list.filter((p) => statuses.includes(statusOf(p)));

    const sorted = [...list];
    switch (sort) {
      case "newest":
        sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));
        break;
      case "az":
        sorted.sort((a, b) => a.title.localeCompare(b.title));
        break;
      case "spent":
        sorted.sort((a, b) => b.spent_usd - a.spent_usd);
        break;
      case "status":
        sorted.sort(
          (a, b) => STATUS_ORDER[statusOf(a)] - STATUS_ORDER[statusOf(b)]
        );
        break;
      default: // recently edited — the API order
        sorted.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    }
    return sorted;
  }, [projects, search, sort, genres, looks, statuses]);

  const filtersActive =
    genres.length > 0 || looks.length > 0 || statuses.length > 0 || search !== "";

  const toggle = (list: string[], set: (v: string[]) => void, value: string) =>
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  const handleAction = (action: ProjectAction, project: ProjectOverviewItem) => {
    switch (action) {
      case "open":
        go(`/projects/${project.id}/script`);
        break;
      case "poster":
        setPosterTarget(project);
        break;
      case "rename":
        setRenameTarget(project);
        break;
      case "duplicate":
        duplicateProject.mutate(project.id);
        break;
      case "delete":
        setDeleteTarget(project);
        break;
    }
  };

  return (
    <main className="relative min-h-screen">
      <AmbientBackdrop />
      <header className="sticky top-0 z-40 glass border-b hairline">
        <div className="mx-auto max-w-7xl px-6 h-14 flex items-center justify-between">
          <GoLink href="/" className="transition-opacity hover:opacity-80">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/rexgent_wordmark.png"
              alt="Rexgent"
              className="h-4 w-auto"
            />
          </GoLink>
          <UserMenu />
        </div>
      </header>

      {/* depth: slightly lighter up top where the shelf sits, darkening down */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[55vh] bg-gradient-to-b from-white/[0.02] to-transparent"
      />

      <div className="mx-auto max-w-7xl space-y-10 px-6 py-8">
        <div className="relative">
          {/* barely-there violet halo behind the shelf only */}
          <div
            aria-hidden
            className="pointer-events-none absolute -inset-x-16 -inset-y-10 -z-10"
            style={{
              background:
                "radial-gradient(55% 75% at 50% 35%, rgba(139,92,246,0.08), transparent 70%)",
            }}
          />
          <RecapShelf
            overview={data}
            userName={firstName}
            onNewDrama={() => setNewOpen(true)}
          />
        </div>

        <section>
          {/* toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight">Your dramas</h2>
            <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
              {filtered.length}
            </span>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search dramas"
                  className="h-9 w-64 rounded-lg border border-white/10 bg-zinc-900 pl-8 pr-3 text-sm placeholder:text-zinc-500 outline-none transition-colors focus-visible:border-violet-500/40 focus-visible:ring-2 focus-visible:ring-violet-500/25"
                />
              </div>
              <Select value={sort} onValueChange={(v) => v && setSort(v)}>
                <SelectTrigger className="h-9 w-44">
                  {/* base-ui renders the raw value otherwise ("az", "edited") */}
                  <SelectValue>
                    {SORTS.find((s) => s.value === sort)?.label}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {SORTS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex overflow-hidden rounded-lg border border-white/10">
                {(
                  [
                    ["grid", LayoutGrid],
                    ["list", List],
                  ] as const
                ).map(([v, Icon]) => (
                  <button
                    key={v}
                    aria-label={`${v} view`}
                    onClick={() => changeView(v)}
                    className={cn(
                      "flex h-9 w-9 items-center justify-center transition-colors",
                      view === v
                        ? "bg-violet-500/15 text-violet-300"
                        : "text-zinc-500 hover:text-zinc-300"
                    )}
                  >
                    <Icon className="size-4" />
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* filters: genre multi-select + status chips */}
          {(allGenres.length > 0 || allStatuses.length > 0) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {allGenres.length > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className={cn(
                      "flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs outline-none transition-colors",
                      genres.length > 0
                        ? "border-violet-500 bg-violet-500/10 text-violet-300"
                        : "border-white/10 text-zinc-400 hover:border-white/25 hover:text-zinc-300"
                    )}
                  >
                    Genre{genres.length > 0 && ` · ${genres.length}`}
                    <ChevronDown className="size-3.5" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-44 glass">
                    {allGenres.map((g) => (
                      <DropdownMenuCheckboxItem
                        key={g}
                        checked={genres.includes(g)}
                        closeOnClick={false}
                        onCheckedChange={() => toggle(genres, setGenres, g)}
                        className="capitalize"
                      >
                        {g}
                      </DropdownMenuCheckboxItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
              {allLooks.length > 1 && (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className={cn(
                      "flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs outline-none transition-colors",
                      looks.length > 0
                        ? "border-violet-500 bg-violet-500/10 text-violet-300"
                        : "border-white/10 text-zinc-400 hover:border-white/25 hover:text-zinc-300"
                    )}
                  >
                    Style{looks.length > 0 && ` · ${looks.length}`}
                    <ChevronDown className="size-3.5" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-48 glass">
                    {allLooks.map((v) => (
                      <DropdownMenuCheckboxItem
                        key={v}
                        checked={looks.includes(v)}
                        closeOnClick={false}
                        onCheckedChange={() => toggle(looks, setLooks, v)}
                      >
                        {lookLabel(v)}
                      </DropdownMenuCheckboxItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
              {allStatuses.map((s) => (
                <Chip
                  key={s}
                  active={statuses.includes(s)}
                  onClick={() => toggle(statuses, setStatuses, s)}
                >
                  {s}
                </Chip>
              ))}
              {filtersActive && (
                <button
                  onClick={() => {
                    setGenres([]);
                    setLooks([]);
                    setStatuses([]);
                    setSearch("");
                  }}
                  className="text-xs text-zinc-500 underline-offset-2 transition-colors hover:text-zinc-300 hover:underline"
                >
                  Clear all
                </button>
              )}
            </div>
          )}

          {/* content */}
          <div className="mt-5">
            {isLoading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="min-h-[220px] rounded-xl" />
                ))}
              </div>
            ) : projects.length === 0 ? (
              <EmptyState
                title="No dramas yet"
                line="Type one premise and watch a studio go to work."
              >
                <Button
                  onClick={() => setNewOpen(true)}
                  className={cn("h-10", BTN_PRIMARY)}
                >
                  Start your first drama
                  <CtaArrow />
                </Button>
              </EmptyState>
            ) : view === "grid" ? (
              <div className="grid grid-flow-dense grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {/* the freshest drama leads as a 2x2 hero — the grid gets a
                    focal point instead of a uniform wall */}
                {filtered.length > 0 && (
                  <ProjectCard
                    key={filtered[0].id}
                    hero
                    project={filtered[0]}
                    previewing={previewId === filtered[0].id}
                    onPreview={setPreviewId}
                    onAction={handleAction}
                    className="card-rise sm:col-span-2 sm:row-span-2"
                  />
                )}
                <NewProjectTile
                  className="card-rise"
                  style={{ animationDelay: "40ms" }}
                  onClick={() => setNewOpen(true)}
                />
                {filtered.slice(1).map((p, i) => (
                  <ProjectCard
                    key={p.id}
                    project={p}
                    previewing={previewId === p.id}
                    onPreview={setPreviewId}
                    onAction={handleAction}
                    className="card-rise"
                    style={{ animationDelay: `${Math.min(i + 2, 12) * 40}ms` }}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {filtered.map((p, i) => (
                  <ProjectRow
                    key={p.id}
                    project={p}
                    onAction={handleAction}
                    className="card-rise"
                    style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
                  />
                ))}
              </div>
            )}
            {!isLoading && projects.length > 0 && filtered.length === 0 && (
              <p className="mt-8 text-center text-sm text-muted-foreground">
                Nothing matches those filters.
              </p>
            )}
          </div>
        </section>
      </div>

      <SiteFooter />

      <NewProjectModal open={newOpen} onOpenChange={setNewOpen} />
      <RenameDialog
        project={renameTarget}
        onOpenChange={(v) => !v && setRenameTarget(null)}
      />
      <PosterPicker
        project={posterTarget}
        onOpenChange={(v) => !v && setPosterTarget(null)}
      />
      <DeleteProjectModal
        project={deleteTarget}
        onDelete={async (id) => {
          await deleteProject.mutateAsync(id);
          setDeleteTarget(null);
        }}
        pending={deleteProject.isPending}
        error={
          deleteProject.isError
            ? errText(deleteProject.error)
            : null
        }
        onOpenChange={(v) => !v && setDeleteTarget(null)}
      />
    </main>
  );
}

function DeleteProjectModal({
  project,
  onDelete,
  pending,
  error,
  onOpenChange,
}: {
  project: ProjectOverviewItem | null;
  onDelete: (id: string) => void;
  pending: boolean;
  error: string | null;
  onOpenChange: (v: boolean) => void;
}) {
  return (
    <Dialog open={Boolean(project)} onOpenChange={onOpenChange}>
      <DialogContent className="glass sm:max-w-md" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle className="text-xl">Delete this drama?</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">
              “{project?.title}”
            </span>{" "}
            and everything inside it — script, characters, storyboard, and
            generated clips — will be permanently deleted. This cannot be
            undone.
          </p>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={pending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => project && onDelete(project.id)}
              disabled={pending}
            >
              {pending ? (
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
