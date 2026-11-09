import os
import hashlib
import uuid
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

from app.config import settings

# Base storage directory
STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "storage"


class StorageService:
    """
    Persistent document storage service.
    Stores files securely on local disk organized by owner_user_id,
    with an interface designed to be cloud-ready (e.g. Azure Blob Storage).
    """

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or STORAGE_ROOT
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_dir(self, user_id: str) -> Path:
        sanitized_uid = "".join(c for c in user_id if c.isalnum() or c in ("-", "_"))
        if not sanitized_uid:
            sanitized_uid = "system_default"
        user_dir = self.root_dir / sanitized_uid
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def save_file(
        self,
        user_id: str,
        filename: str,
        content: bytes,
    ) -> Tuple[str, str, int, str]:
        """
        Save file content persistently.
        Returns (storage_key, sha256_hash, file_size, content_type).
        """
        sha256_hash = hashlib.sha256(content).hexdigest()
        ext = Path(filename).suffix.lower()
        if not ext:
            ext = ".pdf"
        storage_key = f"{uuid.uuid4().hex}{ext}"

        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/pdf" if ext == ".pdf" else "application/octet-stream"

        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / storage_key
        target_path.write_bytes(content)

        return storage_key, sha256_hash, len(content), content_type

    def get_file(self, user_id: str, storage_key: str) -> Optional[Tuple[bytes, str]]:
        """
        Retrieve stored file content and content type.
        """
        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / storage_key
        if not target_path.is_file():
            # Check default system storage as fallback
            default_path = self.root_dir / "system_default" / storage_key
            if default_path.is_file():
                target_path = default_path
            else:
                return None

        content = target_path.read_bytes()
        content_type, _ = mimetypes.guess_type(storage_key)
        if not content_type:
            content_type = "application/pdf" if storage_key.endswith(".pdf") else "application/octet-stream"

        return content, content_type

    def delete_file(self, user_id: str, storage_key: str) -> bool:
        """
        Delete a single file from storage.
        """
        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / storage_key
        if target_path.is_file():
            target_path.unlink()
            return True
        return False

    def delete_user_files(self, user_id: str) -> int:
        """
        Delete all stored files for a given user.
        """
        user_dir = self._get_user_dir(user_id)
        count = 0
        if user_dir.is_dir():
            for child in user_dir.iterdir():
                if child.is_file():
                    child.unlink()
                    count += 1
            try:
                user_dir.rmdir()
            except OSError:
                pass
        return count


# Singleton storage instance
storage_service = StorageService()

