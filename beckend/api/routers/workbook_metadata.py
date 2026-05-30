"""
ThoughtSpot Metadata API Router
Provides metadata inspection endpoints for ThoughtSpot -> Power BI migration.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger
from datetime import datetime
import uuid

from storage.migration_store import MigrationStore
from storage.preview_store import PreviewStore


router = APIRouter()

migration_store = MigrationStore()
preview_store = PreviewStore()


# ============================================================
# Request Models
# ============================================================

class ThoughtSpotPreviewRequest(BaseModel):
    """
    Request body for creating a preview from selected ThoughtSpot objects.
    """

    object_ids: List[str]


# ============================================================
# Helper Functions
# ============================================================

def _safe_value(value, default=None):
    """
    Return safe value for None handling.
    """

    return value if value is not None else default


def _get_raw_model(obj):
    """
    Get raw ThoughtSpot model safely from object.
    """

    raw = getattr(obj, "raw_tml", None)

    if raw is None:
        raw = getattr(obj, "raw_model", None)

    if raw is None:
        raw = {}

    return raw


def _get_object_type(obj) -> str:
    """
    Get ThoughtSpot object type as string.
    """

    object_type = getattr(obj, "object_type", "unknown")

    if hasattr(object_type, "value"):
        return object_type.value

    return str(object_type)


def _extract_columns(raw_model: dict) -> List[dict]:
    """
    Extract columns from ThoughtSpot TML/JSON model.
    """

    columns = []

    raw_columns = (
        raw_model.get("columns")
        or raw_model.get("worksheet_columns")
        or raw_model.get("table_columns")
        or []
    )

    for col in raw_columns:
        if isinstance(col, dict):
            columns.append(
                {
                    "name": col.get("name") or col.get("column_name") or col.get("id"),
                    "data_type": col.get("data_type") or col.get("type") or "unknown",
                    "description": col.get("description"),
                    "is_hidden": col.get("is_hidden", False),
                    "is_measure": col.get("is_measure", False),
                    "formula": col.get("formula"),
                }
            )

    return columns


def _extract_formulas(raw_model: dict) -> List[dict]:
    """
    Extract ThoughtSpot formulas/calculated fields.
    """

    formulas = []

    raw_formulas = (
        raw_model.get("formulas")
        or raw_model.get("calculated_fields")
        or raw_model.get("measures")
        or []
    )

    for formula in raw_formulas:
        if isinstance(formula, dict):
            formulas.append(
                {
                    "name": formula.get("name") or formula.get("formula_name"),
                    "expression": formula.get("expr") or formula.get("expression") or formula.get("formula"),
                    "type": formula.get("type", "formula"),
                    "description": formula.get("description"),
                }
            )

    return formulas


def _extract_visuals(raw_model: dict) -> List[dict]:
    """
    Extract Answer/Liveboard visual metadata.
    """

    visuals = []

    raw_visuals = (
        raw_model.get("visualizations")
        or raw_model.get("visuals")
        or raw_model.get("charts")
        or raw_model.get("answers")
        or []
    )

    for visual in raw_visuals:
        if isinstance(visual, dict):
            visuals.append(
                {
                    "name": visual.get("name") or visual.get("title"),
                    "visual_type": visual.get("type") or visual.get("chart_type") or "unknown",
                    "columns": visual.get("columns", []),
                    "measures": visual.get("measures", []),
                    "filters": visual.get("filters", []),
                }
            )

    return visuals


def _extract_filters(raw_model: dict) -> List[dict]:
    """
    Extract filters from ThoughtSpot object.
    """

    filters = []

    raw_filters = raw_model.get("filters") or raw_model.get("filter_groups") or []

    for f in raw_filters:
        if isinstance(f, dict):
            filters.append(
                {
                    "field_name": f.get("field") or f.get("column") or f.get("name"),
                    "filter_type": f.get("type", "unknown"),
                    "operator": f.get("operator"),
                    "values": f.get("values", []),
                }
            )

    return filters


def _extract_relationships(raw_model: dict) -> List[dict]:
    """
    Extract relationships/joins from ThoughtSpot model.
    """

    relationships = []

    raw_relationships = (
        raw_model.get("relationships")
        or raw_model.get("joins")
        or raw_model.get("foreign_keys")
        or []
    )

    for rel in raw_relationships:
        if isinstance(rel, dict):
            relationships.append(
                {
                    "source_table": rel.get("source_table") or rel.get("left_table"),
                    "source_column": rel.get("source_column") or rel.get("left_column"),
                    "target_table": rel.get("target_table") or rel.get("right_table"),
                    "target_column": rel.get("target_column") or rel.get("right_column"),
                    "join_type": rel.get("join_type"),
                    "relationship_type": rel.get("relationship_type"),
                }
            )

    return relationships


def _classify_table(columns: List[dict]) -> dict:
    """
    Basic table classification as FACT or DIMENSION.
    """

    if not columns:
        return {
            "classification": "UNKNOWN",
            "confidence_score": 0,
            "reasoning": "No column metadata available",
        }

    numeric_types = ["int", "integer", "float", "double", "decimal", "number", "real"]
    numeric_count = 0

    for col in columns:
        data_type = str(col.get("data_type", "")).lower()
        if any(t in data_type for t in numeric_types):
            numeric_count += 1

    numeric_density = numeric_count / len(columns)

    if numeric_density >= 0.5:
        return {
            "classification": "FACT",
            "confidence_score": 80,
            "reasoning": f"High numeric column density: {numeric_count}/{len(columns)}",
        }

    return {
        "classification": "DIMENSION",
        "confidence_score": 75,
        "reasoning": f"Low numeric column density: {numeric_count}/{len(columns)}",
    }


# ============================================================
# Metadata Summary
# ============================================================

@router.get("/{migration_id}/thoughtspot-metadata/summary")
async def get_thoughtspot_metadata_summary(migration_id: str):
    """
    Get lightweight ThoughtSpot metadata summary.
    """

    try:
        migration = migration_store.get_migration(migration_id)

        if not migration:
            raise HTTPException(status_code=404, detail="Migration not found")

        objects = migration_store.get_objects_by_migration(migration_id)

        summary_objects = []

        total_tables = 0
        total_worksheets = 0
        total_answers = 0
        total_liveboards = 0
        total_formulas = 0
        total_relationships = 0

        for obj in objects:
            raw_model = _get_raw_model(obj)
            object_type = _get_object_type(obj)

            columns = _extract_columns(raw_model)
            formulas = _extract_formulas(raw_model)
            relationships = _extract_relationships(raw_model)
            visuals = _extract_visuals(raw_model)

            if object_type == "table":
                total_tables += 1
            elif object_type == "worksheet":
                total_worksheets += 1
            elif object_type == "answer":
                total_answers += 1
            elif object_type == "liveboard":
                total_liveboards += 1

            total_formulas += len(formulas)
            total_relationships += len(relationships)

            summary_objects.append(
                {
                    "object_id": obj.object_id,
                    "object_name": obj.object_name,
                    "object_type": object_type,
                    "column_count": len(columns),
                    "formula_count": len(formulas),
                    "relationship_count": len(relationships),
                    "visual_count": len(visuals),
                    "object_guid": getattr(obj, "object_guid", None),
                    "filename": getattr(obj, "filename", None),
                }
            )

        return {
            "migration_id": migration_id,
            "object_count": len(objects),
            "summary": {
                "total_tables": total_tables,
                "total_worksheets": total_worksheets,
                "total_answers": total_answers,
                "total_liveboards": total_liveboards,
                "total_formulas": total_formulas,
                "total_relationships": total_relationships,
            },
            "objects": summary_objects,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get ThoughtSpot metadata summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Complete Metadata
# ============================================================

@router.get("/{migration_id}/thoughtspot-metadata")
async def get_comprehensive_thoughtspot_metadata(migration_id: str):
    """
    Get complete ThoughtSpot metadata for migration review.

    Returns:
    - objects
    - columns
    - formulas
    - relationships
    - filters
    - visuals
    """

    try:
        migration = migration_store.get_migration(migration_id)

        if not migration:
            raise HTTPException(status_code=404, detail="Migration not found")

        objects = migration_store.get_objects_by_migration(migration_id)

        metadata_objects = []

        total_columns = 0
        total_formulas = 0
        total_relationships = 0
        total_filters = 0
        total_visuals = 0

        for obj in objects:
            raw_model = _get_raw_model(obj)
            object_type = _get_object_type(obj)

            columns = _extract_columns(raw_model)
            formulas = _extract_formulas(raw_model)
            relationships = _extract_relationships(raw_model)
            filters = _extract_filters(raw_model)
            visuals = _extract_visuals(raw_model)

            total_columns += len(columns)
            total_formulas += len(formulas)
            total_relationships += len(relationships)
            total_filters += len(filters)
            total_visuals += len(visuals)

            metadata_objects.append(
                {
                    "object_id": obj.object_id,
                    "object_name": obj.object_name,
                    "object_type": object_type,
                    "object_guid": getattr(obj, "object_guid", None),
                    "filename": getattr(obj, "filename", None),
                    "columns": columns,
                    "formulas": formulas,
                    "relationships": relationships,
                    "filters": filters,
                    "visuals": visuals,
                    "raw_model": raw_model,
                }
            )

        return {
            "migration_id": migration_id,
            "objects": metadata_objects,
            "summary": {
                "total_objects": len(objects),
                "total_columns": total_columns,
                "total_formulas": total_formulas,
                "total_relationships": total_relationships,
                "total_filters": total_filters,
                "total_visuals": total_visuals,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get ThoughtSpot metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Object Details
# ============================================================

@router.get("/{migration_id}/thoughtspot-metadata/objects")
async def get_all_thoughtspot_objects(
    migration_id: str,
    object_type: Optional[str] = None,
):
    """
    Get all ThoughtSpot objects from migration.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)

        if object_type:
            objects = [
                obj for obj in objects
                if _get_object_type(obj) == object_type
            ]

        return {
            "objects": [
                {
                    "object_id": obj.object_id,
                    "object_name": obj.object_name,
                    "object_type": _get_object_type(obj),
                    "object_guid": getattr(obj, "object_guid", None),
                    "filename": getattr(obj, "filename", None),
                }
                for obj in objects
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get ThoughtSpot objects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{migration_id}/thoughtspot-metadata/objects/{object_id}")
async def get_thoughtspot_object_detail(
    migration_id: str,
    object_id: str,
):
    """
    Get detailed metadata for one ThoughtSpot object.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)
        obj = next((item for item in objects if item.object_id == object_id), None)

        if not obj:
            raise HTTPException(status_code=404, detail="ThoughtSpot object not found")

        raw_model = _get_raw_model(obj)

        return {
            "object_id": obj.object_id,
            "object_name": obj.object_name,
            "object_type": _get_object_type(obj),
            "object_guid": getattr(obj, "object_guid", None),
            "columns": _extract_columns(raw_model),
            "formulas": _extract_formulas(raw_model),
            "relationships": _extract_relationships(raw_model),
            "filters": _extract_filters(raw_model),
            "visuals": _extract_visuals(raw_model),
            "raw_model": raw_model,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get ThoughtSpot object detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Columns / Formulas / Visuals / Filters
# ============================================================

@router.get("/{migration_id}/thoughtspot-metadata/columns")
async def get_all_columns(migration_id: str):
    """
    Get all columns from ThoughtSpot objects.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)

        all_columns = []

        for obj in objects:
            raw_model = _get_raw_model(obj)
            columns = _extract_columns(raw_model)

            for col in columns:
                all_columns.append(
                    {
                        **col,
                        "object_id": obj.object_id,
                        "object_name": obj.object_name,
                        "object_type": _get_object_type(obj),
                    }
                )

        return {"columns": all_columns}

    except Exception as e:
        logger.error(f"Failed to get columns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{migration_id}/thoughtspot-metadata/formulas")
async def get_all_formulas(migration_id: str):
    """
    Get all formulas/calculated fields from ThoughtSpot objects.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)

        all_formulas = []

        for obj in objects:
            raw_model = _get_raw_model(obj)
            formulas = _extract_formulas(raw_model)

            for formula in formulas:
                all_formulas.append(
                    {
                        **formula,
                        "object_id": obj.object_id,
                        "object_name": obj.object_name,
                        "object_type": _get_object_type(obj),
                    }
                )

        return {"formulas": all_formulas}

    except Exception as e:
        logger.error(f"Failed to get formulas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{migration_id}/thoughtspot-metadata/visuals")
async def get_all_visuals(migration_id: str):
    """
    Get all visuals from ThoughtSpot Answers/Liveboards.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)

        all_visuals = []

        for obj in objects:
            raw_model = _get_raw_model(obj)
            visuals = _extract_visuals(raw_model)

            for visual in visuals:
                all_visuals.append(
                    {
                        **visual,
                        "object_id": obj.object_id,
                        "object_name": obj.object_name,
                        "object_type": _get_object_type(obj),
                    }
                )

        return {"visuals": all_visuals}

    except Exception as e:
        logger.error(f"Failed to get visuals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{migration_id}/thoughtspot-metadata/filters")
async def get_all_filters(migration_id: str):
    """
    Get all filters from ThoughtSpot objects.
    """

    try:
        objects = migration_store.get_objects_by_migration(migration_id)

        all_filters = []

        for obj in objects:
            raw_model = _get_raw_model(obj)
            filters = _extract_filters(raw_model)

            for f in filters:
                all_filters.append(
                    {
                        **f,
                        "object_id": obj.object_id,
                        "object_name": obj.object_name,
                        "object_type": _get_object_type(obj),
                    }
                )

        return {"filters": all_filters}

    except Exception as e:
        logger.error(f"Failed to get filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Model Intelligence
# ============================================================

@router.get("/{migration_id}/thoughtspot-metadata/model-intelligence")
async def get_model_intelligence(migration_id: str):
    """
    Get basic model intelligence for ThoughtSpot objects.

    Classifies objects/tables as FACT, DIMENSION, or REPORT_OBJECT.
    """

    try:
        migration = migration_store.get_migration(migration_id)

        if not migration:
            raise HTTPException(status_code=404, detail="Migration not found")

        objects = migration_store.get_objects_by_migration(migration_id)

        result = {
            "objects": [],
            "summary": {
                "total_objects": 0,
                "fact_tables": 0,
                "dimension_tables": 0,
                "report_objects": 0,
            },
        }

        for obj in objects:
            raw_model = _get_raw_model(obj)
            object_type = _get_object_type(obj)
            columns = _extract_columns(raw_model)

            if object_type in ["answer", "liveboard"]:
                classification = {
                    "classification": "REPORT_OBJECT",
                    "confidence_score": 90,
                    "reasoning": "ThoughtSpot Answer/Liveboard is a reporting object",
                }
                result["summary"]["report_objects"] += 1
            else:
                classification = _classify_table(columns)

                if classification["classification"] == "FACT":
                    result["summary"]["fact_tables"] += 1
                elif classification["classification"] == "DIMENSION":
                    result["summary"]["dimension_tables"] += 1

            result["objects"].append(
                {
                    "object_id": obj.object_id,
                    "object_name": obj.object_name,
                    "object_type": object_type,
                    "column_count": len(columns),
                    "classification": classification["classification"],
                    "confidence_score": classification["confidence_score"],
                    "reasoning": classification["reasoning"],
                }
            )

        result["summary"]["total_objects"] = len(result["objects"])

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get model intelligence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Preview
# ============================================================

@router.post("/{migration_id}/thoughtspot-preview")
async def create_thoughtspot_preview(
    migration_id: str,
    request: ThoughtSpotPreviewRequest,
):
    """
    Create preview session from selected ThoughtSpot objects.
    """

    try:
        object_ids = request.object_ids

        if not object_ids:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_OBJECT_SELECTION",
                        "message": "At least one ThoughtSpot object is required",
                    }
                },
            )

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

        objects = migration_store.get_objects_by_migration(migration_id)

        selected_objects = [
            obj for obj in objects
            if obj.object_id in object_ids
        ]

        if not selected_objects:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "OBJECTS_NOT_FOUND",
                        "message": "No selected ThoughtSpot objects were found",
                    }
                },
            )

        preview_id = f"preview_{uuid.uuid4().hex[:12]}"

        preview_store.create_preview_session(
            preview_id=preview_id,
            file_count=len(selected_objects),
            total_duplicates_detected=0,
        )

        files_preview = []

        for obj in selected_objects:
            raw_model = _get_raw_model(obj)
            columns = _extract_columns(raw_model)

            files_preview.append(
                {
                    "file_id": obj.object_id,
                    "filename": getattr(obj, "filename", obj.object_name),
                    "object_name": obj.object_name,
                    "object_type": _get_object_type(obj),
                    "column_count": len(columns),
                    "columns": columns,
                    "duplicate_groups": [],
                }
            )

        return {
            "preview_id": preview_id,
            "status": "ready",
            "created_at": datetime.utcnow().isoformat(),
            "object_count": len(files_preview),
            "objects": files_preview,
            "total_duplicates_detected": 0,
            "message": f"Preview created successfully with {len(files_preview)} ThoughtSpot objects",
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to create ThoughtSpot preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "THOUGHTSPOT_PREVIEW_FAILED",
                    "message": "Failed to create ThoughtSpot preview",
                    "details": str(e),
                }
            },
        )