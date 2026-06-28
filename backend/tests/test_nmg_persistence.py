import json
import pytest
from unittest.mock import MagicMock
from app.orchestrator.memory_graph import NarrativeMemoryGraph, NarrativeFact
from app.orchestrator.persistence import NMGPersistence


def test_save_to_redis():
    mock_redis = MagicMock()
    persistence = NMGPersistence(redis_client=mock_redis, db=MagicMock())

    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.record_fact(NarrativeFact(fact_id="f1", scene_number=1, category="LOCATION", fact="Tokyo", established_by="dialogue"))

    persistence.save_to_redis(nmg)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "nmg:proj-123"
    assert call_args[0][1] == 7200
    saved_data = json.loads(call_args[0][2])
    assert saved_data["project_id"] == "proj-123"


def test_load_from_redis_hit():
    mock_redis = MagicMock()
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    mock_redis.get.return_value = json.dumps(nmg.to_dict())

    persistence = NMGPersistence(redis_client=mock_redis, db=MagicMock())
    result = persistence.load_from_redis("proj-123")

    assert result is not None
    assert result.project_id == "proj-123"


def test_load_from_redis_miss():
    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    persistence = NMGPersistence(redis_client=mock_redis, db=MagicMock())
    result = persistence.load_from_redis("proj-123")

    assert result is None


def test_load_or_create_returns_new():
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    persistence = NMGPersistence(redis_client=mock_redis, db=mock_db)
    test_id = "00000000-0000-0000-0000-000000000456"
    result = persistence.load_or_create(test_id)

    assert result.project_id == test_id
    assert result.version == 0
