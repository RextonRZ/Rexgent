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
    return "extract_characters"


def _emit_node(state: PipelineState, node: str) -> None:
    pid = state.get("project_id")
    if pid:
        emit("agent:node", {"node": node}, str(pid))


def build_pipeline_graph(db=None):
    async def n_generate_script(state: PipelineState) -> PipelineState:
        _emit_node(state, "generate_script")
        if db is None:
            return state
        out = await pipeline_ops.generate_script_op(
            db, state["project_id"], state["premise"], state.get("genre", "drama"),
            state.get("tone", "dramatic"),
            episode_count=state.get("episode_count", 1),
            target_length=state.get("target_length", 30),
            language=state.get("language", "en"),
        )
        state["script_id"] = out["script_id"]
        state["structured"] = out["structured"]
        return state

    async def n_judge(state: PipelineState) -> PipelineState:
        _emit_node(state, "judge")
        if db is None:
            return state
        state["judgement"] = await NarrativeJudge().evaluate(state.get("structured", {}))
        return state

    async def n_revise(state: PipelineState) -> PipelineState:
        _emit_node(state, "revise")
        state["revise_count"] = state.get("revise_count", 0) + 1
        return state

    async def n_extract_characters(state: PipelineState) -> PipelineState:
        _emit_node(state, "extract_characters")
        if db is None:
            return state
        state["characters"] = await pipeline_ops.extract_characters_op(db, state["script_id"])
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
        if db is not None and state.get("project_id"):
            from app.agent.pipeline_ops import cast_bible_op
            await cast_bible_op(db, state["project_id"])
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
            state["job_id"] = pipeline_ops.dispatch_generation_op(db, state["project_id"])
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
    g.add_node("storyboard", n_storyboard)
    g.add_node("casting", n_casting)
    g.add_node("budget", n_budget)
    g.add_node("generate_video", n_generate_video)

    g.add_edge(START, "generate_script")
    g.add_edge("generate_script", "judge")
    g.add_conditional_edges("judge", route_after_judge,
                            {"revise": "revise", "extract_characters": "extract_characters"})
    g.add_edge("revise", "generate_script")  # self-correction loop
    g.add_edge("extract_characters", "storyboard")
    g.add_edge("storyboard", "casting")
    g.add_edge("casting", "budget")
    g.add_edge("budget", "generate_video")
    g.add_edge("generate_video", END)
    return g.compile()
