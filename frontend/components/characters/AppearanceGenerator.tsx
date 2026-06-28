"use client";

import { Button } from "@/components/ui/button";
import { useGenerateAppearance } from "@/hooks/useFaceEmbed";

interface AppearanceGeneratorProps {
  characterId: string;
  visualDescription: string | null;
}

export function AppearanceGenerator({
  characterId,
  visualDescription,
}: AppearanceGeneratorProps) {
  const generateAppearance = useGenerateAppearance();

  return (
    <div className="space-y-2">
      <Button
        size="sm"
        variant="outline"
        className="w-full"
        onClick={() => generateAppearance.mutate(characterId)}
        disabled={generateAppearance.isPending}
      >
        {generateAppearance.isPending
          ? "Generating with Qwen-Max..."
          : "Generate Appearance (no photo)"}
      </Button>
      {visualDescription && (
        <p className="text-xs text-muted-foreground">{visualDescription}</p>
      )}
    </div>
  );
}
