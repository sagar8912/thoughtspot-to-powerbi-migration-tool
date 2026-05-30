"""
Job management API endpoints for ThoughtSpot -> Power BI Migration Tool.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from loguru import logger

from api.config import config
from api.utils import generate_job_id, generate_preview_id

from api.models.api_models import (
    JobStatus,
    JobCreateResponse,
    JobStatusResponse,
    JobResultResponse,
    JobListResponse,
    JobListItem,
    JobDeleteResponse,
    PreviewDeleteResponse,
)

from api.models.migration_models import (
    MigrationStatus,
    ThoughtSpotObjectType,
)

from storage.job_store import JobStore
from storage.file_store import FileStore
from storage.result_store import ResultStore
from storage.preview_store import PreviewStore

# Worker for ThoughtSpot -> Power BI migration
# You need to create this file later:
# workers/migration_worker.py
from workers.migration_worker import execute_thoughtspot_powerbi_migration


router = APIRouter()

job_store = JobStore()
file_store = FileStore()
result_store = ResultStore()
preview_store = PreviewStore()


# ============================================================
# Helper Functions
# ============================================================

def validate_uploaded_files(files: List[UploadFile]) -> None:
    """
    Validate uploaded ThoughtSpot files.
    """

    if len(files) < 1:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILE_COUNT",
                    "message": "At least 1 ThoughtSpot file is required",
                    "details": {"min_files": 1},
                }
            },
        )

    if len(files) > config.MAX_FILES_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "TOO_MANY_FILES",
                    "message": f"Maximum {config.MAX_FILES_PER_JOB} files allowed",
                    "details": {
                        "max_files": config.MAX_FILES_PER_JOB,
                        "provided": len(files),
                    },
                }
            },
        )


def validate_file_extension(filename: str) -> None:
    """
    Validate file extension for ThoughtSpot migration.
    """

    if not filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILENAME",
                    "message": "Uploaded file must have a valid filename",
                }
            },
        )

    allowed = tuple(config.ALLOWED_EXTENSIONS)

    if not filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": "Unsupported file type for ThoughtSpot migration",
                    "details": {
                        "filename": filename,
                        "allowed_extensions": config.ALLOWED_EXTENSIONS,
                    },
                }
            },
        )


# ============================================================
# Create Migration Job
# ============================================================

@router.post("/", response_model=JobCreateResponse, status_code=201)
async def create_job(
    files: List[UploadFile] = File(
        ...,
        description="ThoughtSpot export files: .tml, .yaml, .yml, .json, .zip, .csv, .xlsx",
    ),
    background_tasks: BackgroundTasks = None,
):
    """
    Create a new ThoughtSpot -> Power BI migration job.

    Upload ThoughtSpot metadata/TML/export files.
    The migration will run in the background.
    """

    try:
        validate_uploaded_files(files)

        job_id = generate_job_id()

        # Create job first because uploaded files may depend on job_id
        job = job_store.create_job(
            job_id=job_id,
            file_count=len(files),
        )

        file_paths = []

        for file in files:
            content = await file.read()
            file_size = len(content)

            validate_file_extension(file.filename)

            is_valid, error_msg = file_store.validate_file(
                file.filename,
                file_size,
            )

            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "INVALID_FILE",
                            "message": error_msg,
                            "details": {"filename": file.filename},
                        }
                    },
                )

            uploaded_file = file_store.save_uploaded_file(
                job_id=job_id,
                original_filename=file.filename,
                file_content=content,
            )

            file_paths.append(uploaded_file.file_path)

        if background_tasks is None:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "BACKGROUND_TASK_NOT_AVAILABLE",
                        "message": "Background task system is not available",
                    }
                },
            )

        background_tasks.add_task(
            execute_thoughtspot_powerbi_migration,
            job_id=job_id,
            file_paths=file_paths,
        )

        logger.info(
            f"Created ThoughtSpot -> Power BI migration job {job_id} with {len(files)} files"
        )

        return JobCreateResponse(
            job_id=job.job_id,
            status=job.status,
            created_at=job.created_at,
            file_count=job.file_count,
            message="ThoughtSpot to Power BI migration job created successfully",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to create migration job: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MIGRATION_JOB_CREATION_FAILED",
                    "message": "Failed to create ThoughtSpot to Power BI migration job",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Get Job Status
# ============================================================

@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get migration job status and progress.
    """

    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Migration job {job_id} not found",
                    "details": {"job_id": job_id},
                }
            },
        )

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        file_count=job.file_count,
        relationships_found=getattr(job, "relationship_count", None),
        error=job.error_message,
    )


# ============================================================
# Get Job Result
# ============================================================

@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(job_id: str):
    """
    Get ThoughtSpot -> Power BI migration result.

    Returns generated metadata, DAX conversion output,
    relationships, and Power BI output information.
    """

    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Migration job {job_id} not found",
                    "details": {"job_id": job_id},
                }
            },
        )

    if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job.job_id,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "current_stage": job.current_stage,
                "message": "Migration job is still processing",
            },
        )

    if job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MIGRATION_JOB_FAILED",
                    "message": "ThoughtSpot to Power BI migration failed",
                    "details": {
                        "job_id": job_id,
                        "error": job.error_message,
                    },
                }
            },
        )

    result = result_store.get_result(job_id)

    if not result:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RESULT_NOT_FOUND",
                    "message": "Migration completed but result was not found",
                    "details": {"job_id": job_id},
                }
            },
        )

    return JobResultResponse(
        job_id=job.job_id,
        status=job.status,
        result=result,
        completed_at=job.completed_at,
        message=None,
    )


# ============================================================
# List Jobs
# ============================================================

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    List ThoughtSpot -> Power BI migration jobs.
    """

    try:
        jobs, total = job_store.list_jobs(
            limit=limit,
            offset=offset,
            status=status,
        )

        job_items = [
            JobListItem(
                job_id=job.job_id,
                status=job.status,
                created_at=job.created_at,
                completed_at=job.completed_at,
                file_count=job.file_count,
                relationships_found=getattr(job, "relationship_count", None),
                progress_percent=job.progress_percent,
            )
            for job in jobs
        ]

        return JobListResponse(
            total=total,
            limit=limit,
            offset=offset,
            jobs=job_items,
        )

    except Exception as e:
        logger.error(f"Failed to list migration jobs: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LIST_MIGRATION_JOBS_FAILED",
                    "message": "Failed to list migration jobs",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Delete Job
# ============================================================

@router.delete("/{job_id}", response_model=JobDeleteResponse)
async def delete_job(job_id: str):
    """
    Delete a migration job and its related uploaded/result files.
    """

    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Migration job {job_id} not found",
                    "details": {"job_id": job_id},
                }
            },
        )

    try:
        files_deleted = 0

        if config.DELETE_FILES_ON_JOB_DELETE:
            files_deleted = file_store.delete_job_files(job_id)
            result_store.delete_result(job_id)

        job_store.delete_job(job_id)

        logger.info(f"Deleted migration job {job_id}")

        return JobDeleteResponse(
            message=f"Migration job {job_id} deleted successfully",
            job_id=job_id,
            files_deleted=files_deleted,
        )

    except Exception as e:
        logger.error(f"Failed to delete migration job {job_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "DELETE_MIGRATION_JOB_FAILED",
                    "message": "Failed to delete migration job",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Preview Upload
# ============================================================

@router.post("/preview", status_code=201)
async def create_preview(
    files: List[UploadFile] = File(
        ...,
        description="ThoughtSpot files to preview before migration",
    ),
):
    """
    Upload ThoughtSpot files for preview.

    This endpoint only saves files and returns basic file metadata.
    Actual parsing can be handled later in migration service/worker.
    """

    try:
        validate_uploaded_files(files)

        preview_id = generate_preview_id()
        saved_files = []

        preview_store.create_preview_session(
            preview_id=preview_id,
            file_count=len(files),
            total_duplicates_detected=0,
        )

        for file in files:
            content = await file.read()
            file_size = len(content)

            validate_file_extension(file.filename)

            is_valid, error_msg = file_store.validate_file(
                file.filename,
                file_size,
            )

            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "INVALID_FILE",
                            "message": error_msg,
                            "details": {"filename": file.filename},
                        }
                    },
                )

            preview_file = preview_store.save_preview_file(
                preview_id=preview_id,
                original_filename=file.filename,
                file_content=content,
                df=None,
                metadata={
                    "source": "thoughtspot",
                    "migration_target": "powerbi",
                    "file_size": file_size,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
            )

            saved_files.append(
                {
                    "file_id": preview_file.file_id,
                    "original_filename": preview_file.original_filename,
                    "file_size": file_size,
                }
            )

        logger.info(f"Created ThoughtSpot migration preview {preview_id}")

        return {
            "preview_id": preview_id,
            "status": "preview_ready",
            "created_at": datetime.utcnow().isoformat(),
            "file_count": len(saved_files),
            "files": saved_files,
            "message": "Preview created successfully. You can now confirm and start migration.",
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to create migration preview: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MIGRATION_PREVIEW_CREATION_FAILED",
                    "message": "Failed to create migration preview",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Cancel Preview
# ============================================================

@router.delete("/preview/{preview_id}", response_model=PreviewDeleteResponse)
async def cancel_preview(preview_id: str):
    """
    Cancel preview and delete uploaded preview files.
    """

    try:
        session = preview_store.get_preview_session(preview_id)

        if not session:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "PREVIEW_NOT_FOUND",
                        "message": f"Preview {preview_id} not found",
                        "details": {"preview_id": preview_id},
                    }
                },
            )

        files_deleted = preview_store.delete_preview(preview_id)

        logger.info(f"Cancelled migration preview {preview_id}")

        return PreviewDeleteResponse(
            message=f"Preview {preview_id} cancelled and files deleted",
            preview_id=preview_id,
            files_deleted=files_deleted,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to cancel preview {preview_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "PREVIEW_DELETE_FAILED",
                    "message": "Failed to cancel preview",
                    "details": str(e),
                }
            },
        )