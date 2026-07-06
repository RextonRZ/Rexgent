"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { PipelineFlow } from "./PipelineFlow";
import { useAgentChat, type ChatMessage } from "@/hooks/useAgentChat";

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

/** The showrunner's feed: every agent narrates its work as it happens. */
export function AgentChat({ projectId }: { projectId: string }) {
  const { messages, running } = useAgentChat(projectId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(() => Date.now());

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
  }, [messages.length, running.length]);

  const stage = running[0]?.stage ?? null;

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
      </div>
    </div>
  );
}
