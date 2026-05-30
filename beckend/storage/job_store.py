"""
Job persistence and state management for ThoughtSpot -> Power BI Migration Tool.

This store manages the main `jobs` table:
- create job
- get job
- list jobs
- update status
- update progress
- save progress logs
- delete job
"""

from datetime import datetime
from typing import Optional, List, Tuple, Any

from loguru import logger

from storage.database import get_db_connection
from api.models.job_models import MigrationJob
from api.models.api_models import JobStatus
from api.models.migration_models import MigrationStage


class JobStore:
    """
    Manages job persistence in SQLite database.
    """

    # ============================================================
    # Internal Helpers
    # ============================================================

    @staticmethod
    def _status_value(status: Any) -> str:
        """
        Convert JobStatus enum/string to database value.
        """

        if hasattr(status, "value"):
            return status.value

        return str(status)

    @staticmethod
    def _stage_value(stage: Any) -> Optional[str]:
        """
        Convert MigrationStage enum/string to database value.
        """

        if stage is None:
            return None

        if hasattr(stage, "value"):
            return stage.value

        return str(stage)

    @staticmethod
    def _row_to_job(row) -> Optional[MigrationJob]:
        """
        Convert SQLite row into MigrationJob domain model.

        This maps the `jobs` table columns to the MigrationJob dataclass.
        """

        if row is None:
            return None

        def get(key: str, default=None):
            try:
                return row[key]
            except Exception:
                return default

        def parse_datetime(value):
            if value and isinstance(value, str):
                return datetime.fromisoformat(value)
            return value

        current_stage_value = get("current_stage")

        job = MigrationJob(
            job_id=get("job_id"),
            status=JobStatus(get("status")),
            created_at=parse_datetime(get("created_at")),

            total_objects=get("total_objects", 0) or 0,
            progress_percent=get("progress_percent", 0) or 0,

            current_stage=(
                MigrationStage(current_stage_value)
                if current_stage_value and current_stage_value in [stage.value for stage in MigrationStage]
                else None
            ),
            current_object_name=get("current_object_name"),

            started_at=parse_datetime(get("started_at")),
            completed_at=parse_datetime(get("completed_at")),

            error_message=get("error_message"),

            objects_completed=get("objects_completed", 0) or 0,
            objects_failed=get("objects_failed", 0) or 0,
            objects_skipped=get("objects_skipped", 0) or 0,

            formulas_converted=get("formulas_converted", 0) or 0,
            relationships_created=get("relationships_created", 0) or 0,

            powerbi_workspace_id=get("powerbi_workspace_id"),
            powerbi_dataset_id=get("powerbi_dataset_id"),
            powerbi_report_id=get("powerbi_report_id"),
            powerbi_report_url=get("powerbi_report_url"),

            result_file_path=get("result_file_path"),
            pbix_file_path=get("pbix_file_path"),
            report_json_path=get("report_json_path"),
        )

        # Compatibility attributes for older router code
        job.file_count = get("file_count", 0) or 0
        job.relationship_count = get("relationships_created", 0) or 0

        return job

    # ============================================================
    # Create Job
    # ============================================================

    def create_job(
        self,
        job_id: str,
        file_count: int = 0,
        total_objects: int = 0,
    ) -> MigrationJob:
        """
        Create a new ThoughtSpot -> Power BI migration job.

        Args:
            job_id: Unique job identifier.
            file_count: Number of uploaded files.
            total_objects: Number of ThoughtSpot objects, if already known.

        Returns:
            Created MigrationJob object.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    status,
                    file_count,
                    total_objects,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    JobStatus.PENDING.value,
                    file_count,
                    total_objects,
                    datetime.utcnow(),
                ),
            )

        logger.info(
            f"Created ThoughtSpot -> Power BI job {job_id} "
            f"with {file_count} uploaded files"
        )

        job = self.get_job(job_id)

        if job is None:
            raise RuntimeError(f"Failed to create job {job_id}")

        return job

    # ============================================================
    # Get Job
    # ============================================================

    def get_job(
        self,
        job_id: str,
    ) -> Optional[MigrationJob]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier.

        Returns:
            MigrationJob object or None.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    job_id,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    progress_percent,
                    current_stage,
                    current_object_name,
                    error_message,

                    file_count,
                    total_objects,
                    objects_completed,
                    objects_failed,
                    objects_skipped,

                    formulas_converted,
                    relationships_created,

                    powerbi_workspace_id,
                    powerbi_dataset_id,
                    powerbi_report_id,
                    powerbi_report_url,

                    result_file_path,
                    pbix_file_path,
                    report_json_path
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        return self._row_to_job(row)

    # ============================================================
    # List Jobs
    # ============================================================

    def list_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Tuple[List[MigrationJob], int]:
        """
        List jobs with pagination.

        Args:
            limit: Maximum number of jobs to return.
            offset: Number of jobs to skip.
            status: Optional status filter.

        Returns:
            Tuple of jobs list and total count.
        """

        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)

        with get_db_connection() as conn:
            where_clause = ""
            params: List[Any] = []

            if status:
                where_clause = "WHERE status = ?"
                params.append(status)

            count_query = f"""
                SELECT COUNT(*)
                FROM jobs
                {where_clause}
            """

            total = conn.execute(count_query, params).fetchone()[0]

            query = f"""
                SELECT
                    job_id,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    progress_percent,
                    current_stage,
                    current_object_name,
                    error_message,

                    file_count,
                    total_objects,
                    objects_completed,
                    objects_failed,
                    objects_skipped,

                    formulas_converted,
                    relationships_created,

                    powerbi_workspace_id,
                    powerbi_dataset_id,
                    powerbi_report_id,
                    powerbi_report_url,

                    result_file_path,
                    pbix_file_path,
                    report_json_path
                FROM jobs
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """

            rows = conn.execute(
                query,
                params + [limit, offset],
            ).fetchall()

            jobs = [self._row_to_job(row) for row in rows]

        return jobs, total

    # ============================================================
    # Update Status
    # ============================================================

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        total_objects: Optional[int] = None,
        objects_completed: Optional[int] = None,
        objects_failed: Optional[int] = None,
        objects_skipped: Optional[int] = None,
        formulas_converted: Optional[int] = None,
        relationships_created: Optional[int] = None,
        result_file_path: Optional[str] = None,
        pbix_file_path: Optional[str] = None,
        report_json_path: Optional[str] = None,
        powerbi_workspace_id: Optional[str] = None,
        powerbi_dataset_id: Optional[str] = None,
        powerbi_report_id: Optional[str] = None,
        powerbi_report_url: Optional[str] = None,
        relationship_count: Optional[int] = None,
    ) -> None:
        """
        Update job status and optional migration result fields.

        Args:
            job_id: Job identifier.
            status: New job status.
            error: Error message if failed.
            total_objects: Total ThoughtSpot objects.
            objects_completed: Number of successful objects.
            objects_failed: Number of failed objects.
            objects_skipped: Number of skipped objects.
            formulas_converted: Number of formulas converted.
            relationships_created: Number of relationships created.
            result_file_path: Result JSON path.
            pbix_file_path: PBIX file path, if generated.
            report_json_path: Report JSON path, if generated.
            powerbi_workspace_id: Power BI workspace ID.
            powerbi_dataset_id: Power BI dataset ID.
            powerbi_report_id: Power BI report ID.
            powerbi_report_url: Power BI report URL.
            relationship_count: Backward-compatible alias for relationships_created.
        """

        status_value = self._status_value(status)

        if relationship_count is not None and relationships_created is None:
            relationships_created = relationship_count

        update_fields = ["status = ?"]
        params: List[Any] = [status_value]

        if error is not None:
            update_fields.append("error_message = ?")
            params.append(error)

        optional_updates = {
            "total_objects": total_objects,
            "objects_completed": objects_completed,
            "objects_failed": objects_failed,
            "objects_skipped": objects_skipped,
            "formulas_converted": formulas_converted,
            "relationships_created": relationships_created,
            "result_file_path": result_file_path,
            "pbix_file_path": pbix_file_path,
            "report_json_path": report_json_path,
            "powerbi_workspace_id": powerbi_workspace_id,
            "powerbi_dataset_id": powerbi_dataset_id,
            "powerbi_report_id": powerbi_report_id,
            "powerbi_report_url": powerbi_report_url,
        }

        for column_name, value in optional_updates.items():
            if value is not None:
                update_fields.append(f"{column_name} = ?")
                params.append(value)

        if status_value == JobStatus.RUNNING.value:
            update_fields.append("started_at = COALESCE(started_at, ?)")
            params.append(datetime.utcnow())

        if status_value in [
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ]:
            update_fields.append("completed_at = ?")
            params.append(datetime.utcnow())

        params.append(job_id)

        query = f"""
            UPDATE jobs
            SET {", ".join(update_fields)}
            WHERE job_id = ?
        """

        with get_db_connection() as conn:
            conn.execute(query, params)

        logger.info(f"Updated job {job_id} status to {status_value}")

    # ============================================================
    # Update Progress
    # ============================================================

    def update_progress(
        self,
        job_id: str,
        percent: int,
        stage: str,
        message: Optional[str] = None,
        current_object_name: Optional[str] = None,
        level: str = "info",
        details: Optional[str] = None,
    ) -> None:
        """
        Update job progress.

        Args:
            job_id: Job identifier.
            percent: Progress percentage between 0 and 100.
            stage: Current migration stage.
            message: Optional progress message.
            current_object_name: Current ThoughtSpot object being processed.
            level: Log level.
            details: Optional JSON details string.
        """

        percent = max(0, min(100, int(percent)))

        stage_value = self._stage_value(stage)

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET
                    progress_percent = ?,
                    current_stage = ?,
                    current_object_name = COALESCE(?, current_object_name)
                WHERE job_id = ?
                """,
                (
                    percent,
                    stage_value,
                    current_object_name,
                    job_id,
                ),
            )

            if message:
                conn.execute(
                    """
                    INSERT INTO job_progress (
                        job_id,
                        stage,
                        message,
                        percent,
                        level,
                        object_name,
                        details
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        stage_value,
                        message,
                        percent,
                        level,
                        current_object_name,
                        details,
                    ),
                )

        logger.debug(
            f"Updated job {job_id} progress to {percent}% "
            f"at stage {stage_value}"
        )

    # ============================================================
    # Counters
    # ============================================================

    def increment_completed_objects(
        self,
        job_id: str,
        count: int = 1,
    ) -> None:
        """
        Increment successful object count.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET objects_completed = objects_completed + ?
                WHERE job_id = ?
                """,
                (count, job_id),
            )

    def increment_failed_objects(
        self,
        job_id: str,
        count: int = 1,
    ) -> None:
        """
        Increment failed object count.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET objects_failed = objects_failed + ?
                WHERE job_id = ?
                """,
                (count, job_id),
            )

    def increment_skipped_objects(
        self,
        job_id: str,
        count: int = 1,
    ) -> None:
        """
        Increment skipped object count.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET objects_skipped = objects_skipped + ?
                WHERE job_id = ?
                """,
                (count, job_id),
            )

    # ============================================================
    # Logs
    # ============================================================

    def get_recent_progress_logs(
        self,
        job_id: str,
        limit: int = 10,
    ) -> List[dict]:
        """
        Get recent progress logs for a job.

        Args:
            job_id: Job identifier.
            limit: Maximum number of logs to return.

        Returns:
            List of progress log dictionaries.
        """

        limit = min(max(limit, 1), 100)

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    timestamp,
                    stage,
                    message,
                    percent,
                    level,
                    object_name,
                    details
                FROM job_progress
                WHERE job_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()

        return [
            {
                "timestamp": row["timestamp"],
                "stage": row["stage"],
                "message": row["message"],
                "percent": row["percent"],
                "level": row["level"],
                "object_name": row["object_name"],
                "details": row["details"],
            }
            for row in rows
        ]

    # ============================================================
    # Delete Job
    # ============================================================

    def delete_job(
        self,
        job_id: str,
    ) -> bool:
        """
        Delete a job and all related data.

        Args:
            job_id: Job identifier.

        Returns:
            True if deleted, False if not found.
        """

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted job {job_id}")

        return deleted

    # ============================================================
    # Existence / Status Helpers
    # ============================================================

    def job_exists(
        self,
        job_id: str,
    ) -> bool:
        """
        Check if job exists.

        Args:
            job_id: Job identifier.

        Returns:
            True if job exists.
        """

        with get_db_connection() as conn:
            count = conn.execute(
                """
                SELECT COUNT(*)
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()[0]

        return count > 0

    def is_job_running(
        self,
        job_id: str,
    ) -> bool:
        """
        Check if job is currently running.
        """

        job = self.get_job(job_id)

        if not job:
            return False

        return job.status == JobStatus.RUNNING

    def mark_failed(
        self,
        job_id: str,
        error: str,
    ) -> None:
        """
        Mark job as failed.
        """

        self.update_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=error,
        )

    def mark_completed(
        self,
        job_id: str,
        result_file_path: Optional[str] = None,
        powerbi_dataset_id: Optional[str] = None,
        powerbi_report_id: Optional[str] = None,
        powerbi_report_url: Optional[str] = None,
    ) -> None:
        """
        Mark job as completed.
        """

        self.update_status(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            result_file_path=result_file_path,
            powerbi_dataset_id=powerbi_dataset_id,
            powerbi_report_id=powerbi_report_id,
            powerbi_report_url=powerbi_report_url,
        )