"""Re-host generated clips on our OSS bucket.

DashScope returns SIGNED video URLs that expire (~24h). Storing them raw means
every paid clip dies a day later — so download once and keep our own copy,
exactly like plates. Falls back to the original URL if the re-host fails
(better an expiring clip than none).
"""
import logging
import uuid

import httpx

from app.config import get_settings
from app.services.oss_manager import OSSManager

logger = logging.getLogger(__name__)


def persist_clip_url(project_id: str, name_hint: str, url: str) -> str:
    try:
        data = httpx.get(url, timeout=180.0).content
        oss = OSSManager(get_settings())
        key = oss.get_project_path(
            project_id, "clips", f"{name_hint}_{uuid.uuid4().hex[:8]}.mp4"
        )
        return oss.upload_bytes(data, key, content_type="video/mp4")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"clip re-host failed ({e}); storing the expiring URL")
        return url
