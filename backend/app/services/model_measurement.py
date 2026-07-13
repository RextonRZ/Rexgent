"""Pure analysis for the anchor-model measurement harness. Given the continuity
scores of clips rendered under a candidate config, summarize them and pick the
config that holds identity best. No I/O — the script does the rendering."""


def _mean(values):
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def summarize(clips: list[dict]) -> dict:
    """Mean face/outfit/continuity over a config's clips (skipping None scores).
    n is the clip count, not the count of present scores."""
    if not clips:
        return {"n": 0, "mean_face": None, "mean_outfit": None, "mean_continuity": None}
    return {
        "n": len(clips),
        "mean_face": _mean([c.get("face_score") for c in clips]),
        "mean_outfit": _mean([c.get("outfit_score") for c in clips]),
        "mean_continuity": _mean([c.get("consistency_score") for c in clips]),
    }


def pick_winner(results: list[dict]) -> str | None:
    """The config with the highest mean_face (tie-break: mean_continuity).
    Configs with no measured face score are ignored. None if nothing measured."""
    ranked = [r for r in results if r.get("mean_face") is not None]
    if not ranked:
        return None
    best = max(ranked, key=lambda r: (r["mean_face"], r.get("mean_continuity") or 0))
    return best["config"]


def format_scorecard(results: list[dict]) -> str:
    """A readable table of the per-config means with the winner marked."""
    winner = pick_winner(results)
    lines = ["config        n   face    outfit  continuity",
             "-----------------------------------------------"]
    for r in results:
        lines.append("{:<12}  {:<3} {:<7} {:<7} {}".format(
            r.get("config", "?"), r.get("n", 0),
            _fmt(r.get("mean_face")), _fmt(r.get("mean_outfit")),
            _fmt(r.get("mean_continuity"))))
    lines.append("")
    lines.append(f"WINNER: {winner}" if winner else "WINNER: (no data)")
    return "\n".join(lines)


def _fmt(v) -> str:
    return "-" if v is None else (f"{v:.2f}" if v < 1 else f"{v:.1f}")
