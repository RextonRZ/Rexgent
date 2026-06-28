import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.orchestrator.memory_graph import NarrativeMemoryGraph
from app.models.narrative_snapshot import NarrativeMemorySnapshot


class NMGPersistence:
    REDIS_TTL = 7200  # 2 hours

    def __init__(self, redis_client, db: Session):
        self.redis = redis_client
        self.db = db

    def _redis_key(self, project_id: str) -> str:
        return f"nmg:{project_id}"

    def save_to_redis(self, nmg: NarrativeMemoryGraph) -> None:
        key = self._redis_key(nmg.project_id)
        data = json.dumps(nmg.to_dict(), default=str)
        self.redis.setex(key, self.REDIS_TTL, data)

    def load_from_redis(self, project_id: str) -> NarrativeMemoryGraph | None:
        key = self._redis_key(project_id)
        data = self.redis.get(key)
        if data is None:
            return None
        return NarrativeMemoryGraph.from_dict(json.loads(data))

    def save_snapshot(self, nmg: NarrativeMemoryGraph, stage: str) -> None:
        snapshot = NarrativeMemorySnapshot(
            id=uuid.uuid4(),
            project_id=uuid.UUID(nmg.project_id),
            version=nmg.version,
            stage=stage,
            graph_json=nmg.to_dict(),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(snapshot)
        self.db.commit()

    def load_latest_snapshot(self, project_id: str) -> NarrativeMemoryGraph | None:
        snapshot = (
            self.db.query(NarrativeMemorySnapshot)
            .filter(NarrativeMemorySnapshot.project_id == uuid.UUID(project_id))
            .order_by(NarrativeMemorySnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            return None
        return NarrativeMemoryGraph.from_dict(snapshot.graph_json)

    def load_snapshot_by_stage(self, project_id: str, stage: str) -> NarrativeMemoryGraph | None:
        snapshot = (
            self.db.query(NarrativeMemorySnapshot)
            .filter(
                NarrativeMemorySnapshot.project_id == uuid.UUID(project_id),
                NarrativeMemorySnapshot.stage == stage,
            )
            .order_by(NarrativeMemorySnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            return None
        return NarrativeMemoryGraph.from_dict(snapshot.graph_json)

    def save(self, nmg: NarrativeMemoryGraph, stage: str) -> None:
        self.save_to_redis(nmg)
        self.save_snapshot(nmg, stage)

    def load_or_create(self, project_id: str) -> NarrativeMemoryGraph:
        nmg = self.load_from_redis(project_id)
        if nmg:
            return nmg
        nmg = self.load_latest_snapshot(project_id)
        if nmg:
            self.save_to_redis(nmg)
            return nmg
        return NarrativeMemoryGraph(project_id=project_id)
