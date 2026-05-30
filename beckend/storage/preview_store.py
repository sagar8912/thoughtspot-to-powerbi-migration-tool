"""
Preview session storage management for ThoughtSpot -> Power BI Migration Tool.

This store manages:
- ThoughtSpot migration preview sessions
- Uploaded preview file metadata
- Raw preview files
- Optional DataFrame pickle support for CSV/Excel preview files
- Preview cleanup
"""

import os
import json
import pickle
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from loguru import logger

try:
    import pandas as pd
except Exception:
    pd = None

from storage.database import get_db_connection
from api.config import config


class PreviewFile:
    """
    Preview file metadata.

    This represents one uploaded file inside a preview session.
    """

    def __init__(
        self,
        file_id: str,
        preview_id: str,
        original_filename: str,
        file_path: str,
        dataframe_pickle_path: Optional[str] = None,
        row_count: Optional[int] = None,
        column_count: Optional[int] = None,
        metadata_json: Optional[str] = None,
    ):
        self.file_id = file_id
        self.preview_id = preview_id
        self.original_filename = original_filename
        self.file_path = file_path
        self.dataframe_pickle_path = dataframe_pickle_path
        self.row_count = row_count
        self.column_count = column_count
        self.metadata_json = metadata_json

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert preview file to dictionary.
        """

        metadata = None

        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
            except Exception:
                metadata = None

        return {
            "file_id": self.file_id,
            "preview_id": self.preview_id,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "dataframe_pickle_path": self.dataframe_pickle_path,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "metadata": metadata,
        }


class PreviewSession:
    """
    Preview session metadata.
    """

    def __init__(
        self,
        preview_id: str,
        status: str,
        created_at: datetime,
        file_count: int,
        total_duplicates_detected: int = 0,
    ):
        self.preview_id = preview_id
        self.status = status
        self.created_at = created_at
        self.file_count = file_count
        self.total_duplicates_detected = total_duplicates_detected

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert preview session to dictionary.
        """

        return {
            "preview_id": self.preview_id,
            "status": self.status,
            "created_at": self.created_at.isoformat()
            if isinstance(self.created_at, datetime)
            else self.created_at,
            "file_count": self.file_count,
            "total_duplicates_detected": self.total_duplicates_detected,
        }


class PreviewStore:
    """
    Manages ThoughtSpot preview sessions and preview files.
    """

    def __init__(self):
        """
        Initialize preview store and ensure preview directory exists.
        """

        self.preview_base_dir = Path(config.UPLOAD_DIR) / "previews"
        self.preview_base_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Internal Helpers
    # ============================================================

    @staticmethod
    def _generate_file_id() -> str:
        """
        Generate unique preview file ID.
        """

        return f"file_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """
        Sanitize filename before saving to disk.
        """

        return Path(filename).name.replace(" ", "_")

    @staticmethod
    def _detect_file_type(filename: str) -> str:
        """
        Detect file type based on extension.
        """

        extension = Path(filename).suffix.lower()

        mapping = {
            ".tml": "tml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".zip": "zip",
            ".csv": "csv",
            ".xlsx": "excel",
            ".xls": "excel",
        }

        return mapping.get(extension, "unknown")

    @staticmethod
    def _detect_thoughtspot_object_type(filename: str) -> Optional[str]:
        """
        Best-effort ThoughtSpot object type detection from filename.
        """

        name = filename.lower()

        if "worksheet" in name:
            return "worksheet"

        if "liveboard" in name or "dashboard" in name:
            return "liveboard"

        if "answer" in name:
            return "answer"

        if "table" in name:
            return "table"

        if "connection" in name:
            return "connection"

        return None

    @staticmethod
    def _parse_datetime(value):
        """
        Parse datetime safely.
        """

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return datetime.utcnow()

        return datetime.utcnow()

    @staticmethod
    def _json_dumps_safe(value: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Safely dump metadata to JSON.
        """

        if value is None:
            return None

        try:
            return json.dumps(value)
        except Exception:
            return json.dumps({"raw_metadata_error": "metadata could not be serialized"})

    @staticmethod
    def _json_loads_safe(value: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Safely parse metadata JSON.
        """

        if not value:
            return None

        try:
            return json.loads(value)
        except Exception:
            return None

    # ============================================================
    # Preview Session
    # ============================================================

    def create_preview_session(
        self,
        preview_id: str,
        file_count: int,
        total_duplicates_detected: int = 0,
    ) -> PreviewSession:
        """
        Create a new ThoughtSpot preview session.

        Args:
            preview_id: Unique preview identifier.
            file_count: Number of files in preview.
            total_duplicates_detected: Kept for compatibility with older UI.

        Returns:
            PreviewSession object.
        """

        session = PreviewSession(
            preview_id=preview_id,
            status="preview_ready",
            created_at=datetime.utcnow(),
            file_count=file_count,
            total_duplicates_detected=total_duplicates_detected,
        )

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO preview_sessions (
                    preview_id,
                    status,
                    created_at,
                    file_count,
                    total_duplicates_detected
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.preview_id,
                    session.status,
                    session.created_at,
                    session.file_count,
                    session.total_duplicates_detected,
                ),
            )

        preview_dir = self.preview_base_dir / preview_id
        preview_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Created ThoughtSpot preview session {preview_id} "
            f"with {file_count} files"
        )

        return session

    def get_preview_session(
        self,
        preview_id: str,
    ) -> Optional[PreviewSession]:
        """
        Get preview session metadata.

        Args:
            preview_id: Preview identifier.

        Returns:
            PreviewSession or None.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    preview_id,
                    status,
                    created_at,
                    file_count,
                    total_duplicates_detected
                FROM preview_sessions
                WHERE preview_id = ?
                """,
                (preview_id,),
            ).fetchone()

        if not row:
            return None

        return PreviewSession(
            preview_id=row["preview_id"],
            status=row["status"],
            created_at=self._parse_datetime(row["created_at"]),
            file_count=row["file_count"],
            total_duplicates_detected=row["total_duplicates_detected"],
        )

    def update_session_status(
        self,
        preview_id: str,
        status: str,
    ) -> bool:
        """
        Update preview session status.

        Args:
            preview_id: Preview identifier.
            status: New status. Allowed values:
                preview_ready, confirmed, cancelled

        Returns:
            True if updated, False otherwise.
        """

        allowed_statuses = {"preview_ready", "confirmed", "cancelled"}

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid preview status: {status}. "
                f"Allowed: {', '.join(sorted(allowed_statuses))}"
            )

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE preview_sessions
                SET status = ?
                WHERE preview_id = ?
                """,
                (
                    status,
                    preview_id,
                ),
            )

            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Updated preview {preview_id} status to {status}")

        return updated

    # ============================================================
    # Save Preview Files
    # ============================================================

    def save_preview_file(
        self,
        preview_id: str,
        original_filename: str,
        file_content: bytes,
        df: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PreviewFile:
        """
        Save a ThoughtSpot preview file.

        Args:
            preview_id: Preview session identifier.
            original_filename: Original file name.
            file_content: Raw file content.
            df: Optional pandas DataFrame for CSV/Excel previews.
            metadata: Preview metadata.

        Returns:
            PreviewFile object.
        """

        if not original_filename:
            raise ValueError("original_filename is required")

        if file_content is None:
            file_content = b""

        file_id = self._generate_file_id()

        preview_dir = self.preview_base_dir / preview_id
        preview_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = self._safe_filename(original_filename)
        stored_filename = f"{file_id}_{safe_filename}"
        file_path = preview_dir / stored_filename

        with open(file_path, "wb") as f:
            f.write(file_content)

        file_type = self._detect_file_type(original_filename)
        thoughtspot_object_type = self._detect_thoughtspot_object_type(
            original_filename
        )

        row_count = 0
        column_count = 0
        dataframe_pickle_path = None

        if df is not None:
            pickle_filename = f"{file_id}.pkl"
            pickle_path = preview_dir / pickle_filename

            with open(pickle_path, "wb") as f:
                pickle.dump(df, f)

            dataframe_pickle_path = str(pickle_path)

            try:
                row_count = len(df)
                column_count = len(df.columns)
            except Exception:
                row_count = 0
                column_count = 0

        final_metadata = metadata or {}

        final_metadata.update(
            {
                "source": "thoughtspot",
                "migration_target": "powerbi",
                "file_type": file_type,
                "file_size": len(file_content),
                "thoughtspot_object_type": thoughtspot_object_type,
                "uploaded_at": datetime.utcnow().isoformat(),
            }
        )

        preview_file = PreviewFile(
            file_id=file_id,
            preview_id=preview_id,
            original_filename=original_filename,
            file_path=str(file_path),
            dataframe_pickle_path=dataframe_pickle_path,
            row_count=row_count,
            column_count=column_count,
            metadata_json=self._json_dumps_safe(final_metadata),
        )

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO preview_files (
                    file_id,
                    preview_id,
                    original_filename,
                    file_path,
                    dataframe_pickle_path,
                    row_count,
                    column_count,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preview_file.file_id,
                    preview_file.preview_id,
                    preview_file.original_filename,
                    preview_file.file_path,
                    preview_file.dataframe_pickle_path,
                    preview_file.row_count,
                    preview_file.column_count,
                    preview_file.metadata_json,
                ),
            )

        logger.info(
            f"Saved ThoughtSpot preview file {original_filename} "
            f"for preview {preview_id}"
        )

        return preview_file

    # ============================================================
    # Get Preview Files
    # ============================================================

    def get_preview_files(
        self,
        preview_id: str,
    ) -> List[PreviewFile]:
        """
        Get all files for a preview session.

        Args:
            preview_id: Preview identifier.

        Returns:
            List of PreviewFile objects.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    file_id,
                    preview_id,
                    original_filename,
                    file_path,
                    dataframe_pickle_path,
                    row_count,
                    column_count,
                    metadata_json
                FROM preview_files
                WHERE preview_id = ?
                ORDER BY original_filename
                """,
                (preview_id,),
            ).fetchall()

        files = []

        for row in rows:
            files.append(
                PreviewFile(
                    file_id=row["file_id"],
                    preview_id=row["preview_id"],
                    original_filename=row["original_filename"],
                    file_path=row["file_path"],
                    dataframe_pickle_path=row["dataframe_pickle_path"],
                    row_count=row["row_count"],
                    column_count=row["column_count"],
                    metadata_json=row["metadata_json"],
                )
            )

        return files

    def get_preview_file(
        self,
        file_id: str,
    ) -> Optional[PreviewFile]:
        """
        Get one preview file by file ID.

        Args:
            file_id: File identifier.

        Returns:
            PreviewFile or None.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    file_id,
                    preview_id,
                    original_filename,
                    file_path,
                    dataframe_pickle_path,
                    row_count,
                    column_count,
                    metadata_json
                FROM preview_files
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()

        if not row:
            return None

        return PreviewFile(
            file_id=row["file_id"],
            preview_id=row["preview_id"],
            original_filename=row["original_filename"],
            file_path=row["file_path"],
            dataframe_pickle_path=row["dataframe_pickle_path"],
            row_count=row["row_count"],
            column_count=row["column_count"],
            metadata_json=row["metadata_json"],
        )

    def get_file_metadata(
        self,
        file_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get preview file metadata.

        Args:
            file_id: File identifier.

        Returns:
            Metadata dict or None.
        """

        preview_file = self.get_preview_file(file_id)

        if not preview_file:
            return None

        return self._json_loads_safe(preview_file.metadata_json)

    def get_file_path(
        self,
        file_id: str,
    ) -> Optional[str]:
        """
        Get the file path for a preview file.

        Args:
            file_id: File identifier.

        Returns:
            File path or None.
        """

        preview_file = self.get_preview_file(file_id)

        if not preview_file:
            return None

        return preview_file.file_path

    def read_preview_file(
        self,
        file_id: str,
    ) -> bytes:
        """
        Read raw preview file content.

        Args:
            file_id: File identifier.

        Returns:
            File content as bytes.
        """

        preview_file = self.get_preview_file(file_id)

        if not preview_file:
            raise FileNotFoundError(f"Preview file record not found: {file_id}")

        if not os.path.exists(preview_file.file_path):
            raise FileNotFoundError(
                f"Preview file does not exist: {preview_file.file_path}"
            )

        with open(preview_file.file_path, "rb") as f:
            return f.read()

    # ============================================================
    # Optional DataFrame Helpers
    # ============================================================

    def load_dataframe(
        self,
        file_id: str,
    ) -> Optional[Any]:
        """
        Load a DataFrame from pickle.

        This is optional and only useful for CSV/Excel preview files.
        ThoughtSpot TML/YAML/JSON files normally do not need DataFrame loading.

        Args:
            file_id: File identifier.

        Returns:
            DataFrame or None.
        """

        preview_file = self.get_preview_file(file_id)

        if not preview_file or not preview_file.dataframe_pickle_path:
            logger.warning(f"No DataFrame pickle found for {file_id}")
            return None

        pickle_path = Path(preview_file.dataframe_pickle_path)

        if not pickle_path.exists():
            logger.warning(f"Pickle file does not exist: {pickle_path}")
            return None

        try:
            with open(pickle_path, "rb") as f:
                df = pickle.load(f)

            logger.debug(f"Loaded DataFrame from {pickle_path}")
            return df

        except Exception as e:
            logger.error(f"Failed to load pickle {pickle_path}: {e}", exc_info=True)
            return None

    def load_all_dataframes(
        self,
        preview_id: str,
    ) -> Dict[str, Any]:
        """
        Load all DataFrames for a preview session.

        Args:
            preview_id: Preview session identifier.

        Returns:
            Dict mapping file_id_original_filename to DataFrame.
        """

        dataframes = {}

        files = self.get_preview_files(preview_id)

        for preview_file in files:
            df = self.load_dataframe(preview_file.file_id)

            if df is not None:
                dict_key = f"{preview_file.file_id}_{preview_file.original_filename}"
                dataframes[dict_key] = df

        logger.info(
            f"Loaded {len(dataframes)} DataFrames for preview {preview_id}"
        )

        return dataframes

    # ============================================================
    # Preview Summary
    # ============================================================

    def get_preview_summary(
        self,
        preview_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get full preview summary with session and files.

        Args:
            preview_id: Preview identifier.

        Returns:
            Preview summary dictionary.
        """

        session = self.get_preview_session(preview_id)

        if not session:
            return None

        files = self.get_preview_files(preview_id)

        return {
            "session": session.to_dict(),
            "files": [file.to_dict() for file in files],
        }

    # ============================================================
    # Delete / Cleanup
    # ============================================================

    def delete_preview(
        self,
        preview_id: str,
    ) -> int:
        """
        Delete a preview session and all associated files.

        Args:
            preview_id: Preview identifier.

        Returns:
            Number of physical files deleted.
        """

        preview_dir = self.preview_base_dir / preview_id

        files_deleted = 0

        if preview_dir.exists():
            files_deleted = len(
                [
                    item
                    for item in preview_dir.rglob("*")
                    if item.is_file()
                ]
            )

            shutil.rmtree(preview_dir)

        with get_db_connection() as conn:
            conn.execute(
                """
                DELETE FROM preview_sessions
                WHERE preview_id = ?
                """,
                (preview_id,),
            )

        logger.info(
            f"Deleted preview session {preview_id} "
            f"({files_deleted} physical files)"
        )

        return files_deleted

    def cleanup_expired_previews(
        self,
        hours: int = 1,
    ) -> int:
        """
        Delete preview sessions older than specified hours.

        Args:
            hours: Number of hours to keep previews.

        Returns:
            Number of previews deleted.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT preview_id
                FROM preview_sessions
                WHERE created_at < datetime('now', '-' || ? || ' hours')
                """,
                (hours,),
            ).fetchall()

        expired_ids = [row["preview_id"] for row in rows]

        deleted_count = 0

        for preview_id in expired_ids:
            try:
                self.delete_preview(preview_id)
                deleted_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to delete expired preview {preview_id}: {e}",
                    exc_info=True,
                )

        logger.info(f"Cleaned up {deleted_count} expired preview sessions")

        return deleted_count


# Global preview store instance
preview_store = PreviewStore()