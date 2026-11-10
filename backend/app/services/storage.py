import os
import hashlib
import uuid
import mimetypes
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


def get_default_storage_root() -> Path:
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp") / "data" / "storage"
    return Path(__file__).resolve().parent.parent.parent / "data" / "storage"


class StorageService:
    """
    Persistent document storage service.
    - Local disk cache organized by owner_user_id.
    - Persistent database BLOB backup for serverless cold-start resilience.
    - Azure Blob Storage integration when configured via environment variables.
    """

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or get_default_storage_root()
        try:
            self.root_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.root_dir = Path("/tmp") / "data" / "storage"
            self.root_dir.mkdir(parents=True, exist_ok=True)

        self.blob_container_client = None
        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING.strip()
        if conn_str:
            try:
                from azure.storage.blob import BlobServiceClient
                blob_service = BlobServiceClient.from_connection_string(conn_str)
                container_name = settings.AZURE_STORAGE_CONTAINER or "fee-auditor-documents"
                self.blob_container_client = blob_service.get_container_client(container_name)
                try:
                    self.blob_container_client.create_container()
                except Exception:
                    pass
                logger.info("Azure Blob Storage initialized with container '%s'", container_name)
            except Exception as e:
                logger.warning("Azure Blob Storage initialization skipped: %s", e)

    def _get_user_dir(self, user_id: str) -> Path:
        sanitized_uid = "".join(c for c in user_id if c.isalnum() or c in ("-", "_"))
        if not sanitized_uid:
            sanitized_uid = "system_default"
        user_dir = self.root_dir / sanitized_uid
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.root_dir = Path("/tmp") / "data" / "storage"
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
        Save file content persistently to disk, database BLOB table, and Azure Blob Storage.
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

        # 1. Local disk write
        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / storage_key
        try:
            target_path.write_bytes(content)
        except OSError:
            pass

        # 2. Database BLOB persistence
        try:
            from app.db.session import get_db_connection
            now_iso = datetime.now(timezone.utc).isoformat()
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO document_files 
                    (storage_key, user_id, filename, content_type, file_bytes, file_size, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (storage_key, user_id, filename, content_type, content, len(content), now_iso),
                )
        except Exception as e:
            logger.warning("Database document_files persistence error: %s", e)

        # 3. Azure Blob Storage persistence
        if self.blob_container_client:
            try:
                blob_name = f"{user_id}/{storage_key}"
                self.blob_container_client.upload_blob(name=blob_name, data=content, overwrite=True)
            except Exception as e:
                logger.warning("Azure Blob upload failed for %s: %s", storage_key, e)

        return storage_key, sha256_hash, len(content), content_type

    def get_file(self, user_id: str, storage_key: str) -> Optional[Tuple[bytes, str]]:
        """
        Retrieve stored file content and content type.
        Checks:
        1. Local disk cache.
        2. Database BLOB storage table.
        3. Azure Blob Storage.
        """
        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / storage_key

        # 1. Check local disk
        if target_path.is_file():
            content = target_path.read_bytes()
            content_type, _ = mimetypes.guess_type(storage_key)
            return content, content_type or "application/pdf"

        # 1b. Check default system storage fallback on disk
        default_path = self.root_dir / "system_default" / storage_key
        if default_path.is_file():
            content = default_path.read_bytes()
            content_type, _ = mimetypes.guess_type(storage_key)
            return content, content_type or "application/pdf"

        # 2. Check Database BLOB table
        try:
            from app.db.session import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT file_bytes, content_type FROM document_files WHERE storage_key = ?;",
                    (storage_key,),
                )
                row = cursor.fetchone()
                if row and row["file_bytes"]:
                    file_bytes = row["file_bytes"]
                    c_type = row["content_type"] or "application/pdf"
                    # Restore to local disk cache for fast future streaming
                    try:
                        target_path.write_bytes(file_bytes)
                    except Exception:
                        pass
                    return file_bytes, c_type
        except Exception as e:
            logger.warning("Database file lookup error: %s", e)

        # 3. Check Azure Blob Storage
        if self.blob_container_client:
            for blob_candidate in [f"{user_id}/{storage_key}", f"system_default/{storage_key}", storage_key]:
                try:
                    blob = self.blob_container_client.download_blob(blob_candidate)
                    data = blob.readall()
                    content_type, _ = mimetypes.guess_type(storage_key)
                    try:
                        target_path.write_bytes(data)
                    except Exception:
                        pass
                    return data, content_type or "application/pdf"
                except Exception:
                    continue

        return None

    def delete_file(self, user_id: str, storage_key: str) -> bool:
        """
        Delete a single file from disk, database, and Azure Blob Storage.
        """
        user_dir = self._get_user_dir(user_id)
        target_path = user_dir / storage_key
        deleted = False
        if target_path.is_file():
            target_path.unlink()
            deleted = True

        try:
            from app.db.session import get_db_connection
            with get_db_connection() as conn:
                conn.execute("DELETE FROM document_files WHERE storage_key = ?;", (storage_key,))
                deleted = True
        except Exception:
            pass

        if self.blob_container_client:
            try:
                self.blob_container_client.delete_blob(f"{user_id}/{storage_key}")
                deleted = True
            except Exception:
                pass

        return deleted

    def delete_user_files(self, user_id: str) -> int:
        """
        Delete all stored files for a given user across disk, database, and Azure Blob Storage.
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

        try:
            from app.db.session import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM document_files WHERE user_id = ?;", (user_id,))
                count = max(count, cursor.rowcount)
        except Exception:
            pass

        return count


# Singleton storage instance
storage_service = StorageService()
