import redis
from sqlalchemy.orm import Session
from app.config import get_settings
from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.orchestrator.memory_graph import NarrativeMemoryGraph
from app.orchestrator.persistence import NMGPersistence


class ShowMindOrchestrator:
    def __init__(self, project_id: str, db: Session):
        self.project_id = project_id
        self.db = db
        settings = get_settings()
        self.qwen = QwenClient(settings)
        self.oss = OSSManager(settings)
        redis_client = redis.from_url(settings.redis_url)
        self.persistence = NMGPersistence(redis_client=redis_client, db=db)
        self.memory_graph: NarrativeMemoryGraph | None = None

    async def load_or_create_graph(self) -> NarrativeMemoryGraph:
        self.memory_graph = self.persistence.load_or_create(self.project_id)
        return self.memory_graph

    async def save_graph(self, stage: str) -> None:
        if self.memory_graph:
            self.persistence.save(self.memory_graph, stage)
