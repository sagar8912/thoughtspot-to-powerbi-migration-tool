"""
Migration job persistence and state management for ThoughtSpot -> Power BI Migration Tool.

This store manages:
- Migration jobs
- ThoughtSpot objects
- ThoughtSpot formulas/calculated fields
- ThoughtSpot relationships/joins
- Power BI / DAX conversions
- Validation results
- Migration progress logs
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger
import json

from storage.database import get_db_connection

from api.models.migration_models import (
    MigrationJob,
    MigrationStatus,
    ThoughtSpotObject,
    ThoughtSpotFormula,
    PowerBIConversion,
    ValidationResult,
    ThoughtSpotRelationship,
    ConversionMethod,
    ConversionStatus,
    ErrorCategory,
)


class MigrationStore:
    """
    Manages ThoughtSpot -> Power BI migration persistence in SQLite database.
    """

    # ============================================================
    # Internal Helpers
    # ============================================================

    @staticmethod
    def _enum_value(value: Any) -> Any:
        """
        Return enum value if value is Enum, otherwise return value.
        """

        if hasattr(value, "value"):
            return value.value

        return value

    @staticmethod
    def _json_dumps(value: Any) -> Optional[str]:
        """
        Convert object/list/dict to JSON string safely.
        """

        if value is None:
            return None

        return json.dumps(value)

    @staticmethod
    def _json_loads(value: Any, default: Any = None) -> Any:
        """
        Convert JSON string to Python object safely.
        """

        if value is None:
            return default

        if isinstance(value, (dict, list)):
            return value

        try:
            return json.loads(value)
        except Exception:
            return default

    # ============================================================
    # Migration Job Operations
    # ============================================================

    def create_migration(
        self,
        migration_id: str,
        job_id: Optional[str] = None,
    ) -> MigrationJob:
        """
        Create a new ThoughtSpot -> Power BI migration job.

        Args:
            migration_id: Unique migration identifier.
            job_id: Optional associated API job ID.

        Returns:
            Created MigrationJob object.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO migration_jobs (
                    migration_id,
                    job_id,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    migration_id,
                    job_id,
                    MigrationStatus.PENDING.value,
                    datetime.utcnow(),
                ),
            )

        logger.info(f"Created ThoughtSpot -> Power BI migration {migration_id}")

        migration = self.get_migration(migration_id)

        if migration is None:
            raise RuntimeError(f"Failed to create migration {migration_id}")

        return migration

    def get_migration(
        self,
        migration_id: str,
    ) -> Optional[MigrationJob]:
        """
        Get migration by ID.

        Args:
            migration_id: Migration identifier.

        Returns:
            MigrationJob object or None.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    migration_id,
                    job_id,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    progress_percent,
                    current_stage,
                    error_message,

                    object_count,
                    formula_count,
                    relationship_count,
                    report_count,
                    dashboard_count,

                    powerbi_workspace_id,
                    powerbi_dataset_id,
                    powerbi_report_id,
                    powerbi_report_url
                FROM migration_jobs
                WHERE migration_id = ?
                """,
                (migration_id,),
            ).fetchone()

        if row:
            return MigrationJob.from_db_row(row)

        return None

    def list_migrations(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> tuple[List[MigrationJob], int]:
        """
        List migrations with pagination.

        Args:
            limit: Maximum rows to return.
            offset: Offset for pagination.
            status: Optional migration status filter.

        Returns:
            Tuple of migrations list and total count.
        """

        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)

        with get_db_connection() as conn:
            where_clause = ""
            params: List[Any] = []

            if status:
                where_clause = "WHERE status = ?"
                params.append(status)

            total = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM migration_jobs
                {where_clause}
                """,
                params,
            ).fetchone()[0]

            rows = conn.execute(
                f"""
                SELECT
                    migration_id,
                    job_id,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    progress_percent,
                    current_stage,
                    error_message,

                    object_count,
                    formula_count,
                    relationship_count,
                    report_count,
                    dashboard_count,

                    powerbi_workspace_id,
                    powerbi_dataset_id,
                    powerbi_report_id,
                    powerbi_report_url
                FROM migration_jobs
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()

        return [MigrationJob.from_db_row(row) for row in rows], total

    def update_migration_status(
        self,
        migration_id: str,
        status: MigrationStatus,
        error_message: Optional[str] = None,
        current_stage: Optional[str] = None,
    ) -> None:
        """
        Update migration status.

        Args:
            migration_id: Migration identifier.
            status: New status.
            error_message: Optional error message.
            current_stage: Optional current stage.
        """

        status_value = self._enum_value(status)
        now = datetime.utcnow()

        updates = ["status = ?"]
        params: List[Any] = [status_value]

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if current_stage is not None:
            updates.append("current_stage = ?")
            params.append(current_stage)

        if status_value in [
            MigrationStatus.PARSING.value,
            MigrationStatus.DISCOVERING.value,
            MigrationStatus.CONVERTING.value,
            MigrationStatus.VALIDATING.value,
            MigrationStatus.PUBLISHING.value,
        ]:
            updates.append("started_at = COALESCE(started_at, ?)")
            params.append(now)
            updates.append("error_message = NULL")

        if status_value in [
            MigrationStatus.COMPLETED.value,
            MigrationStatus.FAILED.value,
            MigrationStatus.CANCELLED.value,
        ]:
            updates.append("completed_at = ?")
            params.append(now)

        params.append(migration_id)

        query = f"""
            UPDATE migration_jobs
            SET {", ".join(updates)}
            WHERE migration_id = ?
        """

        with get_db_connection() as conn:
            conn.execute(query, params)

        logger.info(f"Updated migration {migration_id} status to {status_value}")

    def update_migration_progress(
        self,
        migration_id: str,
        progress_percent: int,
        current_stage: str,
        message: Optional[str] = None,
        level: str = "info",
        object_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update migration progress and insert progress log.

        Args:
            migration_id: Migration identifier.
            progress_percent: Progress percentage.
            current_stage: Current stage.
            message: Optional progress message.
            level: Log level.
            object_name: Optional current object name.
            details: Optional details dictionary.
        """

        progress_percent = max(0, min(100, int(progress_percent)))
        details_json = self._json_dumps(details)

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE migration_jobs
                SET
                    progress_percent = ?,
                    current_stage = ?
                WHERE migration_id = ?
                """,
                (
                    progress_percent,
                    current_stage,
                    migration_id,
                ),
            )

            conn.execute(
                """
                INSERT INTO migration_progress (
                    migration_id,
                    stage,
                    message,
                    percent,
                    level,
                    object_name,
                    details,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    migration_id,
                    current_stage,
                    message,
                    progress_percent,
                    level,
                    object_name,
                    details_json,
                    datetime.utcnow(),
                ),
            )

        logger.debug(
            f"Migration {migration_id}: {current_stage} "
            f"({progress_percent}%) - {message}"
        )

    def update_migration_counts(
        self,
        migration_id: str,
        object_count: Optional[int] = None,
        formula_count: Optional[int] = None,
        relationship_count: Optional[int] = None,
        report_count: Optional[int] = None,
        dashboard_count: Optional[int] = None,
    ) -> None:
        """
        Update migration object/formula/relationship/report counts.

        Args:
            migration_id: Migration identifier.
            object_count: Number of ThoughtSpot objects.
            formula_count: Number of formulas.
            relationship_count: Number of relationships.
            report_count: Number of reports.
            dashboard_count: Number of dashboards/liveboards.
        """

        updates = []
        params: List[Any] = []

        optional_updates = {
            "object_count": object_count,
            "formula_count": formula_count,
            "relationship_count": relationship_count,
            "report_count": report_count,
            "dashboard_count": dashboard_count,
        }

        for column, value in optional_updates.items():
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value)

        if not updates:
            return

        params.append(migration_id)

        query = f"""
            UPDATE migration_jobs
            SET {", ".join(updates)}
            WHERE migration_id = ?
        """

        with get_db_connection() as conn:
            conn.execute(query, params)

        logger.debug(f"Updated migration counts for {migration_id}")

    def update_powerbi_output_info(
        self,
        migration_id: str,
        powerbi_workspace_id: Optional[str] = None,
        powerbi_dataset_id: Optional[str] = None,
        powerbi_report_id: Optional[str] = None,
        powerbi_report_url: Optional[str] = None,
    ) -> None:
        """
        Update Power BI output information on migration job.
        """

        updates = []
        params: List[Any] = []

        optional_updates = {
            "powerbi_workspace_id": powerbi_workspace_id,
            "powerbi_dataset_id": powerbi_dataset_id,
            "powerbi_report_id": powerbi_report_id,
            "powerbi_report_url": powerbi_report_url,
        }

        for column, value in optional_updates.items():
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value)

        if not updates:
            return

        params.append(migration_id)

        with get_db_connection() as conn:
            conn.execute(
                f"""
                UPDATE migration_jobs
                SET {", ".join(updates)}
                WHERE migration_id = ?
                """,
                params,
            )

        logger.info(f"Updated Power BI output info for migration {migration_id}")

    def delete_migration(
        self,
        migration_id: str,
    ) -> bool:
        """
        Delete migration and related data using foreign-key cascade.

        Args:
            migration_id: Migration identifier.

        Returns:
            True if deleted, False if not found.
        """

        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM migration_jobs
                WHERE migration_id = ?
                """,
                (migration_id,),
            )

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted migration {migration_id}")

        return deleted

    # ============================================================
    # ThoughtSpot Object Operations
    # ============================================================

    def save_object(
        self,
        obj: ThoughtSpotObject,
    ) -> None:
        """
        Save ThoughtSpot object metadata.

        Args:
            obj: ThoughtSpotObject object.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO thoughtspot_objects (
                    object_id,
                    migration_id,
                    object_name,
                    object_type,
                    filename,
                    file_path,
                    object_guid,
                    column_count,
                    formula_count,
                    relationship_count,
                    visual_count,
                    raw_tml,
                    extracted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obj.object_id,
                    obj.migration_id,
                    obj.object_name,
                    self._enum_value(obj.object_type),
                    obj.filename,
                    obj.file_path,
                    obj.object_guid,
                    obj.column_count,
                    obj.formula_count,
                    obj.relationship_count,
                    obj.visual_count,
                    self._json_dumps(obj.raw_tml),
                    obj.extracted_at or datetime.utcnow(),
                ),
            )

        logger.debug(f"Saved ThoughtSpot object {obj.object_id}")

    def get_object(
        self,
        object_id: str,
    ) -> Optional[ThoughtSpotObject]:
        """
        Get ThoughtSpot object by ID.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    object_id,
                    migration_id,
                    object_name,
                    object_type,
                    filename,
                    file_path,
                    object_guid,
                    column_count,
                    formula_count,
                    relationship_count,
                    raw_tml,
                    visual_count,
                    extracted_at
                FROM thoughtspot_objects
                WHERE object_id = ?
                """,
                (object_id,),
            ).fetchone()

        if row:
            return ThoughtSpotObject.from_db_row(row)

        return None

    def get_objects_by_migration(
        self,
        migration_id: str,
    ) -> List[ThoughtSpotObject]:
        """
        Get all ThoughtSpot objects for a migration.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    object_id,
                    migration_id,
                    object_name,
                    object_type,
                    filename,
                    file_path,
                    object_guid,
                    column_count,
                    formula_count,
                    relationship_count,
                    raw_tml,
                    visual_count,
                    extracted_at
                FROM thoughtspot_objects
                WHERE migration_id = ?
                ORDER BY extracted_at
                """,
                (migration_id,),
            ).fetchall()

        return [ThoughtSpotObject.from_db_row(row) for row in rows]

    def get_objects_by_type(
        self,
        migration_id: str,
        object_type: str,
    ) -> List[ThoughtSpotObject]:
        """
        Get ThoughtSpot objects by object type.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    object_id,
                    migration_id,
                    object_name,
                    object_type,
                    filename,
                    file_path,
                    object_guid,
                    column_count,
                    formula_count,
                    relationship_count,
                    raw_tml,
                    visual_count,
                    extracted_at
                FROM thoughtspot_objects
                WHERE migration_id = ?
                AND object_type = ?
                ORDER BY extracted_at
                """,
                (
                    migration_id,
                    object_type,
                ),
            ).fetchall()

        return [ThoughtSpotObject.from_db_row(row) for row in rows]

    # ============================================================
    # ThoughtSpot Formula Operations
    # ============================================================

    def save_formula(
        self,
        formula: ThoughtSpotFormula,
    ) -> None:
        """
        Save ThoughtSpot formula/calculated field.

        Args:
            formula: ThoughtSpotFormula object.
        """

        visual_context = formula.visual_context or {}

        if formula.is_aggregate:
            visual_context["is_aggregate"] = True

        if formula.is_filter_formula:
            visual_context["is_filter_formula"] = True

        if formula.used_in_filters:
            visual_context["used_in_filters"] = formula.used_in_filters

        if formula.used_in_visuals:
            visual_context["used_in_visuals"] = formula.used_in_visuals

        used_in_answers_str = (
            ",".join(formula.used_in_answers)
            if formula.used_in_answers
            else None
        )

        used_in_liveboards_str = (
            ",".join(formula.used_in_liveboards)
            if formula.used_in_liveboards
            else None
        )

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO thoughtspot_formulas (
                    formula_id,
                    object_id,
                    formula_name,
                    formula_expression,
                    formula_type,
                    visual_context,
                    dependency_level,
                    depends_on,
                    depends_on_metadata,
                    used_in_answers,
                    used_in_liveboards,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    formula.formula_id,
                    formula.object_id,
                    formula.formula_name,
                    formula.formula_expression,
                    self._enum_value(formula.formula_type),
                    self._json_dumps(visual_context),
                    formula.dependency_level,
                    self._json_dumps(formula.depends_on),
                    self._json_dumps(formula.depends_on_metadata),
                    used_in_answers_str,
                    used_in_liveboards_str,
                    formula.created_at or datetime.utcnow(),
                ),
            )

        logger.debug(f"Saved ThoughtSpot formula {formula.formula_id}")

    def get_formula(
        self,
        formula_id: str,
    ) -> Optional[ThoughtSpotFormula]:
        """
        Get ThoughtSpot formula by ID.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    formula_id,
                    object_id,
                    formula_name,
                    formula_expression,
                    formula_type,
                    visual_context,
                    dependency_level,
                    depends_on,
                    depends_on_metadata,
                    used_in_answers,
                    used_in_liveboards,
                    created_at
                FROM thoughtspot_formulas
                WHERE formula_id = ?
                """,
                (formula_id,),
            ).fetchone()

        if row:
            return ThoughtSpotFormula.from_db_row(row)

        return None

    def get_formulas_by_object(
        self,
        object_id: str,
    ) -> List[ThoughtSpotFormula]:
        """
        Get all formulas for one ThoughtSpot object.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    formula_id,
                    object_id,
                    formula_name,
                    formula_expression,
                    formula_type,
                    visual_context,
                    dependency_level,
                    depends_on,
                    depends_on_metadata,
                    used_in_answers,
                    used_in_liveboards,
                    created_at
                FROM thoughtspot_formulas
                WHERE object_id = ?
                ORDER BY dependency_level, formula_name
                """,
                (object_id,),
            ).fetchall()

        return [ThoughtSpotFormula.from_db_row(row) for row in rows]

    def get_formulas_by_migration(
        self,
        migration_id: str,
    ) -> List[ThoughtSpotFormula]:
        """
        Get all formulas for a migration.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    f.formula_id,
                    f.object_id,
                    f.formula_name,
                    f.formula_expression,
                    f.formula_type,
                    f.visual_context,
                    f.dependency_level,
                    f.depends_on,
                    f.depends_on_metadata,
                    f.used_in_answers,
                    f.used_in_liveboards,
                    f.created_at
                FROM thoughtspot_formulas f
                JOIN thoughtspot_objects o
                    ON f.object_id = o.object_id
                WHERE o.migration_id = ?
                ORDER BY f.dependency_level, f.formula_name
                """,
                (migration_id,),
            ).fetchall()

        return [ThoughtSpotFormula.from_db_row(row) for row in rows]

    # ============================================================
    # Power BI / DAX Conversion Operations
    # ============================================================

    def save_conversion(
        self,
        conversion: PowerBIConversion,
    ) -> None:
        """
        Save Power BI / DAX conversion result.

        Args:
            conversion: PowerBIConversion object.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO powerbi_conversions (
                    conversion_id,
                    source_formula_id,
                    migration_id,
                    dax_formula,
                    conversion_method,
                    confidence_score,
                    reasoning,
                    warnings,
                    status,
                    created_at,
                    updated_at,
                    target_powerbi_object_type,
                    target_powerbi_object_id,
                    target_powerbi_object_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversion.conversion_id,
                    conversion.source_formula_id,
                    conversion.migration_id,
                    conversion.dax_formula,
                    self._enum_value(conversion.conversion_method),
                    conversion.confidence_score,
                    conversion.reasoning,
                    self._json_dumps(conversion.warnings),
                    self._enum_value(conversion.status),
                    conversion.created_at or datetime.utcnow(),
                    conversion.updated_at or datetime.utcnow(),
                    self._enum_value(conversion.target_powerbi_object_type),
                    conversion.target_powerbi_object_id,
                    conversion.target_powerbi_object_name,
                ),
            )

        logger.debug(f"Saved Power BI conversion {conversion.conversion_id}")

    def update_conversion(
        self,
        conversion_id: str,
        dax_formula: Optional[str] = None,
        conversion_method: Optional[ConversionMethod] = None,
        reasoning: Optional[str] = None,
        warnings: Optional[List[str]] = None,
        status: Optional[ConversionStatus] = None,
        confidence_score: Optional[float] = None,
        target_powerbi_object_type: Optional[str] = None,
        target_powerbi_object_id: Optional[str] = None,
        target_powerbi_object_name: Optional[str] = None,
    ) -> Optional[PowerBIConversion]:
        """
        Update Power BI / DAX conversion.

        Args:
            conversion_id: Conversion identifier.
            dax_formula: Updated DAX formula.
            conversion_method: Updated conversion method.
            reasoning: Updated reasoning.
            warnings: Updated warnings.
            status: Updated status.
            confidence_score: Updated confidence score.
            target_powerbi_object_type: Power BI target object type.
            target_powerbi_object_id: Power BI target object ID.
            target_powerbi_object_name: Power BI target object name.

        Returns:
            Updated PowerBIConversion or None.
        """

        updates = ["updated_at = ?"]
        params: List[Any] = [datetime.utcnow()]

        optional_updates = {
            "dax_formula": dax_formula,
            "conversion_method": self._enum_value(conversion_method),
            "reasoning": reasoning,
            "warnings": self._json_dumps(warnings) if warnings is not None else None,
            "status": self._enum_value(status),
            "confidence_score": confidence_score,
            "target_powerbi_object_type": self._enum_value(target_powerbi_object_type),
            "target_powerbi_object_id": target_powerbi_object_id,
            "target_powerbi_object_name": target_powerbi_object_name,
        }

        for column, value in optional_updates.items():
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value)

        params.append(conversion_id)

        query = f"""
            UPDATE powerbi_conversions
            SET {", ".join(updates)}
            WHERE conversion_id = ?
        """

        with get_db_connection() as conn:
            conn.execute(query, params)

        logger.debug(f"Updated Power BI conversion {conversion_id}")

        return self.get_conversion(conversion_id)

    def get_conversion(
        self,
        conversion_id: str,
    ) -> Optional[PowerBIConversion]:
        """
        Get conversion by ID.
        """

        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    conversion_id,
                    source_formula_id,
                    migration_id,
                    dax_formula,
                    conversion_method,
                    confidence_score,
                    reasoning,
                    warnings,
                    status,
                    created_at,
                    updated_at,
                    target_powerbi_object_type,
                    target_powerbi_object_id,
                    target_powerbi_object_name
                FROM powerbi_conversions
                WHERE conversion_id = ?
                """,
                (conversion_id,),
            ).fetchone()

        if row:
            return PowerBIConversion.from_db_row(row)

        return None

    def get_conversions_by_migration(
        self,
        migration_id: str,
    ) -> List[PowerBIConversion]:
        """
        Get all conversions for a migration.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    conversion_id,
                    source_formula_id,
                    migration_id,
                    dax_formula,
                    conversion_method,
                    confidence_score,
                    reasoning,
                    warnings,
                    status,
                    created_at,
                    updated_at,
                    target_powerbi_object_type,
                    target_powerbi_object_id,
                    target_powerbi_object_name
                FROM powerbi_conversions
                WHERE migration_id = ?
                ORDER BY created_at
                """,
                (migration_id,),
            ).fetchall()

        return [PowerBIConversion.from_db_row(row) for row in rows]

    def get_conversions_by_formula(
        self,
        formula_id: str,
    ) -> List[PowerBIConversion]:
        """
        Get all conversions for one formula.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    conversion_id,
                    source_formula_id,
                    migration_id,
                    dax_formula,
                    conversion_method,
                    confidence_score,
                    reasoning,
                    warnings,
                    status,
                    created_at,
                    updated_at,
                    target_powerbi_object_type,
                    target_powerbi_object_id,
                    target_powerbi_object_name
                FROM powerbi_conversions
                WHERE source_formula_id = ?
                ORDER BY created_at
                """,
                (formula_id,),
            ).fetchall()

        return [PowerBIConversion.from_db_row(row) for row in rows]

    # ============================================================
    # ThoughtSpot Relationship Operations
    # ============================================================

    def save_relationship(
        self,
        relationship: ThoughtSpotRelationship,
    ) -> None:
        """
        Save ThoughtSpot relationship/join metadata.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO thoughtspot_relationships (
                    relationship_id,
                    migration_id,
                    source_table,
                    source_column,
                    target_table,
                    target_column,
                    join_type,
                    powerbi_cardinality,
                    is_active,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship.relationship_id,
                    relationship.migration_id,
                    relationship.source_table,
                    relationship.source_column,
                    relationship.target_table,
                    relationship.target_column,
                    relationship.join_type,
                    relationship.powerbi_cardinality,
                    int(relationship.is_active),
                    relationship.created_at or datetime.utcnow(),
                ),
            )

        logger.debug(f"Saved ThoughtSpot relationship {relationship.relationship_id}")

    def get_relationships_by_migration(
        self,
        migration_id: str,
    ) -> List[ThoughtSpotRelationship]:
        """
        Get all relationships for a migration.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    relationship_id,
                    migration_id,
                    source_table,
                    source_column,
                    target_table,
                    target_column,
                    join_type,
                    powerbi_cardinality,
                    is_active,
                    created_at
                FROM thoughtspot_relationships
                WHERE migration_id = ?
                ORDER BY created_at
                """,
                (migration_id,),
            ).fetchall()

        return [ThoughtSpotRelationship.from_db_row(row) for row in rows]

    # ============================================================
    # Validation Result Operations
    # ============================================================

    def save_validation_result(
        self,
        result: ValidationResult,
    ) -> None:
        """
        Save validation result for ThoughtSpot value vs Power BI value.
        """

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO validation_results (
                    validation_id,
                    conversion_id,
                    test_slice,
                    thoughtspot_value,
                    powerbi_value,
                    delta,
                    relative_error,
                    passed,
                    error_category,
                    correction_attempts,
                    validated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.validation_id,
                    result.conversion_id,
                    self._json_dumps(result.test_slice),
                    result.thoughtspot_value,
                    result.powerbi_value,
                    result.delta,
                    result.relative_error,
                    int(result.passed),
                    self._enum_value(result.error_category),
                    result.correction_attempts,
                    result.validated_at or datetime.utcnow(),
                ),
            )

        logger.debug(f"Saved validation result {result.validation_id}")

    def get_validation_results_by_conversion(
        self,
        conversion_id: str,
    ) -> List[ValidationResult]:
        """
        Get validation results for one conversion.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    validation_id,
                    conversion_id,
                    test_slice,
                    thoughtspot_value,
                    powerbi_value,
                    delta,
                    relative_error,
                    passed,
                    error_category,
                    correction_attempts,
                    validated_at
                FROM validation_results
                WHERE conversion_id = ?
                ORDER BY validated_at
                """,
                (conversion_id,),
            ).fetchall()

        return [ValidationResult.from_db_row(row) for row in rows]

    def get_validation_results_by_migration(
        self,
        migration_id: str,
    ) -> Dict[str, List[ValidationResult]]:
        """
        Get all validation results for a migration.

        Returns:
            Dictionary mapping conversion_id to list of ValidationResult objects.
        """

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    vr.validation_id,
                    vr.conversion_id,
                    vr.test_slice,
                    vr.thoughtspot_value,
                    vr.powerbi_value,
                    vr.delta,
                    vr.relative_error,
                    vr.passed,
                    vr.error_category,
                    vr.correction_attempts,
                    vr.validated_at
                FROM validation_results vr
                JOIN powerbi_conversions pc
                    ON vr.conversion_id = pc.conversion_id
                WHERE pc.migration_id = ?
                ORDER BY vr.conversion_id, vr.validated_at
                """,
                (migration_id,),
            ).fetchall()

        results_by_conversion: Dict[str, List[ValidationResult]] = {}

        for row in rows:
            conversion_id = row["conversion_id"]

            if conversion_id not in results_by_conversion:
                results_by_conversion[conversion_id] = []

            results_by_conversion[conversion_id].append(
                ValidationResult.from_db_row(row)
            )

        logger.debug(
            f"Bulk fetched validation results for "
            f"{len(results_by_conversion)} conversions"
        )

        return results_by_conversion

    def get_validation_summary(
        self,
        migration_id: str,
    ) -> Dict[str, Any]:
        """
        Get validation summary for a migration.
        """

        with get_db_connection() as conn:
            result = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_validations,
                    SUM(CASE WHEN vr.passed = 1 THEN 1 ELSE 0 END) AS passed_count,
                    SUM(CASE WHEN vr.passed = 0 THEN 1 ELSE 0 END) AS failed_count,
                    AVG(vr.delta) AS avg_delta,
                    MAX(vr.delta) AS max_delta,
                    AVG(vr.relative_error) AS avg_relative_error
                FROM validation_results vr
                JOIN powerbi_conversions pc
                    ON vr.conversion_id = pc.conversion_id
                WHERE pc.migration_id = ?
                """,
                (migration_id,),
            ).fetchone()

        if result and result["total_validations"] > 0:
            total = result["total_validations"]
            passed = result["passed_count"] or 0
            failed = result["failed_count"] or 0

            return {
                "total_validations": total,
                "passed_count": passed,
                "failed_count": failed,
                "pass_rate": passed / total if total > 0 else 0,
                "avg_delta": result["avg_delta"],
                "max_delta": result["max_delta"],
                "avg_relative_error": result["avg_relative_error"],
            }

        return {
            "total_validations": 0,
            "passed_count": 0,
            "failed_count": 0,
            "pass_rate": 0,
            "avg_delta": 0,
            "max_delta": 0,
            "avg_relative_error": 0,
        }

    # ============================================================
    # Progress Logs
    # ============================================================

    def get_recent_progress_logs(
        self,
        migration_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get recent migration progress logs.
        """

        limit = min(max(limit, 1), 100)

        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    stage,
                    message,
                    percent,
                    level,
                    object_name,
                    details,
                    timestamp
                FROM migration_progress
                WHERE migration_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (
                    migration_id,
                    limit,
                ),
            ).fetchall()

        logs = []

        for row in rows:
            logs.append(
                {
                    "stage": row["stage"],
                    "message": row["message"],
                    "percent": row["percent"],
                    "level": row["level"],
                    "object_name": row["object_name"],
                    "details": self._json_loads(row["details"], default={}),
                    "timestamp": row["timestamp"],
                }
            )

        return logs

    # ============================================================
    # Existence Helpers
    # ============================================================

    def migration_exists(
        self,
        migration_id: str,
    ) -> bool:
        """
        Check whether migration exists.
        """

        with get_db_connection() as conn:
            count = conn.execute(
                """
                SELECT COUNT(*)
                FROM migration_jobs
                WHERE migration_id = ?
                """,
                (migration_id,),
            ).fetchone()[0]

        return count > 0