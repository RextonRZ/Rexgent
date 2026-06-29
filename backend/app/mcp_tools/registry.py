"""Single source of truth for the 6 Rexgent tools.

Both the FastAPI HTTP routes and the standalone MCP server (mcp_server/) call
these same functions, so the tools are genuinely shared capabilities — not
REST endpoints wearing an MCP label. This module has no FastAPI/MCP imports,
so it loads cleanly in either process.
"""
from app.mcp_tools.plot_gap_detector import PlotGapDetector
from app.mcp_tools.ending_engine import EndingEngine
from app.mcp_tools.narrative_judge import NarrativeJudge
from app.mcp_tools.token_optimizer import TokenOptimizer
from app.mcp_tools.scene_prompt_craft import ScenePromptCraft
from app.mcp_tools.consistency_guard import ConsistencyGuard


async def _plot_gap(args: dict) -> dict:
    return await PlotGapDetector().detect(args["script"], args.get("sensitivity", "NORMAL"))


async def _ending(args: dict) -> dict:
    return await EndingEngine().analyse(args["script"])


async def _judge(args: dict) -> dict:
    return await NarrativeJudge().evaluate(args["script"], args.get("blocking_threshold", 5.0))


def _token(args: dict) -> dict:
    return TokenOptimizer().allocate(args["shots"], args.get("budget_usd", 40.0))


async def _prompt(args: dict) -> dict:
    return await ScenePromptCraft().craft(
        args["shot"], args["character_visuals"], args.get("target_model", "wan")
    )


async def _consistency(args: dict) -> dict:
    return await ConsistencyGuard().validate(
        args["clip_url"], args["duration"], args["expected_characters"], args.get("threshold", 0.6)
    )


_TOOLS = {
    "plot_gap_detector": _plot_gap,
    "ending_engine": _ending,
    "narrative_judge": _judge,
    "token_optimizer": _token,
    "scene_prompt_craft": _prompt,
    "consistency_guard": _consistency,
}

TOOL_DEFINITIONS = [
    {"name": "plot_gap_detector", "description": "Detect typed narrative problems in a structured script.",
     "inputSchema": {"type": "object", "properties": {"script": {"type": "object"}}, "required": ["script"]}},
    {"name": "ending_engine", "description": "Assess ending completeness and propose alternatives.",
     "inputSchema": {"type": "object", "properties": {"script": {"type": "object"}}, "required": ["script"]}},
    {"name": "narrative_judge", "description": "Score a script on 5 axes; gate generation.",
     "inputSchema": {"type": "object", "properties": {"script": {"type": "object"}}, "required": ["script"]}},
    {"name": "token_optimizer", "description": "Score shots and allocate Wan/HappyHorse within budget.",
     "inputSchema": {"type": "object", "properties": {"shots": {"type": "array"}, "budget_usd": {"type": "number"}}, "required": ["shots"]}},
    {"name": "scene_prompt_craft", "description": "Build a sanitized cinematic video prompt from shot data.",
     "inputSchema": {"type": "object", "properties": {"shot": {"type": "object"}, "character_visuals": {"type": "object"}}, "required": ["shot", "character_visuals"]}},
    {"name": "consistency_guard", "description": "Verify character faces in a clip via real ArcFace embeddings.",
     "inputSchema": {"type": "object", "properties": {"clip_url": {"type": "string"}, "duration": {"type": "number"}, "expected_characters": {"type": "array"}}, "required": ["clip_url", "duration", "expected_characters"]}},
]


def get_tool(name: str):
    return _TOOLS[name]
