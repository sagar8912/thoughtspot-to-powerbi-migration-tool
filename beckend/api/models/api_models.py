"""
API request/response models for ThoughtSpot -> Power BI Migration Tool.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ============================================================
# Common Enums
# ============================================================

class JobStatus(str, Enum):
    """
    Job status values used by API jobs table.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApiResponseStatus(str, Enum):
    """
    Generic API response status.
    """

    SUCCESS = "success"
    ERROR = "error"


# ============================================================
# Error Models
# ============================================================

class ErrorDetail(BaseModel):
    """
    API error detail.
    """

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(None, description="Optional error details")


class ErrorResponse(BaseModel):
    """
    Standard API error response.
    """

    error: ErrorDetail


# ============================================================
# Uploaded File Models
# ============================================================

class UploadedFileInfo(BaseModel):
    """
    Uploaded ThoughtSpot file information.
    """

    file_id: str
    original_filename: str
    stored_filename: Optional[str] = None
    file_size: int
    file_type: Optional[str] = None
    thoughtspot_object_type: Optional[str] = None
    thoughtspot_object_name: Optional[str] = None
    thoughtspot_object_guid: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class FileUploadResponse(BaseModel):
    """
    Response returned after uploading a file.
    """

    file_id: str
    job_id: str
    original_filename: str
    stored_filename: Optional[str] = None
    file_size: int
    file_type: Optional[str] = None
    thoughtspot_object_type: Optional[str] = None
    thoughtspot_object_name: Optional[str] = None
    thoughtspot_object_guid: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    message: str = "File uploaded successfully"


# ============================================================
# Job Create / Status / Result Models
# ============================================================

class JobCreateResponse(BaseModel):
    """
    Response returned after creating a migration job.
    """

    job_id: str = Field(..., description="Created job ID")
    status: JobStatus = Field(..., description="Initial job status")
    message: str = Field(..., description="Response message")
    file_count: int = Field(0, description="Number of uploaded files")
    files: List[UploadedFileInfo] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_20260529203000_abc12345",
                "status": "pending",
                "message": "Job created successfully",
                "file_count": 2,
                "files": [],
                "created_at": "2026-05-29T20:30:00",
            }
        }


class JobStatusResponse(BaseModel):
    """
    Response for job status endpoint.
    """

    job_id: str
    status: JobStatus

    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    progress_percent: int = 0
    current_stage: Optional[str] = None
    current_object_name: Optional[str] = None
    error_message: Optional[str] = None

    file_count: int = 0
    total_objects: int = 0
    objects_completed: int = 0
    objects_failed: int = 0
    objects_skipped: int = 0

    formulas_converted: int = 0
    relationships_created: int = 0
    relationship_count: Optional[int] = None

    powerbi_workspace_id: Optional[str] = None
    powerbi_dataset_id: Optional[str] = None
    powerbi_report_id: Optional[str] = None
    powerbi_report_url: Optional[str] = None

    result_file_path: Optional[str] = None
    pbix_file_path: Optional[str] = None
    report_json_path: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_20260529203000_abc12345",
                "status": "running",
                "created_at": "2026-05-29T20:30:00",
                "started_at": "2026-05-29T20:30:05",
                "completed_at": None,
                "progress_percent": 45,
                "current_stage": "metadata_discovered",
                "file_count": 2,
                "total_objects": 5,
                "formulas_converted": 3,
                "relationships_created": 2,
            }
        }


class JobResultResponse(BaseModel):
    """
    Response for job result endpoint.
    """

    job_id: str
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    result_file_path: Optional[str] = None
    message: Optional[str] = None


class JobDeleteResponse(BaseModel):
    """
    Response after deleting a job.
    """

    job_id: str
    deleted: bool
    message: str


# ============================================================
# Job List Models
# ============================================================

class JobListItem(BaseModel):
    """
    Single job item in job list response.
    """

    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime] = None

    file_count: int = 0
    total_objects: int = 0

    relationships_found: Optional[int] = None
    relationships_created: Optional[int] = None
    relationship_count: Optional[int] = None

    formulas_converted: Optional[int] = None
    progress_percent: int = 0
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    """
    Response for job list query.
    """

    total: int = Field(..., description="Total number of jobs")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Offset for pagination")
    jobs: List[JobListItem] = Field(default_factory=list)


# ============================================================
# Progress Models
# ============================================================

class ProgressLogItem(BaseModel):
    """
    Job progress log item.
    """

    timestamp: Optional[datetime] = None
    stage: Optional[str] = None
    message: Optional[str] = None
    percent: int = 0
    level: str = "info"
    object_name: Optional[str] = None
    details: Optional[Any] = None


class JobProgressResponse(BaseModel):
    """
    Job progress log response.
    """

    job_id: str
    logs: List[ProgressLogItem] = Field(default_factory=list)


# ============================================================
# Preview Models
# ============================================================

class PreviewFileInfo(BaseModel):
    """
    Preview file information.
    """

    file_id: str
    preview_id: Optional[str] = None
    original_filename: str
    file_path: Optional[str] = None
    row_count: Optional[int] = 0
    column_count: Optional[int] = 0
    metadata: Optional[Dict[str, Any]] = None


class PreviewCreateResponse(BaseModel):
    """
    Preview creation response.
    """

    preview_id: str
    status: str
    created_at: Optional[datetime] = None
    file_count: int = 0
    total_duplicates_detected: int = 0
    files: List[PreviewFileInfo] = Field(default_factory=list)
    message: Optional[str] = None


class PreviewConfirmRequest(BaseModel):
    """
    Request to confirm preview and start job.
    """

    preview_id: str


class PreviewConfirmResponse(BaseModel):
    """
    Response after confirming preview and creating job.
    """

    preview_id: str
    job_id: str
    status: JobStatus = JobStatus.PENDING
    message: str = "Preview confirmed and job created"


class PreviewCancelResponse(BaseModel):
    """
    Preview cancel response.
    """

    preview_id: str
    cancelled: bool
    message: str


class PreviewDeleteResponse(BaseModel):
    """
    Response after deleting/cancelling a preview session.
    """

    preview_id: str
    deleted: bool
    message: str


class PreviewSummaryResponse(BaseModel):
    """
    Preview summary response.
    """

    preview_id: str
    status: str
    created_at: Optional[datetime] = None
    file_count: int = 0
    total_duplicates_detected: int = 0
    files: List[PreviewFileInfo] = Field(default_factory=list)


# ============================================================
# ThoughtSpot Metadata Models
# ============================================================

class ThoughtSpotObjectPreview(BaseModel):
    """
    ThoughtSpot object preview response model.
    """

    object_name: str
    object_type: str
    filename: Optional[str] = None
    object_guid: Optional[str] = None
    column_count: int = 0
    formula_count: int = 0
    relationship_count: int = 0
    visual_count: int = 0


class FormulaPreview(BaseModel):
    """
    ThoughtSpot formula preview response model.
    """

    formula_name: str
    formula_expression: str
    formula_type: Optional[str] = "formula"
    dax_formula: Optional[str] = None
    confidence_score: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)


class RelationshipPreview(BaseModel):
    """
    ThoughtSpot relationship preview response model.
    """

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    join_type: Optional[str] = None
    powerbi_cardinality: Optional[str] = None


# ============================================================
# Migration API Common Models
# ============================================================

class MigrationStartRequest(BaseModel):
    """
    Request to start migration from uploaded files.
    """

    job_id: Optional[str] = None
    file_ids: Optional[List[str]] = None
    workspace_id: Optional[str] = None
    publish_to_powerbi: bool = False


class MigrationStartResponse(BaseModel):
    """
    Migration start response.
    """

    migration_id: str
    job_id: Optional[str] = None
    status: str
    message: str


class MigrationStatusResponse(BaseModel):
    """
    Migration status response.
    """

    migration_id: str
    job_id: Optional[str] = None
    status: str
    progress_percent: int = 0
    current_stage: Optional[str] = None
    error_message: Optional[str] = None

    object_count: int = 0
    formula_count: int = 0
    relationship_count: int = 0
    report_count: int = 0
    dashboard_count: int = 0

    powerbi_workspace_id: Optional[str] = None
    powerbi_dataset_id: Optional[str] = None
    powerbi_report_id: Optional[str] = None
    powerbi_report_url: Optional[str] = None

    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================
# Health / Root Models
# ============================================================

class HealthResponse(BaseModel):
    """
    Health check response.
    """

    status: str = "healthy"
    service: str = "thoughtspot-powerbi-migration-api"
    version: str = "1.0.0"


class RootResponse(BaseModel):
    """
    Root endpoint response.
    """

    message: str
    version: str
    docs: str = "/docs"
    health: str = "/health"


# ============================================================
# Generic Success Response
# ============================================================

class SuccessResponse(BaseModel):
    """
    Generic success response.
    """

    status: ApiResponseStatus = ApiResponseStatus.SUCCESS
    message: str
    data: Optional[Dict[str, Any]] = None