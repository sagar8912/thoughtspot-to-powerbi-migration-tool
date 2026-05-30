"""
File storage management for uploaded ThoughtSpot files.

This store handles:
- Saving uploaded ThoughtSpot export/TML/metadata files
- Validating supported file extensions
- Reading files for migration jobs
- Deleting uploaded files when a job is deleted
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from storage.database import get_db_connection
from api.models.job_models import ThoughtSpotUploadedFile
from api.config import config


class FileStore:
    """
    Manages uploaded ThoughtSpot file storage.
    """

    def __init__(self):
        """
        Initialize file store and ensure upload directory exists.
        """

        Path(config.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Helpers
    # ============================================================

    @staticmethod
    def _generate_file_id() -> str:
        """
        Generate unique file ID.
        """

        return f"file_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """
        Sanitize filename for safe storage.
        """

        return Path(filename).name.replace(" ", "_")

    @staticmethod
    def _detect_file_type(filename: str) -> str:
        """
        Detect file type from extension.
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
        Try to detect ThoughtSpot object type from filename.

        This is only a best-effort detection.
        The real object type should be detected later by the parser.
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

    # ============================================================
    # Save Files
    # ============================================================

    def save_uploaded_file(
        self,
        job_id: str,
        original_filename: str,
        file_content: bytes,
        thoughtspot_object_type: Optional[str] = None,
        thoughtspot_object_name: Optional[str] = None,
        thoughtspot_object_guid: Optional[str] = None,
    ) -> ThoughtSpotUploadedFile:
        """
        Save an uploaded ThoughtSpot file.

        Args:
            job_id: Migration job identifier.
            original_filename: Original uploaded filename.
            file_content: File content as bytes.
            thoughtspot_object_type: Optional detected object type.
            thoughtspot_object_name: Optional ThoughtSpot object name.
            thoughtspot_object_guid: Optional ThoughtSpot object GUID.

        Returns:
            ThoughtSpotUploadedFile object.
        """

        if not original_filename:
            raise ValueError("original_filename is required")

        file_id = self._generate_file_id()
        safe_original_filename = self._safe_filename(original_filename)
        stored_filename = f"{file_id}_{safe_original_filename}"

        file_type = self._detect_file_type(original_filename)

        if thoughtspot_object_type is None:
            thoughtspot_object_type = self._detect_thoughtspot_object_type(
                original_filename
            )

        job_dir = Path(config.UPLOAD_DIR) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        file_path = job_dir / stored_filename

        with open(file_path, "wb") as f:
            f.write(file_content)

        file_size = len(file_content)

        uploaded_file = ThoughtSpotUploadedFile(
            file_id=file_id,
            job_id=job_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size=file_size,
            file_type=file_type,
            thoughtspot_object_type=thoughtspot_object_type,
            thoughtspot_object_name=thoughtspot_object_name,
            thoughtspot_object_guid=thoughtspot_object_guid,
            parsed_successfully=False,
            parse_error=None,
        )

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO uploaded_files (
                    file_id,
                    job_id,
                    original_filename,
                    stored_filename,
                    file_path,
                    file_size,
                    file_type,
                    thoughtspot_object_type,
                    thoughtspot_object_name,
                    thoughtspot_object_guid,
                    parsed_successfully,
                    parse_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uploaded_file.file_id,
                    uploaded_file.job_id,
                    uploaded_file.original_filename,
                    uploaded_file.stored_filename,
                    uploaded_file.file_path,
                    uploaded_file.file_size,
                    uploaded_file.file_type,
                    uploaded_file.thoughtspot_object_type,
                    uploaded_file.thoughtspot_object_name,
                    uploaded_file.thoughtspot_object_guid,
                    int(uploaded_file.parsed_successfully),
                    uploaded_file.parse_error,
                ),
            )

        logger.info(
            f"Saved ThoughtSpot file {original_filename} for job {job_id} "
            f"({file_size} bytes)"
        )

        return uploaded_file

    # ============================================================
    # Read Files
    # ============================================================

    def get_job_files(
        self,
        job_id: str,
    ) -> List[ThoughtSpotUploadedFile]:
        """
        Get all uploaded ThoughtSpot files for a job.

        Args:
            job_id: Job identifier.

        Returns:
            List of ThoughtSpotUploadedFile objects.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    file_id,
                    job_id,
                    original_filename,
                    stored_filename,
                    file_path,
                    file_size,
                    file_type,
                    thoughtspot_object_type,
                    thoughtspot_object_name,
                    thoughtspot_object_guid,
                    parsed_successfully,
                    parse_error,
                    uploaded_at
                FROM uploaded_files
                WHERE job_id = ?
                ORDER BY uploaded_at
                """,
                (job_id,),
            ).fetchall()

        return [ThoughtSpotUploadedFile.from_db_row(tuple(row)) for row in rows]

    def get_file(
        self,
        file_id: str,
    ) -> Optional[ThoughtSpotUploadedFile]:
        """
        Get one uploaded file by file ID.

        Args:
            file_id: File identifier.

        Returns:
            ThoughtSpotUploadedFile or None.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    file_id,
                    job_id,
                    original_filename,
                    stored_filename,
                    file_path,
                    file_size,
                    file_type,
                    thoughtspot_object_type,
                    thoughtspot_object_name,
                    thoughtspot_object_guid,
                    parsed_successfully,
                    parse_error,
                    uploaded_at
                FROM uploaded_files
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()

        if not row:
            return None

        return ThoughtSpotUploadedFile.from_db_row(tuple(row))

    def get_job_file_paths(
        self,
        job_id: str,
    ) -> List[str]:
        """
        Get all uploaded file paths for a job.

        Args:
            job_id: Job identifier.

        Returns:
            List of file paths.
        """

        files = self.get_job_files(job_id)
        return [file.file_path for file in files]

    def read_file_content(
        self,
        file_id: str,
    ) -> bytes:
        """
        Read uploaded file content.

        Args:
            file_id: File identifier.

        Returns:
            File content as bytes.
        """

        uploaded_file = self.get_file(file_id)

        if not uploaded_file:
            raise FileNotFoundError(f"File record not found: {file_id}")

        if not os.path.exists(uploaded_file.file_path):
            raise FileNotFoundError(
                f"Physical file not found: {uploaded_file.file_path}"
            )

        with open(uploaded_file.file_path, "rb") as f:
            return f.read()

    # ============================================================
    # Update Parse Metadata
    # ============================================================

    def update_file_parse_status(
        self,
        file_id: str,
        parsed_successfully: bool,
        parse_error: Optional[str] = None,
        thoughtspot_object_type: Optional[str] = None,
        thoughtspot_object_name: Optional[str] = None,
        thoughtspot_object_guid: Optional[str] = None,
    ) -> bool:
        """
        Update parsing status and detected ThoughtSpot metadata.

        Args:
            file_id: File identifier.
            parsed_successfully: Whether parser succeeded.
            parse_error: Parser error message.
            thoughtspot_object_type: Detected ThoughtSpot object type.
            thoughtspot_object_name: Detected object name.
            thoughtspot_object_guid: Detected object GUID.

        Returns:
            True if record was updated, False otherwise.
        """

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE uploaded_files
                SET
                    parsed_successfully = ?,
                    parse_error = ?,
                    thoughtspot_object_type = COALESCE(?, thoughtspot_object_type),
                    thoughtspot_object_name = COALESCE(?, thoughtspot_object_name),
                    thoughtspot_object_guid = COALESCE(?, thoughtspot_object_guid)
                WHERE file_id = ?
                """,
                (
                    int(parsed_successfully),
                    parse_error,
                    thoughtspot_object_type,
                    thoughtspot_object_name,
                    thoughtspot_object_guid,
                    file_id,
                ),
            )

            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Updated parse status for file {file_id}")

        return updated

    # ============================================================
    # Delete Files
    # ============================================================

    def delete_job_files(
        self,
        job_id: str,
    ) -> int:
        """
        Delete all uploaded files for a job.

        Args:
            job_id: Job identifier.

        Returns:
            Number of physical files deleted.
        """

        files = self.get_job_files(job_id)
        deleted_count = 0

        for uploaded_file in files:
            try:
                if os.path.exists(uploaded_file.file_path):
                    os.remove(uploaded_file.file_path)
                    deleted_count += 1
                    logger.debug(f"Deleted file {uploaded_file.file_path}")

            except Exception as e:
                logger.error(
                    f"Failed to delete file {uploaded_file.file_path}: {e}",
                    exc_info=True,
                )

        job_dir = Path(config.UPLOAD_DIR) / job_id

        if job_dir.exists():
            try:
                if not any(job_dir.iterdir()):
                    job_dir.rmdir()
                else:
                    shutil.rmtree(job_dir)

                logger.debug(f"Deleted job upload directory {job_dir}")

            except Exception as e:
                logger.error(
                    f"Failed to delete job directory {job_dir}: {e}",
                    exc_info=True,
                )

        with get_db_connection() as conn:
            conn.execute(
                """
                DELETE FROM uploaded_files
                WHERE job_id = ?
                """,
                (job_id,),
            )

        logger.info(f"Deleted {deleted_count} uploaded files for job {job_id}")

        return deleted_count

    def delete_file(
        self,
        file_id: str,
    ) -> bool:
        """
        Delete one uploaded file.

        Args:
            file_id: File identifier.

        Returns:
            True if deleted, False otherwise.
        """

        uploaded_file = self.get_file(file_id)

        if not uploaded_file:
            return False

        try:
            if os.path.exists(uploaded_file.file_path):
                os.remove(uploaded_file.file_path)

        except Exception as e:
            logger.error(
                f"Failed to delete physical file {uploaded_file.file_path}: {e}",
                exc_info=True,
            )

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM uploaded_files
                WHERE file_id = ?
                """,
                (file_id,),
            )

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted uploaded file {file_id}")

        return deleted

    # ============================================================
    # Validation
    # ============================================================

    def validate_file(
        self,
        filename: str,
        file_size: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded ThoughtSpot migration file.

        Args:
            filename: Uploaded filename.
            file_size: File size in bytes.

        Returns:
            Tuple of (is_valid, error_message).
        """

        if not filename:
            return False, "Filename is required"

        file_extension = Path(filename).suffix.lower()

        if file_extension not in config.ALLOWED_EXTENSIONS:
            return (
                False,
                "Invalid file extension. Allowed: "
                + ", ".join(config.ALLOWED_EXTENSIONS),
            )

        max_size = config.MAX_FILE_SIZE_MB * 1024 * 1024

        if file_size > max_size:
            return (
                False,
                f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds "
                f"maximum ({config.MAX_FILE_SIZE_MB}MB)",
            )

        if file_size <= 0:
            return False, "Uploaded file is empty"

        return True, None

    def validate_file_exists(
        self,
        file_path: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that a physical file exists.

        Args:
            file_path: File path.

        Returns:
            Tuple of (exists, error_message).
        """

        if not file_path:
            return False, "File path is required"

        if not os.path.exists(file_path):
            return False, f"File does not exist: {file_path}"

        return True, None


# Global file store instance
file_store = FileStore()