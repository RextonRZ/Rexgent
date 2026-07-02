import uuid
import logging
from app.models.agent_report import AgentReport
from app.websocket.emitter import emit

logger = logging.getLogger(__name__)


def _mirror_neo4j(project_id, agent, decision, rationale, confidence):
    try:
        from app.graph.narrative_graph import NarrativeGraph
        ng = NarrativeGraph(project_id=str(project_id))
        if hasattr(ng, "record_agent_decision"):
            ng.record_agent_decision(agent=agent, rationale=rationale, confidence=confidence)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Neo4j agent-decision mirror skipped: {e}")


def _as_uuid(v):
    try:
        return uuid.UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        return v


def report_agent(db, project_id, agent, stage, decision, rationale, confidence):
    row = AgentReport(project_id=_as_uuid(project_id), agent=agent, stage=stage,
                      decision=decision, rationale=rationale, confidence=confidence)
    db.add(row)
    db.commit()
    payload = {"agent": agent, "stage": stage, "decision": decision,
               "rationale": rationale, "confidence": confidence}
    emit("agent:report", payload, str(project_id))
    _mirror_neo4j(project_id, agent, decision, rationale, confidence)
    return row
