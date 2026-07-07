"""Per-TOOL progress events for the crew workflow graph.

`stage:progress` narrates at STAGE level. The crew modal's two-level graph
needs the machinery INSIDE each stage — which model wrote, what hit the DB,
what got validated — ticking individually. One uniform event carries it all:

    tool:progress {
        stage:   script | characters | storyboard | generate | export
        tool:    snake_case node label, e.g. "llm_write", "write_clip_db"
        status:  started | succeeded | failed
        agent?:  owning crew member ("Screenwriter")
        artifact?: short edge label for what flowed out ("8 shots", "5 plates")
        index?/total?: progress within the tool ("shot 3/12")
        error?:  failed only, truncated
    }

Best-effort like every WS emit — a socket failure never breaks the pipeline.
"""
from contextlib import contextmanager
from app.websocket.emitter import emit


def tool_event(project_id, stage: str, tool: str, status: str,
               agent: str | None = None, artifact: str | None = None,
               error: str | None = None,
               index: int | None = None, total: int | None = None) -> None:
    try:
        data: dict = {"stage": stage, "tool": tool, "status": status}
        if agent:
            data["agent"] = agent
        if artifact:
            data["artifact"] = artifact
        if error:
            data["error"] = str(error)[:200]
        if index is not None:
            data["index"] = index
        if total is not None:
            data["total"] = total
        emit("tool:progress", data, str(project_id))
    except Exception:  # noqa: BLE001 — never let telemetry break the pipeline
        pass


@contextmanager
def tool_run(project_id, stage: str, tool: str, agent: str | None = None,
             total: int | None = None):
    """started -> succeeded/failed around a block. Yields a dict; set
    box["artifact"] inside to label the outgoing edge:

        with tool_run(pid, "script", "llm_write", "Screenwriter") as box:
            draft = await ...
            box["artifact"] = "1 draft"
    """
    tool_event(project_id, stage, tool, "started", agent=agent, total=total)
    box: dict = {"artifact": None}
    try:
        yield box
    except Exception as e:
        tool_event(project_id, stage, tool, "failed", agent=agent, error=str(e))
        raise
    tool_event(project_id, stage, tool, "succeeded", agent=agent,
               artifact=box.get("artifact"))
