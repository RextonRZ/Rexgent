"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { getSocket } from "@/lib/websocket";
import { PipelineFlow } from "./PipelineFlow";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAgentChat, type ChatMessage } from "@/hooks/useAgentChat";
import { useClarifications } from "@/hooks/useAgents";
import { useApproveCasting } from "@/hooks/useCasting";
import { useCalculateBudget } from "@/hooks/useBudget";
import { useUpdateProject } from "@/hooks/useProjects";

// a stable tint per agent so the feed reads like a room of specialists
const AGENT_DOT: Record<string, string> = {
  Screenwriter: "bg-violet-400",
  Director: "bg-sky-400",
  "Casting Director": "bg-pink-400",
  "Story Analyst": "bg-teal-400",
  Renderer: "bg-amber-400",
  Continuity: "bg-emerald-400",
  Producer: "bg-red-400",
  Showrunner: "bg-primary",
};

const KIND_MARK: Record<ChatMessage["kind"], { glyph: string; cls: string }> = {
  done: { glyph: "✓", cls: "text-ok" },
  info: { glyph: "·", cls: "text-muted-foreground" },
  warn: { glyph: "●", cls: "text-warn" },
  fail: { glyph: "✕", cls: "text-bad" },
};

function timeOf(at: number) {
  return new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function prettyAgent(raw: string) {
  if (AGENT_DOT[raw]) return raw;
  // backend report keys like narrative_judge / style_casting → Title Case
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function Bubble({ m }: { m: ChatMessage }) {
  const agent = prettyAgent(m.agent);
  const mark = KIND_MARK[m.kind];
  return (
    <div className="group">
      <div className="flex items-center gap-1.5">
        <span className={cn("h-1.5 w-1.5 rounded-full", AGENT_DOT[agent] ?? "bg-secondary")} />
        <span className="text-[10px] font-medium text-muted-foreground">{agent}</span>
        {typeof m.pct === "number" && m.pct > 0 && (
          <span className="text-[9px] tabular-nums text-muted-foreground/70">{m.pct}%</span>
        )}
        <span className="ml-auto text-[9px] tabular-nums text-muted-foreground/50 opacity-0 group-hover:opacity-100 transition-opacity">
          {timeOf(m.at)}
        </span>
      </div>
      <div className="mt-0.5 flex gap-1.5 rounded-lg rounded-tl-sm bg-white/[0.03] px-2.5 py-1.5">
        <span className={cn("shrink-0 text-[11px] leading-4", mark.cls)}>{mark.glyph}</span>
        <p className="text-[11px] leading-4 text-foreground/90">
          {m.text}
          {m.detail && (
            <span className="ml-1 text-muted-foreground">({m.detail})</span>
          )}
        </p>
      </div>
    </div>
  );
}

/** Live "…is working" bubble with animated dots and elapsed time — nothing in
 * the studio ever looks hung again. */
function TypingBubble({
  agent,
  label,
  since,
  index,
  total,
  now,
}: {
  agent: string;
  label: string;
  since: number;
  index?: number;
  total?: number;
  now: number;
}) {
  const secs = Math.max(0, Math.floor((now - since) / 1000));
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <span className={cn("h-1.5 w-1.5 rounded-full animate-pulse", AGENT_DOT[agent] ?? "bg-primary")} />
        <span className="text-[10px] font-medium text-foreground">{agent}</span>
        <span className="ml-auto text-[9px] tabular-nums text-muted-foreground">
          {secs >= 60 ? `${Math.floor(secs / 60)}m ${secs % 60}s` : `${secs}s`}
        </span>
      </div>
      <div className="mt-0.5 rounded-lg rounded-tl-sm border border-primary/20 bg-primary/[0.06] px-2.5 py-1.5">
        <p className="text-[11px] leading-4 text-foreground/90">
          {label}
          {index && total ? (
            <span className="ml-1 tabular-nums text-muted-foreground">
              {index}/{total}
            </span>
          ) : null}
        </p>
        <span className="mt-1 flex gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1 w-1 rounded-full bg-primary/70 animate-bounce"
              style={{ animationDelay: `${i * 0.18}s` }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}

/** An "I need you" card from the crew: framed hotter than the log bubbles. */
function ActionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-primary/30 bg-primary/[0.08] p-2.5 space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-primary">
        {title}
      </p>
      {children}
    </div>
  );
}

/** The crew pauses and asks; you answer without leaving the chat. */
function ClarificationCard({ projectId }: { projectId: string }) {
  const { questions, submit } = useClarifications(projectId);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  if (questions.length === 0) return null;

  const done = questions.every((q) => (answers[q.topic] || "").trim());
  const handle = async () => {
    setBusy(true);
    try {
      await submit(
        questions.map((q) => ({ topic: q.topic, answer: (answers[q.topic] || "").trim() }))
      );
      setAnswers({});
    } finally {
      setBusy(false);
    }
  };

  return (
    <ActionCard title="The crew needs input">
      {questions.map((q) => (
        <div key={q.topic} className="space-y-1">
          <p className="text-[11px] leading-4 text-foreground/90">{q.question}</p>
          {q.options && q.options.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {q.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setAnswers((a) => ({ ...a, [q.topic]: opt }))}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[10px] transition-colors",
                    answers[q.topic] === opt
                      ? "border-primary bg-primary/20 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/40"
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
          <Input
            value={answers[q.topic] ?? ""}
            onChange={(e) => setAnswers((a) => ({ ...a, [q.topic]: e.target.value }))}
            placeholder="Type your answer…"
            className="h-7 bg-background/50 text-[11px]"
          />
        </div>
      ))}
      <Button size="sm" className="h-7 w-full text-xs" disabled={!done || busy} onClick={handle}>
        {busy ? "Resuming…" : "Answer and resume"}
      </Button>
    </ActionCard>
  );
}

interface BudgetFit {
  deferred: number;
  downgraded: number;
  cap: number;
  suggested_cap: number;
}

export function AgentChat({ projectId }: { projectId: string }) {
  const router = useRouter();
  const { messages, running } = useAgentChat(projectId);
  const approveCasting = useApproveCasting(projectId);
  const updateProject = useUpdateProject();
  const recalcBudget = useCalculateBudget();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(() => Date.now());
  const [awaitingCasting, setAwaitingCasting] = useState(false);
  const [budgetFit, setBudgetFit] = useState<BudgetFit | null>(null);
  const [exportUrl, setExportUrl] = useState<string | null>(null);

  // decision moments arrive as events and park as cards until acted on
  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    const onAwait = () => setAwaitingCasting(true);
    const onCast = (p: { auto_approved?: boolean }) => {
      if (p?.auto_approved) setAwaitingCasting(false);
    };
    const onFit = (p: BudgetFit) => setBudgetFit(p?.deferred > 0 ? p : null);
    const onExport = (p: { url?: string }) => setExportUrl(p?.url ?? null);
    socket.on("casting.awaiting_review", onAwait);
    socket.on("casting.completed", onCast);
    socket.on("budget:fitted", onFit);
    socket.on("export.completed", onExport);
    return () => {
      socket.off("casting.awaiting_review", onAwait);
      socket.off("casting.completed", onCast);
      socket.off("budget:fitted", onFit);
      socket.off("export.completed", onExport);
    };
  }, [projectId]);

  // tick the elapsed timers only while something is running
  useEffect(() => {
    if (running.length === 0) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running.length]);

  // stay pinned to the newest message
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, running.length, awaitingCasting, budgetFit, exportUrl]);

  const stage = running[0]?.stage ?? null;

  const raiseCap = async () => {
    if (!budgetFit) return;
    await updateProject.mutateAsync({
      projectId,
      credit_budget: budgetFit.suggested_cap,
    });
    await recalcBudget.mutateAsync(projectId);
    setBudgetFit(null);
  };

  return (
    <div className="flex flex-col gap-3">
      <PipelineFlow current={stage} />

      <div
        ref={scrollRef}
        className="max-h-[46vh] space-y-2.5 overflow-y-auto pr-0.5"
      >
        {messages.length === 0 && running.length === 0 ? (
          <p className="text-[11px] leading-5 text-muted-foreground">
            Your crew reports here while it works: the screenwriter, director,
            casting director, continuity and the renderer. Start any step and
            watch the studio come alive.
          </p>
        ) : (
          messages.map((m) => <Bubble key={m.id} m={m} />)
        )}

        {running.map((r) => (
          <TypingBubble
            key={r.stage}
            agent={r.agent}
            label={r.label}
            since={r.since}
            index={r.index}
            total={r.total}
            now={now}
          />
        ))}

        <ClarificationCard projectId={projectId} />

        {awaitingCasting && (
          <ActionCard title="Casting ready for review">
            <p className="text-[11px] leading-4 text-foreground/90">
              The bible is cast: faces, costumes, locations and style plates.
              Approving fits the budget and starts paid video generation.
            </p>
            <div className="flex gap-1.5">
              <Button
                size="sm"
                variant="outline"
                className="h-7 flex-1 text-xs"
                onClick={() => router.push(`/projects/${projectId}/characters`)}
              >
                Review plates
              </Button>
              <Button
                size="sm"
                className="h-7 flex-1 text-xs"
                disabled={approveCasting.isPending}
                onClick={() =>
                  approveCasting.mutate(undefined, {
                    onSuccess: () => setAwaitingCasting(false),
                  })
                }
              >
                {approveCasting.isPending ? "Starting…" : "Approve and generate"}
              </Button>
            </div>
          </ActionCard>
        )}

        {budgetFit && (
          <ActionCard title="Plan trimmed to fit the cap">
            <p className="text-[11px] leading-4 text-foreground/90">
              {budgetFit.deferred} shot(s) deferred
              {budgetFit.downgraded > 0
                ? ` and ${budgetFit.downgraded} downgraded`
                : ""}{" "}
              to fit your ${budgetFit.cap.toFixed(0)} cap. Raising it to $
              {budgetFit.suggested_cap} keeps every shot.
            </p>
            <div className="flex gap-1.5">
              <Button
                size="sm"
                variant="outline"
                className="h-7 flex-1 text-xs"
                onClick={() => setBudgetFit(null)}
              >
                Keep the trim
              </Button>
              <Button
                size="sm"
                className="h-7 flex-1 text-xs"
                disabled={updateProject.isPending || recalcBudget.isPending}
                onClick={raiseCap}
              >
                {updateProject.isPending || recalcBudget.isPending
                  ? "Refitting…"
                  : `Raise cap to $${budgetFit.suggested_cap}`}
              </Button>
            </div>
          </ActionCard>
        )}

        {exportUrl && (
          <ActionCard title="Your episode is ready">
            <p className="text-[11px] leading-4 text-foreground/90">
              Rendered, voiced and subtitled. Premiere it.
            </p>
            <Button
              size="sm"
              className="h-7 w-full text-xs glow"
              onClick={() => {
                setExportUrl(null);
                router.push(`/projects/${projectId}/export`);
              }}
            >
              ▶ Watch the episode
            </Button>
          </ActionCard>
        )}
      </div>
    </div>
  );
}
