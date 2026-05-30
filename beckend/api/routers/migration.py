"""
Migration API Router - ThoughtSpot to Power BI migration endpoints.
"""

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
)
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional, Any, Dict
from pathlib import Path
from datetime import datetime
from loguru import logger
import zipfile
import json
import io

from api.config import config
from api.utils import (
    generate_migration_id,
    generate_file_id,
)

from api.models.migration_models import (
    MigrationStatus,
    ConversionMethod,
    ConversionStatus,
)

from storage.migration_store import MigrationStore
from storage.file_store import FileStore
from storage.job_store import JobStore
from storage.result_store import ResultStore

from workers.migration_worker import execute_thoughtspot_powerbi_migration


router = APIRouter()

migration_store = MigrationStore()
file_store = FileStore()
job_store = JobStore()
result_store = ResultStore()


# ============================================================
# Helper Functions
# ============================================================

def validate_thoughtspot_file(filename: str) -> None:
    """
    Validate ThoughtSpot upload file.
    Supported files:
    .tml, .yaml, .yml, .json, .zip, .csv, .xlsx, .xls
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

    allowed_extensions = tuple(config.ALLOWED_EXTENSIONS)

    if not filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": "Unsupported ThoughtSpot file type",
                    "details": {
                        "filename": filename,
                        "allowed_extensions": config.ALLOWED_EXTENSIONS,
                    },
                }
            },
        )


def clamp_pagination(limit: int, offset: int, max_limit: int = 1000):
    """
    Keep pagination values safe.
    """

    limit = min(max(1, limit), max_limit)
    offset = max(0, offset)
    return limit, offset


def _to_plain_dict(value: Any) -> Any:
    """
    Convert Python objects, enums, and model objects to JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(value, dict):
        return {
            key: _to_plain_dict(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_to_plain_dict(item) for item in value]

    if isinstance(value, tuple):
        return [_to_plain_dict(item) for item in value]

    if hasattr(value, "to_dict"):
        return _to_plain_dict(value.to_dict())

    if hasattr(value, "model_dump"):
        return _to_plain_dict(value.model_dump())

    if hasattr(value, "dict"):
        try:
            return _to_plain_dict(value.dict())
        except Exception:
            pass

    if hasattr(value, "value"):
        return value.value

    return value


def _unwrap_result_payload(data: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize result payload:
    - {"result": {...}} -> {...}
    - {...} -> {...}
    """

    if not data:
        return None

    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        return data["result"]

    if isinstance(data, dict):
        return data

    return None


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """
    Safely load JSON from file.
    """

    try:
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        return _unwrap_result_payload(data)

    except Exception as error:
        logger.warning(f"Failed to load JSON file {path}: {error}")
        return None


def _load_result_data_from_file_or_store(migration_id: str) -> Optional[Dict[str, Any]]:
    """
    Load result data for both:
    - job IDs created from /jobs
    - migration IDs created from /migration/upload

    This function tries:
    1. ResultStore methods
    2. JobStore result_file_path
    3. Common result folders
    """

    # 1. Try common ResultStore method names
    for method_name in ["get_result", "load_result", "read_result"]:
        try:
            if hasattr(result_store, method_name):
                method = getattr(result_store, method_name)
                data = method(migration_id)
                normalized = _unwrap_result_payload(_to_plain_dict(data))

                if normalized:
                    return normalized

        except Exception as error:
            logger.warning(
                f"ResultStore.{method_name} failed for {migration_id}: {error}"
            )

    # 2. Try JobStore result_file_path
    try:
        job = None

        if hasattr(job_store, "get_job"):
            job = job_store.get_job(migration_id)

        job_data = _to_plain_dict(job)

        result_file_path = None

        if isinstance(job_data, dict):
            result_file_path = job_data.get("result_file_path")

        if result_file_path:
            data = _load_json_file(Path(result_file_path))

            if data:
                return data

    except Exception as error:
        logger.warning(f"JobStore result_file_path lookup failed for {migration_id}: {error}")

    # 3. Search common result folders
    search_dirs = [
        Path(getattr(config, "RESULT_DIR", "data/results")),
        Path("data/results"),
        Path("output/reports"),
        Path("output"),
    ]

    for folder in search_dirs:
        try:
            if not folder.exists():
                continue

            patterns = [
                f"{migration_id}.json",
                f"{migration_id}_result.json",
                f"*{migration_id}*.json",
            ]

            for pattern in patterns:
                matches = list(folder.rglob(pattern))

                for match in matches:
                    data = _load_json_file(match)

                    if data:
                        return data

        except Exception as error:
            logger.warning(f"Result folder search failed in {folder}: {error}")

    return None


def _get_result_or_migration_data(migration_id: str) -> Optional[Dict[str, Any]]:
    """
    Return result data from ResultStore/job result first.
    If not found, fallback to MigrationStore.
    """

    result_data = _load_result_data_from_file_or_store(migration_id)

    if result_data:
        return result_data

    migration = migration_store.get_migration(migration_id)

    if not migration:
        return None

    objects = migration_store.get_objects_by_migration(migration_id)
    formulas = migration_store.get_formulas_by_migration(migration_id)
    conversions = migration_store.get_conversions_by_migration(migration_id)
    relationships = migration_store.get_relationships_by_migration(migration_id)

    return {
        "job_id": migration_id,
        "migration_id": migration_id,
        "status": "completed",
        "summary": _to_plain_dict(migration),
        "objects": _to_plain_dict(objects),
        "workbooks": _to_plain_dict(objects),
        "formulas": _to_plain_dict(formulas),
        "calculations": _to_plain_dict(formulas),
        "conversions": _to_plain_dict(conversions),
        "relationships": _to_plain_dict(relationships),
        "suggested_relationships": _to_plain_dict(relationships),
    }


def _build_model_bim_from_conversions(
    migration_id: str,
    conversions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a simple Power BI model.bim with generated DAX measures.
    """

    measures = []

    for index, conversion in enumerate(conversions):
        measure_name = (
            conversion.get("target_powerbi_object_name")
            or conversion.get("calc_name")
            or conversion.get("name")
            or conversion.get("source_formula_id")
            or conversion.get("calc_id")
            or f"Measure_{index + 1}"
        )

        dax_formula = (
            conversion.get("dax_formula")
            or conversion.get("target_formula")
            or conversion.get("converted_formula")
            or conversion.get("source_formula")
            or "BLANK()"
        )

        measures.append(
            {
                "name": str(measure_name),
                "expression": str(dax_formula),
                "formatString": "#,##0.00",
            }
        )

    return {
        "name": f"ThoughtSpot_Migration_{migration_id}",
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "tables": [
                {
                    "name": "_Measures",
                    "columns": [
                        {
                            "name": "Placeholder",
                            "dataType": "string",
                            "sourceColumn": "Placeholder",
                        }
                    ],
                    "partitions": [
                        {
                            "name": "Partition",
                            "mode": "import",
                            "source": {
                                "type": "m",
                                "expression": (
                                    "let\n"
                                    "    Source = #table({\"Placeholder\"}, {{\"\"}})\n"
                                    "in\n"
                                    "    Source"
                                ),
                            },
                        }
                    ],
                    "measures": measures,
                }
            ],
        },
    }


# ============================================================
# Migration Upload / Start
# ============================================================

@router.post("/upload")
async def upload_thoughtspot_files(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload ThoughtSpot metadata/TML/export files and create a migration job.
    """

    try:
        if not files:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "NO_FILES_UPLOADED",
                        "message": "Please upload at least one ThoughtSpot file",
                    }
                },
            )

        if len(files) > config.MAX_FILES_PER_JOB:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "TOO_MANY_FILES",
                        "message": f"Maximum {config.MAX_FILES_PER_JOB} files are allowed",
                        "details": {
                            "max_files": config.MAX_FILES_PER_JOB,
                            "provided": len(files),
                        },
                    }
                },
            )

        migration_id = generate_migration_id()
        migration = migration_store.create_migration(migration_id)

        file_paths = []
        uploaded_files = []

        Path(config.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(config.RESULT_DIR).mkdir(parents=True, exist_ok=True)

        max_file_size = config.MAX_FILE_SIZE_MB * 1024 * 1024

        for file in files:
            validate_thoughtspot_file(file.filename)

            content = await file.read()
            file_size = len(content)

            if file_size > max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "error": {
                            "code": "FILE_TOO_LARGE",
                            "message": f"File {file.filename} exceeds {config.MAX_FILE_SIZE_MB}MB limit",
                            "details": {
                                "filename": file.filename,
                                "max_size_mb": config.MAX_FILE_SIZE_MB,
                                "actual_size_mb": round(file_size / 1024 / 1024, 2),
                            },
                        }
                    },
                )

            file_id = generate_file_id()
            safe_filename = Path(file.filename).name
            stored_path = Path(config.UPLOAD_DIR) / f"{migration_id}_{file_id}_{safe_filename}"

            with open(stored_path, "wb") as f:
                f.write(content)

            file_paths.append(str(stored_path))

            uploaded_files.append(
                {
                    "file_id": file_id,
                    "filename": safe_filename,
                    "stored_path": str(stored_path),
                    "file_size": file_size,
                }
            )

            logger.info(f"Saved ThoughtSpot file: {safe_filename} ({file_size} bytes)")

        migration_store.update_migration_counts(
            migration_id,
            object_count=len(files),
        )

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
            migration_id,
            file_paths,
        )

        logger.info(f"Started ThoughtSpot -> Power BI migration: {migration_id}")

        return {
            "migration_id": migration_id,
            "status": migration.status.value
            if hasattr(migration.status, "value")
            else migration.status,
            "file_count": len(files),
            "files": uploaded_files,
            "message": "ThoughtSpot to Power BI migration created successfully",
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to upload ThoughtSpot files: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MIGRATION_UPLOAD_FAILED",
                    "message": "Failed to upload ThoughtSpot files",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Migration Status / Delete
# ============================================================

@router.get("/{migration_id}")
async def get_migration_status(migration_id: str):
    """
    Get ThoughtSpot -> Power BI migration status.
    """

    migration = migration_store.get_migration(migration_id)

    if migration:
        return migration.to_dict()

    result_data = _load_result_data_from_file_or_store(migration_id)

    if result_data:
        summary = result_data.get("summary") or {}

        return {
            "migration_id": migration_id,
            "job_id": migration_id,
            "status": result_data.get("status", "completed"),
            "progress_percent": 100,
            "current_stage": "completed",
            "object_count": summary.get("object_count", summary.get("total_dashboards", 0)),
            "formula_count": summary.get("formula_count", summary.get("total_calculated_fields", 0)),
            "conversion_count": summary.get("conversion_count", len(result_data.get("conversions", []))),
            "summary": summary,
        }

    raise HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "MIGRATION_NOT_FOUND",
                "message": f"Migration {migration_id} not found",
            }
        },
    )


@router.delete("/{migration_id}")
async def delete_migration(migration_id: str):
    """
    Delete a migration job and related data.
    """

    migration = migration_store.get_migration(migration_id)

    if not migration:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MIGRATION_NOT_FOUND",
                    "message": f"Migration {migration_id} not found",
                }
            },
        )

    try:
        migration_store.delete_migration(migration_id)

        logger.info(f"Deleted migration: {migration_id}")

        return {
            "message": "Migration deleted successfully",
            "migration_id": migration_id,
        }

    except Exception as e:
        logger.error(f"Failed to delete migration {migration_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "DELETE_MIGRATION_FAILED",
                    "message": "Failed to delete migration",
                    "details": str(e),
                }
            },
        )


# ============================================================
# ThoughtSpot Objects
# ============================================================

@router.get("/{migration_id}/objects")
async def get_thoughtspot_objects(
    migration_id: str,
    object_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get ThoughtSpot objects extracted during migration.
    """

    try:
        limit, offset = clamp_pagination(limit, offset)

        result_data = _load_result_data_from_file_or_store(migration_id)

        if result_data:
            objects = result_data.get("objects") or result_data.get("workbooks") or []

            if object_type:
                objects = [
                    obj for obj in objects
                    if obj.get("object_type") == object_type or obj.get("type") == object_type
                ]

            total = len(objects)
            paginated_objects = objects[offset:offset + limit]

            return {
                "objects": paginated_objects,
                "workbooks": paginated_objects,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            }

        objects = migration_store.get_objects_by_migration(migration_id)

        if object_type:
            objects = [
                obj for obj in objects
                if obj.object_type.value == object_type
            ]

        total = len(objects)
        paginated_objects = objects[offset:offset + limit]

        return {
            "objects": [obj.to_dict() for obj in paginated_objects],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    except Exception as e:
        logger.error(f"Failed to get ThoughtSpot objects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_OBJECTS_FAILED",
                    "message": "Failed to get ThoughtSpot objects",
                    "details": str(e),
                }
            },
        )


@router.get("/{migration_id}/objects/{object_id}/model")
async def get_thoughtspot_object_model(
    migration_id: str,
    object_id: str,
):
    """
    Get raw ThoughtSpot TML/JSON model for one object.
    """

    objects = migration_store.get_objects_by_migration(migration_id)
    obj = next((item for item in objects if item.object_id == object_id), None)

    if not obj:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OBJECT_NOT_FOUND",
                    "message": f"ThoughtSpot object {object_id} not found",
                }
            },
        )

    return obj.raw_tml or {}


# ============================================================
# Formulas / DAX Conversion
# ============================================================

@router.get("/{migration_id}/formulas")
async def get_formulas(
    migration_id: str,
    object_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get ThoughtSpot formulas/calculated fields extracted during migration.
    """

    try:
        limit, offset = clamp_pagination(limit, offset)

        result_data = _load_result_data_from_file_or_store(migration_id)

        if result_data:
            formulas = result_data.get("formulas") or result_data.get("calculations") or []

            if object_id:
                formulas = [
                    formula for formula in formulas
                    if formula.get("object_id") == object_id
                ]

            total = len(formulas)
            paginated_formulas = formulas[offset:offset + limit]

            return {
                "formulas": paginated_formulas,
                "calculations": paginated_formulas,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            }

        if object_id:
            formulas = migration_store.get_formulas_by_object(object_id)
        else:
            formulas = migration_store.get_formulas_by_migration(migration_id)

        total = len(formulas)
        paginated_formulas = formulas[offset:offset + limit]

        return {
            "formulas": [formula.to_dict() for formula in paginated_formulas],
            "calculations": [formula.to_dict() for formula in paginated_formulas],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    except Exception as e:
        logger.error(f"Failed to get formulas: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_FORMULAS_FAILED",
                    "message": "Failed to get ThoughtSpot formulas",
                    "details": str(e),
                }
            },
        )


@router.get("/{migration_id}/conversions")
async def get_conversions(
    migration_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get Power BI / DAX conversions.
    """

    try:
        limit, offset = clamp_pagination(limit, offset)

        result_data = _load_result_data_from_file_or_store(migration_id)

        if result_data:
            conversions = result_data.get("conversions") or []

            if status:
                conversions = [
                    conv for conv in conversions
                    if conv.get("status") == status
                ]

            total = len(conversions)
            paginated_conversions = conversions[offset:offset + limit]

            return {
                "conversions": paginated_conversions,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            }

        conversions = migration_store.get_conversions_by_migration(migration_id)

        if status:
            conversions = [
                conv for conv in conversions
                if conv.status.value == status
            ]

        total = len(conversions)
        paginated_conversions = conversions[offset:offset + limit]

        return {
            "conversions": [conv.to_dict() for conv in paginated_conversions],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    except Exception as e:
        logger.error(f"Failed to get conversions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_CONVERSIONS_FAILED",
                    "message": "Failed to get Power BI conversions",
                    "details": str(e),
                }
            },
        )


@router.get("/{migration_id}/conversions/{conversion_id}")
async def get_conversion(
    migration_id: str,
    conversion_id: str,
):
    """
    Get one DAX conversion.
    """

    result_data = _load_result_data_from_file_or_store(migration_id)

    if result_data:
        conversions = result_data.get("conversions") or []
        conversion = next(
            (
                item for item in conversions
                if item.get("conversion_id") == conversion_id
            ),
            None,
        )

        if conversion:
            return conversion

    conversion = migration_store.get_conversion(conversion_id)

    if not conversion:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "CONVERSION_NOT_FOUND",
                    "message": f"Conversion {conversion_id} not found",
                }
            },
        )

    return conversion.to_dict()


@router.patch("/{migration_id}/conversions/{conversion_id}")
async def update_conversion(
    migration_id: str,
    conversion_id: str,
    request: dict,
):
    """
    Manually override a DAX conversion.
    """

    try:
        dax_formula = request.get("dax_formula")
        reasoning = request.get("reasoning", "Manual override by user")

        if not dax_formula:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": "dax_formula is required",
                    }
                },
            )

        conversion = migration_store.get_conversion(conversion_id)

        if not conversion:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "CONVERSION_NOT_FOUND",
                        "message": f"Conversion {conversion_id} not found",
                    }
                },
            )

        updated = migration_store.update_conversion(
            conversion_id=conversion_id,
            dax_formula=dax_formula,
            conversion_method=ConversionMethod.MANUAL_OVERRIDE,
            reasoning=reasoning,
            status=ConversionStatus.PENDING,
        )

        logger.info(f"Updated DAX conversion {conversion_id}")

        return {
            "conversion_id": conversion_id,
            "dax_formula": updated.dax_formula,
            "conversion_method": updated.conversion_method.value,
            "status": updated.status.value,
            "message": "Conversion updated. Validation pending.",
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to update conversion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "UPDATE_CONVERSION_FAILED",
                    "message": "Failed to update DAX conversion",
                    "details": str(e),
                }
            },
        )


@router.post("/{migration_id}/trigger-conversion")
async def trigger_conversion(
    migration_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Trigger or re-run ThoughtSpot formula to DAX conversion.
    """

    migration = migration_store.get_migration(migration_id)

    if not migration:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MIGRATION_NOT_FOUND",
                    "message": f"Migration {migration_id} not found",
                }
            },
        )

    migration_store.update_migration_status(
        migration_id,
        MigrationStatus.CONVERTING,
        current_stage="Generating DAX from ThoughtSpot formulas",
    )

    background_tasks.add_task(
        execute_thoughtspot_powerbi_migration,
        migration_id,
        [],
    )

    return {
        "status": "conversion_started",
        "migration_id": migration_id,
        "message": "DAX conversion has been queued",
    }


# ============================================================
# Relationships
# ============================================================

@router.get("/{migration_id}/suggested-relationships")
async def get_suggested_relationships(migration_id: str):
    """
    Get suggested relationships extracted from ThoughtSpot joins.
    """

    try:
        result_data = _load_result_data_from_file_or_store(migration_id)

        if result_data:
            relationships = (
                result_data.get("relationships")
                or result_data.get("suggested_relationships")
                or []
            )

            return {
                "relationships": relationships,
                "suggested_relationships": relationships,
            }

        relationships = migration_store.get_relationships_by_migration(migration_id)

        return {
            "relationships": [rel.to_dict() for rel in relationships],
            "suggested_relationships": [rel.to_dict() for rel in relationships],
        }

    except Exception as e:
        logger.error(f"Failed to get relationships: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_RELATIONSHIPS_FAILED",
                    "message": "Failed to get suggested relationships",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Workbook Metadata
# ============================================================

@router.get("/{migration_id}/workbook-metadata")
async def get_workbook_metadata(migration_id: str):
    """
    Get frontend-compatible workbook metadata.
    """

    result_data = _get_result_or_migration_data(migration_id)

    if not result_data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "WORKBOOK_METADATA_NOT_FOUND",
                    "message": f"Workbook metadata not found for {migration_id}",
                }
            },
        )

    return {
        "summary": result_data.get("summary") or {},
        "workbooks": result_data.get("workbooks") or result_data.get("objects") or [],
        "objects": result_data.get("objects") or result_data.get("workbooks") or [],
        "tables": result_data.get("tables") or [],
        "formulas": result_data.get("formulas") or result_data.get("calculations") or [],
        "calculations": result_data.get("calculations") or result_data.get("formulas") or [],
        "conversions": result_data.get("conversions") or [],
        "relationships": result_data.get("relationships") or [],
    }


@router.get("/{migration_id}/workbook-metadata/summary")
async def get_workbook_metadata_summary(migration_id: str):
    """
    Get workbook metadata summary.
    """

    result_data = _get_result_or_migration_data(migration_id)

    if not result_data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "WORKBOOK_SUMMARY_NOT_FOUND",
                    "message": f"Workbook summary not found for {migration_id}",
                }
            },
        )

    return result_data.get("summary") or {}


@router.get("/{migration_id}/workbook-metadata/tables-data")
async def get_tables_data(migration_id: str):
    """
    Get tables data for model intelligence page.
    """

    result_data = _get_result_or_migration_data(migration_id)

    if not result_data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "TABLES_DATA_NOT_FOUND",
                    "message": f"Tables data not found for {migration_id}",
                }
            },
        )

    return {
        "tables": result_data.get("tables") or [],
        "objects": result_data.get("objects") or result_data.get("workbooks") or [],
        "summary": result_data.get("summary") or {},
    }


@router.get("/{migration_id}/workbook-metadata/model-intelligence")
async def get_model_intelligence(migration_id: str):
    """
    Get model intelligence data.
    """

    result_data = _get_result_or_migration_data(migration_id)

    if not result_data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MODEL_INTELLIGENCE_NOT_FOUND",
                    "message": f"Model intelligence data not found for {migration_id}",
                }
            },
        )

    return {
        "tables": result_data.get("tables") or [],
        "objects": result_data.get("objects") or result_data.get("workbooks") or [],
        "workbooks": result_data.get("workbooks") or result_data.get("objects") or [],
        "relationships": result_data.get("relationships") or [],
        "summary": result_data.get("summary") or {},
    }


# ============================================================
# Validation
# ============================================================

@router.post("/{migration_id}/validate")
async def trigger_validation(
    migration_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Trigger validation of ThoughtSpot formula output vs Power BI DAX output.
    """

    migration = migration_store.get_migration(migration_id)

    if not migration:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MIGRATION_NOT_FOUND",
                    "message": f"Migration {migration_id} not found",
                }
            },
        )

    migration_store.update_migration_status(
        migration_id,
        MigrationStatus.VALIDATING,
        current_stage="Validating Power BI DAX conversions",
    )

    return {
        "message": "Validation started",
        "migration_id": migration_id,
    }


@router.get("/{migration_id}/validation-results")
async def get_validation_results(migration_id: str):
    """
    Get validation results for all conversions.
    """

    try:
        result_data = _load_result_data_from_file_or_store(migration_id)

        if result_data:
            conversions = result_data.get("conversions") or []

            return {
                "results": [],
                "validation_results": [],
                "summary": {
                    "total_conversions": len(conversions),
                    "passed": len(conversions),
                    "failed": 0,
                    "pass_rate": 100 if conversions else 0,
                },
            }

        conversions = migration_store.get_conversions_by_migration(migration_id)

        validation_results_by_conversion = (
            migration_store.get_validation_results_by_migration(migration_id)
        )

        results = []
        passed_count = 0

        for conversion in conversions:
            validation_results = validation_results_by_conversion.get(
                conversion.conversion_id,
                [],
            )

            test_slices = [vr.to_dict() for vr in validation_results]
            overall_passed = (
                all(vr.passed for vr in validation_results)
                if validation_results
                else False
            )

            if overall_passed:
                passed_count += 1

            results.append(
                {
                    "conversion_id": conversion.conversion_id,
                    "test_slices": test_slices,
                    "overall_passed": overall_passed,
                    "correction_attempts": (
                        validation_results[0].correction_attempts
                        if validation_results
                        else 0
                    ),
                }
            )

        total = len(conversions)

        return {
            "results": results,
            "validation_results": results,
            "summary": {
                "total_conversions": total,
                "passed": passed_count,
                "failed": total - passed_count,
                "pass_rate": round((passed_count / total * 100), 1)
                if total
                else 0,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get validation results: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_VALIDATION_RESULTS_FAILED",
                    "message": "Failed to get validation results",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Filters / Visuals / Recommendations
# ============================================================

@router.get("/{migration_id}/filters")
async def get_filters(migration_id: str):
    """
    Get filters extracted from ThoughtSpot Answers or Liveboards.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)

        filters = []

        for obj in objects:
            raw = obj.raw_tml or {}

            object_filters = raw.get("filters", [])
            for item in object_filters:
                filters.append(
                    {
                        "object_id": obj.object_id,
                        "object_name": obj.object_name,
                        "field_name": item.get("field") or item.get("column"),
                        "filter_type": item.get("type", "unknown"),
                        "values": item.get("values", []),
                    }
                )

        return {"filters": filters}

    except Exception as e:
        logger.error(f"Failed to get filters: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_FILTERS_FAILED",
                    "message": "Failed to get filters",
                    "details": str(e),
                }
            },
        )


@router.get("/{migration_id}/recommendations")
async def get_recommendations(migration_id: str):
    """
    Get Power BI migration recommendations.
    """

    try:
        result_data = _load_result_data_from_file_or_store(migration_id)

        if result_data:
            conversions = result_data.get("conversions") or []
            formulas = result_data.get("formulas") or result_data.get("calculations") or []
            objects = result_data.get("objects") or result_data.get("workbooks") or []

            total = len(conversions)
            auto_converted = sum(
                1 for conversion in conversions
                if (conversion.get("confidence_score") or 0) >= 0.9
            )
            manual_review = sum(
                1 for conversion in conversions
                if 0.7 <= (conversion.get("confidence_score") or 0) < 0.9
            )
            complex_items = sum(
                1 for conversion in conversions
                if (conversion.get("confidence_score") or 0) < 0.7
            )

            overall_rate = (auto_converted / total * 100) if total > 0 else 0

            recommendations = [
                {
                    "title": "Review Generated DAX Measures",
                    "priority": "HIGH",
                    "description": (
                        "Review all generated DAX measures before importing them "
                        "into a production Power BI model."
                    ),
                    "action_items": [
                        "Check measure names",
                        "Validate DAX syntax",
                        "Compare sample totals with ThoughtSpot",
                        "Adjust formatting in Power BI",
                    ],
                }
            ]

            if formulas:
                recommendations.append(
                    {
                        "title": "Validate Calculated Fields",
                        "priority": "MEDIUM",
                        "description": (
                            "Calculated fields were detected and converted. "
                            "Validate them with business users."
                        ),
                        "action_items": [
                            "Check aggregation logic",
                            "Confirm filter context",
                            "Validate row-level vs measure-level calculations",
                        ],
                    }
                )

            return {
                "success_rate": {
                    "overall_rate": round(overall_rate, 1),
                    "total_conversions": total,
                    "auto_converted": auto_converted,
                    "manual_review": manual_review,
                    "complex": complex_items,
                },
                "recommendations": recommendations,
                "summary": result_data.get("summary") or {},
            }

        conversions = migration_store.get_conversions_by_migration(migration_id)
        formulas = migration_store.get_formulas_by_migration(migration_id)
        objects = migration_store.get_objects_by_migration(migration_id)

        total = len(conversions)
        auto_converted = sum(
            1 for c in conversions
            if (c.confidence_score or 0) >= 0.9
        )
        manual_review = sum(
            1 for c in conversions
            if 0.7 <= (c.confidence_score or 0) < 0.9
        )
        complex_items = sum(
            1 for c in conversions
            if (c.confidence_score or 0) < 0.7
        )

        overall_rate = (auto_converted / total * 100) if total > 0 else 0

        recommendations = []

        has_date_fields = any(
            "date" in f.formula_name.lower()
            or "year" in f.formula_name.lower()
            or "month" in f.formula_name.lower()
            for f in formulas
        )

        if has_date_fields:
            recommendations.append(
                {
                    "title": "Create Power BI Date Table",
                    "priority": "HIGH",
                    "description": (
                        "Date fields were detected. Create a Power BI calendar table "
                        "for time intelligence measures."
                    ),
                    "action_items": [
                        "Create a Calendar table using CALENDARAUTO()",
                        "Mark it as a Date table",
                        "Create relationships with fact tables",
                        "Use TOTALYTD, SAMEPERIODLASTYEAR, DATEADD where needed",
                    ],
                }
            )

        liveboard_count = sum(
            1 for obj in objects
            if obj.object_type.value == "liveboard"
        )

        if liveboard_count > 0:
            recommendations.append(
                {
                    "title": "Review Liveboard Visual Mapping",
                    "priority": "MEDIUM",
                    "description": (
                        "ThoughtSpot Liveboards may not map 1:1 to Power BI dashboards. "
                        "Review visual layout manually after migration."
                    ),
                    "action_items": [
                        "Map KPIs to Card visuals",
                        "Map tables to Matrix visuals",
                        "Map charts to Power BI native chart types",
                        "Review filters and slicers",
                    ],
                }
            )

        return {
            "success_rate": {
                "overall_rate": round(overall_rate, 1),
                "total_conversions": total,
                "auto_converted": auto_converted,
                "manual_review": manual_review,
                "complex": complex_items,
            },
            "recommendations": recommendations,
        }

    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GET_RECOMMENDATIONS_FAILED",
                    "message": "Failed to get recommendations",
                    "details": str(e),
                }
            },
        )


# ============================================================
# Export / Download
# ============================================================

@router.post("/{migration_id}/export")
async def export_powerbi_artifacts(migration_id: str):
    """
    Generate Power BI migration artifacts ZIP.
    """

    result_data = _get_result_or_migration_data(migration_id)

    if not result_data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MIGRATION_NOT_FOUND",
                    "message": f"Migration {migration_id} not found",
                }
            },
        )

    try:
        Path(config.RESULT_DIR).mkdir(parents=True, exist_ok=True)

        artifact_filename = f"{migration_id}_powerbi_artifacts.zip"
        artifact_path = Path(config.RESULT_DIR) / artifact_filename

        summary = result_data.get("summary") or {}
        files = result_data.get("files") or []
        workbooks = result_data.get("workbooks") or result_data.get("objects") or []
        tables = result_data.get("tables") or []
        formulas = result_data.get("formulas") or result_data.get("calculations") or []
        conversions = result_data.get("conversions") or []
        relationships = (
            result_data.get("relationships")
            or result_data.get("suggested_relationships")
            or []
        )

        model_bim = _build_model_bim_from_conversions(
            migration_id=migration_id,
            conversions=conversions,
        )

        with zipfile.ZipFile(artifact_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(
                "migration_summary.json",
                json.dumps(summary, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/files.json",
                json.dumps(files, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/workbooks.json",
                json.dumps(workbooks, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/tables.json",
                json.dumps(tables, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/calculated_fields.json",
                json.dumps(formulas, indent=2, default=str),
            )
            zip_file.writestr(
                "powerbi/dax_conversions.json",
                json.dumps(conversions, indent=2, default=str),
            )
            zip_file.writestr(
                "powerbi/model.bim",
                json.dumps(model_bim, indent=2, default=str),
            )
            zip_file.writestr(
                "relationships.json",
                json.dumps(relationships, indent=2, default=str),
            )

            report_lines = [
                "Metric,Value",
                f"Migration ID,{migration_id}",
                f"Status,{result_data.get('status', 'completed')}",
                f"Dashboards,{summary.get('total_dashboards', summary.get('object_count', 0))}",
                f"Worksheets,{summary.get('total_worksheets', 0)}",
                f"Tables,{summary.get('total_tables', 0)}",
                f"Calculated Fields,{summary.get('total_calculated_fields', summary.get('formula_count', len(formulas)))}",
                f"Conversions,{summary.get('conversion_count', len(conversions))}",
                f"Relationships,{summary.get('relationship_count', len(relationships))}",
            ]

            zip_file.writestr("migration_report.csv", "\n".join(report_lines))

            zip_file.writestr(
                "README.txt",
                (
                    "ThoughtSpot to Power BI Migration Package\n"
                    f"Migration/Job ID: {migration_id}\n"
                    f"Generated At: {datetime.utcnow().isoformat()}\n\n"
                    "Included files:\n"
                    "- migration_summary.json\n"
                    "- migration_report.csv\n"
                    "- source_metadata/files.json\n"
                    "- source_metadata/workbooks.json\n"
                    "- source_metadata/tables.json\n"
                    "- source_metadata/calculated_fields.json\n"
                    "- powerbi/dax_conversions.json\n"
                    "- powerbi/model.bim\n"
                    "- relationships.json\n\n"
                    "How to use model.bim:\n"
                    "1. Open Power BI Desktop.\n"
                    "2. Open Tabular Editor from External Tools.\n"
                    "3. Open powerbi/model.bim.\n"
                    "4. Review or copy generated measures into your Power BI model.\n"
                ),
            )

        logger.info(f"Generated Power BI artifacts for {migration_id}: {artifact_path}")

        return {
            "message": "Power BI artifacts generated successfully",
            "download_url": f"{config.API_PREFIX}/migration/{migration_id}/download",
            "artifacts": {
                "summary": "migration_summary.json",
                "report": "migration_report.csv",
                "files": "source_metadata/files.json",
                "workbooks": "source_metadata/workbooks.json",
                "tables": "source_metadata/tables.json",
                "formulas": "source_metadata/calculated_fields.json",
                "conversions": "powerbi/dax_conversions.json",
                "semantic_model": "powerbi/model.bim",
                "relationships": "relationships.json",
            },
        }

    except Exception as e:
        logger.error(f"Failed to export Power BI artifacts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "EXPORT_FAILED",
                    "message": "Failed to generate Power BI artifacts",
                    "details": str(e),
                }
            },
        )


@router.get("/{migration_id}/download")
async def download_artifacts(migration_id: str):
    """
    Download generated Power BI artifacts ZIP.
    """

    artifact_path = Path(config.RESULT_DIR) / f"{migration_id}_powerbi_artifacts.zip"

    if not artifact_path.exists():
        # Generate it on demand if possible.
        await export_powerbi_artifacts(migration_id)

    if not artifact_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "ARTIFACTS_NOT_FOUND",
                    "message": "Artifacts not found. Please run export first.",
                }
            },
        )

    return FileResponse(
        path=artifact_path,
        filename=f"thoughtspot_powerbi_migration_{migration_id}.zip",
        media_type="application/zip",
    )


@router.get("/{migration_id}/download-all")
async def download_all_artifacts(migration_id: str):
    """
    Download complete migration package.

    If export ZIP does not exist, this endpoint creates it in memory from:
    - ResultStore / job result JSON
    - MigrationStore fallback
    """

    try:
        artifact_path = Path(config.RESULT_DIR) / f"{migration_id}_powerbi_artifacts.zip"

        if artifact_path.exists():
            return FileResponse(
                path=artifact_path,
                filename=f"thoughtspot_powerbi_migration_{migration_id}.zip",
                media_type="application/zip",
            )

        result_data = _get_result_or_migration_data(migration_id)

        if not result_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "MIGRATION_RESULT_NOT_FOUND",
                        "message": f"No migration/job result found for {migration_id}",
                        "details": {
                            "migration_id": migration_id,
                            "hint": "Run migration again and wait until it is completed.",
                        },
                    }
                },
            )

        result_data = _to_plain_dict(result_data)

        if isinstance(result_data, dict) and isinstance(result_data.get("result"), dict):
            result_data = result_data["result"]

        summary = result_data.get("summary") or {}
        files = result_data.get("files") or []
        workbooks = result_data.get("workbooks") or result_data.get("objects") or []
        tables = result_data.get("tables") or []
        formulas = result_data.get("formulas") or result_data.get("calculations") or []
        conversions = result_data.get("conversions") or []
        relationships = (
            result_data.get("relationships")
            or result_data.get("suggested_relationships")
            or []
        )

        model_bim = _build_model_bim_from_conversions(
            migration_id=migration_id,
            conversions=conversions,
        )

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(
                "migration_summary.json",
                json.dumps(summary, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/files.json",
                json.dumps(files, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/workbooks.json",
                json.dumps(workbooks, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/tables.json",
                json.dumps(tables, indent=2, default=str),
            )
            zip_file.writestr(
                "source_metadata/calculated_fields.json",
                json.dumps(formulas, indent=2, default=str),
            )
            zip_file.writestr(
                "powerbi/dax_conversions.json",
                json.dumps(conversions, indent=2, default=str),
            )
            zip_file.writestr(
                "powerbi/model.bim",
                json.dumps(model_bim, indent=2, default=str),
            )
            zip_file.writestr(
                "relationships.json",
                json.dumps(relationships, indent=2, default=str),
            )

            report_lines = [
                "Metric,Value",
                f"Migration ID,{migration_id}",
                f"Status,{result_data.get('status', 'completed')}",
                f"Dashboards,{summary.get('total_dashboards', summary.get('object_count', 0))}",
                f"Worksheets,{summary.get('total_worksheets', 0)}",
                f"Tables,{summary.get('total_tables', 0)}",
                f"Calculated Fields,{summary.get('total_calculated_fields', summary.get('formula_count', len(formulas)))}",
                f"Conversions,{summary.get('conversion_count', len(conversions))}",
                f"Relationships,{summary.get('relationship_count', len(relationships))}",
            ]

            zip_file.writestr("migration_report.csv", "\n".join(report_lines))

            zip_file.writestr(
                "README.txt",
                (
                    "ThoughtSpot to Power BI Migration Package\n"
                    f"Migration/Job ID: {migration_id}\n"
                    f"Generated At: {datetime.utcnow().isoformat()}\n\n"
                    "Included files:\n"
                    "- migration_summary.json\n"
                    "- migration_report.csv\n"
                    "- source_metadata/files.json\n"
                    "- source_metadata/workbooks.json\n"
                    "- source_metadata/tables.json\n"
                    "- source_metadata/calculated_fields.json\n"
                    "- powerbi/dax_conversions.json\n"
                    "- powerbi/model.bim\n"
                    "- relationships.json\n\n"
                    "How to use model.bim:\n"
                    "1. Open Power BI Desktop.\n"
                    "2. Open Tabular Editor from External Tools.\n"
                    "3. Open powerbi/model.bim.\n"
                    "4. Review or copy generated measures into your Power BI model.\n"
                ),
            )

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="thoughtspot_powerbi_migration_{migration_id}.zip"'
                )
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to download all artifacts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "DOWNLOAD_ALL_FAILED",
                    "message": "Failed to download migration artifacts",
                    "details": str(e),
                }
            },
        )