"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MBTIBadge } from "./MBTIBadge";
import { FaceUpload } from "./FaceUpload";
import { AppearanceGenerator } from "./AppearanceGenerator";
import { PlateCard } from "@/components/casting/PlateCard";
import { VoiceRow } from "@/components/casting/VoiceRow";
import { ZoomableImage } from "@/components/shared/Lightbox";
import { SpendConfirm, type SpendRequest } from "@/components/shared/SpendConfirm";
import {
  useRegenerateVariant,
  useSwapOutfit,
  useGenerateCharacterPlates,
  type CastingCharacter,
} from "@/hooks/useCasting";
import type { Character } from "@/lib/types";

/** Collapsible card section with a quiet uppercase heading and a smooth
 *  grid-rows height transition (children stay mounted so state survives). */
function Section({
  title,
  action,
  defaultOpen = false,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-border pt-2.5">
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex-1 flex items-center gap-2 text-left py-1 group/sec"
        >
          <span
            className={`text-[10px] text-muted-foreground transition-transform duration-200 ${
              open ? "rotate-90" : ""
            }`}
          >
            ▸
          </span>
          <span className="text-xs uppercase tracking-wide text-muted-foreground group-hover/sec:text-foreground transition-colors">
            {title}
          </span>
        </button>
        {action}
      </div>
      <div
        className={`grid transition-all duration-300 ease-in-out ${
          open ? "grid-rows-[1fr] opacity-100 mt-2" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="space-y-2.5 pb-1">{children}</div>
        </div>
      </div>
    </div>
  );
}

/** Long generated text collapsed to two lines with a toggle. */
function Expandable({ text }: { text: string }) {
  const [more, setMore] = useState(false);
  return (
    <div>
      <p
        className={
          more
            ? "text-xs text-muted-foreground"
            : "text-xs text-muted-foreground line-clamp-2"
        }
      >
        {text}
      </p>
      {text.length > 120 && (
        <button
          onClick={() => setMore((m) => !m)}
          className="text-[11px] text-muted-foreground underline hover:text-foreground"
        >
          {more ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

export function CharacterCard({
  character,
  casting,
}: {
  character: Character;
  casting?: CastingCharacter;
}) {
  const regenerateVariant = useRegenerateVariant();
  const swapOutfit = useSwapOutfit();
  const generatePlates = useGenerateCharacterPlates();
  const [spend, setSpend] = useState<SpendRequest | null>(null);
  const hasFace = !!character.reference_image_url;
  const hasPlates = (casting?.variants.length ?? 0) > 0;

  // only the plate being worked on shows the spinner, not its siblings
  const variantBusy = (variantId: string) =>
    (swapOutfit.isPending && swapOutfit.variables?.variantId === variantId) ||
    (regenerateVariant.isPending && regenerateVariant.variables === variantId);

  return (
    <Card>
      <CardContent className="px-5 py-1 space-y-3">
        {/* compact header: avatar + name + role */}
        <div className="flex items-center gap-4">
          {hasFace ? (
            <ZoomableImage
              src={character.reference_image_url!}
              alt={character.name}
              className="h-16 w-16 rounded-full object-cover border border-border shrink-0"
            />
          ) : (
            <div className="h-16 w-16 rounded-full bg-secondary flex items-center justify-center text-xl font-semibold text-muted-foreground shrink-0">
              {character.name.charAt(0)}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="font-medium truncate">{character.name}</p>
              <MBTIBadge
                type={character.mbti}
                confidence={character.mbti_confidence}
              />
            </div>
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {character.role || "cast"} · {hasFace ? "face locked" : "no face"}
            </p>
          </div>
        </div>

        {/* bio: two lines with a toggle for the full text */}
        {character.personality_summary && (
          <Expandable text={character.personality_summary} />
        )}

        <Section title="Profile">
          <div className="space-y-1.5 text-xs">
            {character.estimated_age && (
              <p>
                <span className="text-muted-foreground">Age</span> —{" "}
                {character.estimated_age}
              </p>
            )}
            {character.gender && (
              <p>
                <span className="text-muted-foreground">Gender</span> —{" "}
                {character.gender}
              </p>
            )}
            {character.speech_pattern && (
              <p>
                <span className="text-muted-foreground">Speech</span> —{" "}
                {character.speech_pattern}
              </p>
            )}
            {character.emotional_arc && (
              <p className="text-muted-foreground">
                Arc: {character.emotional_arc.start} →{" "}
                {character.emotional_arc.midpoint} →{" "}
                {character.emotional_arc.end}
              </p>
            )}
            {character.physical_description && (
              <Expandable text={character.physical_description} />
            )}
          </div>
        </Section>

        <Section title="Face reference" defaultOpen={!hasFace}>
          <p className="text-[11px] text-muted-foreground">
            The identity anchor — outfits below are built on this exact face.
          </p>
          {character.plate_status === "ref_rejected" && (
            <p className="rounded-md border border-bad/30 bg-bad/10 p-2 text-[11px] leading-snug text-bad">
              This photo was refused by the image service&apos;s content
              filter, which blocks recognizable public figures. Casting would
              invent a different face. Upload an original photo of a non
              famous person instead, and no money is spent until it passes.
            </p>
          )}
          <FaceUpload characterId={character.id} hasReference={hasFace} />
          <AppearanceGenerator
            characterId={character.id}
            visualDescription={character.visual_description}
          />
        </Section>

        {casting && (
          <>
            <Section
              title="Costume plates"
              action={
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={generatePlates.isPending}
                  onClick={() =>
                    setSpend({
                      title: `Generate plates for ${character.name}`,
                      costLine: "Prices below are estimates. A failed face check can add one retry plate.",
                      note: hasFace
                        ? "Every outfit renders on the locked face above."
                        : "No face is set, so a default face gets invented and locked.",
                      confirmLabel: "Generate",
                      breakdown: [
                        {
                          label: "Costume plates",
                          detail: `${Math.max(casting?.variants.length ?? 0, 1)} outfit plate${(casting?.variants.length ?? 0) > 1 ? "s" : ""} on qwen-image-edit-max, at $0.075 per image`,
                          amount: Math.max(casting?.variants.length ?? 0, 1) * 0.075,
                        },
                      ],
                      options: casting?.voice_id
                        ? undefined
                        : [
                            {
                              key: "designVoice",
                              label: "Design a bespoke voice",
                              priceLine: "$0.20 once",
                              note: "qwen-voice-design writes a voice from this character's age and personality. Untick for a free preset voice instead.",
                              defaultOn: true,
                              amount: 0.2,
                            },
                          ],
                      run: (choices) =>
                        generatePlates.mutate({
                          characterId: character.id,
                          designVoice: choices?.designVoice ?? true,
                        }),
                    })
                  }
                  title={
                    (hasFace
                      ? "Generate outfits on the face above."
                      : "No face set, a default face will be invented.") +
                    ` Costs about $${(
                      Math.max(casting?.variants.length ?? 0, 1) * 0.075
                    ).toFixed(2)}.`
                  }
                >
                  {generatePlates.isPending
                    ? "Generating…"
                    : hasPlates
                    ? "↻ Regenerate"
                    : "Generate"}
                </Button>
              }
            >
              {!hasFace && (
                <p className="text-[11px] text-muted-foreground">
                  No face set — generating will invent one. Add a face above
                  first to control it.
                </p>
              )}
              {hasPlates ? (
                <div className="grid grid-cols-2 gap-3">
                  {casting.variants.map((variant) => (
                    <PlateCard
                      key={variant.id}
                      imageUrl={variant.plate_image_url ?? undefined}
                      label={
                        variant.label + (variant.is_default ? " (default)" : "")
                      }
                      status={variant.plate_status}
                      busy={variantBusy(variant.id)}
                      onRegenerate={() => regenerateVariant.mutate(variant.id)}
                      onSwapOutfit={(file) =>
                        swapOutfit.mutate({ variantId: variant.id, file })
                      }
                    />
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  No costume plates yet.
                </p>
              )}
            </Section>

            <Section title="Voice">
              <VoiceRow
                characterId={character.id}
                voiceId={casting.voice_id}
                voiceSource={casting.voice_source}
                voiceDesign={casting.voice_design}
              />
            </Section>
          </>
        )}
        <SpendConfirm request={spend} onClose={() => setSpend(null)} />
      </CardContent>
    </Card>
  );
}
