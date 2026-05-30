"""
Domain models for ThoughtSpot -> Power BI migration job management.

These models are used internally by the backend/database layer.
They are different from Pydantic API schemas.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from api.models.api_models import JobStatus
from api.models.migration_models import MigrationStage


@dataclass
class MigrationJob:
    """
    Domain model for a ThoughtSpot -> Power BI migration job.
    """

    job_id: str
    status: JobStatus
    created_at: datetime

    total_objects: int = 0
    progress_percent: int = 0

    current_stage: Optional[MigrationStage] = None
    current_object_name: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    error_message: Optional[str] = None

    objects_completed: int = 0
    objects_failed: int = 0
    objects_skipped: int = 0

    formulas_converted: int = 0
    relationships_created: int = 0

    powerbi_workspace_id: Optional[str] = None
    powerbi_dataset_id: Optional[str] = None
    powerbi_report_id: Optional[str] = None
    powerbi_report_url: Optional[str] = None

    result_file_path: Optional[str] = None
    pbix_file_path: Optional[str] = None
    report_json_path: Optional[str] = None

    @classmethod
    def from_db_row(cls, row: tuple) -> Optional["MigrationJob"]:
        """
        Create MigrationJob from database row.

        Expected database column order:

        0  job_id
        1  status
        2  created_at
        3  started_at
        4  completed_at
        5  progress_percent
        6  current_stage
        7  current_object_name
        8  error_message
        9  total_objects
        10 objects_completed
        11 objects_failed
        12 objects_skipped
        13 formulas_converted
        14 relationships_created
        15 powerbi_workspace_id
        16 powerbi_dataset_id
        17 powerbi_report_id
        18 powerbi_report_url
        19 result_file_path
        20 pbix_file_path
        21 report_json_path
        """

        if row is None:
            return None

        return cls(
            job_id=row[0],
            status=JobStatus(row[1]),
            created_at=datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
            started_at=datetime.fromisoformat(row[3]) if row[3] and isinstance(row[3], str) else row[3],
            completed_at=datetime.fromisoformat(row[4]) if row[4] and isinstance(row[4], str) else row[4],
            progress_percent=row[5] or 0,
            current_stage=MigrationStage(row[6]) if row[6] else None,
            current_object_name=row[7],
            error_message=row[8],
            total_objects=row[9] or 0,
            objects_completed=row[10] or 0,
            objects_failed=row[11] or 0,
            objects_skipped=row[12] or 0,
            formulas_converted=row[13] or 0,
            relationships_created=row[14] or 0,
            powerbi_workspace_id=row[15],
            powerbi_dataset_id=row[16],
            powerbi_report_id=row[17],
            powerbi_report_url=row[18],
            result_file_path=row[19],
            pbix_file_path=row[20],
            report_json_path=row[21],
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert migration job to dictionary.
        """

        return {
            "job_id": self.job_id,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_percent": self.progress_percent,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "current_object_name": self.current_object_name,
            "error_message": self.error_message,
            "total_objects": self.total_objects,
            "objects_completed": self.objects_completed,
            "objects_failed": self.objects_failed,
            "objects_skipped": self.objects_skipped,
            "formulas_converted": self.formulas_converted,
            "relationships_created": self.relationships_created,
            "powerbi_workspace_id": self.powerbi_workspace_id,
            "powerbi_dataset_id": self.powerbi_dataset_id,
            "powerbi_report_id": self.powerbi_report_id,
            "powerbi_report_url": self.powerbi_report_url,
            "result_file_path": self.result_file_path,
            "pbix_file_path": self.pbix_file_path,
            "report_json_path": self.report_json_path,
        }


@dataclass
class ThoughtSpotUploadedFile:
    """
    Domain model for uploaded ThoughtSpot files.

    This can store uploaded TML, JSON, CSV, Excel, or ZIP files.
    """

    file_id: str
    job_id: str
    original_filename: str
    stored_filename: str
    file_path: str
    file_size: int

    file_type: Optional[str] = None
    thoughtspot_object_type: Optional[str] = None
    thoughtspot_object_name: Optional[str] = None
    thoughtspot_object_guid: Optional[str] = None

    parsed_successfully: bool = False
    parse_error: Optional[str] = None

    uploaded_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: tuple) -> Optional["ThoughtSpotUploadedFile"]:
        """
        Create ThoughtSpotUploadedFile from database row.

        Expected database column order:

        0  file_id
        1  job_id
        2  original_filename
        3  stored_filename
        4  file_path
        5  file_size
        6  file_type
        7  thoughtspot_object_type
        8  thoughtspot_object_name
        9  thoughtspot_object_guid
        10 parsed_successfully
        11 parse_error
        12 uploaded_at
        """

        if row is None:
            return None

        return cls(
            file_id=row[0],
            job_id=row[1],
            original_filename=row[2],
            stored_filename=row[3],
            file_path=row[4],
            file_size=row[5],
            file_type=row[6],
            thoughtspot_object_type=row[7],
            thoughtspot_object_name=row[8],
            thoughtspot_object_guid=row[9],
            parsed_successfully=bool(row[10]) if row[10] is not None else False,
            parse_error=row[11],
            uploaded_at=datetime.fromisoformat(row[12]) if row[12] and isinstance(row[12], str) else row[12],
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert uploaded file to dictionary.
        """

        return {
            "file_id": self.file_id,
            "job_id": self.job_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "thoughtspot_object_type": self.thoughtspot_object_type,
            "thoughtspot_object_name": self.thoughtspot_object_name,
            "thoughtspot_object_guid": self.thoughtspot_object_guid,
            "parsed_successfully": self.parsed_successfully,
            "parse_error": self.parse_error,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


@dataclass
class MigrationLog:
    """
    Domain model for migration progress logs.
    """

    log_id: str
    job_id: str
    stage: str
    message: str
    percent: int
    level: str = "info"
    object_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: tuple) -> Optional["MigrationLog"]:
        """
        Create MigrationLog from database row.

        Expected database column order:

        0 log_id
        1 job_id
        2 stage
        3 message
        4 percent
        5 level
        6 object_name
        7 created_at
        """

        if row is None:
            return None

        return cls(
            log_id=row[0],
            job_id=row[1],
            stage=row[2],
            message=row[3],
            percent=row[4] or 0,
            level=row[5] or "info",
            object_name=row[6],
            created_at=datetime.fromisoformat(row[7]) if row[7] and isinstance(row[7], str) else row[7],
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert migration log to dictionary.
        """

        return {
            "log_id": self.log_id,
            "job_id": self.job_id,
            "stage": self.stage,
            "message": self.message,
            "percent": self.percent,
            "level": self.level,
            "object_name": self.object_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }