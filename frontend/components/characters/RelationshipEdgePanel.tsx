"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CharacterRelationship } from "@/lib/types";

export interface EdgeCharacterInfo {
  name: string;
  image?: string | null;
}

interface RelationshipEdgePanelProps {
  rel: CharacterRelationship | null;
  characterById: Record<string, EdgeCharacterInfo>;
  onClose: () => void;
}

const EVOLUTION_LABELS: Record<string, string> = {
  STATIC: "Stays the same",
  GROWS: "Grows stronger",
  DETERIORATES: "Deteriorates",
  TRANSFORMS: "Transforms",
};

// mirrors the edge colors in RelationshipGraph so the timeline reads the same
const REL_COLORS: Record<string, string> = {
  ROMANTIC: "#ec4899",
  RIVAL: "#ef4444",
  FAMILY: "#3b82f6",
  MENTOR: "#f59e0b",
  ALLY: "#22c55e",
  ENEMY: "#dc2626",
  STRANGER: "#9ca3af",
  COLLEAGUE: "#8b5cf6",
};

function Face({ info }: { info?: EdgeCharacterInfo }) {
  return info?.image ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={info.image}
      alt={info.name}
      className="h-16 w-16 rounded-full object-cover border-2 border-primary/50"
    />
  ) : (
    <div className="h-16 w-16 rounded-full bg-secondary flex items-center justify-center text-lg font-semibold text-muted-foreground">
      {(info?.name ?? "?").charAt(0)}
    </div>
  );
}

export function RelationshipEdgePanel({
  rel,
  characterById,
  onClose,
}: RelationshipEdgePanelProps) {
  if (!rel) return null;

  const from = characterById[rel.from_char_id];
  const to = characterById[rel.to_char_id];
  const stages = rel.stages ?? [];

  return (
    <div className="fixed right-0 top-14 h-[calc(100vh-3.5rem)] w-80 bg-background border-l hairline shadow-xl z-50 p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Relationship</h3>
        <Button size="sm" variant="ghost" onClick={onClose}>
          ✕
        </Button>
      </div>

      {/* who ↔ who, with faces */}
      <div className="flex items-center justify-center gap-4">
        <div className="flex flex-col items-center gap-1.5">
          <Face info={from} />
          <span className="text-xs font-medium">{from?.name || "?"}</span>
        </div>
        <span className="text-lg text-muted-foreground">↔</span>
        <div className="flex flex-col items-center gap-1.5">
          <Face info={to} />
          <span className="text-xs font-medium">{to?.name || "?"}</span>
        </div>
      </div>

      <div className="flex items-center justify-center gap-2">
        <Badge>{rel.rel_type}</Badge>
        <Badge variant="outline">Strength {rel.strength}/10</Badge>
      </div>

      {rel.description && <p className="text-sm">{rel.description}</p>}

      {rel.evidence_quote && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Evidence
          </p>
          <p className="text-sm italic border-l-2 border-border pl-2 text-muted-foreground">
            &ldquo;{rel.evidence_quote}&rdquo;
          </p>
        </div>
      )}

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1">
          Evolution
        </p>
        <p className="text-sm">
          {EVOLUTION_LABELS[rel.evolution] || rel.evolution}
        </p>

        {/* the arc, stage by stage — only worth drawing when it actually changes */}
        {stages.length > 1 ? (
          <ol className="mt-3 space-y-0">
            {stages.map((s, i) => {
              const color = REL_COLORS[s.type] || "#9ca3af";
              const last = i === stages.length - 1;
              return (
                <li key={i} className="flex gap-2.5">
                  {/* dot + connecting line */}
                  <div className="flex flex-col items-center">
                    <span
                      className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    {!last && (
                      <span className="w-px flex-1 bg-border my-0.5 min-h-4" />
                    )}
                  </div>
                  <div className={last ? "pb-0" : "pb-3"}>
                    <div className="flex items-center gap-1.5">
                      <span
                        className="text-xs font-semibold"
                        style={{ color }}
                      >
                        {s.type}
                      </span>
                      {s.scene != null && (
                        <span className="text-[10px] text-muted-foreground">
                          Scene {s.scene}
                        </span>
                      )}
                      {last && (
                        <Badge variant="outline" className="h-4 px-1 text-[9px]">
                          now
                        </Badge>
                      )}
                    </div>
                    {s.label && (
                      <p className="text-xs text-muted-foreground">{s.label}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        ) : (
          rel.evolution_description && (
            <p className="text-xs text-muted-foreground mt-1">
              {rel.evolution_description}
            </p>
          )
        )}
      </div>

      {rel.first_established_scene != null && (
        <p className="text-xs text-muted-foreground">
          First established in Scene {rel.first_established_scene}
        </p>
      )}
    </div>
  );
}
