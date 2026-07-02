from unittest.mock import MagicMock, patch
from app.agents.reporter import report_agent


def test_report_agent_persists_and_emits():
    db = MagicMock()
    with patch("app.agents.reporter.emit") as m_emit, \
         patch("app.agents.reporter._mirror_neo4j"):
        report_agent(db, "p1", agent="continuity", stage="generation",
                     decision={"score": 82}, rationale="face matched", confidence=0.82)
    db.add.assert_called_once()
    db.commit.assert_called_once()
    m_emit.assert_called_once()
    assert m_emit.call_args[0][0] == "agent:report"
