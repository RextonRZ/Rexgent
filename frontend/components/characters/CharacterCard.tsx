"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MBTIBadge } from "./MBTIBadge";
import { FaceUpload } from "./FaceUpload";
import { AppearanceGenerator } from "./AppearanceGenerator";
import type { Character } from "@/lib/types";

const ROLE_COLORS: Record<string, string> = {
  PROTAGONIST: "bg-primary/15 text-primary",
  ANTAGONIST: "bg-bad/15 text-bad",
  SUPPORTING: "bg-ok/15 text-ok",
  MINOR: "bg-secondary text-muted-foreground",
};

export function CharacterCard({ character }: { character: Character }) {
  const locked = !!character.reference_image_url;
  return (
    <Card className="hover:border-primary/40 transition-colors">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">{character.name}</CardTitle>
            <span
              className={`inline-flex items-center gap-1 text-[10px] rounded-full px-1.5 py-0.5 ${
                locked ? "bg-ok/15 text-ok" : "bg-secondary text-muted-foreground"
              }`}
              title={locked ? "Identity locked" : "No reference set"}
            >
              {locked ? "● locked" : "○ no ID"}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {character.role && (
              <span
                className={`text-[11px] font-medium rounded-full px-2 py-0.5 ${
                  ROLE_COLORS[character.role] || "bg-secondary text-muted-foreground"
                }`}
              >
                {character.role}
              </span>
            )}
            <MBTIBadge
              type={character.mbti}
              confidence={character.mbti_confidence}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {character.estimated_age && (
          <p>
            <span className="text-muted-foreground">Age:</span>{" "}
            {character.estimated_age}
          </p>
        )}
        {character.gender && (
          <p>
            <span className="text-muted-foreground">Gender:</span>{" "}
            {character.gender}
          </p>
        )}
        {character.physical_description && (
          <p>
            <span className="text-muted-foreground">Appearance:</span>{" "}
            {character.physical_description}
          </p>
        )}
        {character.personality_summary && (
          <p className="text-muted-foreground">
            {character.personality_summary}
          </p>
        )}
        {character.speech_pattern && (
          <p>
            <span className="text-muted-foreground">Speech:</span>{" "}
            {character.speech_pattern}
          </p>
        )}
        {character.emotional_arc && (
          <div className="flex items-center gap-2 text-xs flex-wrap">
            <span className="text-muted-foreground">Arc:</span>
            <span>{character.emotional_arc.start}</span>
            <span>→</span>
            <span>{character.emotional_arc.midpoint}</span>
            <span>→</span>
            <span>{character.emotional_arc.end}</span>
          </div>
        )}
        <div className="pt-1 space-y-2">
          <FaceUpload
            characterId={character.id}
            hasReference={!!character.reference_image_url}
          />
          <AppearanceGenerator
            characterId={character.id}
            visualDescription={character.visual_description}
          />
        </div>
      </CardContent>
    </Card>
  );
}
