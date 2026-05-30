"""
Fidelity Validation Store - Database operations for ThoughtSpot -> Power BI validation.

This store is responsible for:
- Saving high-fidelity validation results
- Saving ThoughtSpot vs Power BI value comparisons
- Saving self-healing correction attempts
- Returning validation history and statistics
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from loguru import logger

from storage.database import get_db_connection


class FidelityValidationStore:
    """
    Store for high-fidelity ThoughtSpot -> Power BI validation results.

    Stores:
    - Validation results from validation services
    - Test slices with ThoughtSpot vs Power BI comparisons
    - Self-healing DAX correction attempts
    """

    def __init__(self):
        """
        Initialize the store.
        """
        logger.info("Fidelity Validation Store initialized")

    # ============================================================
    # Internal Helpers
    # ============================================================

    @staticmethod
    def _get_value(obj: Any, key: str, default: Any = None) -> Any:
        """
        Safely get value from a dataclass/object or dictionary.
        """

        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    @staticmethod
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

    @staticmethod
    def _enum_value(value: Any) -> Any:
        """
        Return enum value if input is Enum, otherwise return same value.
        """

        if hasattr(value, "value"):
            return value.value

        return value

    # ============================================================
    # Validation Results
    # ============================================================

    def save_validation_result(
        self,
        migration_id: str,
        conversion_id: str,
        validation_result: Any,
    ) -> str:
        """
        Save ThoughtSpot -> Power BI fidelity validation result.

        Args:
            migration_id: Migration ID.
            conversion_id: Power BI conversion ID.
            validation_result: Validation result object or dict.

        Expected validation_result fields:
            overall_passed: bool
            pass_rate: float
            correction_attempts: int
            final_dax: str
            test_slices: list

        Each test slice can contain:
            dimensions
            thoughtspot_value
            powerbi_value
            delta
            relative_error
            passed
            error_category

        Returns:
            validation_id
        """

        validation_id = f"val_{uuid.uuid4().hex[:12]}"

        overall_passed = bool(
            self._get_value(validation_result, "overall_passed", False)
        )
        pass_rate = float(
            self._get_value(validation_result, "pass_rate", 0.0) or 0.0
        )
        correction_attempts = int(
            self._get_value(validation_result, "correction_attempts", 0) or 0
        )
        final_dax = self._get_value(validation_result, "final_dax")

        test_slices = self._get_value(validation_result, "test_slices", []) or []

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO fidelity_validations (
                    validation_id,
                    migration_id,
                    conversion_id,
                    overall_passed,
                    pass_rate,
                    correction_attempts,
                    final_dax
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id,
                    migration_id,
                    conversion_id,
                    overall_passed,
                    pass_rate,
                    correction_attempts,
                    final_dax,
                ),
            )

            for test_slice in test_slices:
                slice_id = f"slice_{uuid.uuid4().hex[:12]}"

                dimensions = self._get_value(test_slice, "dimensions", {}) or {}

                thoughtspot_value = self._get_value(
                    test_slice,
                    "thoughtspot_value",
                    self._get_value(test_slice, "source_value"),
                )

                powerbi_value = self._get_value(
                    test_slice,
                    "powerbi_value",
                    self._get_value(test_slice, "target_value"),
                )

                delta = self._get_value(test_slice, "delta", 0.0)
                relative_error = self._get_value(test_slice, "relative_error")
                passed = bool(self._get_value(test_slice, "passed", False))

                error_category = self._enum_value(
                    self._get_value(test_slice, "error_category")
                )

                cursor.execute(
                    """
                    INSERT INTO validation_test_slices (
                        slice_id,
                        validation_id,
                        dimensions,
                        thoughtspot_value,
                        powerbi_value,
                        delta,
                        relative_error,
                        passed,
                        error_category
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slice_id,
                        validation_id,
                        json.dumps(dimensions),
                        thoughtspot_value,
                        powerbi_value,
                        delta,
                        relative_error,
                        passed,
                        error_category,
                    ),
                )

            conn.commit()

        logger.info(
            f"Saved ThoughtSpot -> Power BI validation result {validation_id} "
            f"({pass_rate:.1%} pass rate)"
        )

        return validation_id

    def get_validation_by_migration(
        self,
        migration_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest validation result for a migration.

        Args:
            migration_id: Migration ID.

        Returns:
            Validation result with test slices.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    validation_id,
                    conversion_id,
                    overall_passed,
                    pass_rate,
                    correction_attempts,
                    final_dax,
                    created_at
                FROM fidelity_validations
                WHERE migration_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (migration_id,),
            )

            row = cursor.fetchone()

            if not row:
                return None

            validation_id = row["validation_id"]

            test_slices = self.get_test_slices(validation_id)

            return {
                "validation_id": validation_id,
                "migration_id": migration_id,
                "conversion_id": row["conversion_id"],
                "overall_passed": bool(row["overall_passed"]),
                "pass_rate": row["pass_rate"],
                "correction_attempts": row["correction_attempts"],
                "final_dax": row["final_dax"],
                "created_at": row["created_at"],
                "test_slices": test_slices,
            }

    def get_validation_by_conversion(
        self,
        conversion_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest validation result for a specific conversion.

        Args:
            conversion_id: Conversion ID.

        Returns:
            Validation result with test slices.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    validation_id,
                    migration_id,
                    overall_passed,
                    pass_rate,
                    correction_attempts,
                    final_dax,
                    created_at
                FROM fidelity_validations
                WHERE conversion_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (conversion_id,),
            )

            row = cursor.fetchone()

            if not row:
                return None

            validation_id = row["validation_id"]

            test_slices = self.get_test_slices(validation_id)

            return {
                "validation_id": validation_id,
                "migration_id": row["migration_id"],
                "conversion_id": conversion_id,
                "overall_passed": bool(row["overall_passed"]),
                "pass_rate": row["pass_rate"],
                "correction_attempts": row["correction_attempts"],
                "final_dax": row["final_dax"],
                "created_at": row["created_at"],
                "test_slices": test_slices,
            }

    def get_all_validations_by_migration(
        self,
        migration_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all validation results for a migration.

        Args:
            migration_id: Migration ID.

        Returns:
            List of validation results.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    validation_id,
                    conversion_id,
                    overall_passed,
                    pass_rate,
                    correction_attempts,
                    final_dax,
                    created_at
                FROM fidelity_validations
                WHERE migration_id = ?
                ORDER BY created_at DESC
                """,
                (migration_id,),
            )

            validations = []

            for row in cursor.fetchall():
                validation_id = row["validation_id"]

                validations.append(
                    {
                        "validation_id": validation_id,
                        "migration_id": migration_id,
                        "conversion_id": row["conversion_id"],
                        "overall_passed": bool(row["overall_passed"]),
                        "pass_rate": row["pass_rate"],
                        "correction_attempts": row["correction_attempts"],
                        "final_dax": row["final_dax"],
                        "created_at": row["created_at"],
                        "test_slices": self.get_test_slices(validation_id),
                    }
                )

            return validations

    def get_test_slices(
        self,
        validation_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get test slices for a validation result.

        Args:
            validation_id: Validation ID.

        Returns:
            List of test slices.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    slice_id,
                    dimensions,
                    thoughtspot_value,
                    powerbi_value,
                    delta,
                    relative_error,
                    passed,
                    error_category
                FROM validation_test_slices
                WHERE validation_id = ?
                ORDER BY slice_id
                """,
                (validation_id,),
            )

            test_slices = []

            for row in cursor.fetchall():
                test_slices.append(
                    {
                        "slice_id": row["slice_id"],
                        "dimensions": self._json_loads_safe(
                            row["dimensions"],
                            default={},
                        ),
                        "thoughtspot_value": row["thoughtspot_value"],
                        "powerbi_value": row["powerbi_value"],
                        "delta": row["delta"],
                        "relative_error": row["relative_error"],
                        "passed": bool(row["passed"]),
                        "error_category": row["error_category"],
                    }
                )

            return test_slices

    # ============================================================
    # Correction Attempts
    # ============================================================

    def save_correction_attempt(
        self,
        validation_id: str,
        attempt_number: int,
        original_dax: str,
        corrected_dax: str,
        root_cause: str,
        explanation: str,
        changes_made: List[str],
    ) -> str:
        """
        Save self-healing correction attempt.

        Args:
            validation_id: Validation ID.
            attempt_number: Attempt number.
            original_dax: Original DAX that failed.
            corrected_dax: Corrected DAX.
            root_cause: Root cause analysis.
            explanation: Explanation of correction.
            changes_made: List of changes.

        Returns:
            attempt_id
        """

        attempt_id = f"attempt_{uuid.uuid4().hex[:12]}"

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO correction_attempts (
                    attempt_id,
                    validation_id,
                    attempt_number,
                    original_dax,
                    corrected_dax,
                    root_cause,
                    explanation,
                    changes_made
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    validation_id,
                    attempt_number,
                    original_dax,
                    corrected_dax,
                    root_cause,
                    explanation,
                    json.dumps(changes_made or []),
                ),
            )

            conn.commit()

        logger.info(f"Saved correction attempt {attempt_number} for {validation_id}")

        return attempt_id

    def get_correction_history(
        self,
        validation_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all correction attempts for a validation.

        Args:
            validation_id: Validation ID.

        Returns:
            List of correction attempts.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    attempt_id,
                    attempt_number,
                    original_dax,
                    corrected_dax,
                    root_cause,
                    explanation,
                    changes_made,
                    created_at
                FROM correction_attempts
                WHERE validation_id = ?
                ORDER BY attempt_number
                """,
                (validation_id,),
            )

            attempts = []

            for row in cursor.fetchall():
                attempts.append(
                    {
                        "attempt_id": row["attempt_id"],
                        "attempt_number": row["attempt_number"],
                        "original_dax": row["original_dax"],
                        "corrected_dax": row["corrected_dax"],
                        "root_cause": row["root_cause"],
                        "explanation": row["explanation"],
                        "changes_made": self._json_loads_safe(
                            row["changes_made"],
                            default=[],
                        ),
                        "created_at": row["created_at"],
                    }
                )

            return attempts

    def get_correction_history_by_migration(
        self,
        migration_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all correction attempts for a migration.

        Args:
            migration_id: Migration ID.

        Returns:
            List of correction attempts across all validations.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    ca.attempt_id,
                    ca.attempt_number,
                    ca.original_dax,
                    ca.corrected_dax,
                    ca.root_cause,
                    ca.explanation,
                    ca.changes_made,
                    ca.created_at,
                    fv.validation_id,
                    fv.conversion_id
                FROM correction_attempts ca
                JOIN fidelity_validations fv
                    ON ca.validation_id = fv.validation_id
                WHERE fv.migration_id = ?
                ORDER BY ca.created_at
                """,
                (migration_id,),
            )

            attempts = []

            for row in cursor.fetchall():
                attempts.append(
                    {
                        "attempt_id": row["attempt_id"],
                        "attempt_number": row["attempt_number"],
                        "original_dax": row["original_dax"],
                        "corrected_dax": row["corrected_dax"],
                        "root_cause": row["root_cause"],
                        "explanation": row["explanation"],
                        "changes_made": self._json_loads_safe(
                            row["changes_made"],
                            default=[],
                        ),
                        "created_at": row["created_at"],
                        "validation_id": row["validation_id"],
                        "conversion_id": row["conversion_id"],
                    }
                )

            return attempts

    # ============================================================
    # Statistics
    # ============================================================

    def get_validation_stats(
        self,
        migration_id: str,
    ) -> Dict[str, Any]:
        """
        Get validation statistics for a migration.

        Args:
            migration_id: Migration ID.

        Returns:
            Statistics summary.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_validations,
                    AVG(pass_rate) AS avg_pass_rate,
                    SUM(CASE WHEN overall_passed THEN 1 ELSE 0 END) AS perfect_matches,
                    SUM(correction_attempts) AS total_corrections
                FROM fidelity_validations
                WHERE migration_id = ?
                """,
                (migration_id,),
            )

            row = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    error_category,
                    COUNT(*) AS count
                FROM validation_test_slices vts
                JOIN fidelity_validations fv
                    ON vts.validation_id = fv.validation_id
                WHERE fv.migration_id = ?
                AND vts.passed = 0
                GROUP BY error_category
                """,
                (migration_id,),
            )

            error_breakdown = {
                error_row["error_category"] or "UNKNOWN": error_row["count"]
                for error_row in cursor.fetchall()
            }

            total_validations = row["total_validations"] or 0
            avg_pass_rate = row["avg_pass_rate"] or 0
            perfect_matches = row["perfect_matches"] or 0
            total_corrections = row["total_corrections"] or 0

            return {
                "migration_id": migration_id,
                "total_validations": total_validations,
                "avg_pass_rate": avg_pass_rate,
                "avg_pass_rate_percent": round(avg_pass_rate * 100, 2),
                "perfect_matches": perfect_matches,
                "total_corrections": total_corrections,
                "error_breakdown": error_breakdown,
            }

    def get_failed_test_slices(
        self,
        migration_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all failed validation test slices for a migration.

        Args:
            migration_id: Migration ID.

        Returns:
            Failed test slices.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    fv.validation_id,
                    fv.conversion_id,
                    vts.slice_id,
                    vts.dimensions,
                    vts.thoughtspot_value,
                    vts.powerbi_value,
                    vts.delta,
                    vts.relative_error,
                    vts.error_category
                FROM validation_test_slices vts
                JOIN fidelity_validations fv
                    ON vts.validation_id = fv.validation_id
                WHERE fv.migration_id = ?
                AND vts.passed = 0
                ORDER BY fv.created_at DESC
                """,
                (migration_id,),
            )

            failed_slices = []

            for row in cursor.fetchall():
                failed_slices.append(
                    {
                        "validation_id": row["validation_id"],
                        "conversion_id": row["conversion_id"],
                        "slice_id": row["slice_id"],
                        "dimensions": self._json_loads_safe(
                            row["dimensions"],
                            default={},
                        ),
                        "thoughtspot_value": row["thoughtspot_value"],
                        "powerbi_value": row["powerbi_value"],
                        "delta": row["delta"],
                        "relative_error": row["relative_error"],
                        "error_category": row["error_category"],
                    }
                )

            return failed_slices

    def delete_validation(
        self,
        validation_id: str,
    ) -> bool:
        """
        Delete a validation result and its related slices/correction attempts.

        Args:
            validation_id: Validation ID.

        Returns:
            True if deleted, False otherwise.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM fidelity_validations
                WHERE validation_id = ?
                """,
                (validation_id,),
            )

            deleted = cursor.rowcount > 0

            conn.commit()

        if deleted:
            logger.info(f"Deleted validation result {validation_id}")

        return deleted

    def delete_validations_by_migration(
        self,
        migration_id: str,
    ) -> int:
        """
        Delete all validation results for a migration.

        Args:
            migration_id: Migration ID.

        Returns:
            Number of deleted validation records.
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM fidelity_validations
                WHERE migration_id = ?
                """,
                (migration_id,),
            )

            deleted = cursor.rowcount

            conn.commit()

        logger.info(
            f"Deleted {deleted} validation results for migration {migration_id}"
        )

        return deleted