class TokenOptimizer:
    """Adaptive video-budget allocator.

    Scores each shot's narrative importance, tiers it Wan (premium) or
    HappyHorse (economy), then FITS the plan to the spend cap instead of just
    reporting an overrun: first the least important Wan shots downgrade to
    HappyHorse, then the least important shots defer entirely. Scene 1 is the
    hook — the seconds that decide whether a viewer keeps watching — so hook
    shots score higher and are never downgraded or deferred.
    """
    # Real Qwen Cloud catalog pricing (conservative high end):
    # Wan2.7 $0.10-0.15/sec, HappyHorse-1.1 $0.084-0.108/sec.
    WAN_COST_PER_SEC = 0.15
    HH_COST_PER_SEC = 0.108
    RESERVE_PCT = 0.15
    HOOK_SCENE = 1

    # Model ids the generation runner actually dispatches (qwen_client).
    WAN_MODEL = "wan2.7-t2v"
    HH_MODEL = "happyhorse-1.1-t2v"

    CLIMAX_WORDS = {
        "climax", "revelation", "confrontation", "betrayal",
        "breaking point", "twist", "sacrifice",
    }

    def score_shot(self, shot: dict) -> int:
        score = 0
        beat = (shot.get("emotional_beat") or "").lower()
        if any(word in beat for word in self.CLIMAX_WORDS):
            score += 3
        chars = shot.get("characters_in_frame") or []
        if len(chars) >= 2:
            score += 1
        if len(chars) >= 1:
            score += 1
        if shot.get("dialogue"):
            score += 2
        shot_weights = {"CU": 2, "ECU": 2, "MCU": 1, "MS": 1, "LS": 0, "EWS": 0, "POV": 1, "OTS": 1}
        score += shot_weights.get(shot.get("shot_type", ""), 0)
        if (shot.get("estimated_duration_seconds") or 0) >= 10:
            score += 1
        # The hook: the opening scene is where retention is won or lost.
        if shot.get("scene_number") == self.HOOK_SCENE:
            score += 2
        return min(score, 10)

    def _cost_of(self, tier: str, duration: float) -> float:
        if tier == "wan":
            return self.WAN_COST_PER_SEC * duration
        if tier == "happyhorse_fast":
            return self.HH_COST_PER_SEC * 0.8 * duration
        if tier == "deferred":
            return 0.0
        return self.HH_COST_PER_SEC * duration

    def allocate(self, shots: list[dict], budget_usd: float = 40.0) -> dict:
        available = budget_usd * (1 - self.RESERVE_PCT)
        scored = []
        for shot in shots:
            importance = self.score_shot(shot)
            if importance >= 7:
                tier, model = "wan", self.WAN_MODEL
            elif importance >= 4:
                tier, model = "happyhorse", self.HH_MODEL
            else:
                tier, model = "happyhorse_fast", self.HH_MODEL
            duration = shot.get("estimated_duration_seconds", 5)
            scored.append({
                "shot_id": shot.get("shot_id", ""),
                "importance_score": importance,
                "quality_tier": tier,
                "model": model,
                "is_hook": shot.get("scene_number") == self.HOOK_SCENE,
                "duration": duration,
                "estimated_cost_usd": round(self._cost_of(tier, duration), 3),
                "reasoning": f"Score {importance}/10 -> {tier}",
            })

        def total() -> float:
            return sum(s["estimated_cost_usd"] for s in scored)

        # Fit to the cap. Pass 1: downgrade the least important non-hook Wan
        # shots to HappyHorse. Pass 2: defer the least important non-hook
        # shots entirely (the runner skips tier == "deferred").
        downgraded = deferred = 0
        if total() > available:
            for s in sorted((x for x in scored if x["quality_tier"] == "wan" and not x["is_hook"]),
                            key=lambda x: x["importance_score"]):
                s["quality_tier"], s["model"] = "happyhorse", self.HH_MODEL
                s["estimated_cost_usd"] = round(self._cost_of("happyhorse", s["duration"]), 3)
                s["reasoning"] += " | downgraded to fit the spend cap"
                downgraded += 1
                if total() <= available:
                    break
        if total() > available:
            for s in sorted((x for x in scored if x["quality_tier"] != "deferred" and not x["is_hook"]),
                            key=lambda x: x["importance_score"]):
                s["quality_tier"] = "deferred"
                s["estimated_cost_usd"] = 0.0
                s["reasoning"] += " | deferred: does not fit the spend cap"
                deferred += 1
                if total() <= available:
                    break

        video_cost = total()
        active = [s for s in scored if s["quality_tier"] != "deferred"]
        total_seconds = sum(s["duration"] for s in active)
        wan_count = sum(1 for s in active if s["quality_tier"] == "wan")
        hh_count = len(active) - wan_count
        hook_count = sum(1 for s in scored if s["is_hook"])

        summary = f"{wan_count} key scenes -> Wan 2.7, {hh_count} supporting -> HappyHorse 1.1"
        if hook_count:
            summary += f"; {hook_count} hook shot(s) protected"
        if downgraded:
            summary += f"; {downgraded} downgraded to fit the cap"
        if deferred:
            summary += f"; {deferred} deferred to fit the cap"

        for s in scored:
            s.pop("duration", None)

        return {
            "total_shots": len(scored),
            "total_estimated_seconds": total_seconds,
            "budget_usd": round(budget_usd, 2),
            "budget_available": round(available, 2),
            "budget_reserved": round(budget_usd * self.RESERVE_PCT, 2),
            "scored_shots": scored,
            "wan_shots": wan_count,
            "happyhorse_shots": hh_count,
            "hook_shots": hook_count,
            "downgraded_shots": downgraded,
            "deferred_shots": deferred,
            "fits_budget": video_cost <= available,
            "video_cost_usd": round(video_cost, 2),
            "total_estimated_cost": round(video_cost, 2),
            "budget_remaining": round(available - video_cost, 2),
            "optimisation_summary": summary,
        }
