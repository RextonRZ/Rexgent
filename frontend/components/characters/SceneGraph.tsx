"use client";

import type {
  GraphScene,
  GraphCharacterInfo,
} from "@/hooks/useRelationshipGraph";

/** Horizontal scene flow: each scene is a card with its location plate and the
 *  faces of the characters in it, connected in story order. */
export function SceneGraph({
  scenes,
  characters,
}: {
  scenes: GraphScene[];
  characters: GraphCharacterInfo[];
}) {
  if (scenes.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No scenes to graph yet.
      </p>
    );
  }

  const faceByName = new Map(
    characters.map((c) => [c.name.toUpperCase(), c.reference_image_url])
  );

  return (
    <div className="rounded-xl border hairline bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">
        Scene flow
      </p>
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {scenes.map((scene, i) => (
          <div key={scene.number} className="flex items-center gap-2 shrink-0">
            <div className="w-56 rounded-xl border hairline bg-background/40 overflow-hidden">
              <div className="relative h-24 bg-secondary/40">
                {scene.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={scene.image}
                    alt={scene.heading || `Scene ${scene.number}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
                    no location plate yet
                  </div>
                )}
                <span className="absolute top-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  Scene {scene.number}
                </span>
              </div>
              <div className="p-2.5 space-y-2">
                <p className="text-[11px] font-medium line-clamp-1">
                  {scene.heading || "Untitled"}
                </p>
                <div className="flex items-center -space-x-1.5">
                  {(scene.characters || []).map((name) => {
                    const img = faceByName.get(String(name).toUpperCase());
                    return img ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        key={name}
                        src={img}
                        alt={name}
                        title={name}
                        className="h-7 w-7 rounded-full object-cover border-2 border-card"
                      />
                    ) : (
                      <span
                        key={name}
                        title={name}
                        className="h-7 w-7 rounded-full bg-secondary text-[9px] font-medium flex items-center justify-center border-2 border-card text-muted-foreground"
                      >
                        {String(name).slice(0, 2)}
                      </span>
                    );
                  })}
                  {(scene.characters || []).length === 0 && (
                    <span className="text-[10px] text-muted-foreground">
                      no cast listed
                    </span>
                  )}
                </div>
              </div>
            </div>
            {i < scenes.length - 1 && (
              <span className="text-muted-foreground shrink-0">→</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
