"""
Progress manager for ThoughtSpot -> Power BI migration jobs.

This module provides a database + WebSocket progress callback that can be used
by workers/services during long-running migrations.

It supports:
- Job progress updates
- Migration progress updates
- Stage-based progress calculation
- WebSocket broadcasting
- Error and completion broadcasting
"""

import asyncio
from enum import Enum
from typing import Optional, Dict, Any

from loguru import logger

from storage.job_store import JobStore
from storage.migration_store import MigrationStore
from workers.websocket_manager import ws_manager


class MigrationStage(str, Enum):
    """
    ThoughtSpot -> Power BI migration stages.

    Each stage has a weight. The weight controls how much progress percentage
    that stage contributes to the total migration progress.
    """

    INITIALIZING = "initializing"
    UPLOADING = "uploading"
    PARSING = "parsing"
    EXTRACTING_METADATA = "extracting_metadata"
    DISCOVERING_OBJECTS = "discovering_objects"
    EXTRACTING_FORMULAS = "extracting_formulas"
    EXTRACTING_RELATIONSHIPS = "extracting_relationships"
    CONVERTING_DAX = "converting_dax"
    VALIDATING = "validating"
    GENERATING_POWERBI_MODEL = "generating_powerbi_model"
    EXPORTING_ARTIFACTS = "exporting_artifacts"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def stage_name(self) -> str:
        """
        Human-readable stage name.
        """

        names = {
            MigrationStage.INITIALIZING: "Initializing migration",
            MigrationStage.UPLOADING: "Uploading ThoughtSpot files",
            MigrationStage.PARSING: "Parsing ThoughtSpot files",
            MigrationStage.EXTRACTING_METADATA: "Extracting ThoughtSpot metadata",
            MigrationStage.DISCOVERING_OBJECTS: "Discovering ThoughtSpot objects",
            MigrationStage.EXTRACTING_FORMULAS: "Extracting formulas",
            MigrationStage.EXTRACTING_RELATIONSHIPS: "Extracting relationships",
            MigrationStage.CONVERTING_DAX: "Converting formulas to DAX",
            MigrationStage.VALIDATING: "Validating DAX conversions",
            MigrationStage.GENERATING_POWERBI_MODEL: "Generating Power BI model",
            MigrationStage.EXPORTING_ARTIFACTS: "Exporting Power BI artifacts",
            MigrationStage.COMPLETED: "Completed",
            MigrationStage.FAILED: "Failed",
        }

        return names.get(self, self.value)

    @property
    def weight(self) -> int:
        """
        Percentage weight for each stage.
        Total weights should equal 100.
        """

        weights = {
            MigrationStage.INITIALIZING: 5,
            MigrationStage.UPLOADING: 5,
            MigrationStage.PARSING: 10,
            MigrationStage.EXTRACTING_METADATA: 10,
            MigrationStage.DISCOVERING_OBJECTS: 10,
            MigrationStage.EXTRACTING_FORMULAS: 10,
            MigrationStage.EXTRACTING_RELATIONSHIPS: 10,
            MigrationStage.CONVERTING_DAX: 15,
            MigrationStage.VALIDATING: 10,
            MigrationStage.GENERATING_POWERBI_MODEL: 10,
            MigrationStage.EXPORTING_ARTIFACTS: 5,
            MigrationStage.COMPLETED: 0,
            MigrationStage.FAILED: 0,
        }

        return weights.get(self, 0)


class DatabaseProgressCallback:
    """
    Progress callback that persists progress to database
    and broadcasts updates through WebSocket.
    """

    def __init__(
        self,
        job_id: Optional[str] = None,
        migration_id: Optional[str] = None,
    ):
        """
        Initialize progress callback.

        Args:
            job_id: Optional job ID from jobs table.
            migration_id: Optional migration ID from migration_jobs table.
        """

        if not job_id and not migration_id:
            raise ValueError("Either job_id or migration_id is required")

        self.job_id = job_id
        self.migration_id = migration_id

        self.job_store = JobStore()
        self.migration_store = MigrationStore()

        self.current_stage: Optional[MigrationStage] = None
        self.total_items: int = 0
        self.current_items: int = 0
        self.base_percent: int = 0

    # ============================================================
    # Stage Progress
    # ============================================================

    def set_stage(
        self,
        stage: MigrationStage,
        total_items: int = 1,
        message: Optional[str] = None,
        object_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Set current processing stage.

        Args:
            stage: Migration stage.
            total_items: Number of items in this stage.
            message: Optional message.
            object_name: Optional current object/file name.
            details: Optional extra metadata.
        """

        self.current_stage = stage
        self.total_items = max(total_items, 1)
        self.current_items = 0
        self.base_percent = self._calculate_base_percent(stage)

        final_message = message or f"Starting {stage.stage_name}"

        self._persist_progress(
            percent=self.base_percent,
            stage=stage.value,
            message=final_message,
            object_name=object_name,
            level="info",
            details=details,
        )

        self._broadcast_progress(
            percent=self.base_percent,
            stage=stage.value,
            message=final_message,
            object_name=object_name,
            details=details,
        )

        logger.info(
            f"Progress {self._channel_id}: {final_message} "
            f"({self.base_percent}%)"
        )

    def increment(
        self,
        message: str = "",
        object_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Increment progress within current stage.

        Args:
            message: Optional progress message.
            object_name: Optional current object/file name.
            details: Optional extra metadata.
        """

        self.current_items += 1
        percent = self._calculate_percent()

        stage_value = self.current_stage.value if self.current_stage else "processing"

        self._persist_progress(
            percent=percent,
            stage=stage_value,
            message=message,
            object_name=object_name,
            level="info",
            details=details,
        )

        self._broadcast_progress(
            percent=percent,
            stage=stage_value,
            message=message,
            object_name=object_name,
            details=details,
        )

        if message:
            logger.debug(f"Progress {self._channel_id}: {message} ({percent}%)")

    def update(
        self,
        stage: MigrationStage | str,
        percent: int,
        message: str = "",
        object_name: Optional[str] = None,
        level: str = "info",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Direct progress update.

        Args:
            stage: Stage enum or stage string.
            percent: Progress percentage.
            message: Optional message.
            object_name: Optional current object/file name.
            level: info, warning, error.
            details: Optional extra metadata.
        """

        percent = max(0, min(100, int(percent)))

        stage_value = stage.value if hasattr(stage, "value") else str(stage)

        self._persist_progress(
            percent=percent,
            stage=stage_value,
            message=message,
            object_name=object_name,
            level=level,
            details=details,
        )

        self._broadcast_progress(
            percent=percent,
            stage=stage_value,
            message=message,
            object_name=object_name,
            details=details,
        )

        if message:
            logger.info(f"Progress {self._channel_id}: {message} ({percent}%)")

    # ============================================================
    # Completion / Error
    # ============================================================

    def complete(
        self,
        message: str = "ThoughtSpot to Power BI migration completed successfully",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark progress as completed and broadcast completion.
        """

        self.update(
            stage=MigrationStage.COMPLETED,
            percent=100,
            message=message,
            level="info",
            details=details,
        )

        self._broadcast_completed(details or {})

    def fail(
        self,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark progress as failed and broadcast error.
        """

        self.update(
            stage=MigrationStage.FAILED,
            percent=100,
            message=error_message,
            level="error",
            details=details,
        )

        self._broadcast_error(error_message, details)

    # ============================================================
    # Internal Calculations
    # ============================================================

    def _calculate_base_percent(
        self,
        stage: MigrationStage,
    ) -> int:
        """
        Calculate base percentage at the start of a stage.
        """

        total_before = 0

        for current_stage in MigrationStage:
            if current_stage == stage:
                break

            total_before += current_stage.weight

        return min(100, total_before)

    def _calculate_percent(self) -> int:
        """
        Calculate current percentage inside current stage.
        """

        if self.total_items <= 0 or not self.current_stage:
            return self.base_percent

        stage_progress = (
            self.current_items / self.total_items
        ) * self.current_stage.weight

        return min(100, int(self.base_percent + stage_progress))

    # ============================================================
    # Persistence
    # ============================================================

    def _persist_progress(
        self,
        percent: int,
        stage: str,
        message: str = "",
        object_name: Optional[str] = None,
        level: str = "info",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Persist progress to job and/or migration tables.
        """

        if self.job_id:
            try:
                self.job_store.update_progress(
                    job_id=self.job_id,
                    percent=percent,
                    stage=stage,
                    message=message,
                    current_object_name=object_name,
                    level=level,
                    details=self._details_to_string(details),
                )

            except Exception as e:
                logger.error(
                    f"Failed to update job progress for {self.job_id}: {e}",
                    exc_info=True,
                )

        if self.migration_id:
            try:
                self.migration_store.update_migration_progress(
                    migration_id=self.migration_id,
                    progress_percent=percent,
                    current_stage=stage,
                    message=message,
                    level=level,
                    object_name=object_name,
                    details=details,
                )

            except Exception as e:
                logger.error(
                    f"Failed to update migration progress for "
                    f"{self.migration_id}: {e}",
                    exc_info=True,
                )

    # ============================================================
    # WebSocket Broadcasting
    # ============================================================

    @property
    def _channel_id(self) -> str:
        """
        WebSocket channel ID.

        Job websocket uses job_id.
        Migration websocket uses migration_id.
        """

        return self.job_id or self.migration_id

    def _broadcast_progress(
        self,
        percent: int,
        stage: str,
        message: str = "",
        object_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast progress update via WebSocket.
        """

        payload = {
            "progress_percent": percent,
            "current_stage": stage,
            "message": message,
            "current_object_name": object_name,
            "details": details or {},
        }

        self._run_async(
            ws_manager.broadcast_progress(
                job_id=self._channel_id,
                percent=percent,
                stage=stage,
                message=message,
                extra_data=payload,
            )
        )

    def _broadcast_completed(
        self,
        details: Dict[str, Any],
    ) -> None:
        """
        Broadcast completion event.
        """

        if hasattr(ws_manager, "broadcast_completed"):
            self._run_async(
                ws_manager.broadcast_completed(
                    job_id=self._channel_id,
                    data=details,
                )
            )
        elif hasattr(ws_manager, "broadcast_to_job"):
            self._run_async(
                ws_manager.broadcast_to_job(
                    self._channel_id,
                    {
                        "type": "completed",
                        "job_id": self._channel_id,
                        "data": details,
                    },
                )
            )

    def _broadcast_error(
        self,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast error event.
        """

        if hasattr(ws_manager, "broadcast_error"):
            self._run_async(
                ws_manager.broadcast_error(
                    job_id=self._channel_id,
                    error_message=error_message,
                    extra_data=details or {},
                )
            )
        elif hasattr(ws_manager, "broadcast_to_job"):
            self._run_async(
                ws_manager.broadcast_to_job(
                    self._channel_id,
                    {
                        "type": "error",
                        "job_id": self._channel_id,
                        "data": {
                            "error": error_message,
                            "details": details or {},
                        },
                    },
                )
            )

    @staticmethod
    def _run_async(coro) -> None:
        """
        Sync wrapper for async websocket calls.
        """

        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)

        except Exception as e:
            logger.error(f"Failed to broadcast progress: {e}", exc_info=True)

    @staticmethod
    def _details_to_string(
        details: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Convert details dict to JSON string for job_progress table.
        """

        if details is None:
            return None

        try:
            import json
            return json.dumps(details)

        except Exception:
            return str(details)


# Backward-compatible alias
ProgressManager = DatabaseProgressCallback