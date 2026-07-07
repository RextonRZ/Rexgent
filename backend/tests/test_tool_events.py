import pytest
from unittest.mock import patch
from app.websocket import tool_events
from app.websocket.tool_events import tool_event, tool_run


def test_tool_event_builds_minimal_payload():
    with patch.object(tool_events, "emit") as em:
        tool_event("pid-1", "script", "llm_write", "started")
    event, data, pid = em.call_args[0]
    assert event == "tool:progress"
    assert data == {"stage": "script", "tool": "llm_write", "status": "started"}
    assert pid == "pid-1"


def test_tool_event_carries_artifact_and_progress():
    with patch.object(tool_events, "emit") as em:
        tool_event("pid-1", "generate", "dispatch_video", "started",
                   agent="Renderer", index=3, total=12)
    data = em.call_args[0][1]
    assert data["agent"] == "Renderer"
    assert data["index"] == 3 and data["total"] == 12


def test_tool_run_emits_started_then_succeeded_with_artifact():
    with patch.object(tool_events, "emit") as em:
        with tool_run("pid-1", "export", "stitch_clips", "Editor") as t:
            t["artifact"] = "8 clips"
    events = [c[0][1] for c in em.call_args_list]
    assert [e["status"] for e in events] == ["started", "succeeded"]
    assert events[1]["artifact"] == "8 clips"


def test_tool_run_emits_failed_and_reraises():
    with patch.object(tool_events, "emit") as em:
        with pytest.raises(ValueError):
            with tool_run("pid-1", "script", "llm_write"):
                raise ValueError("model unavailable")
    events = [c[0][1] for c in em.call_args_list]
    assert [e["status"] for e in events] == ["started", "failed"]
    assert "model unavailable" in events[1]["error"]


def test_tool_event_never_raises():
    # telemetry must not break the pipeline even if the emitter blows up
    with patch.object(tool_events, "emit", side_effect=RuntimeError("redis down")):
        tool_event("pid-1", "script", "llm_write", "started")  # no raise
