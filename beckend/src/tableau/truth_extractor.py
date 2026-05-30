"""Truth Map Extractor - Extract ground truth from Tableau Hyper files for validation"""
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

try:
    from tableauhyperapi import HyperProcess, Telemetry, Connection, CreateMode
    HYPER_AVAILABLE = True
except ImportError:
    HYPER_AVAILABLE = False
    logger.warning("tableauhyperapi not available - using DuckDB fallback")

import duckdb


@dataclass
class TruthSlice:
    """A single test slice with ground truth value"""
    dimensions: Dict[str, Any]  # e.g., {"Region": "East", "Year": 2024}
    truth_value: Optional[float]
    slice_key: str  # Composite key for matching


class TruthMapExtractor:
    """
    Extract ground truth from Tableau data sources for validation

    Design:
    1. Query Hyper file with same dimensions as DAX test
    2. Generate "Truth Map" - expected results for test slices
    3. Support both Hyper API and DuckDB fallback
    4. Handle NULL values and edge cases
    """

    def __init__(self, use_hyper: bool = HYPER_AVAILABLE):
        """
        Initialize truth extractor

        Args:
            use_hyper: Use Hyper API if available, otherwise DuckDB
        """
        self.use_hyper = use_hyper and HYPER_AVAILABLE
        # Cache: hyper_path → {raw_table_name: set(lowercase_col_names)}
        # Built once per hyper file, reused for all formula scorings
        self._table_cols_cache: Dict[str, Dict[str, set]] = {}
        logger.info(f"Truth Map Extractor initialized (Hyper: {self.use_hyper})")

    # ============================================
    # Main Extraction Methods
    # ============================================

    def extract_truth_map(
        self,
        data_source: str,
        table_name: str,
        calculation: str,
        dimensions: List[str],
        filters: Optional[List[str]] = None,
        limit: int = 1000
    ) -> Dict[str, TruthSlice]:
        """
        Extract ground truth from data source

        Args:
            data_source: Path to .hyper file or DuckDB-compatible file
            table_name: Table/schema name (e.g., "Extract" or "public.Orders")
            calculation: SQL expression for measure (e.g., 'SUM("Sales")')
            dimensions: List of dimension columns to group by
            filters: Optional WHERE conditions (e.g., ['Category = "Tech"'])
            limit: Max slices to extract (prevent memory issues)

        Returns:
            Truth map keyed by composite dimension string

        Example:
            >>> extractor = TruthMapExtractor()
            >>> truth = extractor.extract_truth_map(
            ...     "data.hyper",
            ...     "Extract",
            ...     'SUM("Sales")',
            ...     ["Region", "Year"]
            ... )
            >>> # Returns: {"East|2024": TruthSlice(...), "West|2024": TruthSlice(...)}
        """
        if self.use_hyper:
            return self._extract_from_hyper(
                data_source, table_name, calculation, dimensions, filters, limit
            )
        else:
            return self._extract_from_duckdb(
                data_source, table_name, calculation, dimensions, filters, limit
            )

    # ============================================
    # Hyper API Implementation
    # ============================================

    def _extract_from_hyper(
        self,
        hyper_path: str,
        table_name: str,
        calculation: str,
        dimensions: List[str],
        filters: Optional[List[str]],
        limit: int
    ) -> Dict[str, TruthSlice]:
        """Extract using Tableau Hyper API with auto table-detection."""
        if not HYPER_AVAILABLE:
            raise Exception("tableauhyperapi not installed - use DuckDB fallback")

        # Convert Tableau formula to SQL (strips (TableName) qualifiers automatically)
        sql_calculation = self._tableau_to_sql(calculation)

        # Auto-detect the best-matching Hyper table for this formula's columns
        best_table = self._find_best_table(hyper_path, sql_calculation)
        resolved_table = best_table if best_table else table_name
        if resolved_table != table_name:
            logger.info(f"Auto-selected table: {resolved_table} (requested: {table_name})")

        # ── Calculated-field guard ────────────────────────────────────────────
        # Some formulas reference OTHER calculated fields (e.g. Calculation_175…)
        # that are computed by Tableau at runtime and never stored in any Hyper
        # table. Querying for them always fails. Detect this early and skip.
        #
        # Two signals mark a reference as a calculated field, not a raw column:
        #   1. Name matches Tableau's internal pattern  Calculation_\d+
        #   2. Name is not present in ANY table's physical column set (cache)
        # Only block Tableau's auto-named internal calc fields (Calculation_\d+)
        # Do NOT use the all_cols_in_file check — it would wrongly block real columns
        # like "Amount", "Cross sell bugdet" etc. if the cache wasn't warm yet.
        quoted_refs = set(re.findall(r'"([^"]+)"', sql_calculation))
        calc_pattern = re.compile(r'^Calculation_\d+$')
        phantom_cols = {c for c in quoted_refs if calc_pattern.match(c)}

        if phantom_cols:
            logger.warning(
                f"⚠️  Skipping truth extraction — formula references intermediate "
                f"calculated fields not stored in raw data: {phantom_cols}"
            )
            return {}
        # ─────────────────────────────────────────────────────────────────────

        # Build SQL query against the resolved table
        query = self._build_sql_query(resolved_table, sql_calculation, dimensions, filters, limit)

        truth_map = {}

        try:
            try:
                telemetry = Telemetry.DO_NOT_SEND_USAGE_DATA
            except AttributeError:
                telemetry = Telemetry.SEND_USAGE_DATA_TO_TABLEAU

            with HyperProcess(telemetry=telemetry) as hyper:
                with Connection(endpoint=hyper.endpoint, database=hyper_path) as connection:
                    result = connection.execute_list_query(query)

                    for row in result:
                        dim_values = {dimensions[i]: row[i] for i in range(len(dimensions))}
                        truth_value = float(row[-1]) if row[-1] is not None else None
                        slice_key = self._make_slice_key(dim_values)
                        truth_map[slice_key] = TruthSlice(
                            dimensions=dim_values,
                            truth_value=truth_value,
                            slice_key=slice_key
                        )

            logger.info(f"✅ Extracted {len(truth_map)} truth slices from Hyper")
            return truth_map

        except Exception as e:
            logger.error(f"Hyper extraction failed: {e}")
            logger.info("Falling back to DuckDB...")
            return self._extract_from_duckdb(
                hyper_path, resolved_table, calculation, dimensions, filters, limit
            )


    # ============================================
    # DuckDB Fallback Implementation
    # ============================================

    def _extract_from_duckdb(
        self,
        data_source: str,
        table_name: str,
        calculation: str,
        dimensions: List[str],
        filters: Optional[List[str]],
        limit: int
    ) -> Dict[str, TruthSlice]:
        """Extract using DuckDB — for Hyper files loads data via HyperDataProfiler."""

        sql_calculation = self._tableau_to_sql(calculation)
        truth_map = {}

        try:
            con = duckdb.connect(database=':memory:')

            if data_source.endswith('.hyper'):
                # For Hyper files, load the matching table into DuckDB as "data"
                # (DuckDB cannot query Hyper schema-qualified names directly)
                try:
                    from src.tableau.hyper_profiler import HyperDataProfiler
                    profiler = HyperDataProfiler(data_source)
                    # Resolve best table (same logic as Hyper path)
                    best_raw = table_name if table_name else profiler.list_tables()[0]
                    unquoted = best_raw.replace('"', '').replace("'", '')
                    df = profiler.read_table(unquoted)
                    con.execute("CREATE TABLE data AS SELECT * FROM df")
                    # Query from "data" (DuckDB in-memory table)
                    query = self._build_sql_query('data', sql_calculation, dimensions, filters, limit)
                    logger.info(f"DuckDB fallback: loaded {len(df)} rows from '{unquoted}'")
                except Exception as load_err:
                    logger.error(f"DuckDB Hyper load failed: {load_err}")
                    return {}
            elif data_source.endswith('.parquet'):
                con.execute(f"CREATE TABLE data AS SELECT * FROM '{data_source}'")
                query = self._build_sql_query('data', sql_calculation, dimensions, filters, limit)
            elif data_source.endswith('.csv'):
                con.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{data_source}')")
                query = self._build_sql_query('data', sql_calculation, dimensions, filters, limit)
            else:
                query = self._build_sql_query(table_name, sql_calculation, dimensions, filters, limit)

            result = con.execute(query).fetchall()

            for row in result:
                dim_values = {dimensions[i]: row[i] for i in range(len(dimensions))}
                truth_value = float(row[-1]) if row[-1] is not None else None
                slice_key = self._make_slice_key(dim_values)
                truth_map[slice_key] = TruthSlice(
                    dimensions=dim_values,
                    truth_value=truth_value,
                    slice_key=slice_key
                )

            con.close()
            logger.info(f"✅ Extracted {len(truth_map)} truth slices from DuckDB")
            return truth_map

        except Exception as e:
            logger.error(f"DuckDB extraction failed: {e}")
            return {}

    # ============================================
    # SQL Query Builder
    # ============================================

    def _build_sql_query(
        self,
        table_name: str,
        calculation: str,
        dimensions: List[str],
        filters: Optional[List[str]],
        limit: int
    ) -> str:
        """
        Build SQL query for truth extraction

        Example output:
            SELECT "Region", "Year", SUM("Sales") as truth_value
            FROM "Extract"
            LIMIT 1000
        """
        # Ensure table name is properly quoted
        # If already quoted, use as-is; otherwise quote it
        if not (table_name.startswith('"') or table_name.startswith("'")):
            quoted_table = f'"{table_name}"'
        else:
            quoted_table = table_name

        # Handle empty dimensions (simple aggregation with no grouping)
        if not dimensions or len(dimensions) == 0:
            query = f"""
                SELECT {calculation} as truth_value
                FROM {quoted_table}
            """

            if filters:
                where_clause = " AND ".join(filters)
                query += f"\n                WHERE {where_clause}"

            query += f"\n                LIMIT {limit}"

            return query.strip()

        # Quote column names to handle spaces/special chars
        select_dims = ", ".join([f'"{d}"' for d in dimensions])
        group_by_dims = ", ".join([f'"{d}"' for d in dimensions])
        order_by_dims = ", ".join([f'"{d}"' for d in dimensions])

        # Build query
        query = f"""
            SELECT {select_dims}, {calculation} as truth_value
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
    # Utility Methods
    # ============================================

    def _make_slice_key(self, dimensions: Dict[str, Any]) -> str:
        """
        Create composite key from dimension values

        Args:
            dimensions: {"Region": "East", "Year": 2024}

        Returns:
            "East|2024" or "total" if no dimensions
        """
        if not dimensions:
            return "total"  # Single row for aggregate with no grouping

        # Sort by key for consistency
        sorted_dims = sorted(dimensions.items())
        return "|".join([str(v) for k, v in sorted_dims])

    def _tableau_to_sql(self, tableau_formula: str) -> str:
        """
        Convert Tableau calculation syntax to SQL.

        Handles:
        - [Field Name]         → "Field Name"
        - "col (TableName)"    → "col"        (strip cross-source qualifier)
        - IF/ELSEIF/ELSE/END   → CASE WHEN
        - IIF(c, t, f)         → CASE WHEN c THEN t ELSE f END
        - AND / OR (keyword)   → AND / OR (already SQL)
        - ISNULL(x) / IFNULL   → x IS NULL / COALESCE
        - ZN(x)                → COALESCE(x, 0)
        - CONTAINS(x, y)       → x LIKE '%y%'
        - COUNTD(x)            → COUNT(DISTINCT x)
        - ATTR(x)              → MIN(x)
        - DATEPART / DATEDIFF  → EXTRACT / date math stubs
        - Single-quote strings → keep as-is (SQL standard)
        """
        sql = tableau_formula.strip()

        # ── 1. [Field Name] → "Field Name" ──────────────────────────────────
        sql = re.sub(r'\[([^\]]+)\]', r'"\1"', sql)

        # ── 2. Strip (TableName) cross-source qualifiers FIRST ───────────────
        #     "income_class (Invoice)" → "income_class"
        #     "Amount (Fees)"          → "Amount"
        # MUST run before string-literal detection so that column refs with
        # spaces from table qualifiers won't be misidentified as string literals.
        sql = re.sub(r'"([^"]+)\s+\([^)]+\)"', r'"\1"', sql)

        # ── 1b. Tableau string literals in double quotes → SQL single quotes ─
        # In Tableau syntax:
        #   [Field Name] = "string value"  → double quotes are ALWAYS string literals
        #   [Field Name] → "Field Name"    → already converted to double-quoted column above
        # So any quoted token that appears AFTER an operator ( =, !=, <>, <, > )
        # must be a string literal and should become a single-quoted SQL string.
        # We also LOWER() both sides for case-insensitive comparison.
        
        def _fix_string_literal(m):
            op = m.group(1).strip()
            content = m.group(2)
            
            # Always treat as string literal — Tableau uses double-quotes for strings,
            # column refs were already converted from [Field] → "Field" above.
            # We lower-case the value since Tableau comparisons are case-insensitive.
            return f" {op} '{content.lower()}'"

        # Apply to double-quoted tokens that follow =, <>, !=, <, >
        sql = re.sub(
            r'([=!<>]+)\s*"([^"]+)"',
            _fix_string_literal,
            sql
        )
        
        # Now wrap the column identifier before the operator in LOWER()
        # e.g., "income_class"='cross sell' → LOWER("income_class")='cross sell'
        sql = re.sub(
            r'"([^"]+)"\s*([=!<>]+)\s*\'([^\']+)\'',
            r"""LOWER("\1")\2'\3'""",
            sql
        )

        # Handle THEN "value" and ELSE "value" where value has spaces → SQL string literal
        # e.g., THEN "cross sell" → THEN 'cross sell'
        # e.g., THEN "Amount"     → THEN "Amount"  (column ref, no conversion needed)
        # We detect string literals by: lowercase-only, has spaces, or is a known word value
        sql = re.sub(
            r'\b(THEN|ELSE)\s+"([^"]+)"',
            lambda m: (
                f"{m.group(1)} '{m.group(2).lower()}'"  # string literal → single-quoted
                if (
                    ' ' in m.group(2)               # has spaces (e.g. 'cross sell')
                    or m.group(2).islower()          # all-lowercase (e.g. 'open', 'new')
                    or m.group(2).lower() in {       # known Tableau string values
                        'true', 'false', 'null', 'yes', 'no', 'open', 'closed',
                        'new', 'renewal', 'qualify', 'converted', 'pending', 'active',
                        'inactive', 'complete', 'completed', 'incomplete', 'won', 'lost'
                    }
                )
                else f'{m.group(1)} "{m.group(2)}"'  # column ref → keep double-quoted
            ),
            sql, flags=re.IGNORECASE
        )



        # ── 3. IIF(condition, true_val, false_val) → CASE WHEN … END ─────────
        def _expand_iif(m):
            cond = m.group(1).strip()
            tv   = m.group(2).strip()
            fv   = m.group(3).strip()
            return f"CASE WHEN {cond} THEN {tv} ELSE {fv} END"

        sql = re.sub(
            r'\bIIF\s*\(\s*(.+?)\s*,\s*(.+?)\s*,\s*(.+?)\s*\)',
            _expand_iif, sql, flags=re.IGNORECASE
        )

        # ── 4. IF [ELSEIF]* ELSE END → CASE WHEN … END ─────────────────────
        def _expand_if(m):
            body = m.group(1)
            # Split on ELSEIF / ELSE
            parts = re.split(r'\bELSEIF\b', body, flags=re.IGNORECASE)
            chunks = []
            for i, part in enumerate(parts):
                # Each part: "condition THEN value"
                then_split = re.split(r'\bTHEN\b', part, maxsplit=1, flags=re.IGNORECASE)
                if len(then_split) == 2:
                    cond, val = then_split
                    # val may contain ELSE
                    else_split = re.split(r'\bELSE\b', val, maxsplit=1, flags=re.IGNORECASE)
                    if len(else_split) == 2 and i == len(parts) - 1:
                        chunks.append(f"WHEN {cond.strip()} THEN {else_split[0].strip()}")
                        chunks.append(f"ELSE {else_split[1].strip()}")
                    else:
                        chunks.append(f"WHEN {cond.strip()} THEN {val.strip()}")
                else:
                    # Bare ELSE clause (first part only had condition)
                    chunks.append(f"ELSE {part.strip()}")
            return "CASE " + " ".join(chunks) + " END"

        sql = re.sub(
            r'\bIF\s+(.+?)\s+END\b',
            _expand_if, sql, flags=re.IGNORECASE | re.DOTALL
        )

        # ── 5. Aggregations ──────────────────────────────────────────────────
        sql = re.sub(r'\bCOUNTD\s*\(', 'COUNT(DISTINCT ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bATTR\s*\(',   'MIN(',            sql, flags=re.IGNORECASE)

        # ── 6. Null helpers ──────────────────────────────────────────────────
        # ZN(x) → COALESCE(x, 0)
        sql = re.sub(r'\bZN\s*\((.+?)\)', r'COALESCE(\1, 0)', sql, flags=re.IGNORECASE)
        # ISNULL(x) → x IS NULL
        sql = re.sub(r'\bISNULL\s*\((.+?)\)', r'(\1 IS NULL)', sql, flags=re.IGNORECASE)
        # IFNULL(x, y) → COALESCE(x, y)
        sql = re.sub(r'\bIFNULL\s*\(', 'COALESCE(', sql, flags=re.IGNORECASE)

        # ── 7. String helpers ────────────────────────────────────────────────
        # CONTAINS("col", "val") → "col" LIKE '%val%'
        def _expand_contains(m):
            field = m.group(1).strip()
            needle = m.group(2).strip().strip("'\"")
            return f"{field} LIKE '%{needle}%'"

        sql = re.sub(
            r'\bCONTAINS\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)',
            _expand_contains, sql, flags=re.IGNORECASE
        )

        # ── 8. Date functions (stub — exact flavour depends on Hyper/DuckDB) ─
        # DATEPART('year', [Date]) → EXTRACT(YEAR FROM "Date")
        def _expand_datepart(m):
            part  = m.group(1).strip().strip("'\"").upper()
            field = m.group(2).strip()
            return f"EXTRACT({part} FROM {field})"

        sql = re.sub(
            r'\bDATEPART\s*\(\s*([^,]+)\s*,\s*(.+?)\s*\)',
            _expand_datepart, sql, flags=re.IGNORECASE
        )

        # DATEDIFF('day', start, end) → DATEDIFF('day', start, end)  ← pass-through for Hyper
        # (Hyper supports DATEDIFF natively, DuckDB uses age/epoch arithmetic; leave for now)

        # ── 9. Boolean operator normalisation ───────────────────────────────
        # Tableau uses AND / OR as keywords — same as SQL, nothing to do.
        # But Tableau also uses != which is already SQL. Leave as-is.

        logger.info(f"🔄 Tableau→SQL:\n  IN:  {tableau_formula}\n  OUT: {sql}")
        return sql


    # ============================================
    # Table Auto-Detection
    # ============================================

    def _find_best_table(
        self,
        hyper_path: str,
        sql_calculation: str
    ) -> Optional[str]:
        """
        Scan all tables in a Hyper file and return the raw table name whose
        columns best match the column references in sql_calculation.

        Uses read_table(limit=1) to get column names — cached per hyper_path
        so column maps are built once and reused across all 21+ formula scorings.
        """
        try:
            from src.tableau.hyper_profiler import HyperDataProfiler
            profiler = HyperDataProfiler(hyper_path)
            all_tables = profiler.list_tables()

            if not all_tables:
                return None

            # Build column map for this hyper file once, then cache it
            if hyper_path not in self._table_cols_cache:
                cache: Dict[str, set] = {}
                for raw_table in all_tables:
                    try:
                        unquoted = raw_table.replace('"', '').replace("'", '')
                        df = profiler.read_table(unquoted, limit=1)
                        # tableauhyperapi returns Name objects, not strings
                        # Use str() to safely convert before calling .lower()
                        cache[raw_table] = {str(c).lower() for c in df.columns}
                    except Exception as e:
                        logger.debug(f"Cache build failed for {raw_table}: {e}")
                        cache[raw_table] = set()
                self._table_cols_cache[hyper_path] = cache
                cols_per_table = {t: len(c) for t, c in cache.items()}
                logger.debug(f"Built column cache for {len(cache)} tables: {cols_per_table}")

            table_cols_map = self._table_cols_cache[hyper_path]

            # Extract double-quoted identifiers from the SQL formula
            # Exclude: (1) Calculation_\d+ internal fields, (2) string literal values
            calc_pattern_re = re.compile(r'^Calculation_\d+$')
            all_col_refs = set(re.findall(r'"([^"]+)"', sql_calculation))
            col_refs = {
                c for c in all_col_refs
                if not calc_pattern_re.match(c)   # not a Tableau internal calc name
                and len(c) > 1                     # not a single char
                and ' ' not in c                   # not a string literal with spaces (e.g. "cross sell")
                and c.lower() not in {             # not common SQL-string values or Tableau literals
                    'open', 'closed', 'true', 'false', 'null', 'yes', 'no',
                    'new', 'renewal', 'qualify', 'converted', 'pending', 'active',
                    'inactive', 'complete', 'completed', 'incomplete', 'won', 'lost',
                    'in progress', 'on hold', 'cancelled', 'canceled'
                }
                and not c[0].isdigit()             # not a number
            }

            # Score each table: count how many formula columns it contains
            best_table = None
            best_score = -1
            for raw_table, cols in table_cols_map.items():
                score = sum(1 for c in col_refs if c.lower() in cols)
                if score > best_score:
                    best_score = score
                    best_table = raw_table

            if best_table and best_score > 0:
                return best_table

            return all_tables[0]  # Fallback to first table

        except Exception as e:
            logger.debug(f"Table auto-detection failed: {e}")
            return None


    def save_truth_map(self, truth_map: Dict[str, TruthSlice], output_path: str):
        """Save truth map to JSON file for debugging"""
        serializable = {
            key: {
                "dimensions": slice.dimensions,
                "truth_value": slice.truth_value,
                "slice_key": slice.slice_key
            }
            for key, slice in truth_map.items()
        }

        with open(output_path, 'w') as f:
            json.dump(serializable, f, indent=2)

        logger.info(f"Truth map saved to {output_path}")

    def extract_sample_slices(
        self,
        data_source: str,
        table_name: str,
        calculation: str,
        dimensions: List[str],
        sample_size: int = 10
    ) -> Dict[str, TruthSlice]:
        """
        Extract a small sample for quick validation testing

        Useful for:
        - Initial debugging
        - Smoke tests
        - Demo scenarios
        """
        return self.extract_truth_map(
            data_source, table_name, calculation, dimensions,
            filters=None, limit=sample_size
        )


# ============================================
# Convenience Functions
# ============================================

def extract_tableau_truth(
    hyper_path: str,
    calculation: str,
    dimensions: List[str],
    table_name: str = "Extract"
) -> Dict[str, float]:
    """
    Simple convenience function for basic truth extraction

    Args:
        hyper_path: Path to .hyper file
        calculation: SQL expression (e.g., 'SUM("Sales") / NULLIF(SUM("Quantity"), 0)')
        dimensions: Grouping columns
        table_name: Table name (default "Extract" for Tableau extracts)

    Returns:
        Simple dict mapping composite keys to values
    """
    extractor = TruthMapExtractor()
    truth_map = extractor.extract_truth_map(
        hyper_path, table_name, calculation, dimensions
    )

    return {key: slice.truth_value for key, slice in truth_map.items()}


if __name__ == "__main__":
    # Example usage
    print("Truth Map Extractor - Example Usage\n")

    # Mock example (replace with real .hyper file)
    EXAMPLE_HYPER = "superstore.hyper"

    if Path(EXAMPLE_HYPER).exists():
        extractor = TruthMapExtractor()

        truth = extractor.extract_truth_map(
            data_source=EXAMPLE_HYPER,
            table_name='"Extract"."Extract"',
            calculation='SUM("Sales")',
            dimensions=["Region", "Category"],
            limit=50
        )

        print(f"Extracted {len(truth)} test slices:")
        for key, slice in list(truth.items())[:5]:
            print(f"  {slice.dimensions} = ${slice.truth_value:,.2f}")
    else:
        print(f"Example file {EXAMPLE_HYPER} not found")
        print("This module requires a Tableau .hyper file to test")
