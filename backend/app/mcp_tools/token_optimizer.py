class TokenOptimizer:
    # Real Qwen Cloud catalog pricing (conservative high end):
    # Wan2.7 $0.10-0.15/sec, HappyHorse-1.1 $0.084-0.108/sec.
    WAN_COST_PER_SEC = 0.15
    HH_COST_PER_SEC = 0.108
    RESERVE_PCT = 0.15

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
        return min(score, 10)

    def allocate(self, shots: list[dict], budget_usd: float = 40.0) -> dict:
        available = budget_usd * (1 - self.RESERVE_PCT)
        scored = []
        for shot in shots:
            importance = self.score_shot(shot)
            if importance >= 7:
                tier, model, cost_per_sec = "wan", "wan2.1-t2v-plus", self.WAN_COST_PER_SEC
            elif importance >= 4:
                tier, model, cost_per_sec = "happyhorse", "happyhorse-1.1-t2v", self.HH_COST_PER_SEC
            else:
                tier, model, cost_per_sec = "happyhorse_fast", "happyhorse-1.1-t2v", self.HH_COST_PER_SEC * 0.8
            duration = shot.get("estimated_duration_seconds", 5)
            cost = cost_per_sec * duration
            scored.append({
                "shot_id": shot.get("shot_id", ""),
                "importance_score": importance,
                "quality_tier": tier,
                "model": model,
                "estimated_cost_usd": round(cost, 3),
                "reasoning": f"Score {importance}/10 -> {tier}",
            })

        video_cost = sum(s["estimated_cost_usd"] for s in scored)
        total_seconds = sum(shot.get("estimated_duration_seconds", 5) for shot in shots)
        wan_count = sum(1 for s in scored if s["quality_tier"] == "wan")
        hh_count = len(scored) - wan_count

        return {
            "total_shots": len(scored),
            "total_estimated_seconds": total_seconds,
            "budget_available": round(available, 2),
            "budget_reserved": round(budget_usd * self.RESERVE_PCT, 2),
            "scored_shots": scored,
            "wan_shots": wan_count,
            "happyhorse_shots": hh_count,
            "video_cost_usd": round(video_cost, 2),
            "total_estimated_cost": round(video_cost, 2),
            "budget_remaining": round(available - video_cost, 2),
            "optimisation_summary": f"{wan_count} key scenes -> Wan 2.7, {hh_count} supporting -> HappyHorse 1.1",
        }
