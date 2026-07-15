import math

from app.services.shot_roles import angle_changed


class TokenOptimizer:
    """Adaptive video-budget allocator.

    Every shot renders on the one video model. The allocator scores each shot's
    narrative importance to pick a quality LEVEL — full or fast — then FITS the
    plan to the spend cap instead of just reporting an overrun: first the least
    important full shots ease to fast, then the least important shots defer
    entirely. Scene 1 is the hook — the seconds that decide whether a viewer
    keeps watching — so hook shots score higher and are never eased or deferred.
    """
    # Real Qwen Cloud catalog pricing (conservative high end):
    # HappyHorse-1.1 $0.084-0.108/sec. Fast pass runs at 0.8x the full rate.
    # Wan2.7 renders at $0.15/sec (matches cost_rates.video_cost).
    HH_COST_PER_SEC = 0.108
    WAN_COST_PER_SEC = 0.15
    RESERVE_PCT = 0.15
    HOOK_SCENE = 1
    # The hook is the OPENING BEATS, not the whole first scene — a one-scene
    # drama would otherwise protect every shot and make the cap unfittable.
    HOOK_MAX_SHOTS = 2

    # Model ids the generation runner actually dispatches (qwen_client).
    HH_MODEL = "happyhorse-1.1-t2v"
    WAN_MODEL = "wan2.7-t2v"

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
        if tier == "happyhorse_fast":
            return self.HH_COST_PER_SEC * 0.8 * duration
        if tier == "deferred":
            return 0.0
        if tier == "wan":  # wan_primary silent-visual tier — real Wan rate
            return self.WAN_COST_PER_SEC * duration
        return self.HH_COST_PER_SEC * duration

    def allocate(self, shots: list[dict], budget_usd: float = 40.0,
                 wan_primary: bool = False) -> dict:
        available = budget_usd * (1 - self.RESERVE_PCT)
        # Hook = the first HOOK_MAX_SHOTS shots of scene 1 (by shot_number when
        # given, else list order) — the seconds that stop the scroll.
        scene1 = sorted(
            (i for i, s in enumerate(shots) if s.get("scene_number") == self.HOOK_SCENE),
            key=lambda i: shots[i].get("shot_number") or 10 ** 9,
        )
        hook_indices = set(scene1[:self.HOOK_MAX_SHOTS])
        # Match render_plan / _dispatch_by_role so the budget split agrees with the
        # storyboard badge. A scene's opening shot (lowest shot_number) is the
        # identity ANCHOR; a shot that brings in a character absent from the
        # previous shot of the same scene re-locks a face (NEWCOMER).
        min_shot_by_scene: dict = {}
        for s in shots:
            scn, sn = s.get("scene_number"), s.get("shot_number")
            if sn is not None and (scn not in min_shot_by_scene or sn < min_shot_by_scene[scn]):
                min_shot_by_scene[scn] = sn
        prev_cast: dict = {}
        # previous shot's framing per scene: an angle change routes to HappyHorse
        # (reangles never ride Wan continuation), so the budget must mirror it.
        # Entries exist only when a previous shot exists — the scene opener is an
        # anchor, never a reangle. The blocking reverse_angle flag isn't in the
        # planner's shot dicts; the shot_type diff is the shared signal.
        prev_type: dict = {}
        by_scene: dict = {}
        for s in shots:
            by_scene.setdefault(s.get("scene_number"), []).append(s)
        for grp in by_scene.values():
            seen: set = set()
            prior = None
            for s in sorted(grp, key=lambda x: x.get("shot_number") or 0):
                prev_cast[id(s)] = set(seen)
                if prior is not None:
                    prev_type[id(s)] = prior.get("shot_type")
                seen = {str(c) for c in (s.get("characters_in_frame") or [])}
                prior = s
        scored = []
        for i, shot in enumerate(shots):
            importance = self.score_shot(shot)
            if wan_primary:
                # HappyHorse renders the CHARACTERS — a shot that speaks, the
                # scene's opening anchor with faces, a shot bringing back a face
                # absent from the previous shot, or a REANGLE (an angle change
                # never rides Wan continuation); Wan renders the other silent
                # visuals (scenery, or a same-angle continuation of a shown face).
                cast = [str(c) for c in (shot.get("characters_in_frame") or [])]
                has_faces = bool(cast)
                is_anchor = shot.get("shot_number") == min_shot_by_scene.get(shot.get("scene_number"))
                newcomer = any(c not in prev_cast.get(id(shot), set()) for c in cast)
                reangle = (id(shot) in prev_type
                           and angle_changed(prev_type[id(shot)],
                                             shot.get("shot_type"), False))
                # a faceless shot has no identity to lock, so scenery/atmosphere
                # goes to Wan even on an angle change; reangle only forces HH
                # when there are faces
                if (shot.get("dialogue") or (is_anchor and has_faces)
                        or newcomer or (reangle and has_faces)):
                    tier, model = "happyhorse", self.HH_MODEL
                else:
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
                "is_hook": i in hook_indices,
                "duration": duration,
                "estimated_cost_usd": round(self._cost_of(tier, duration), 3),
                "reasoning": f"Score {importance}/10 -> {tier}",
            })

        def total() -> float:
            return sum(s["estimated_cost_usd"] for s in scored)

        # what the full plan would cost before any fitting — the number a
        # user needs when deciding whether to raise the cap instead
        unfitted_cost = round(total(), 2)

        # Fit to the cap. Pass 1: ease the least important non-hook full shots
        # to fast. Pass 2: defer the least important non-hook shots entirely
        # (the runner skips tier == "deferred").
        # The ease pass is a QUALITY lever (full -> fast) that does not exist
        # under wan_primary — Wan is never downgraded to HappyHorse — so it is
        # skipped; only the deferral pass fits a wan_primary plan.
        downgraded = deferred = 0
        if not wan_primary and total() > available:
            for s in sorted((x for x in scored if x["quality_tier"] == "happyhorse" and not x["is_hook"]),
                            key=lambda x: x["importance_score"]):
                s["quality_tier"], s["model"] = "happyhorse_fast", self.HH_MODEL
                s["estimated_cost_usd"] = round(self._cost_of("happyhorse_fast", s["duration"]), 3)
                s["reasoning"] += " | eased to fit the spend cap"
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
        # Legacy quality split (0 under wan_primary — no happyhorse_fast tier).
        fast_count = sum(1 for s in active if s["quality_tier"] == "happyhorse_fast")
        full_count = sum(1 for s in active if s["quality_tier"] == "happyhorse")
        # Wan-primary model split (0 under legacy — gated so the legacy return
        # is unchanged and the frontend falls back to the full/fast view).
        if wan_primary:
            wan_count = sum(1 for s in active if s["quality_tier"] == "wan")
            happyhorse_count = sum(1 for s in active if s["quality_tier"] == "happyhorse")
        else:
            wan_count = happyhorse_count = 0
        hook_count = sum(1 for s in scored if s["is_hook"])

        # When the plan had to shrink, name the cap that would NOT shrink it:
        # the smallest whole dollar whose 85% covers the unfitted plan. The
        # weakness is never the fitting, it is fitting silently.
        recommended = None
        if downgraded or deferred:
            recommended = int(math.ceil(unfitted_cost / (1 - self.RESERVE_PCT)))

        if wan_primary:
            summary = (f"{wan_count} on Wan (visuals), "
                       f"{happyhorse_count} on HappyHorse (characters)")
        else:
            summary = f"{full_count} shots at full quality, {fast_count} lighter"
        if hook_count:
            summary += f"; {hook_count} hook shot(s) protected"
        if downgraded:
            summary += f"; {downgraded} eased to fit the cap"
        if deferred:
            summary += f"; {deferred} deferred to fit the cap"
        if recommended:
            summary += f"; a ${recommended} cap renders the full plan"

        for s in scored:
            s.pop("duration", None)

        return {
            "total_shots": len(scored),
            "total_estimated_seconds": total_seconds,
            "budget_usd": round(budget_usd, 2),
            "budget_available": round(available, 2),
            "budget_reserved": round(budget_usd * self.RESERVE_PCT, 2),
            "scored_shots": scored,
            "full_shots": full_count,
            "fast_shots": fast_count,
            "wan_shots": wan_count,
            "happyhorse_shots": happyhorse_count,
            "hook_shots": hook_count,
            "downgraded_shots": downgraded,
            "deferred_shots": deferred,
            "unfitted_cost_usd": unfitted_cost,
            "recommended_budget_usd": recommended,
            "fits_budget": video_cost <= available,
            "video_cost_usd": round(video_cost, 2),
            "total_estimated_cost": round(video_cost, 2),
            "budget_remaining": round(available - video_cost, 2),
            "optimisation_summary": summary,
        }
