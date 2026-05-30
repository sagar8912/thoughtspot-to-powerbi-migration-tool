"""
WebSocket manager for real-time ThoughtSpot -> Power BI migration progress updates.

This manager supports:
- Job WebSocket channels
- Migration WebSocket channels
- Progress events
- Completed events
- Error events
- Generic broadcast messages
"""

from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
from loguru import logger
from datetime import datetime


class WebSocketManager:
    """
    Manages WebSocket connections for real-time progress updates.

    active_connections format:
        {
            "job_20260529203000_abcd1234": {websocket1, websocket2},
            "migration_20260529203000_abcd1234": {websocket3}
        }
    """

    def __init__(self):
        """
        Initialize WebSocket manager.
        """

        self.active_connections: Dict[str, Set[WebSocket]] = {}

    # ============================================================
    # Connection Management
    # ============================================================

    async def connect(
        self,
        websocket: WebSocket,
        job_id: str,
    ) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket connection.
            job_id: Job ID or migration ID used as WebSocket channel.
        """

        await websocket.accept()

        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()

        self.active_connections[job_id].add(websocket)

        logger.info(
            f"WebSocket connected for channel {job_id}. "
            f"Total connections: {len(self.active_connections[job_id])}"
        )

    def disconnect(
        self,
        websocket: WebSocket,
        job_id: str,
    ) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: FastAPI WebSocket connection.
            job_id: Job ID or migration ID used as WebSocket channel.
        """

        if job_id not in self.active_connections:
            return

        self.active_connections[job_id].discard(websocket)

        if not self.active_connections[job_id]:
            del self.active_connections[job_id]

        logger.info(f"WebSocket disconnected for channel {job_id}")

    def disconnect_all(
        self,
        job_id: str,
    ) -> None:
        """
        Remove all WebSocket connections for one channel.

        Args:
            job_id: Job ID or migration ID.
        """

        if job_id in self.active_connections:
            del self.active_connections[job_id]
            logger.info(f"Disconnected all WebSockets for channel {job_id}")

    # ============================================================
    # Send / Broadcast
    # ============================================================

    async def send_message(
        self,
        websocket: WebSocket,
        message: dict,
    ) -> None:
        """
        Send message to a specific WebSocket.

        Args:
            websocket: FastAPI WebSocket.
            message: JSON-serializable message.
        """

        try:
            await websocket.send_json(message)

        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}", exc_info=True)

    async def broadcast_to_job(
        self,
        job_id: str,
        message: dict,
    ) -> None:
        """
        Broadcast message to all connections for a specific job/migration channel.

        Args:
            job_id: Job ID or migration ID.
            message: JSON-serializable message.
        """

        if job_id not in self.active_connections:
            logger.debug(f"No active WebSocket connections for channel {job_id}")
            return

        message.setdefault("timestamp", datetime.utcnow().isoformat())

        disconnected = set()

        for websocket in list(self.active_connections.get(job_id, set())):
            try:
                await websocket.send_json(message)

            except Exception as e:
                logger.error(
                    f"Failed to send WebSocket message for channel {job_id}: {e}",
                    exc_info=True,
                )
                disconnected.add(websocket)

        for websocket in disconnected:
            self.disconnect(websocket, job_id)

    # Alias for generic channel broadcast
    async def broadcast_to_channel(
        self,
        channel_id: str,
        message: dict,
    ) -> None:
        """
        Broadcast message to a generic channel.

        Args:
            channel_id: Job ID or migration ID.
            message: JSON-serializable message.
        """

        await self.broadcast_to_job(channel_id, message)

    # ============================================================
    # Progress Broadcasts
    # ============================================================

    async def broadcast_progress(
        self,
        job_id: str,
        percent: Optional[int] = None,
        stage: Optional[str] = None,
        message: str = "",
        extra_data: Optional[dict] = None,
        progress_percent: Optional[int] = None,
        current_stage: Optional[str] = None,
    ) -> None:
        """
        Broadcast progress update.

        Supports both old and new call styles:

        Old:
            broadcast_progress(job_id, progress_percent, current_stage, message)

        New:
            broadcast_progress(job_id, percent=50, stage="converting", message="...")
        """

        final_percent = progress_percent if progress_percent is not None else percent
        final_stage = current_stage if current_stage is not None else stage

        if final_percent is None:
            final_percent = 0

        if final_stage is None:
            final_stage = "processing"

        data = {
            "progress_percent": final_percent,
            "current_stage": final_stage,
            "message": message,
        }

        if extra_data:
            data.update(extra_data)

        event_type = "progress"

        await self.broadcast_to_job(
            job_id,
            {
                "type": event_type,
                "job_id": job_id,
                "migration_id": job_id if str(job_id).startswith("migration_") else None,
                "data": data,
            },
        )

    async def broadcast_completed(
        self,
        job_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast completion event.

        Args:
            job_id: Job ID or migration ID.
            data: Optional completion data.
        """

        payload = {
            "status": "completed",
            "message": "ThoughtSpot to Power BI migration completed successfully",
        }

        if data:
            payload.update(data)

        await self.broadcast_to_job(
            job_id,
            {
                "type": "completed",
                "job_id": job_id,
                "migration_id": job_id if str(job_id).startswith("migration_") else None,
                "data": payload,
            },
        )

    async def broadcast_completion(
        self,
        job_id: str,
        relationship_count: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Backward-compatible completion method.

        Old code may call:
            broadcast_completion(job_id, relationship_count)

        New code can call:
            broadcast_completed(job_id, data)
        """

        payload = {
            "status": "completed",
            "relationship_count": relationship_count,
            "message": "ThoughtSpot to Power BI migration completed successfully",
        }

        if data:
            payload.update(data)

        await self.broadcast_completed(job_id, payload)

    async def broadcast_error(
        self,
        job_id: str,
        error_message: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast error event.

        Args:
            job_id: Job ID or migration ID.
            error_message: Error message.
            extra_data: Optional additional data.
        """

        payload = {
            "status": "failed",
            "error": error_message,
            "message": error_message,
        }

        if extra_data:
            payload.update(extra_data)

        await self.broadcast_to_job(
            job_id,
            {
                "type": "error",
                "job_id": job_id,
                "migration_id": job_id if str(job_id).startswith("migration_") else None,
                "data": payload,
            },
        )

    async def broadcast_warning(
        self,
        job_id: str,
        warning_message: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast warning event.

        Args:
            job_id: Job ID or migration ID.
            warning_message: Warning message.
            extra_data: Optional additional data.
        """

        payload = {
            "status": "warning",
            "warning": warning_message,
            "message": warning_message,
        }

        if extra_data:
            payload.update(extra_data)

        await self.broadcast_to_job(
            job_id,
            {
                "type": "warning",
                "job_id": job_id,
                "migration_id": job_id if str(job_id).startswith("migration_") else None,
                "data": payload,
            },
        )

    async def broadcast_log(
        self,
        job_id: str,
        level: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast log event.

        Args:
            job_id: Job ID or migration ID.
            level: info, warning, error, debug.
            message: Log message.
            extra_data: Optional additional data.
        """

        payload = {
            "level": level,
            "message": message,
        }

        if extra_data:
            payload.update(extra_data)

        await self.broadcast_to_job(
            job_id,
            {
                "type": "log",
                "job_id": job_id,
                "migration_id": job_id if str(job_id).startswith("migration_") else None,
                "data": payload,
            },
        )

    # ============================================================
    # Status / Utility
    # ============================================================

    def get_connection_count(
        self,
        job_id: str,
    ) -> int:
        """
        Get number of active connections for a job/migration channel.

        Args:
            job_id: Job ID or migration ID.

        Returns:
            Number of active WebSocket connections.
        """

        return len(self.active_connections.get(job_id, set()))

    def get_total_connection_count(self) -> int:
        """
        Get total number of active WebSocket connections.

        Returns:
            Total active WebSocket connections.
        """

        return sum(len(connections) for connections in self.active_connections.values())

    def get_active_channels(self) -> list:
        """
        Get all active WebSocket channel IDs.

        Returns:
            List of channel IDs.
        """

        return list(self.active_connections.keys())

    def has_connections(
        self,
        job_id: str,
    ) -> bool:
        """
        Check whether a channel has active WebSocket connections.

        Args:
            job_id: Job ID or migration ID.

        Returns:
            True if channel has active WebSocket connections.
        """

        return self.get_connection_count(job_id) > 0


# Global WebSocket manager instance
ws_manager = WebSocketManager()