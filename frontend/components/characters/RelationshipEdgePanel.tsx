"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CharacterRelationship } from "@/lib/types";

interface RelationshipEdgePanelProps {
  rel: CharacterRelationship | null;
  characterNames: Record<string, string>;
  onClose: () => void;
}

const EVOLUTION_LABELS: Record<string, string> = {
  STATIC: "Stays the same",
  GROWS: "Grows stronger",
  DETERIORATES: "Deteriorates",
  TRANSFORMS: "Transforms",
};

export function RelationshipEdgePanel({
  rel,
  characterNames,
  onClose,
}: RelationshipEdgePanelProps) {
  if (!rel) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-80 bg-background border-l shadow-lg z-50 p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Relationship</h3>
        <Button size="sm" variant="ghost" onClick={onClose}>
          ✕
        </Button>
      </div>
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium">
          {characterNames[rel.from_char_id] || "?"}
        </span>
        <span className="text-muted-foreground">→</span>
        <span className="font-medium">
          {characterNames[rel.to_char_id] || "?"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Badge>{rel.rel_type}</Badge>
        <Badge variant="outline">Strength {rel.strength}/10</Badge>
      </div>
      {rel.description && <p className="text-sm">{rel.description}</p>}
      {rel.evidence_quote && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Evidence
          </p>
          <p className="text-sm italic border-l-2 pl-2">
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
        {rel.evolution_description && (
          <p className="text-xs text-muted-foreground mt-1">
            {rel.evolution_description}
          </p>
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
