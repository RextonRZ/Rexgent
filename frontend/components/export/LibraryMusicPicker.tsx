"use client";

import { useSuggestMusic, type SuggestedTrack } from "@/hooks/useExport";
import { errText } from "@/lib/errText";

/** A meta line like "medium tempo · 0:50" for one track, dashes avoided. */
function trackMeta(track: SuggestedTrack): string {
  const bits: string[] = [];
  if (track.tempo) bits.push(`${track.tempo} tempo`);
  if (track.duration != null) {
    const total = Math.round(track.duration);
    const mins = Math.floor(total / 60);
    const secs = String(total % 60).padStart(2, "0");
    bits.push(`${mins}:${secs}`);
  }
  return bits.join(" · ");
}

/** Suggest mood-matched music from the shared library and set it as the export
 *  track. Fires only when the user asks, since resolving uploads to storage. */
export function LibraryMusicPicker({
  projectId,
  onPick,
}: {
  projectId: string;
  onPick: (track: { url: string; title: string }) => void;
}) {
  const suggest = useSuggestMusic(projectId);
  const suggestion = suggest.data;

  return (
    <div className="rounded-xl border hairline bg-card p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-medium">Library music</h2>
          <p className="text-[11px] text-muted-foreground">
            Match a soundtrack to your story mood from the shared library
          </p>
        </div>
        <button
          onClick={() => suggest.mutate()}
          disabled={suggest.isPending}
          className="rounded-md bg-primary/15 text-primary px-3 py-1.5 text-xs font-medium hover:bg-primary/25 disabled:opacity-60"
        >
          {suggest.isPending ? "Suggesting…" : "Suggest from library"}
        </button>
      </div>

      {suggest.isError && (
        <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          {errText(suggest.error)}
        </p>
      )}

      {suggestion && (
        <>
          <p className="mb-2 text-[11px] text-muted-foreground">
            Matched mood: <span className="text-foreground">{suggestion.mood}</span>
          </p>
          {suggestion.results.length === 0 ? (
            <div className="h-16 rounded-lg border border-dashed border-border flex items-center justify-center text-[11px] text-muted-foreground">
              No matching tracks in the library yet.
            </div>
          ) : (
            <ul className="space-y-2">
              {suggestion.results.map((track) => {
                const meta = trackMeta(track);
                const hasAudio = Boolean(track.url);
                return (
                  <li
                    key={track.id}
                    className="rounded-lg border hairline bg-background/40 p-2.5 flex flex-wrap items-center gap-2"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-xs truncate" title={track.title}>
                        {track.title}
                      </p>
                      {meta && (
                        <p className="text-[10px] text-muted-foreground">{meta}</p>
                      )}
                      {!hasAudio && (
                        <p className="text-[10px] text-muted-foreground">
                          No audio file yet
                        </p>
                      )}
                    </div>
                    {hasAudio && (
                      // eslint-disable-next-line jsx-a11y/media-has-caption
                      <audio
                        src={track.url!}
                        controls
                        preload="none"
                        className="h-8 max-w-[200px]"
                      />
                    )}
                    <button
                      onClick={() =>
                        onPick({ url: track.url!, title: track.title })
                      }
                      disabled={!hasAudio}
                      className="rounded bg-primary/15 text-primary px-2.5 py-1 text-[11px] font-medium hover:bg-primary/25 disabled:opacity-40 disabled:hover:bg-primary/15"
                    >
                      Use
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
