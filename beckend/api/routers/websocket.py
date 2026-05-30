"""
WebSocket endpoints for real-time ThoughtSpot -> Power BI migration progress updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from workers.websocket_manager import ws_manager
from storage.job_store import JobStore
from storage.migration_store import MigrationStore


router = APIRouter()

job_store = JobStore()
migration_store = MigrationStore()


@router.websocket("/jobs/{job_id}/ws")
async def job_websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job progress updates.

    Frontend URL:
        ws://localhost:8000/api/v1/jobs/{job_id}/ws

    Message format:
    {
        "type": "connected" | "progress" | "completed" | "error" | "pong",
        "job_id": "job_20260529203000_abcd1234",
        "data": {
            "status": "running",
            "progress_percent": 45,
            "current_stage": "parsing_thoughtspot"
        }
    }
    """

    job = job_store.get_job(job_id)

    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    await ws_manager.connect(websocket, job_id)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "job_id": job_id,
                "data": {
                    "status": job.status.value if hasattr(job.status, "value") else job.status,
                    "progress_percent": job.progress_percent,
                    "current_stage": job.current_stage,
                    "current_object_name": getattr(job, "current_object_name", None),
                    "message": "Connected to ThoughtSpot to Power BI migration job updates",
                },
            }
        )

        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "job_id": job_id,
                            "data": {
                                "message": "Connection alive"
                            },
                        }
                    )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected normally for job {job_id}")
                break

            except Exception as e:
                logger.error(f"WebSocket error for job {job_id}: {e}", exc_info=True)
                break

    finally:
        ws_manager.disconnect(websocket, job_id)


@router.websocket("/migration/{migration_id}/ws")
async def migration_websocket_endpoint(websocket: WebSocket, migration_id: str):
    """
    WebSocket endpoint for real-time migration progress updates.

    Frontend URL:
        ws://localhost:8000/api/v1/migration/{migration_id}/ws

    Message format:
    {
        "type": "connected" | "progress" | "completed" | "error" | "pong",
        "migration_id": "migration_20260529203000_abcd1234",
        "data": {
            "status": "converting",
            "progress_percent": 60,
            "current_stage": "generating_dax"
        }
    }
    """

    migration = migration_store.get_migration(migration_id)

    if not migration:
        await websocket.close(code=4004, reason="Migration not found")
        return

    await ws_manager.connect(websocket, migration_id)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "migration_id": migration_id,
                "data": {
                    "status": migration.status.value if hasattr(migration.status, "value") else migration.status,
                    "progress_percent": migration.progress_percent,
                    "current_stage": migration.current_stage,
                    "object_count": getattr(migration, "object_count", 0),
                    "formula_count": getattr(migration, "formula_count", 0),
                    "relationship_count": getattr(migration, "relationship_count", 0),
                    "message": "Connected to ThoughtSpot to Power BI migration updates",
                },
            }
        )

        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "migration_id": migration_id,
                            "data": {
                                "message": "Connection alive"
                            },
                        }
                    )

            except WebSocketDisconnect:
                logger.info(
                    f"WebSocket disconnected normally for migration {migration_id}"
                )
                break

            except Exception as e:
                logger.error(
                    f"WebSocket error for migration {migration_id}: {e}",
                    exc_info=True,
                )
                break

    finally:
        ws_manager.disconnect(websocket, migration_id)