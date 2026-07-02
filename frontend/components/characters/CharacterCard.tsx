"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MBTIBadge } from "./MBTIBadge";
import { FaceUpload } from "./FaceUpload";
import { AppearanceGenerator } from "./AppearanceGenerator";
import { PlateCard } from "@/components/casting/PlateCard";
import { VoiceRow } from "@/components/casting/VoiceRow";
import {
  useRegenerateVariant,
  useOverrideVariant,
  useGenerateCharacterPlates,
  type CastingCharacter,
} from "@/hooks/useCasting";
import type { Character } from "@/lib/types";

const ROLE_COLORS: Record<string, string> = {
  PROTAGONIST: "bg-primary/15 text-primary",
  ANTAGONIST: "bg-bad/15 text-bad",
  SUPPORTING: "bg-ok/15 text-ok",
  MINOR: "bg-secondary text-muted-foreground",
};

export function CharacterCard({
  character,
  casting,
}: {
  character: Character;
  casting?: CastingCharacter;
}) {
  const locked = !!character.reference_image_url;
  const regenerateVariant = useRegenerateVariant();
  const overrideVariant = useOverrideVariant();
  const generatePlates = useGenerateCharacterPlates();
  const hasFace = !!character.reference_image_url;
  const hasPlates = (casting?.variants.length ?? 0) > 0;
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
        {/* 1 · Face reference — the identity anchor (face only, no outfit) */}
        <div className="pt-2 mt-1 border-t hairline space-y-2">
          <div>
            <p className="text-[11px] font-semibold text-primary/80">
              1 · Face reference{" "}
              <span className="font-normal text-muted-foreground">
                — identity, face only
              </span>
            </p>
            <p className="text-[10px] text-muted-foreground">
              Upload or generate the face. Outfits below are built on this exact
              face.
            </p>
          </div>
          <FaceUpload
            characterId={character.id}
            hasReference={!!character.reference_image_url}
          />
          <AppearanceGenerator
            characterId={character.id}
            visualDescription={character.visual_description}
          />
        </div>

        {casting && (
          <>
            {/* 2 · Costume plates — full outfits generated on top of the face */}
            <div className="pt-2 mt-2 border-t hairline space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold text-primary/80">
                  2 · Costume plates{" "}
                  <span className="font-normal text-muted-foreground">
                    — outfits, same face
                  </span>
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={generatePlates.isPending}
                  onClick={() => generatePlates.mutate(character.id)}
                  title={
                    hasFace
                      ? "Generate outfits on the face above"
                      : "No face set — a default face will be invented"
                  }
                >
                  {generatePlates.isPending
                    ? "Generating…"
                    : hasPlates
                    ? "Regenerate"
                    : "Generate plates"}
                </Button>
              </div>

              {!hasFace && (
                <p className="text-[10px] text-muted-foreground">
                  No face set — generating will <em>invent</em> a default face.
                  Upload/generate a face above first to control it.
                </p>
              )}
              {hasFace && hasPlates && (
                <p className="text-[10px] text-muted-foreground">
                  Changed the face above? Click <span className="text-primary">Regenerate</span> to re-match.
                </p>
              )}

              {hasPlates ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {casting.variants.map((variant) => (
                    <PlateCard
                      key={variant.id}
                      imageUrl={variant.plate_image_url ?? undefined}
                      label={variant.label + (variant.is_default ? " (default)" : "")}
                      description={variant.outfit_description ?? undefined}
                      status={variant.plate_status}
                      onRegenerate={() => regenerateVariant.mutate(variant.id)}
                      onUpload={(file) =>
                        overrideVariant.mutate({ variantId: variant.id, file })
                      }
                    />
                  ))}
                </div>
              ) : (
                <p className="text-[10px] text-muted-foreground">
                  No costume plates yet.
                </p>
              )}
            </div>

            {/* 3 · Voice */}
            <div className="pt-2 mt-2 border-t hairline space-y-2">
              <p className="text-[11px] font-semibold text-primary/80">3 · Voice</p>
              <VoiceRow
                characterId={character.id}
                voiceId={casting.voice_id}
                voiceSource={casting.voice_source}
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
