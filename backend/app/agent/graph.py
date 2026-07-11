"""LangGraph autonomous pipeline.

A state machine that runs the whole Rexgent pipeline from a premise:
generate_script -> judge -> (revise loop) -> extract_characters -> storyboard
-> budget -> dispatch_video, surfacing a final report.
"""
from langgraph.graph import StateGraph, START, END
from app.agent.state import PipelineState
from app.agent import pipeline_ops
from app.mcp_tools.narrative_judge import NarrativeJudge
from app.websocket.emitter import emit

MAX_REVISIONS = 1


def route_after_judge(state: PipelineState) -> str:
    rec = (state.get("judgement") or {}).get("recommendation", "PROCEED")
    if rec in ("REVISE_FIRST", "MAJOR_REWRITE") and state.get("revise_count", 0) < MAX_REVISIONS:
        return "revise"
    # Full Auto rolls straight on. Otherwise the run ENDS here, at the script
    # checkpoint: the Showrunner chat hands the user the controls (review the
    # script, or continue to casting) — later stages never start themselves.
    return "extract_characters" if state.get("dispatch_video") else "END"


def _emit_node(state: PipelineState, node: str) -> None:
    pid = state.get("project_id")
    if pid:
        emit("agent:node", {"node": node}, str(pid))


def build_pipeline_graph(db=None):
    async def n_generate_script(state: PipelineState) -> PipelineState:
        _emit_node(state, "generate_script")
        if db is None:
            return state
        # On a revision pass, feed the judge's actual critique back in — a
        # regeneration that ignores WHY the draft failed just rolls the dice.
        notes = ""
        if state.get("revise_count", 0) > 0 and state.get("judgement"):
            j = state["judgement"]
            points = list(j.get("blocking_issues") or []) + list(j.get("top_weaknesses") or [])
            if points:
                notes = (
                    "REVISION PASS — the previous draft was rejected by the script "
                    "judge. Fix these specific problems while keeping what worked:\n- "
                    + "\n- ".join(str(p) for p in points[:6])
                )
        out = await pipeline_ops.generate_script_op(
            db, state["project_id"], state["premise"], state.get("genre", "drama"),
            state.get("tone", "dramatic"),
            episode_count=state.get("episode_count", 1),
            target_length=state.get("target_length", 30),
            language=state.get("language", "en"),
            notes=notes,
            model=state.get("model") or None,
        )
        state["script_id"] = out["script_id"]
        state["structured"] = out["structured"]
        return state

    async def n_judge(state: PipelineState) -> PipelineState:
        _emit_node(state, "judge")
        if db is None:
            return state
        from app.websocket.tool_events import tool_run
        with tool_run(state["project_id"], "script", "narrative_judge",
                      "Story Analyst") as tb:
            state["judgement"] = await NarrativeJudge().evaluate(state.get("structured", {}))
            tb["artifact"] = (state["judgement"] or {}).get("recommendation", "scored")
        from app.agents.reporter import report_agent
        j = state["judgement"]
        report_agent(db, state["project_id"], agent="narrative_judge", stage="judge",
                     decision=j.get("scores", {}),
                     rationale=j.get("recommendation", ""),
                     confidence=float(j.get("overall", 0)) / 10.0)
        return state

    async def n_revise(state: PipelineState) -> PipelineState:
        _emit_node(state, "revise")
        state["revise_count"] = state.get("revise_count", 0) + 1
        if db is not None and state.get("project_id"):
            from app.agents.reporter import report_agent
            j = state.get("judgement") or {}
            report_agent(db, state["project_id"], agent="script_reviser", stage="revise",
                         decision={"feeding_back": (j.get("blocking_issues") or [])
                                   + (j.get("top_weaknesses") or [])},
                         rationale="Rewriting with the judge's critique as revision notes",
                         confidence=float(j.get("overall", 0) or 0) / 10.0)
        return state

    async def n_extract_characters(state: PipelineState) -> PipelineState:
        _emit_node(state, "extract_characters")
        if db is None:
            return state
        state["characters"] = await pipeline_ops.extract_characters_op(db, state["script_id"])
        return state

    async def n_clarify(state: PipelineState) -> PipelineState:
        _emit_node(state, "clarify")
        if db is not None and state.get("project_id"):
            from app.agent.pipeline_ops import clarify_op
            out = await clarify_op(db, state["project_id"])
            state["clarify_pause"] = out["pause"]
        return state

    async def n_storyboard(state: PipelineState) -> PipelineState:
        _emit_node(state, "storyboard")
        if db is None:
            return state
        state["shots"] = await pipeline_ops.generate_storyboard_op(
            db, state["script_id"], target_length=state.get("target_length", 30)
        )
        return state

    async def n_casting(state: PipelineState) -> PipelineState:
        _emit_node(state, "casting")
        # Casting generates reference plates (real image-gen spend). In plan-only mode
        # it is SKIPPED — the user runs casting via the reviewed Casting panel
        # ("Generate plates" -> async casting worker). Only full-auto (dispatch_video)
        # runs it inline here.
        if db is not None and state.get("project_id") and state.get("dispatch_video"):
            from app.agent.pipeline_ops import cast_bible_op
            await cast_bible_op(db, state["project_id"])
        return state

    async def n_audio(state: PipelineState) -> PipelineState:
        _emit_node(state, "audio")
        # Dialogue synthesis (TTS spend) — same rule as casting: full-auto only.
        if db is not None and state.get("project_id") and state.get("dispatch_video"):
            from app.agent.pipeline_ops import synth_dialogue_op
            await synth_dialogue_op(db, state["project_id"])
        return state

    async def n_budget(state: PipelineState) -> PipelineState:
        _emit_node(state, "budget")
        if db is None:
            return state
        state["budget"] = pipeline_ops.allocate_budget_op(
            db, state["project_id"], state.get("shots", [])
        )
        return state

    async def n_generate_video(state: PipelineState) -> PipelineState:
        # Plan-only by default: build the script/cast/storyboard/budget but do
        # NOT dispatch video (which spends the voucher) unless explicitly asked.
        dispatch = bool(state.get("dispatch_video"))
        _emit_node(state, "generate_video" if dispatch else "finalize")
        if db is None:
            return state
        if dispatch:
            # full-auto: the job auto-exports the finished episode on completion
            state["job_id"] = pipeline_ops.dispatch_generation_op(
                db, state["project_id"], auto_export=True)
        state["report"] = {
            "judgement": state.get("judgement"),
            "characters": len(state.get("characters", [])),
            "shots": len(state.get("shots", [])),
            "budget": state.get("budget"),
            "job_id": state.get("job_id"),
            "dispatched": dispatch,
            "revisions": state.get("revise_count", 0),
        }
        return state

    g = StateGraph(PipelineState)
    g.add_node("generate_script", n_generate_script)
    g.add_node("judge", n_judge)
    g.add_node("revise", n_revise)
    g.add_node("extract_characters", n_extract_characters)
    g.add_node("clarify", n_clarify)
    g.add_node("storyboard", n_storyboard)
    g.add_node("casting", n_casting)
    g.add_node("audio", n_audio)
    g.add_node("budget", n_budget)
    g.add_node("generate_video", n_generate_video)

    g.add_edge(START, "generate_script")
    g.add_edge("generate_script", "judge")
    g.add_conditional_edges("judge", route_after_judge,
                            {"revise": "revise",
                             "extract_characters": "extract_characters",
                             "END": END})
    g.add_edge("revise", "generate_script")  # self-correction loop
    g.add_edge("extract_characters", "clarify")
    g.add_conditional_edges("clarify",
        lambda s: "END" if s.get("clarify_pause") else "storyboard",
        {"END": END, "storyboard": "storyboard"})
    g.add_edge("storyboard", "casting")
    g.add_edge("casting", "audio")
    g.add_edge("audio", "budget")
    g.add_edge("budget", "generate_video")
    g.add_edge("generate_video", END)
    return g.compile()
