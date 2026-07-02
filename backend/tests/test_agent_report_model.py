from app.models.agent_report import AgentReport
from app.models.project import Project


def test_agent_report_columns():
    cols = AgentReport.__table__.columns.keys()
    for c in ["id", "project_id", "agent", "stage", "decision", "rationale", "confidence", "created_at"]:
        assert c in cols


def test_project_auto_clarify():
    assert "auto_clarify" in Project.__table__.columns.keys()
