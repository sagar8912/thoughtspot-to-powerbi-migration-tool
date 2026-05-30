"""
Migration domain models for ThoughtSpot -> Power BI Migration Tool.

These models are used internally by:
- storage/migration_store.py
- storage/job_store.py
- workers/migration_worker.py
- API routers

They are dataclass/domain models, not Pydantic request/response schemas.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


# ============================================================
# Helper Functions
# ============================================================

def _row_get(row: Any, key: str, index: Optional[int] = None, default: Any = None) -> Any:
    """
    Safely get value from sqlite3.Row, dict, tuple, or object.
    """

    if row is None:
        return default

    if isinstance(row, dict):
        return row.get(key, default)

    try:
        return row[key]
    except Exception:
        pass

    if index is not None:
        try:
            return row[index]
        except Exception:
            pass

    return getattr(row, key, default)


def _parse_datetime(value: Any) -> Optional[datetime]:
    """
    Safely parse datetime from string or datetime.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    return None


def _json_loads_safe(value: Any, default: Any = None) -> Any:
    """
    Safely parse JSON string.
    """

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return default


def _json_dumps_safe(value: Any) -> Optional[str]:
    """
    Safely convert value to JSON string.
    """

    if value is None:
        return None

    try:
        return json.dumps(value, default=str)
    except Exception:
        return json.dumps(str(value))


def _enum_value(value: Any) -> Any:
    """
    Return enum.value if input is enum, else original value.
    """

    if hasattr(value, "value"):
        return value.value

    return value


def _safe_enum(enum_cls, value: Any, default: Any = None):
    """
    Safely convert value to enum.
    """

    if value is None:
        return default

    if isinstance(value, enum_cls):
        return value

    try:
        return enum_cls(value)
    except Exception:
        return default if default is not None else value


# ============================================================
# Enums
# ============================================================

class MigrationStage(str, Enum):
    """
    Stages for ThoughtSpot -> Power BI migration progress.
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


class MigrationStatus(str, Enum):
    """
    Migration lifecycle status.
    """

    PENDING = "pending"
    PARSING = "parsing"
    DISCOVERING = "discovering"
    CONVERTING = "converting"
    VALIDATING = "validating"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThoughtSpotObjectType(str, Enum):
    """
    ThoughtSpot object types.
    """

    TABLE = "table"
    WORKSHEET = "worksheet"
    ANSWER = "answer"
    LIVEBOARD = "liveboard"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


class FormulaType(str, Enum):
    """
    ThoughtSpot formula/calculated field type.
    """

    FORMULA = "formula"
    MEASURE = "measure"
    COLUMN = "column"
    FILTER = "filter"
    CALCULATED_FIELD = "calculated_field"
    UNKNOWN = "unknown"


class ConversionMethod(str, Enum):
    """
    Method used for ThoughtSpot formula -> DAX conversion.
    """

    RULE_BASED = "rule_based"
    LLM = "llm"
    MANUAL = "manual"
    HYBRID = "hybrid"


class ConversionStatus(str, Enum):
    """
    DAX conversion status.
    """

    PENDING = "pending"
    CONVERTED = "converted"
    MANUAL_REVIEW = "manual_review"
    FAILED = "failed"
    VALIDATED = "validated"


class ErrorCategory(str, Enum):
    """
    Validation/conversion error category.
    """

    NONE = "none"
    SYNTAX_ERROR = "syntax_error"
    SEMANTIC_ERROR = "semantic_error"
    AGGREGATION_MISMATCH = "aggregation_mismatch"
    FILTER_CONTEXT_MISMATCH = "filter_context_mismatch"
    DATA_TYPE_MISMATCH = "data_type_mismatch"
    RELATIONSHIP_MISMATCH = "relationship_mismatch"
    UNSUPPORTED_FUNCTION = "unsupported_function"
    UNKNOWN = "unknown"


class PowerBIObjectType(str, Enum):
    """
    Power BI target object type.
    """

    SEMANTIC_MODEL = "semantic_model"
    DATASET = "dataset"
    TABLE = "table"
    MEASURE = "measure"
    COLUMN = "column"
    REPORT = "report"
    VISUAL = "visual"


# ============================================================
# Migration Job
# ============================================================

@dataclass
class MigrationJob:
    """
    Migration-level job model.
    """

    migration_id: str
    status: MigrationStatus
    created_at: datetime

    job_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

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

    @classmethod
    def from_db_row(cls, row: Any) -> Optional["MigrationJob"]:
        """
        Create MigrationJob from database row.
        """

        if row is None:
            return None

        return cls(
            migration_id=_row_get(row, "migration_id", 0),
            job_id=_row_get(row, "job_id", 1),
            status=_safe_enum(
                MigrationStatus,
                _row_get(row, "status", 2),
                MigrationStatus.PENDING,
            ),
            created_at=_parse_datetime(_row_get(row, "created_at", 3)) or datetime.utcnow(),
            started_at=_parse_datetime(_row_get(row, "started_at", 4)),
            completed_at=_parse_datetime(_row_get(row, "completed_at", 5)),
            progress_percent=_row_get(row, "progress_percent", 6, 0) or 0,
            current_stage=_row_get(row, "current_stage", 7),
            error_message=_row_get(row, "error_message", 8),

            object_count=_row_get(row, "object_count", 9, 0) or 0,
            formula_count=_row_get(row, "formula_count", 10, 0) or 0,
            relationship_count=_row_get(row, "relationship_count", 11, 0) or 0,
            report_count=_row_get(row, "report_count", 12, 0) or 0,
            dashboard_count=_row_get(row, "dashboard_count", 13, 0) or 0,

            powerbi_workspace_id=_row_get(row, "powerbi_workspace_id", 14),
            powerbi_dataset_id=_row_get(row, "powerbi_dataset_id", 15),
            powerbi_report_id=_row_get(row, "powerbi_report_id", 16),
            powerbi_report_url=_row_get(row, "powerbi_report_url", 17),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        """

        return {
            "migration_id": self.migration_id,
            "job_id": self.job_id,
            "status": _enum_value(self.status),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_percent": self.progress_percent,
            "current_stage": self.current_stage,
            "error_message": self.error_message,
            "object_count": self.object_count,
            "formula_count": self.formula_count,
            "relationship_count": self.relationship_count,
            "report_count": self.report_count,
            "dashboard_count": self.dashboard_count,
            "powerbi_workspace_id": self.powerbi_workspace_id,
            "powerbi_dataset_id": self.powerbi_dataset_id,
            "powerbi_report_id": self.powerbi_report_id,
            "powerbi_report_url": self.powerbi_report_url,
        }


# ============================================================
# ThoughtSpot Object
# ============================================================

@dataclass
class ThoughtSpotObject:
    """
    Extracted ThoughtSpot object metadata.
    """

    object_id: str
    migration_id: str
    object_name: str
    object_type: Any
    filename: str
    file_path: str

    object_guid: Optional[str] = None
    column_count: int = 0
    formula_count: int = 0
    relationship_count: int = 0
    visual_count: int = 0

    raw_tml: Optional[Dict[str, Any]] = field(default_factory=dict)
    extracted_at: Optional[datetime] = field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: Any) -> Optional["ThoughtSpotObject"]:
        """
        Create ThoughtSpotObject from database row.
        """

        if row is None:
            return None

        return cls(
            object_id=_row_get(row, "object_id", 0),
            migration_id=_row_get(row, "migration_id", 1),
            object_name=_row_get(row, "object_name", 2),
            object_type=_safe_enum(
                ThoughtSpotObjectType,
                _row_get(row, "object_type", 3),
                _row_get(row, "object_type", 3),
            ),
            filename=_row_get(row, "filename", 4),
            file_path=_row_get(row, "file_path", 5),
            object_guid=_row_get(row, "object_guid", 6),
            column_count=_row_get(row, "column_count", 7, 0) or 0,
            formula_count=_row_get(row, "formula_count", 8, 0) or 0,
            relationship_count=_row_get(row, "relationship_count", 9, 0) or 0,
            raw_tml=_json_loads_safe(_row_get(row, "raw_tml", 10), default={}),
            visual_count=_row_get(row, "visual_count", 11, 0) or 0,
            extracted_at=_parse_datetime(_row_get(row, "extracted_at", 12)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        """

        return {
            "object_id": self.object_id,
            "migration_id": self.migration_id,
            "object_name": self.object_name,
            "object_type": _enum_value(self.object_type),
            "filename": self.filename,
            "file_path": self.file_path,
            "object_guid": self.object_guid,
            "column_count": self.column_count,
            "formula_count": self.formula_count,
            "relationship_count": self.relationship_count,
            "visual_count": self.visual_count,
            "raw_tml": self.raw_tml,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
        }


# ============================================================
# ThoughtSpot Formula
# ============================================================

@dataclass
class ThoughtSpotFormula:
    """
    ThoughtSpot formula/calculated field model.
    """

    formula_id: str
    object_id: str
    formula_name: str
    formula_expression: str

    formula_type: Any = FormulaType.FORMULA
    visual_context: Dict[str, Any] = field(default_factory=dict)
    dependency_level: int = 0
    depends_on: List[str] = field(default_factory=list)
    depends_on_metadata: Dict[str, Any] = field(default_factory=dict)

    used_in_answers: List[str] = field(default_factory=list)
    used_in_liveboards: List[str] = field(default_factory=list)

    is_aggregate: bool = False
    is_filter_formula: bool = False
    used_in_filters: List[str] = field(default_factory=list)
    used_in_visuals: List[str] = field(default_factory=list)

    created_at: Optional[datetime] = field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: Any) -> Optional["ThoughtSpotFormula"]:
        """
        Create ThoughtSpotFormula from database row.
        """

        if row is None:
            return None

        visual_context = _json_loads_safe(_row_get(row, "visual_context", 5), default={}) or {}

        return cls(
            formula_id=_row_get(row, "formula_id", 0),
            object_id=_row_get(row, "object_id", 1),
            formula_name=_row_get(row, "formula_name", 2),
            formula_expression=_row_get(row, "formula_expression", 3),
            formula_type=_safe_enum(
                FormulaType,
                _row_get(row, "formula_type", 4),
                _row_get(row, "formula_type", 4),
            ),
            visual_context=visual_context,
            dependency_level=_row_get(row, "dependency_level", 6, 0) or 0,
            depends_on=_json_loads_safe(_row_get(row, "depends_on", 7), default=[]),
            depends_on_metadata=_json_loads_safe(
                _row_get(row, "depends_on_metadata", 8),
                default={},
            ),
            used_in_answers=(
                str(_row_get(row, "used_in_answers", 9)).split(",")
                if _row_get(row, "used_in_answers", 9)
                else []
            ),
            used_in_liveboards=(
                str(_row_get(row, "used_in_liveboards", 10)).split(",")
                if _row_get(row, "used_in_liveboards", 10)
                else []
            ),
            is_aggregate=bool(visual_context.get("is_aggregate", False)),
            is_filter_formula=bool(visual_context.get("is_filter_formula", False)),
            used_in_filters=visual_context.get("used_in_filters", []) or [],
            used_in_visuals=visual_context.get("used_in_visuals", []) or [],
            created_at=_parse_datetime(_row_get(row, "created_at", 11)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        """

        return {
            "formula_id": self.formula_id,
            "object_id": self.object_id,
            "formula_name": self.formula_name,
            "formula_expression": self.formula_expression,
            "formula_type": _enum_value(self.formula_type),
            "visual_context": self.visual_context,
            "dependency_level": self.dependency_level,
            "depends_on": self.depends_on,
            "depends_on_metadata": self.depends_on_metadata,
            "used_in_answers": self.used_in_answers,
            "used_in_liveboards": self.used_in_liveboards,
            "is_aggregate": self.is_aggregate,
            "is_filter_formula": self.is_filter_formula,
            "used_in_filters": self.used_in_filters,
            "used_in_visuals": self.used_in_visuals,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# ThoughtSpot Relationship
# ============================================================

@dataclass
class ThoughtSpotRelationship:
    """
    ThoughtSpot relationship/join metadata.
    """

    relationship_id: str
    migration_id: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str

    join_type: Optional[str] = None
    powerbi_cardinality: str = "many-to-one"
    is_active: bool = True
    created_at: Optional[datetime] = field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: Any) -> Optional["ThoughtSpotRelationship"]:
        """
        Create ThoughtSpotRelationship from database row.
        """

        if row is None:
            return None

        return cls(
            relationship_id=_row_get(row, "relationship_id", 0),
            migration_id=_row_get(row, "migration_id", 1),
            source_table=_row_get(row, "source_table", 2),
            source_column=_row_get(row, "source_column", 3),
            target_table=_row_get(row, "target_table", 4),
            target_column=_row_get(row, "target_column", 5),
            join_type=_row_get(row, "join_type", 6),
            powerbi_cardinality=_row_get(row, "powerbi_cardinality", 7, "many-to-one"),
            is_active=bool(_row_get(row, "is_active", 8, 1)),
            created_at=_parse_datetime(_row_get(row, "created_at", 9)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        """

        return {
            "relationship_id": self.relationship_id,
            "migration_id": self.migration_id,
            "source_table": self.source_table,
            "source_column": self.source_column,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "join_type": self.join_type,
            "powerbi_cardinality": self.powerbi_cardinality,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# Power BI Conversion
# ============================================================

@dataclass
class PowerBIConversion:
    """
    ThoughtSpot formula to Power BI DAX conversion result.
    """

    conversion_id: str
    source_formula_id: str
    migration_id: str
    dax_formula: str

    conversion_method: Any = ConversionMethod.RULE_BASED
    confidence_score: float = 0.0
    reasoning: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    status: Any = ConversionStatus.PENDING

    created_at: Optional[datetime] = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = field(default_factory=datetime.utcnow)

    target_powerbi_object_type: Optional[Any] = None
    target_powerbi_object_id: Optional[str] = None
    target_powerbi_object_name: Optional[str] = None

    @classmethod
    def from_db_row(cls, row: Any) -> Optional["PowerBIConversion"]:
        """
        Create PowerBIConversion from database row.
        """

        if row is None:
            return None

        return cls(
            conversion_id=_row_get(row, "conversion_id", 0),
            source_formula_id=_row_get(row, "source_formula_id", 1),
            migration_id=_row_get(row, "migration_id", 2),
            dax_formula=_row_get(row, "dax_formula", 3),
            conversion_method=_safe_enum(
                ConversionMethod,
                _row_get(row, "conversion_method", 4),
                _row_get(row, "conversion_method", 4),
            ),
            confidence_score=float(_row_get(row, "confidence_score", 5, 0.0) or 0.0),
            reasoning=_row_get(row, "reasoning", 6),
            warnings=_json_loads_safe(_row_get(row, "warnings", 7), default=[]),
            status=_safe_enum(
                ConversionStatus,
                _row_get(row, "status", 8),
                _row_get(row, "status", 8),
            ),
            created_at=_parse_datetime(_row_get(row, "created_at", 9)),
            updated_at=_parse_datetime(_row_get(row, "updated_at", 10)),
            target_powerbi_object_type=_row_get(row, "target_powerbi_object_type", 11),
            target_powerbi_object_id=_row_get(row, "target_powerbi_object_id", 12),
            target_powerbi_object_name=_row_get(row, "target_powerbi_object_name", 13),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        """

        return {
            "conversion_id": self.conversion_id,
            "source_formula_id": self.source_formula_id,
            "migration_id": self.migration_id,
            "dax_formula": self.dax_formula,
            "conversion_method": _enum_value(self.conversion_method),
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "status": _enum_value(self.status),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "target_powerbi_object_type": _enum_value(self.target_powerbi_object_type),
            "target_powerbi_object_id": self.target_powerbi_object_id,
            "target_powerbi_object_name": self.target_powerbi_object_name,
        }


# ============================================================
# Validation Result
# ============================================================

@dataclass
class ValidationResult:
    """
    Validation result comparing ThoughtSpot output value vs Power BI output value.
    """

    validation_id: str
    conversion_id: str
    test_slice: Dict[str, Any]

    thoughtspot_value: Optional[float] = None
    powerbi_value: Optional[float] = None
    delta: Optional[float] = None
    relative_error: Optional[float] = None

    passed: bool = False
    error_category: Any = ErrorCategory.UNKNOWN
    correction_attempts: int = 0
    validated_at: Optional[datetime] = field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: Any) -> Optional["ValidationResult"]:
        """
        Create ValidationResult from database row.
        """

        if row is None:
            return None

        return cls(
            validation_id=_row_get(row, "validation_id", 0),
            conversion_id=_row_get(row, "conversion_id", 1),
            test_slice=_json_loads_safe(_row_get(row, "test_slice", 2), default={}),
            thoughtspot_value=_row_get(row, "thoughtspot_value", 3),
            powerbi_value=_row_get(row, "powerbi_value", 4),
            delta=_row_get(row, "delta", 5),
            relative_error=_row_get(row, "relative_error", 6),
            passed=bool(_row_get(row, "passed", 7, False)),
            error_category=_safe_enum(
                ErrorCategory,
                _row_get(row, "error_category", 8),
                _row_get(row, "error_category", 8),
            ),
            correction_attempts=_row_get(row, "correction_attempts", 9, 0) or 0,
            validated_at=_parse_datetime(_row_get(row, "validated_at", 10)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        """

        return {
            "validation_id": self.validation_id,
            "conversion_id": self.conversion_id,
            "test_slice": self.test_slice,
            "thoughtspot_value": self.thoughtspot_value,
            "powerbi_value": self.powerbi_value,
            "delta": self.delta,
            "relative_error": self.relative_error,
            "passed": self.passed,
            "error_category": _enum_value(self.error_category),
            "correction_attempts": self.correction_attempts,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
        }


# ============================================================
# Lightweight aliases / compatibility names
# ============================================================

ThoughtSpotCalculation = ThoughtSpotFormula
DAXConversion = PowerBIConversion
Relationship = ThoughtSpotRelationship