"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MBTIBadge } from "./MBTIBadge";
import type { Character } from "@/lib/types";

const ROLE_COLORS: Record<string, string> = {
  PROTAGONIST: "bg-blue-500",
  ANTAGONIST: "bg-red-500",
  SUPPORTING: "bg-green-500",
  MINOR: "bg-gray-400",
};

export function CharacterCard({ character }: { character: Character }) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-lg">{character.name}</CardTitle>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {character.role && (
              <Badge className={ROLE_COLORS[character.role] || "bg-gray-400"}>
                {character.role}
              </Badge>
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
        <div className="h-20 bg-muted rounded flex items-center justify-center text-xs text-muted-foreground">
          {character.reference_image_url
            ? "Reference image set"
            : "No reference image — add in Face step"}
        </div>
      </CardContent>
    </Card>
  );
}
