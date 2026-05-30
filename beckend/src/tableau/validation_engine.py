"""Validation Engine - Test functional equivalence of Tableau vs DAX formulas"""
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from loguru import logger

from src.tableau.hyper_profiler import HyperDataProfiler
from src.tableau.dax_generator import DAXGenerator, DAXResult
from src.tableau.truth_extractor import TruthMapExtractor, TruthSlice as TruthSliceData
from src.powerbi.dax_executor import DAXExecutor, DAXExecutionResult
from api.models.migration_models import ErrorCategory


@dataclass
class TestSlice:
    """A test slice for validation"""
    dimensions: Dict[str, Any]  # e.g., {"Region": "East", "Year": 2024}
    tableau_value: Optional[float]
    dax_value: Optional[float]
    delta: float
    relative_error: float
    passed: bool
    error_category: ErrorCategory


@dataclass
class ValidationResult:
    """Overall validation result for a conversion"""
    conversion_id: str
    test_slices: List[TestSlice]
    overall_passed: bool
    pass_rate: float
    correction_attempts: int
    final_dax: str
    needs_manual_review: bool = False  # Flag when validation was skipped or has issues


class ValidationEngine:
    """
    Validation engine for testing functional equivalence

    Design:
    1. Extract ground truth from Tableau (Hyper file)
    2. Execute DAX candidate (using DuckDB as mock Power BI)
    3. Compare results with epsilon tolerance
    4. Categorize discrepancies
    5. Trigger self-correction if needed
    """

    def __init__(self, epsilon: float = 0.0001, max_correction_attempts: int = 3):
        """
        Initialize validation engine

        Args:
            epsilon: Tolerance for floating-point comparison (default: 0.01%)
            max_correction_attempts: Maximum self-correction loops
        """
        self.epsilon = epsilon
        self.max_correction_attempts = max_correction_attempts
        self.dax_generator = DAXGenerator()

        # NEW: Initialize truth extractor and DAX executor
        self.truth_extractor = TruthMapExtractor()
        logger.info("Validation Engine initialized with Truth Extractor and DAX Executor")

        # DuckDB validation disabled — commented out while DAX generation is being stabilised.
        # Re-enable by uncommenting the block below.
        # try:
        #     import duckdb
        #     self.duckdb_conn = duckdb.connect()
        #     logger.info("DuckDB initialized for DAX validation")
        # except ImportError:
        #     logger.warning("DuckDB not available - validation will be limited")
        #     self.duckdb_conn = None
        self.duckdb_conn = None  # Validation disabled

    # ============================================
    # Main Validation Flow
    # ============================================

    def validate_conversion_v2(
        self,
        conversion_id: str,
        tableau_formula: str,
        dax_formula: str,
        hyper_path: str,
        table_name: str,
        dimensions: List[str],
        filters: Optional[List[str]] = None,
        migration_id: Optional[str] = None,  # C2 fix: explicit param
        raw_table_name: Optional[str] = None  # Full Hyper schema.table for truth extractor
    ) -> ValidationResult:
        """
        High-fidelity validation using Truth Map Extractor and DAX Executor.
        C2 fix: accepts migration_id explicitly instead of parsing from conversion_id.
        C4 fix: uses relative epsilon instead of absolute.
        """
        logger.info(f"🔍 High-fidelity validation for {conversion_id}")
        logger.info(f"  Tableau: {tableau_formula}")
        logger.info(f"  DAX: {dax_formula[:100]}...")

        # Check if formula references other calculations
        if self._references_calculated_fields(tableau_formula):
            logger.info(f"🔄 Formula references calculated fields - attempting expansion...")

            if migration_id:
                expanded_formula = self._expand_calculated_field_references(
                    tableau_formula,
                    migration_id=migration_id,
                    calc_name=conversion_id
                )
                if expanded_formula:
                    logger.info(f"✅ Expanded formula: {expanded_formula[:100]}...")
                    tableau_formula = expanded_formula
                else:
                    return self._manual_review_result(conversion_id, dax_formula,
                        "Could not expand calculated fields")
            else:
                return self._manual_review_result(conversion_id, dax_formula,
                    "No migration_id provided")

        current_dax = dax_formula
        correction_attempts = 0
        slice_results = []

        # Validation loop with self-correction
        while correction_attempts <= self.max_correction_attempts:
            slice_results = []

            try:
                # Step 1: Extract Truth Map from Tableau
                logger.info("📊 Extracting ground truth from Hyper file...")
                # Use raw_table_name (full Hyper schema.table) if available, else clean name
                truth_table = raw_table_name if raw_table_name else table_name
                truth_map = self.truth_extractor.extract_truth_map(
                    data_source=hyper_path,
                    table_name=truth_table,
                    calculation=self._tableau_to_sql(tableau_formula),
                    dimensions=dimensions,
                    filters=filters,
                    limit=100  # Test sample
                )

                if not truth_map:
                    logger.warning("⚠️ No truth data extracted - likely missing columns (calculated fields)")
                    # Return early with skip status - flag for manual review
                    return ValidationResult(
                        conversion_id=conversion_id,
                        test_slices=[],
                        overall_passed=False,  # Changed from True - this is a failure!
                        pass_rate=0.0,  # Changed from 1.0
                        final_dax=dax_formula,
                        correction_attempts=0,
                        needs_manual_review=True  # Flag for manual review
                    )

                logger.info(f"✅ Extracted {len(truth_map)} truth slices")

                # Step 2: Execute DAX Candidate
                logger.info("⚙️ Executing DAX candidate...")
                dax_executor = DAXExecutor(hyper_path)
                dax_results = dax_executor.execute_dax_measure(
                    dax_formula=current_dax,
                    table_name=table_name,
                    dimensions=dimensions,
                    filters=filters,
                    limit=100
                )

                if not dax_results:
                    logger.warning("⚠️ DAX execution failed - validation cannot proceed")
                    break

                logger.info(f"✅ Executed DAX - {len(dax_results)} result slices")

                # Step 3: Compare Results
                logger.info("🔬 Comparing truth vs. DAX...")
                for slice_key, truth_slice in truth_map.items():
                    dax_result = dax_results.get(slice_key)

                    if not dax_result:
                        # DAX didn't return this slice
                        slice_results.append(TestSlice(
                            dimensions=truth_slice.dimensions,
                            tableau_value=truth_slice.truth_value,
                            dax_value=None,
                            delta=float('inf'),
                            relative_error=float('inf'),
                            passed=False,
                            error_category=ErrorCategory.MISSING_VALUE
                        ))
                        continue

                    # Compare values
                    truth_val = truth_slice.truth_value or 0
                    dax_val = dax_result.dax_value or 0

                    delta = abs(truth_val - dax_val)
                    relative_error = (delta / abs(truth_val)) if truth_val != 0 else 0

                    # C4 fix: use relative error with absolute floor for near-zero
                    if abs(truth_val) < 1e-8:
                        passed = delta <= self.epsilon  # absolute for near-zero
                    else:
                        passed = relative_error <= self.epsilon  # relative otherwise

                    error_category = self._categorize_error_v2(
                        truth_val, dax_val, delta, relative_error
                    ) if not passed else ErrorCategory.PERFECT_MATCH

                    slice_results.append(TestSlice(
                        dimensions=truth_slice.dimensions,
                        tableau_value=truth_val,
                        dax_value=dax_val,
                        delta=delta,
                        relative_error=relative_error,
                        passed=passed,
                        error_category=error_category
                    ))

                # Step 4: Check if all passed
                passed_count = sum(1 for s in slice_results if s.passed)
                pass_rate = (passed_count / len(slice_results)) if slice_results else 0

                logger.info(f"📈 Pass Rate: {pass_rate:.1%} ({passed_count}/{len(slice_results)} slices)")

                if pass_rate == 1.0:
                    logger.info("✅ 100% VALIDATION SUCCESS - All slices matched!")
                    break

                # Step 5: Self-Correction
                failures = [s for s in slice_results if not s.passed]

                if correction_attempts >= self.max_correction_attempts:
                    logger.warning(f"⚠️ Max correction attempts reached. Final pass rate: {pass_rate:.1%}")
                    break

                logger.info(f"❌ {len(failures)} slices failed. Triggering self-correction...")

                corrected_dax = self._self_correct(
                    original_tableau=tableau_formula,
                    failed_dax=current_dax,
                    failures=failures,
                    attempt=correction_attempts + 1
                )

                if corrected_dax == current_dax:
                    logger.warning("Self-correction returned same formula. Stopping.")
                    break

                current_dax = corrected_dax
                correction_attempts += 1
                logger.info(f"🔄 Retrying with corrected DAX (attempt {correction_attempts + 1})...")

                dax_executor.close()

            except Exception as e:
                logger.error(f"Validation error: {e}")
                break

        # Final result
        final_pass_rate = (sum(1 for s in slice_results if s.passed) / len(slice_results)) if slice_results else 0

        return ValidationResult(
            conversion_id=conversion_id,
            test_slices=slice_results,
            overall_passed=all(s.passed for s in slice_results),
            pass_rate=final_pass_rate,
            correction_attempts=correction_attempts,
            final_dax=current_dax
        )

    def _tableau_to_sql(self, tableau_formula: str) -> str:
        """Convert Tableau formula to SQL — delegates to the canonical implementation
        in TruthMapExtractor so both paths use identical conversion logic."""
        return self.truth_extractor._tableau_to_sql(tableau_formula)

    def _manual_review_result(self, conversion_id: str, dax_formula: str, reason: str) -> ValidationResult:
        """Helper to create a manual-review ValidationResult."""
        logger.warning(f"⚠️ {reason} - flagging for manual review")
        return ValidationResult(
            conversion_id=conversion_id,
            test_slices=[],
            overall_passed=False,
            pass_rate=0.0,
            final_dax=dax_formula,
            correction_attempts=0,
            needs_manual_review=True
        )

    def _categorize_error_v2(
        self,
        truth_value: float,
        dax_value: float,
        delta: float,
        relative_error: float
    ) -> ErrorCategory:
        """
        Enhanced error categorization with detailed diagnostics

        Categories:
        - PERFECT_MATCH: Delta < 1e-10
        - ROUNDING_ERROR: Relative error < 0.01%
        - SCALE_ERROR: Off by 10x, 100x (percentage vs decimal)
        - NULL_HANDLING: One is 0, other is not
        - CONTEXT_SHIFT: Relative error > 10% (likely filter context)
        - GRAIN_MISMATCH: Values don't align (likely LOD issue)
        - AGGREGATION_MISMATCH: Other arithmetic errors
        """
        # Perfect match
        if delta < 1e-10:
            return ErrorCategory.PERFECT_MATCH

        # Rounding error (negligible)
        if relative_error < 0.0001:  # 0.01%
            return ErrorCategory.ROUNDING_ERROR

        # Scale error (order of magnitude)
        if truth_value != 0 and dax_value != 0:
            ratio = truth_value / dax_value
            if abs(ratio - 100) < 1 or abs(ratio - 0.01) < 0.0001:
                # Off by 100x (percentage vs decimal)
                return ErrorCategory.SCALE_ERROR
            if abs(ratio - 10) < 0.1 or abs(ratio - 0.1) < 0.01:
                # Off by 10x
                return ErrorCategory.SCALE_ERROR

        # Null handling difference
        if (truth_value == 0 and dax_value != 0) or (truth_value != 0 and dax_value == 0):
            return ErrorCategory.NULL_HANDLING

        # Context shift (likely CALCULATE issue)
        if relative_error > 0.1:  # 10%+
            return ErrorCategory.CONTEXT_SHIFT

        # Grain mismatch (LOD issue)
        if relative_error > 0.05:  # 5-10%
            return ErrorCategory.GRAIN_MISMATCH

        # Default: aggregation mismatch
        return ErrorCategory.AGGREGATION_MISMATCH

    # R2: Legacy validate_conversion, _test_slice, _execute_tableau_formula,
    # _execute_dax_formula, _translate_dax_to_sql, _build_where_clause,
    # and _categorize_error methods have been removed.
    # The v2 methods above are the sole validation path.

    # ============================================
    # Self-Correction
    # ============================================

    def _self_correct(
        self,
        original_tableau: str,
        failed_dax: str,
        failures: List[TestSlice],
        attempt: int
    ) -> str:
        """
        Trigger self-correction loop

        Args:
            original_tableau: Original Tableau formula
            failed_dax: DAX that failed validation
            failures: List of failed test slices
            attempt: Correction attempt number

        Returns:
            Corrected DAX formula
        """
        logger.info(f"Self-correction attempt {attempt}")

        # Build diagnostic prompt
        failure_summary = self._summarize_failures(failures)

        prompt = f"""You are debugging a Tableau-to-DAX conversion that failed validation.

## ORIGINAL TABLEAU FORMULA

```tableau
{original_tableau}
```

## YOUR GENERATED DAX (FAILED)

```dax
{failed_dax}
```

## VALIDATION FAILURES

{failure_summary}

## YOUR TASK

Analyze the failures and generate a CORRECTED DAX formula.

**Common issues to check:**
1. **Filter Context:** Are you using CALCULATE, ALL, ALLEXCEPT correctly?
2. **Null Handling:** Did you use DIVIDE() with proper default value?
3. **Aggregation Level:** Is this a measure or calculated column?
4. **LOD Equivalence:** Did you properly map FIXED/INCLUDE/EXCLUDE?
5. **Scale:** Are you calculating percentages vs. decimals?

**Provide:**
1. Root cause analysis
2. Corrected DAX formula
3. Explanation of changes

## OUTPUT FORMAT

Return ONLY valid JSON:

{{
  "root_cause": "Description of what went wrong...",
  "corrected_dax": "Corrected DAX = ...",
  "explanation": "I changed X to Y because..."
}}
"""

        try:
            from src.llm_reasoner import LLMReasoner
            llm = LLMReasoner()

            response = llm.reason(prompt)

            # Parse response
            import json

            # Clean markdown
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            corrected_dax = data.get("corrected_dax", failed_dax)
            explanation = data.get("explanation", "")

            logger.info(f"Self-correction: {explanation}")

            return corrected_dax

        except Exception as e:
            logger.error(f"Self-correction failed: {e}")
            return failed_dax

    def _summarize_failures(self, failures: List[TestSlice]) -> str:
        """Create human-readable failure summary"""
        lines = []

        for i, failure in enumerate(failures, 1):
            lines.append(f"**Failure {i}:**")
            lines.append(f"  Dimensions: {failure.dimensions}")
            lines.append(f"  Expected (Tableau): {failure.tableau_value}")
            lines.append(f"  Got (DAX): {failure.dax_value}")
            lines.append(f"  Delta: {failure.delta} ({failure.relative_error:.2%} error)")
            lines.append(f"  Error Category: {failure.error_category.value}")
            lines.append("")

        return "\n".join(lines)

    # ============================================
    # Utility Methods
    # ============================================

    def _expand_calculated_field_references(
        self,
        formula: str,
        migration_id: str,
        calc_name: str,
        max_depth: int = 10
    ) -> Optional[str]:
        """
        Recursively expand calculated field references to base columns only

        Example:
            Input:  "SUM([Net Profit]) / SUM([Revenue])"
            Where:  [Net Profit] = "SUM([Revenue]) - SUM([Cost])"
            Output: "SUM(SUM([Revenue]) - SUM([Cost])) / SUM([Revenue])"

        Args:
            formula: Tableau formula with calculated field references
            migration_id: Migration ID to lookup calculations
            calc_name: Current calculation name (for logging)
            max_depth: Maximum recursion depth to prevent circular dependencies

        Returns:
            Expanded formula with only base column references, or None if circular dependency
        """
        from storage.migration_store import MigrationStore

        try:
            store = MigrationStore()
            calculations = store.get_calculations_by_migration(migration_id)

            # Build lookup: {calc_name: {formula, metadata}}
            calc_map = {}
            for calc in calculations:
                if calc.depends_on_metadata:
                    calc_map[calc.calc_name] = {
                        "formula": calc.calc_formula,
                        "depends_on": calc.depends_on or [],
                        "metadata": calc.depends_on_metadata
                    }

            # Recursive expansion with depth limit
            expanded = formula
            depth = 0

            while depth < max_depth:
                # Find all [FieldName] references
                pattern = r'\[([^\]]+)\]'
                matches = re.findall(pattern, expanded)

                made_substitution = False
                for match in matches:
                    if match in calc_map:
                        # Check if this is a calculated measure (already aggregated)
                        metadata = calc_map[match]["metadata"]

                        # Look for this field in the metadata
                        field_info = metadata.get(match)
                        if field_info and field_info.get("field_type") == "CALCULATED_MEASURE":
                            # This is already a measure - substitute with its formula
                            calc_formula = calc_map[match]["formula"]
                            # Wrap in parentheses to preserve precedence
                            expanded = expanded.replace(f"[{match}]", f"({calc_formula})")
                            made_substitution = True
                            logger.debug(f"  Expanded [{match}] → ({calc_formula[:50]}...)")

                if not made_substitution:
                    # No more calculated field references to expand
                    break

                depth += 1

            if depth >= max_depth:
                logger.warning(f"Max recursion depth reached for {calc_name} - possible circular dependency")
                return None

            return expanded

        except Exception as e:
            logger.error(f"Failed to expand calculated field references: {e}")
            return None

    def _references_calculated_fields(self, formula: str) -> bool:
        """
        Check if a Tableau formula references other calculated fields

        Calculated fields in Hyper extracts are named like:
        - Calculation_1753307659340042248
        - Meeting_C95B117F736D4522AE7C2584C4641D3A
        - income_class (Invoice) - calculated field from related table
        - stage - custom calculated dimension

        These don't exist as physical columns in the Hyper file,
        so we can't validate calculations that reference them.

        Args:
            formula: Tableau calculation formula

        Returns:
            True if references calculated fields, False otherwise
        """
        import re

        # Pattern 1: Calculation_<numeric_id>
        if re.search(r'\bCalculation_\d+\b', formula):
            logger.debug("Detected Calculation_* pattern")
            return True

        # Pattern 2: <Table>_<hex_guid> (e.g., Meeting_C95B...)
        if re.search(r'\b[A-Za-z]+_[A-F0-9]{32}\b', formula):
            logger.debug("Detected table GUID pattern")
            return True

        # Pattern 3: Field names with table references in parentheses
        # e.g., "income_class (Invoice)", "Amount (Fees)"
        # These often indicate calculated fields from related tables
        if re.search(r'"\w+\s+\([A-Z][a-z]+\)"', formula):
            logger.debug("Detected related table field pattern")
            return True

        return False

    def close(self):
        """Clean up resources"""
        if self.duckdb_conn:
            self.duckdb_conn.close()
