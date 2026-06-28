import pytest
from unittest.mock import MagicMock, patch
from app.services.oss_manager import OSSManager
from app.config import Settings


def make_manager():
    settings = Settings(
        qwen_api_key="test",
        qwen_base_url="https://test",
        oss_access_key_id="test-key-id",
        oss_access_key_secret="test-secret",
        oss_bucket_name="test-bucket",
        oss_endpoint="https://oss-test.aliyuncs.com",
        database_url="postgresql://localhost/test",
    )
    with patch("oss2.Auth"), patch("oss2.Bucket"):
        return OSSManager(settings)


def test_get_project_path():
    manager = make_manager()
    path = manager.get_project_path("proj-123", "clips", "clip_001.mp4")
    assert path == "projects/proj-123/clips/clip_001.mp4"


def test_get_project_path_nested():
    manager = make_manager()
    path = manager.get_project_path("proj-123", "characters/char-456", "reference.jpg")
    assert path == "projects/proj-123/characters/char-456/reference.jpg"


def test_build_url():
    manager = make_manager()
    url = manager._build_url("projects/proj-123/clips/clip.mp4")
    assert url == "https://test-bucket.oss-test.aliyuncs.com/projects/proj-123/clips/clip.mp4"
