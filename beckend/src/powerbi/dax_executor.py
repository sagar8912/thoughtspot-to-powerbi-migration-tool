"""DAX Execution Engine - Execute and test DAX measures using DuckDB as mock Power BI"""
import duckdb
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class DAXExecutionResult:
    """Result of DAX execution"""
    slice_key: str
    dimensions: Dict[str, Any]
    dax_value: Optional[float]
    execution_time_ms: float
    error: Optional[str] = None


class DAXExecutor:
    """
    Execute DAX measures using DuckDB as a lightweight Power BI simulator

    Design Philosophy:
    - DuckDB provides SQL-based testing without full Power BI deployment
    - Converts DAX semantics to SQL equivalents
    - Handles filter context simulation
    - Fast iteration for validation loop

    Limitations:
    - Not a perfect Power BI emulator
    - Complex DAX features (EARLIER, TREATAS) may need custom logic
    - Use for syntactic validation, not production deployment
    """

    def __init__(self, data_source: str):
        """
        Initialize DAX executor

        Args:
            data_source: Path to data file (.hyper, .parquet, .csv, .db)
        """
        self.data_source = data_source
        self.con = duckdb.connect(database=':memory:')

        # Load data into DuckDB
        self._load_data()

        logger.info(f"DAX Executor initialized with {data_source}")

    # ============================================
    # Data Loading
    # ============================================

    def _load_data(self):
        """Load data source into DuckDB"""
        try:
            if self.data_source.endswith('.hyper'):
                # For Hyper files, we need to extract data first
                # DuckDB's spatial extension doesn't directly read Hyper files
                # So we'll use tableauhyperapi to extract, then load into DuckDB
                logger.info("Loading Hyper file via extraction...")

                # Import here to avoid circular dependency
                from src.tableau.hyper_profiler import HyperDataProfiler

                profiler = HyperDataProfiler(self.data_source)
                tables = profiler.list_tables()

                if not tables:
                    raise Exception(f"No tables found in Hyper file: {self.data_source}")

                # Load first table (raw name)
                table_name = tables[0]

                # CRITICAL: Remove quotes from table name before reading
                # HyperDataProfiler.read_table() expects unquoted table names
                clean_table_name = table_name.replace('"', '').replace("'", '')

                # Gap 4: use normalized display name in logs only
                display_name = profiler.get_clean_table_name(table_name)
                logger.info(f"Reading table: {display_name} (raw: {clean_table_name})")
                df = profiler.read_table(clean_table_name)

                # Store original table name for reference
                self.source_table_name = table_name

                # Create table in DuckDB from pandas DataFrame
                # Use simple "data" as table name in DuckDB
                self.con.execute("CREATE TABLE data AS SELECT * FROM df")

                logger.info(f"✅ Loaded Hyper table '{display_name}' into DuckDB ({len(df)} rows)")

            elif self.data_source.endswith('.parquet'):
                self.con.execute(f"CREATE TABLE data AS SELECT * FROM '{self.data_source}'")
                logger.info("✅ Data loaded from Parquet")

            elif self.data_source.endswith('.csv'):
                self.con.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{self.data_source}')")
                logger.info("✅ Data loaded from CSV")

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    # ============================================
    # DAX Execution (SQL Conversion)
    # ============================================

    def execute_dax_measure(
        self,
        dax_formula: str,
        table_name: str,
        dimensions: List[str],
        filters: Optional[List[str]] = None,
        limit: int = 1000
    ) -> Dict[str, DAXExecutionResult]:
        """
        Execute DAX measure by converting to SQL

        Args:
            dax_formula: DAX measure formula
            table_name: Source table name
            dimensions: Grouping columns
            filters: Optional WHERE conditions
            limit: Max results

        Returns:
            Dict mapping slice keys to execution results

        Example:
            >>> executor = DAXExecutor("data.hyper")
            >>> results = executor.execute_dax_measure(
            ...     "SUM([Sales])",
            ...     "Extract",
            ...     ["Region", "Year"]
            ... )
        """
        # Convert DAX to SQL
        sql_measure = self._dax_to_sql(dax_formula)

        # Build query
        query = self._build_execution_query(
            table_name, sql_measure, dimensions, filters, limit
        )

        results = {}

        try:
            import time
            start = time.time()

            # Execute query
            rows = self.con.execute(query).fetchall()

            execution_time = (time.time() - start) * 1000  # ms

            for row in rows:
                dim_values = {dimensions[i]: row[i] for i in range(len(dimensions))}
                dax_value = float(row[-1]) if row[-1] is not None else None

                slice_key = self._make_slice_key(dim_values)

                results[slice_key] = DAXExecutionResult(
                    slice_key=slice_key,
                    dimensions=dim_values,
                    dax_value=dax_value,
                    execution_time_ms=execution_time / max(len(rows), 1),
                    error=None
                )

            logger.info(f"✅ Executed DAX measure - {len(results)} slices in {execution_time:.2f}ms")
            return results

        except Exception as e:
            logger.error(f"DAX execution failed: {e}")
            logger.error(f"Query was: {query}")
            return {}

    # ============================================
    # DAX to SQL Conversion
    # ============================================

    def _dax_to_sql(self, dax_formula: str) -> str:
        """
        Convert simple DAX to SQL equivalent

        Supported patterns:
        - MeasureName = expression → strip the LHS declaration
        - SUM([Column]) -> SUM("Column")
        - AVERAGE([Column]) -> AVG("Column")
        - COUNT([Column]) -> COUNT("Column")
        - DIVIDE([A], [B], 0) -> SUM("A") / NULLIF(SUM("B"), 0)
        - Simple arithmetic: [Sales] - [Cost] -> SUM("Sales") - SUM("Cost")
        """
        import re
        sql = dax_formula.strip()

        # Strip measure-name prefix: "MeasureName = expression" → "expression"
        # DAX measures are stored as full declarations; extract only the formula part.
        # Pattern: identifier (possibly with spaces) followed by ' = '
        # Only strip if the LHS looks like an identifier (not an expression)
        sql = re.sub(r'^[\w_][\w\d_\s]*\s*=\s*', '', sql, count=1)

        # Strip DAX table qualifiers: Table[Column] → [Column]
        # This prevents "Fees[income_class]" from becoming "Fees\"income_class\""
        sql = re.sub(r"\b\w+\[", "[", sql)

        # Replace DAX brackets with SQL quotes
        sql = sql.replace('[', '"').replace(']', '"')


        # DAX functions to SQL equivalents
        replacements = {
            'AVERAGE(': 'AVG(',
            'COUNT(': 'COUNT(',
            'COUNTROWS(': 'COUNT(*)',
            'MIN(': 'MIN(',
            'MAX(': 'MAX(',
            'SUM(': 'SUM(',
            'BLANK()': 'NULL',       # DAX BLANK() → SQL NULL
            'blank()': 'NULL',       # case-insensitive fallback
        }
        for dax_func, sql_func in replacements.items():
            sql = sql.replace(dax_func, sql_func)

        # Convert DAX IF(condition, true_val, false_val) → CASE WHEN ... END
        # DuckDB's IF() is not standard SQL
        def _replace_dax_if(m):
            inner = m.group(1)
            depth = 0
            parts = []
            cur = []
            for ch in inner:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                if ch == ',' and depth == 0:
                    parts.append(''.join(cur).strip())
                    cur = []
                else:
                    cur.append(ch)
            if cur:
                parts.append(''.join(cur).strip())
            if len(parts) == 3:
                return f"CASE WHEN {parts[0]} THEN {parts[1]} ELSE {parts[2]} END"
            return m.group(0)

        sql = re.sub(r'\bIF\s*\((.+)\)', _replace_dax_if, sql, flags=re.IGNORECASE | re.DOTALL)


        # Handle DIVIDE(numerator, denominator, alternate)
        # Convert to: numerator / NULLIF(denominator, 0)
        def replace_divide(m):
            inner = m.group(1)
            # Split on top-level comma
            depth = 0
            parts = []
            cur = []
            for ch in inner:
                if ch == '(' : depth += 1
                elif ch == ')': depth -= 1
                if ch == ',' and depth == 0:
                    parts.append(''.join(cur).strip())
                    cur = []
                else:
                    cur.append(ch)
            if cur:
                parts.append(''.join(cur).strip())
            if len(parts) >= 2:
                return f"{parts[0]} / NULLIF({parts[1]}, 0)"
            return m.group(0)

        sql = re.sub(r'\bDIVIDE\s*\((.+)\)', replace_divide, sql, flags=re.IGNORECASE | re.DOTALL)

        return sql

    def _build_execution_query(
        self,
        table_name: str,
        sql_measure: str,
        dimensions: List[str],
        filters: Optional[List[str]],
        limit: int
    ) -> str:
        """Build SQL query for DAX execution"""

        # IMPORTANT: In DuckDB, we always load data into a table called "data"
        # The table_name parameter is ignored for DuckDB queries
        # We use it only to understand the source, but query against "data"
        quoted_table = "data"

        # Handle empty dimensions (simple aggregation)
        if not dimensions or len(dimensions) == 0:
            query = f"""
                SELECT {sql_measure} as dax_value
                FROM {quoted_table}
            """

            if filters:
                where_clause = " AND ".join(filters)
                query += f"\n                WHERE {where_clause}"

            query += f"\n                LIMIT {limit}"

            return query.strip()

        select_dims = ", ".join([f'"{d}"' for d in dimensions])
        group_by_dims = ", ".join([f'"{d}"' for d in dimensions])
        order_by_dims = ", ".join([f'"{d}"' for d in dimensions])

        query = f"""
            SELECT {select_dims}, {sql_measure} as dax_value
            FROM {quoted_table}
        """

        if filters:
            where_clause = " AND ".join(filters)
            query += f"\n            WHERE {where_clause}"

        query += f"""
            GROUP BY {group_by_dims}
            ORDER BY {order_by_dims}
            LIMIT {limit}
        """

        return query.strip()

    # ============================================
    # Advanced DAX Simulation
    # ============================================

    def execute_dax_with_context(
        self,
        dax_formula: str,
        table_name: str,
        dimensions: List[str],
        calculate_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, DAXExecutionResult]:
        """
        Execute DAX with CALCULATE filter context

        Args:
            dax_formula: Base DAX measure
            table_name: Source table
            dimensions: Grouping columns
            calculate_filters: CALCULATE filter modifiers
                e.g., {"Region": "ALLEXCEPT"} simulates CALCULATE(..., ALLEXCEPT(Table, Region))

        Example:
            # Simulate: CALCULATE(SUM([Sales]), ALLEXCEPT(Table, Table[Region]))
            results = executor.execute_dax_with_context(
                "SUM([Sales])",
                "Extract",
                ["Region", "Year"],
                calculate_filters={"Year": "ALLEXCEPT"}
            )
        """
        # This is a simplified simulation of CALCULATE
        # Real implementation would require full DAX parser

        if not calculate_filters:
            return self.execute_dax_measure(dax_formula, table_name, dimensions)

        # Build modified query based on context modifiers
        # For MVP, we'll pass through to basic execution
        logger.warning("Advanced CALCULATE context simulation not fully implemented")
        return self.execute_dax_measure(dax_formula, table_name, dimensions)

    # ============================================
    # Utility Methods
    # ============================================

    def _make_slice_key(self, dimensions: Dict[str, Any]) -> str:
        """Create composite key from dimensions"""
        sorted_dims = sorted(dimensions.items())
        return "|".join([str(v) for k, v in sorted_dims])

    def close(self):
        """Close DuckDB connection"""
        if self.con:
            self.con.close()
            logger.info("DAX Executor closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================
# Convenience Functions
# ============================================

def test_dax_simple(
    data_source: str,
    dax_formula: str,
    dimensions: List[str],
    table_name: str = "Extract"
) -> Dict[str, float]:
    """
    Quick test function for simple DAX validation

    Args:
        data_source: Path to data file
        dax_formula: DAX measure to test
        dimensions: Grouping columns
        table_name: Table name

    Returns:
        Simple dict of slice_key -> value
    """
    with DAXExecutor(data_source) as executor:
        results = executor.execute_dax_measure(
            dax_formula, table_name, dimensions
        )

        return {key: result.dax_value for key, result in results.items()}


if __name__ == "__main__":
    # Example usage
    print("DAX Execution Engine - Example Usage\n")

    # Mock example (replace with real data)
    EXAMPLE_DATA = "superstore.hyper"

    from pathlib import Path
    if Path(EXAMPLE_DATA).exists():
        with DAXExecutor(EXAMPLE_DATA) as executor:
            results = executor.execute_dax_measure(
                dax_formula="SUM([Sales])",
                table_name='"Extract"."Extract"',
                dimensions=["Region"],
                limit=10
            )

            print(f"Executed DAX measure - {len(results)} slices:")
            for key, result in list(results.items())[:5]:
                print(f"  {result.dimensions} = ${result.dax_value:,.2f} ({result.execution_time_ms:.2f}ms)")
    else:
        print(f"Example file {EXAMPLE_DATA} not found")
        print("This module requires a data source to test")
