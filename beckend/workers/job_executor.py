"""
Background migration worker for ThoughtSpot -> Power BI Migration Tool.

This worker handles:
- ThoughtSpot file parsing
- TML/YAML/JSON/ZIP metadata extraction
- ThoughtSpot object extraction
- Formula extraction
- Relationship extraction
- ThoughtSpot formula to DAX conversion
- Power BI artifact/result generation
- Job and migration progress updates
- WebSocket progress broadcasts
"""

import asyncio
import json
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

try:
    import yaml
except Exception:
    yaml = None

try:
    import pandas as pd
except Exception:
    pd = None

from api.utils import (
    generate_migration_id,
    generate_thoughtspot_object_id,
    generate_formula_id,
    generate_relationship_id,
    generate_conversion_id,
)

try:
    from api.models.api_models import JobStatus
except Exception:
    from api.models.migration_models import JobStatus

from api.models.migration_models import (
    MigrationStatus,
    ThoughtSpotObject,
    ThoughtSpotFormula,
    ThoughtSpotRelationship,
    PowerBIConversion,
    ConversionMethod,
    ConversionStatus,
)

try:
    from api.models.migration_models import ThoughtSpotObjectType
except Exception:
    ThoughtSpotObjectType = None

try:
    from api.models.migration_models import FormulaType
except Exception:
    FormulaType = None

from storage.job_store import JobStore
from storage.result_store import ResultStore
from storage.migration_store import MigrationStore
from workers.websocket_manager import ws_manager


# Thread pool for background migration jobs
executor = ThreadPoolExecutor(max_workers=3)


# ============================================================
# Enum / Value Helpers
# ============================================================

def _enum_value(value):
    """
    Return enum value if value is Enum, otherwise return the original value.
    """

    if hasattr(value, "value"):
        return value.value

    return value


def _safe_enum(enum_cls, value: str, default=None):
    """
    Safely convert string to enum member.

    If enum class is not available or value is invalid, return default or string.
    """

    if enum_cls is None:
        return default if default is not None else value

    try:
        return enum_cls(value)
    except Exception:
        try:
            return enum_cls[value.upper()]
        except Exception:
            return default if default is not None else value


def _status_value(status):
    """
    Return status value safely.
    """

    return status.value if hasattr(status, "value") else str(status)


# ============================================================
# WebSocket Broadcast Helpers
# ============================================================

def _run_async_broadcast(coro):
    """
    Run async websocket broadcast from sync worker code.
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
        logger.error(f"WebSocket broadcast failed: {e}", exc_info=True)


def _broadcast_progress(
    channel_id: str,
    progress_percent: int,
    current_stage: str,
    message: str,
    extra_data: Optional[Dict[str, Any]] = None,
):
    """
    Broadcast progress to websocket clients.
    """

    data = {
        "progress_percent": progress_percent,
        "current_stage": current_stage,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if extra_data:
        data.update(extra_data)

    if hasattr(ws_manager, "broadcast_progress"):
        _run_async_broadcast(
            ws_manager.broadcast_progress(
                channel_id,
                progress_percent,
                current_stage,
                message,
                data,
            )
        )
    elif hasattr(ws_manager, "broadcast_to_job"):
        _run_async_broadcast(
            ws_manager.broadcast_to_job(
                channel_id,
                {
                    "type": "progress",
                    "job_id": channel_id,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        )


def _broadcast_completion(
    channel_id: str,
    summary: Dict[str, Any],
):
    """
    Broadcast migration completion.
    """

    if hasattr(ws_manager, "broadcast_completion"):
        try:
            _run_async_broadcast(
                ws_manager.broadcast_completion(
                    channel_id,
                    summary.get("relationship_count", 0),
                )
            )
            return
        except Exception:
            pass

    if hasattr(ws_manager, "broadcast_to_job"):
        _run_async_broadcast(
            ws_manager.broadcast_to_job(
                channel_id,
                {
                    "type": "completed",
                    "job_id": channel_id,
                    "data": summary,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        )


def _broadcast_error(
    channel_id: str,
    error_message: str,
):
    """
    Broadcast migration error.
    """

    if hasattr(ws_manager, "broadcast_error"):
        try:
            _run_async_broadcast(
                ws_manager.broadcast_error(channel_id, error_message)
            )
            return
        except Exception:
            pass

    if hasattr(ws_manager, "broadcast_to_job"):
        _run_async_broadcast(
            ws_manager.broadcast_to_job(
                channel_id,
                {
                    "type": "error",
                    "job_id": channel_id,
                    "data": {
                        "error": error_message,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        )


# ============================================================
# File Parsing Helpers
# ============================================================

def _load_text_file(file_path: Path) -> str:
    """
    Read a text file using UTF-8 fallback.
    """

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="latin-1")


def _load_json_or_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load JSON/YAML/TML file into dictionary.
    """

    suffix = file_path.suffix.lower()
    text = _load_text_file(file_path)

    if suffix == ".json":
        return json.loads(text)

    if suffix in [".yaml", ".yml", ".tml"]:
        if yaml is None:
            raise RuntimeError(
                "PyYAML is not installed. Please install it using: pip install pyyaml"
            )

        loaded = yaml.safe_load(text)

        if loaded is None:
            return {}

        if isinstance(loaded, dict):
            return loaded

        return {
            "content": loaded,
        }

    return {
        "raw_text": text,
    }


def _load_csv_or_excel_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Load basic metadata from CSV or Excel file.

    This does not convert data itself. It only extracts table-like metadata
    for migration preview and Power BI semantic model preparation.
    """

    if pd is None:
        return {
            "name": file_path.stem,
            "type": "table",
            "columns": [],
            "warning": "pandas is not installed, column metadata could not be extracted",
        }

    suffix = file_path.suffix.lower()

    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path, nrows=100)
        elif suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path, nrows=100)
        else:
            return {}

        columns = []

        for column_name in df.columns:
            columns.append(
                {
                    "name": str(column_name),
                    "data_type": str(df[column_name].dtype),
                    "is_measure": False,
                    "is_hidden": False,
                }
            )

        return {
            "name": file_path.stem,
            "type": "table",
            "columns": columns,
            "row_sample_count": len(df),
        }

    except Exception as e:
        logger.warning(f"Failed to read tabular metadata from {file_path}: {e}")

        return {
            "name": file_path.stem,
            "type": "table",
            "columns": [],
            "parse_error": str(e),
        }


def _extract_zip_files(zip_path: Path) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Extract supported ThoughtSpot files from ZIP and return parsed models.

    Returns:
        List of tuples: (filename, parsed_model)
    """

    parsed_files = []

    supported_extensions = {
        ".tml",
        ".yaml",
        ".yml",
        ".json",
        ".csv",
        ".xlsx",
        ".xls",
    }

    extract_dir = zip_path.parent / f"{zip_path.stem}_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    for extracted_file in extract_dir.rglob("*"):
        if not extracted_file.is_file():
            continue

        if extracted_file.suffix.lower() not in supported_extensions:
            continue

        try:
            if extracted_file.suffix.lower() in [".csv", ".xlsx", ".xls"]:
                parsed = _load_csv_or_excel_metadata(extracted_file)
            else:
                parsed = _load_json_or_yaml(extracted_file)

            parsed_files.append(
                (
                    str(extracted_file.relative_to(extract_dir)),
                    parsed,
                )
            )

        except Exception as e:
            logger.warning(f"Failed to parse file inside ZIP {extracted_file}: {e}")

            parsed_files.append(
                (
                    str(extracted_file.relative_to(extract_dir)),
                    {
                        "name": extracted_file.stem,
                        "type": "unknown",
                        "parse_error": str(e),
                    },
                )
            )

    return parsed_files


def parse_thoughtspot_files(file_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Parse uploaded ThoughtSpot files.

    Supported:
    - .tml
    - .yaml
    - .yml
    - .json
    - .zip
    - .csv
    - .xlsx
    - .xls

    Returns:
        List of parsed object dictionaries.
    """

    parsed_objects = []

    for path in file_paths:
        file_path = Path(path)

        if not file_path.exists():
            logger.warning(f"Uploaded file does not exist: {file_path}")
            continue

        suffix = file_path.suffix.lower()

        try:
            if suffix == ".zip":
                zip_models = _extract_zip_files(file_path)

                for filename, raw_model in zip_models:
                    parsed_objects.append(
                        {
                            "filename": filename,
                            "file_path": str(file_path),
                            "raw_model": raw_model,
                        }
                    )

            elif suffix in [".csv", ".xlsx", ".xls"]:
                raw_model = _load_csv_or_excel_metadata(file_path)

                parsed_objects.append(
                    {
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "raw_model": raw_model,
                    }
                )

            else:
                raw_model = _load_json_or_yaml(file_path)

                parsed_objects.append(
                    {
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "raw_model": raw_model,
                    }
                )

        except Exception as e:
            logger.error(f"Failed to parse ThoughtSpot file {file_path}: {e}", exc_info=True)

            parsed_objects.append(
                {
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "raw_model": {
                        "name": file_path.stem,
                        "type": "unknown",
                        "parse_error": str(e),
                    },
                }
            )

    return parsed_objects


# ============================================================
# ThoughtSpot Metadata Extraction
# ============================================================

def _detect_object_name(raw_model: Dict[str, Any], filename: str) -> str:
    """
    Detect ThoughtSpot object name from raw model.
    """

    possible_keys = [
        "name",
        "display_name",
        "title",
        "worksheet_name",
        "answer_name",
        "liveboard_name",
        "table_name",
        "connection_name",
    ]

    for key in possible_keys:
        value = raw_model.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # Some TML files contain nested object sections
    for section_name in ["worksheet", "answer", "liveboard", "table", "connection"]:
        section = raw_model.get(section_name)

        if isinstance(section, dict):
            for key in possible_keys:
                value = section.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return Path(filename).stem


def _detect_object_type(raw_model: Dict[str, Any], filename: str) -> str:
    """
    Detect ThoughtSpot object type from raw model or filename.
    """

    explicit_type = (
        raw_model.get("type")
        or raw_model.get("object_type")
        or raw_model.get("metadata_type")
    )

    if isinstance(explicit_type, str):
        normalized = explicit_type.lower()

        if normalized in ["table", "worksheet", "answer", "liveboard", "connection"]:
            return normalized

    for section_name in ["worksheet", "answer", "liveboard", "table", "connection"]:
        if section_name in raw_model:
            return section_name

    filename_lower = filename.lower()

    if "worksheet" in filename_lower:
        return "worksheet"

    if "answer" in filename_lower:
        return "answer"

    if "liveboard" in filename_lower or "dashboard" in filename_lower:
        return "liveboard"

    if "connection" in filename_lower:
        return "connection"

    if "table" in filename_lower:
        return "table"

    return "unknown"


def _detect_object_guid(raw_model: Dict[str, Any]) -> Optional[str]:
    """
    Detect ThoughtSpot object GUID.
    """

    possible_keys = [
        "guid",
        "id",
        "object_guid",
        "object_id",
        "worksheet_id",
        "answer_id",
        "liveboard_id",
        "table_id",
    ]

    for key in possible_keys:
        value = raw_model.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    for section_name in ["worksheet", "answer", "liveboard", "table", "connection"]:
        section = raw_model.get(section_name)

        if isinstance(section, dict):
            for key in possible_keys:
                value = section.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return None


def _extract_columns(raw_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract columns from ThoughtSpot object model.
    """

    columns = []

    candidate_lists = [
        raw_model.get("columns"),
        raw_model.get("worksheet_columns"),
        raw_model.get("table_columns"),
        raw_model.get("fields"),
    ]

    for section_name in ["worksheet", "table", "answer"]:
        section = raw_model.get(section_name)
        if isinstance(section, dict):
            candidate_lists.extend(
                [
                    section.get("columns"),
                    section.get("worksheet_columns"),
                    section.get("table_columns"),
                    section.get("fields"),
                ]
            )

    for raw_columns in candidate_lists:
        if not isinstance(raw_columns, list):
            continue

        for col in raw_columns:
            if isinstance(col, str):
                columns.append(
                    {
                        "name": col,
                        "data_type": "unknown",
                        "is_measure": False,
                        "is_hidden": False,
                    }
                )

            elif isinstance(col, dict):
                columns.append(
                    {
                        "name": (
                            col.get("name")
                            or col.get("column_name")
                            or col.get("id")
                            or col.get("display_name")
                        ),
                        "data_type": (
                            col.get("data_type")
                            or col.get("type")
                            or col.get("column_type")
                            or "unknown"
                        ),
                        "is_measure": bool(col.get("is_measure", False)),
                        "is_hidden": bool(col.get("is_hidden", False)),
                        "formula": col.get("formula") or col.get("expr"),
                    }
                )

    # Remove invalid/empty column names
    columns = [col for col in columns if col.get("name")]

    return columns


def _extract_formulas(raw_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract formulas/calculated fields from ThoughtSpot model.
    """

    formulas = []

    candidate_lists = [
        raw_model.get("formulas"),
        raw_model.get("calculated_fields"),
        raw_model.get("measures"),
        raw_model.get("derived_columns"),
    ]

    for section_name in ["worksheet", "answer", "liveboard", "table"]:
        section = raw_model.get(section_name)
        if isinstance(section, dict):
            candidate_lists.extend(
                [
                    section.get("formulas"),
                    section.get("calculated_fields"),
                    section.get("measures"),
                    section.get("derived_columns"),
                ]
            )

    for raw_formulas in candidate_lists:
        if not isinstance(raw_formulas, list):
            continue

        for formula in raw_formulas:
            if isinstance(formula, dict):
                name = (
                    formula.get("name")
                    or formula.get("formula_name")
                    or formula.get("display_name")
                    or formula.get("id")
                )

                expression = (
                    formula.get("expr")
                    or formula.get("expression")
                    or formula.get("formula")
                    or formula.get("sql")
                )

                if name and expression:
                    formulas.append(
                        {
                            "name": name,
                            "expression": expression,
                            "type": formula.get("type", "formula"),
                            "description": formula.get("description"),
                            "depends_on": formula.get("depends_on", []),
                        }
                    )

    # Also treat columns with formula expression as formulas
    for col in _extract_columns(raw_model):
        if col.get("formula"):
            formulas.append(
                {
                    "name": col["name"],
                    "expression": col["formula"],
                    "type": "column",
                    "description": None,
                    "depends_on": [],
                }
            )

    return formulas


def _extract_relationships(raw_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract ThoughtSpot relationships/joins from model.
    """

    relationships = []

    candidate_lists = [
        raw_model.get("relationships"),
        raw_model.get("joins"),
        raw_model.get("foreign_keys"),
    ]

    for section_name in ["worksheet", "table", "connection"]:
        section = raw_model.get(section_name)
        if isinstance(section, dict):
            candidate_lists.extend(
                [
                    section.get("relationships"),
                    section.get("joins"),
                    section.get("foreign_keys"),
                ]
            )

    for raw_relationships in candidate_lists:
        if not isinstance(raw_relationships, list):
            continue

        for rel in raw_relationships:
            if not isinstance(rel, dict):
                continue

            source_table = (
                rel.get("source_table")
                or rel.get("left_table")
                or rel.get("from_table")
            )

            source_column = (
                rel.get("source_column")
                or rel.get("left_column")
                or rel.get("from_column")
            )

            target_table = (
                rel.get("target_table")
                or rel.get("right_table")
                or rel.get("to_table")
            )

            target_column = (
                rel.get("target_column")
                or rel.get("right_column")
                or rel.get("to_column")
            )

            if source_table and source_column and target_table and target_column:
                relationships.append(
                    {
                        "source_table": source_table,
                        "source_column": source_column,
                        "target_table": target_table,
                        "target_column": target_column,
                        "join_type": rel.get("join_type") or rel.get("type"),
                        "powerbi_cardinality": _map_cardinality(rel),
                    }
                )

    return relationships


def _extract_visual_count(raw_model: Dict[str, Any]) -> int:
    """
    Count visuals/charts from Answer or Liveboard metadata.
    """

    total = 0

    candidate_lists = [
        raw_model.get("visualizations"),
        raw_model.get("visuals"),
        raw_model.get("charts"),
        raw_model.get("answers"),
    ]

    for section_name in ["answer", "liveboard"]:
        section = raw_model.get(section_name)
        if isinstance(section, dict):
            candidate_lists.extend(
                [
                    section.get("visualizations"),
                    section.get("visuals"),
                    section.get("charts"),
                    section.get("answers"),
                ]
            )

    for candidate in candidate_lists:
        if isinstance(candidate, list):
            total += len(candidate)

    return total


def _map_cardinality(relationship: Dict[str, Any]) -> str:
    """
    Map ThoughtSpot relationship information to Power BI cardinality.
    """

    cardinality = (
        relationship.get("cardinality")
        or relationship.get("relationship_type")
        or ""
    )

    cardinality = str(cardinality).lower()

    if "many_to_one" in cardinality or "many-to-one" in cardinality:
        return "many-to-one"

    if "one_to_many" in cardinality or "one-to-many" in cardinality:
        return "one-to-many"

    if "one_to_one" in cardinality or "one-to-one" in cardinality:
        return "one-to-one"

    if "many_to_many" in cardinality or "many-to-many" in cardinality:
        return "many-to-many"

    return "many-to-one"


# ============================================================
# DAX Conversion
# ============================================================

def convert_thoughtspot_formula_to_dax(
    formula_name: str,
    expression: str,
) -> Tuple[str, float, str, List[str]]:
    """
    Convert a ThoughtSpot formula expression to a Power BI DAX expression.

    This is a safe rule-based starter converter.
    Later you can connect an LLM converter here.

    Returns:
        dax_formula, confidence_score, reasoning, warnings
    """

    if not expression:
        return "", 0.0, "Empty formula expression", ["Formula expression is empty"]

    dax = str(expression).strip()
    warnings = []

    replacements = [
        ("ifnull", "COALESCE"),
        ("isnull", "ISBLANK"),
        ("count_distinct", "DISTINCTCOUNT"),
        ("distinct_count", "DISTINCTCOUNT"),
        ("sum", "SUM"),
        ("avg", "AVERAGE"),
        ("average", "AVERAGE"),
        ("min", "MIN"),
        ("max", "MAX"),
        ("count", "COUNT"),
        ("year", "YEAR"),
        ("month", "MONTH"),
        ("day", "DAY"),
        ("date_diff", "DATEDIFF"),
    ]

    for source_func, dax_func in replacements:
        dax = dax.replace(f"{source_func}(", f"{dax_func}(")
        dax = dax.replace(f"{source_func.upper()}(", f"{dax_func}(")

    # ThoughtSpot often uses single equals in conditions.
    # DAX also supports =, so keep it unchanged.

    # Quote measure name as DAX measure.
    safe_measure_name = (
        formula_name.replace("[", "")
        .replace("]", "")
        .replace("\n", " ")
        .strip()
    )

    if not safe_measure_name:
        safe_measure_name = "Migrated Measure"

    dax_formula = f"{safe_measure_name} = {dax}"

    lower_expr = expression.lower()

    unsupported_markers = [
        "moving_average",
        "group_aggregate",
        "query_groups",
        "rank",
        "percentile",
        "growth",
    ]

    for marker in unsupported_markers:
        if marker in lower_expr:
            warnings.append(
                f"ThoughtSpot function or pattern '{marker}' may require manual DAX review"
            )

    confidence = 0.85 if not warnings else 0.65

    reasoning = (
        "Converted using rule-based ThoughtSpot to DAX mapping. "
        "Review recommended before publishing to Power BI."
    )

    return dax_formula, confidence, reasoning, warnings


# ============================================================
# Object Persistence
# ============================================================

def _create_thoughtspot_object(
    migration_id: str,
    filename: str,
    file_path: str,
    raw_model: Dict[str, Any],
) -> ThoughtSpotObject:
    """
    Create ThoughtSpotObject model from parsed metadata.
    """

    object_type_value = _detect_object_type(raw_model, filename)
    object_type = _safe_enum(
        ThoughtSpotObjectType,
        object_type_value,
        object_type_value,
    )

    columns = _extract_columns(raw_model)
    formulas = _extract_formulas(raw_model)
    relationships = _extract_relationships(raw_model)
    visual_count = _extract_visual_count(raw_model)

    return ThoughtSpotObject(
        object_id=generate_thoughtspot_object_id(),
        migration_id=migration_id,
        object_name=_detect_object_name(raw_model, filename),
        object_type=object_type,
        filename=filename,
        file_path=file_path,
        object_guid=_detect_object_guid(raw_model),
        column_count=len(columns),
        formula_count=len(formulas),
        relationship_count=len(relationships),
        visual_count=visual_count,
        raw_tml=raw_model,
        extracted_at=datetime.utcnow(),
    )


def _create_formula(
    object_id: str,
    formula_data: Dict[str, Any],
) -> ThoughtSpotFormula:
    """
    Create ThoughtSpotFormula model from formula metadata.
    """

    formula_type_value = formula_data.get("type", "formula")

    formula_type = _safe_enum(
        FormulaType,
        formula_type_value,
        formula_type_value,
    )

    return ThoughtSpotFormula(
        formula_id=generate_formula_id(),
        object_id=object_id,
        formula_name=formula_data.get("name") or "Unnamed Formula",
        formula_expression=formula_data.get("expression") or "",
        formula_type=formula_type,
        visual_context={
            "description": formula_data.get("description"),
        },
        dependency_level=0,
        depends_on=formula_data.get("depends_on", []),
        depends_on_metadata={},
        used_in_answers=[],
        used_in_liveboards=[],
        created_at=datetime.utcnow(),
    )


def _create_relationship(
    migration_id: str,
    relationship_data: Dict[str, Any],
) -> ThoughtSpotRelationship:
    """
    Create ThoughtSpotRelationship model from relationship metadata.
    """

    return ThoughtSpotRelationship(
        relationship_id=generate_relationship_id(),
        migration_id=migration_id,
        source_table=relationship_data.get("source_table"),
        source_column=relationship_data.get("source_column"),
        target_table=relationship_data.get("target_table"),
        target_column=relationship_data.get("target_column"),
        join_type=relationship_data.get("join_type"),
        powerbi_cardinality=relationship_data.get("powerbi_cardinality", "many-to-one"),
        is_active=True,
        created_at=datetime.utcnow(),
    )


def _create_conversion(
    migration_id: str,
    formula: ThoughtSpotFormula,
) -> PowerBIConversion:
    """
    Create PowerBIConversion model from ThoughtSpot formula.
    """

    dax_formula, confidence, reasoning, warnings = convert_thoughtspot_formula_to_dax(
        formula_name=formula.formula_name,
        expression=formula.formula_expression,
    )

    status = (
        ConversionStatus.PENDING
        if confidence >= 0.7
        else ConversionStatus.MANUAL_REVIEW
    )

    return PowerBIConversion(
        conversion_id=generate_conversion_id(),
        source_formula_id=formula.formula_id,
        migration_id=migration_id,
        dax_formula=dax_formula,
        conversion_method=ConversionMethod.RULE_BASED,
        confidence_score=confidence,
        reasoning=reasoning,
        warnings=warnings,
        status=status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        target_powerbi_object_type="semantic_model",
        target_powerbi_object_id=None,
        target_powerbi_object_name=formula.formula_name,
    )


# ============================================================
# Main Worker
# ============================================================

def execute_thoughtspot_powerbi_migration(
    job_id: str,
    file_paths: List[str],
):
    """
    Execute ThoughtSpot -> Power BI migration in background.

    This function supports two call styles:

    1. From jobs router:
        execute_thoughtspot_powerbi_migration(job_id="job_xxx", file_paths=[...])

    2. From migration router:
        execute_thoughtspot_powerbi_migration(job_id="migration_xxx", file_paths=[...])

    Args:
        job_id: Job ID or migration ID.
        file_paths: Uploaded ThoughtSpot file paths.
    """

    job_store = JobStore()
    result_store = ResultStore()
    migration_store = MigrationStore()

    is_job_call = str(job_id).startswith("job_")
    is_migration_call = str(job_id).startswith("migration_")

    migration_id = job_id if is_migration_call else generate_migration_id()

    websocket_channel_id = job_id

    saved_objects = []
    saved_formulas = []
    saved_relationships = []
    saved_conversions = []

    try:
        logger.info(
            f"Starting ThoughtSpot -> Power BI migration. "
            f"job_id={job_id}, migration_id={migration_id}, files={len(file_paths)}"
        )

        # --------------------------------------------------------
        # Initialize job/migration state
        # --------------------------------------------------------

        if is_job_call:
            job_store.update_status(job_id, JobStatus.RUNNING)
            job_store.update_progress(
                job_id=job_id,
                percent=5,
                stage="initializing",
                message="Initializing ThoughtSpot to Power BI migration",
            )

        if not migration_store.migration_exists(migration_id):
            migration_store.create_migration(
                migration_id=migration_id,
                job_id=job_id if is_job_call else None,
            )

        migration_store.update_migration_status(
            migration_id=migration_id,
            status=MigrationStatus.PARSING,
            current_stage="Parsing ThoughtSpot files",
        )

        migration_store.update_migration_progress(
            migration_id=migration_id,
            progress_percent=5,
            current_stage="parsing",
            message="Parsing uploaded ThoughtSpot files",
        )

        _broadcast_progress(
            websocket_channel_id,
            5,
            "parsing",
            "Parsing uploaded ThoughtSpot files",
            {
                "migration_id": migration_id,
                "file_count": len(file_paths),
            },
        )

        # --------------------------------------------------------
        # Parse files
        # --------------------------------------------------------

        parsed_items = parse_thoughtspot_files(file_paths)

        if not parsed_items:
            raise RuntimeError("No valid ThoughtSpot objects found in uploaded files")

        migration_store.update_migration_progress(
            migration_id=migration_id,
            progress_percent=20,
            current_stage="extracting_metadata",
            message=f"Extracted metadata from {len(parsed_items)} file/object(s)",
        )

        if is_job_call:
            job_store.update_progress(
                job_id=job_id,
                percent=20,
                stage="extracting_metadata",
                message=f"Extracted metadata from {len(parsed_items)} file/object(s)",
            )

        _broadcast_progress(
            websocket_channel_id,
            20,
            "extracting_metadata",
            f"Extracted metadata from {len(parsed_items)} file/object(s)",
            {
                "migration_id": migration_id,
                "object_count": len(parsed_items),
            },
        )

        # --------------------------------------------------------
        # Save ThoughtSpot objects, formulas, relationships
        # --------------------------------------------------------

        migration_store.update_migration_status(
            migration_id=migration_id,
            status=MigrationStatus.DISCOVERING,
            current_stage="Discovering ThoughtSpot objects",
        )

        for item in parsed_items:
            filename = item["filename"]
            file_path = item["file_path"]
            raw_model = item["raw_model"] or {}

            ts_object = _create_thoughtspot_object(
                migration_id=migration_id,
                filename=filename,
                file_path=file_path,
                raw_model=raw_model,
            )

            migration_store.save_object(ts_object)
            saved_objects.append(ts_object)

            formulas_data = _extract_formulas(raw_model)

            for formula_data in formulas_data:
                formula = _create_formula(
                    object_id=ts_object.object_id,
                    formula_data=formula_data,
                )

                migration_store.save_formula(formula)
                saved_formulas.append(formula)

            relationships_data = _extract_relationships(raw_model)

            for relationship_data in relationships_data:
                relationship = _create_relationship(
                    migration_id=migration_id,
                    relationship_data=relationship_data,
                )

                migration_store.save_relationship(relationship)
                saved_relationships.append(relationship)

        migration_store.update_migration_counts(
            migration_id=migration_id,
            object_count=len(saved_objects),
            formula_count=len(saved_formulas),
            relationship_count=len(saved_relationships),
            report_count=sum(
                1
                for obj in saved_objects
                if _enum_value(obj.object_type) in ["answer", "liveboard"]
            ),
            dashboard_count=sum(
                1
                for obj in saved_objects
                if _enum_value(obj.object_type) == "liveboard"
            ),
        )

        if is_job_call:
            job_store.update_progress(
                job_id=job_id,
                percent=45,
                stage="metadata_discovered",
                message=(
                    f"Discovered {len(saved_objects)} objects, "
                    f"{len(saved_formulas)} formulas, "
                    f"{len(saved_relationships)} relationships"
                ),
            )

        migration_store.update_migration_progress(
            migration_id=migration_id,
            progress_percent=45,
            current_stage="metadata_discovered",
            message=(
                f"Discovered {len(saved_objects)} objects, "
                f"{len(saved_formulas)} formulas, "
                f"{len(saved_relationships)} relationships"
            ),
        )

        _broadcast_progress(
            websocket_channel_id,
            45,
            "metadata_discovered",
            "ThoughtSpot metadata discovery completed",
            {
                "migration_id": migration_id,
                "object_count": len(saved_objects),
                "formula_count": len(saved_formulas),
                "relationship_count": len(saved_relationships),
            },
        )

        # --------------------------------------------------------
        # Convert formulas to DAX
        # --------------------------------------------------------

        migration_store.update_migration_status(
            migration_id=migration_id,
            status=MigrationStatus.CONVERTING,
            current_stage="Converting ThoughtSpot formulas to DAX",
        )

        for formula in saved_formulas:
            conversion = _create_conversion(
                migration_id=migration_id,
                formula=formula,
            )

            migration_store.save_conversion(conversion)
            saved_conversions.append(conversion)

        migration_store.update_migration_progress(
            migration_id=migration_id,
            progress_percent=70,
            current_stage="dax_conversion",
            message=f"Converted {len(saved_conversions)} ThoughtSpot formulas to DAX",
        )

        if is_job_call:
            job_store.update_progress(
                job_id=job_id,
                percent=70,
                stage="dax_conversion",
                message=f"Converted {len(saved_conversions)} ThoughtSpot formulas to DAX",
            )

        _broadcast_progress(
            websocket_channel_id,
            70,
            "dax_conversion",
            f"Converted {len(saved_conversions)} formulas to DAX",
            {
                "migration_id": migration_id,
                "conversion_count": len(saved_conversions),
            },
        )

        # --------------------------------------------------------
        # Generate result package metadata
        # --------------------------------------------------------

        migration_store.update_migration_status(
            migration_id=migration_id,
            status=MigrationStatus.PUBLISHING,
            current_stage="Generating Power BI artifacts",
        )

        result = {
            "migration_id": migration_id,
            "status": "completed",
            "source": "thoughtspot",
            "target": "powerbi",
            "summary": {
                "object_count": len(saved_objects),
                "formula_count": len(saved_formulas),
                "relationship_count": len(saved_relationships),
                "conversion_count": len(saved_conversions),
                "generated_at": datetime.utcnow().isoformat(),
            },
            "thoughtspot_objects": [
                obj.to_dict() if hasattr(obj, "to_dict") else obj.__dict__
                for obj in saved_objects
            ],
            "thoughtspot_formulas": [
                formula.to_dict() if hasattr(formula, "to_dict") else formula.__dict__
                for formula in saved_formulas
            ],
            "relationships": [
                rel.to_dict() if hasattr(rel, "to_dict") else rel.__dict__
                for rel in saved_relationships
            ],
            "dax_conversions": [
                conv.to_dict() if hasattr(conv, "to_dict") else conv.__dict__
                for conv in saved_conversions
            ],
            "powerbi_artifacts": {
                "semantic_model": "model.bim can be generated from exported DAX conversions",
                "report_json": "report.json can be generated after visual mapping",
                "pbix": "PBIX creation requires Power BI tooling or REST API publishing",
            },
        }

        if is_job_call:
            result_file_path = result_store.save_result(job_id, result)
        else:
            result_file_path = result_store.save_migration_result(migration_id, result)

        result_store.save_thoughtspot_objects_report(
            migration_id,
            result["thoughtspot_objects"],
        )

        result_store.save_formulas_report(
            migration_id,
            result["thoughtspot_formulas"],
        )

        result_store.save_relationships_report(
            migration_id,
            result["relationships"],
        )

        result_store.save_dax_conversions_report(
            migration_id,
            result["dax_conversions"],
        )

        result_store.save_complete_migration_package_metadata(
            migration_id,
            {
                "result_file_path": result_file_path,
                "object_count": len(saved_objects),
                "formula_count": len(saved_formulas),
                "relationship_count": len(saved_relationships),
                "conversion_count": len(saved_conversions),
            },
        )

        # --------------------------------------------------------
        # Mark completed
        # --------------------------------------------------------

        migration_store.update_migration_progress(
            migration_id=migration_id,
            progress_percent=100,
            current_stage="completed",
            message="ThoughtSpot to Power BI migration completed successfully",
        )

        migration_store.update_migration_status(
            migration_id=migration_id,
            status=MigrationStatus.COMPLETED,
            current_stage="Completed",
        )

        if is_job_call:
            job_store.update_progress(
                job_id=job_id,
                percent=100,
                stage="completed",
                message="ThoughtSpot to Power BI migration completed successfully",
            )

            job_store.update_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                total_objects=len(saved_objects),
                formulas_converted=len(saved_conversions),
                relationships_created=len(saved_relationships),
                result_file_path=result_file_path,
            )

        summary = {
            "migration_id": migration_id,
            "job_id": job_id if is_job_call else None,
            "status": "completed",
            "object_count": len(saved_objects),
            "formula_count": len(saved_formulas),
            "relationship_count": len(saved_relationships),
            "conversion_count": len(saved_conversions),
            "result_file_path": result_file_path,
        }

        _broadcast_completion(websocket_channel_id, summary)

        logger.info(
            f"ThoughtSpot -> Power BI migration completed. "
            f"migration_id={migration_id}, objects={len(saved_objects)}, "
            f"formulas={len(saved_formulas)}, relationships={len(saved_relationships)}"
        )

        return summary

    except Exception as e:
        error_message = str(e)

        logger.error(
            f"ThoughtSpot -> Power BI migration failed. "
            f"job_id={job_id}, migration_id={migration_id}, error={error_message}",
            exc_info=True,
        )

        try:
            migration_store.update_migration_status(
                migration_id=migration_id,
                status=MigrationStatus.FAILED,
                error_message=error_message,
                current_stage="Failed",
            )

            migration_store.update_migration_progress(
                migration_id=migration_id,
                progress_percent=100,
                current_stage="failed",
                message=error_message,
                level="error",
            )

        except Exception as migration_error:
            logger.error(
                f"Failed to update failed migration status: {migration_error}",
                exc_info=True,
            )

        if is_job_call:
            try:
                job_store.update_status(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    error=error_message,
                )

                job_store.update_progress(
                    job_id=job_id,
                    percent=100,
                    stage="failed",
                    message=error_message,
                    level="error",
                )

            except Exception as job_error:
                logger.error(
                    f"Failed to update failed job status: {job_error}",
                    exc_info=True,
                )

        _broadcast_error(websocket_channel_id, error_message)

        raise


# ============================================================
# Backward Compatibility Wrappers
# ============================================================

def execute_discovery_job(job_id: str, file_paths: List[str]):
    """
    Backward-compatible wrapper.

    Old code may call execute_discovery_job().
    For this project, it now runs ThoughtSpot -> Power BI migration.
    """

    return execute_thoughtspot_powerbi_migration(
        job_id=job_id,
        file_paths=file_paths,
    )


def execute_tableau_discovery_job(job_id: str, dataframes: Dict[str, Any]):
    """
    Backward-compatible wrapper.

    Tableau discovery is no longer used.
    This wrapper converts DataFrame names into a temporary result-style flow.
    Prefer using execute_thoughtspot_powerbi_migration().
    """

    job_store = JobStore()
    result_store = ResultStore()

    try:
        logger.warning(
            "execute_tableau_discovery_job() was called, but Tableau discovery "
            "has been replaced by ThoughtSpot -> Power BI migration."
        )

        job_store.update_status(job_id, JobStatus.RUNNING)

        files = []

        for table_name, df in dataframes.items():
            columns = []

            try:
                for col in df.columns:
                    columns.append(
                        {
                            "name": str(col),
                            "data_type": str(df[col].dtype),
                        }
                    )

                row_count = len(df)

            except Exception:
                row_count = 0

            files.append(
                {
                    "table_name": str(table_name),
                    "row_count": row_count,
                    "columns": columns,
                }
            )

        result = {
            "job_id": job_id,
            "source": "dataframe_preview",
            "target": "powerbi",
            "status": "completed",
            "summary": {
                "table_count": len(files),
                "relationship_count": 0,
                "message": (
                    "DataFrame preview processed. "
                    "For real migration, upload ThoughtSpot TML/YAML/JSON files."
                ),
            },
            "tables": files,
        }

        result_file_path = result_store.save_result(job_id, result)

        job_store.update_status(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            relationship_count=0,
            result_file_path=result_file_path,
        )

        _broadcast_completion(
            job_id,
            {
                "job_id": job_id,
                "status": "completed",
                "relationship_count": 0,
                "result_file_path": result_file_path,
            },
        )

        return result

    except Exception as e:
        logger.error(f"DataFrame preview job {job_id} failed: {e}", exc_info=True)

        job_store.update_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=str(e),
        )

        _broadcast_error(job_id, str(e))

        raise