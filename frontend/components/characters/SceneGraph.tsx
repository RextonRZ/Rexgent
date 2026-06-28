"use client";

import type { GraphScene } from "@/hooks/useRelationshipGraph";

interface SceneGraphProps {
  scenes: GraphScene[];
  characters: { id: string; name: string; role: string }[];
}

// Deterministic color per character name for the presence dots.
const DOT_COLORS = [
  "#3b82f6",
  "#ec4899",
  "#22c55e",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
  "#14b8a6",
  "#eab308",
];

function colorFor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return DOT_COLORS[Math.abs(hash) % DOT_COLORS.length];
}

export function SceneGraph({ scenes, characters }: SceneGraphProps) {
  if (scenes.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No scenes to graph yet.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 overflow-x-auto pb-4">
        {scenes.map((scene, i) => (
          <div key={scene.number} className="flex items-center gap-2 shrink-0">
            <div className="border rounded-lg p-3 w-44 bg-card">
              <div className="text-xs font-semibold mb-1">
                Scene {scene.number}
              </div>
              <div className="text-xs text-muted-foreground truncate mb-2">
                {scene.heading || "Untitled"}
              </div>
              <div className="flex flex-wrap gap-1">
                {(scene.characters || []).map((name) => (
                  <span
                    key={name}
                    className="flex items-center gap-1 text-[10px]"
                  >
                    <span
                      className="inline-block w-2 h-2 rounded-full"
                      style={{ backgroundColor: colorFor(name) }}
                    />
                    {name}
                  </span>
                ))}
              </div>
            </div>
            {i < scenes.length - 1 && (
              <span className="text-muted-foreground">→</span>
            )}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-xs">
        {characters.map((c) => (
          <span key={c.id} className="flex items-center gap-1">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: colorFor(c.name) }}
            />
            {c.name}
          </span>
        ))}
      </div>
    </div>
  );
}
