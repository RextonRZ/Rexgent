import oss2
import logging
from app.config import Settings

logger = logging.getLogger(__name__)


class OSSManager:
    """Alibaba Cloud OSS file operations.

    This module uses the oss2 SDK for Alibaba Cloud Object Storage Service,
    serving as proof of Alibaba Cloud deployment for the hackathon submission.
    """

    def __init__(self, settings: Settings):
        self.auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        self.bucket = oss2.Bucket(self.auth, settings.oss_endpoint, settings.oss_bucket_name)
        self.bucket_name = settings.oss_bucket_name
        self.endpoint = settings.oss_endpoint

    # Reference images and generated clips must be fetchable by Qwen's servers
    # (vision description + image-to-video) and shown in the browser. We try to
    # mark each object public-read; if the bucket disallows per-object ACLs
    # (Block Public Access), we fall back to a plain upload and rely on the
    # bucket-level ACL instead.
    _PUBLIC_READ = {"x-oss-object-acl": oss2.OBJECT_ACL_PUBLIC_READ}

    def upload_file(self, local_path: str, oss_key: str) -> str:
        try:
            self.bucket.put_object_from_file(oss_key, local_path, headers=dict(self._PUBLIC_READ))
        except oss2.exceptions.AccessDenied:
            self.bucket.put_object_from_file(oss_key, local_path)
        return self._build_url(oss_key)

    def upload_bytes(self, data: bytes, oss_key: str, content_type: str = "application/octet-stream") -> str:
        base = {"Content-Type": content_type}
        try:
            self.bucket.put_object(oss_key, data, headers={**base, **self._PUBLIC_READ})
        except oss2.exceptions.AccessDenied:
            self.bucket.put_object(oss_key, data, headers=base)
        return self._build_url(oss_key)

    def download_file(self, oss_key: str, local_path: str) -> str:
        self.bucket.get_object_to_file(oss_key, local_path)
        return local_path

    def get_presigned_url(self, oss_key: str, expires: int = 900) -> str:
        return self.bucket.sign_url("GET", oss_key, expires)

    def delete_file(self, oss_key: str) -> None:
        self.bucket.delete_object(oss_key)

    def get_project_path(self, project_id: str, category: str, filename: str) -> str:
        return f"projects/{project_id}/{category}/{filename}"

    def _build_url(self, oss_key: str) -> str:
        host = self.endpoint.replace("https://", "").replace("http://", "")
        return f"https://{self.bucket_name}.{host}/{oss_key}"
