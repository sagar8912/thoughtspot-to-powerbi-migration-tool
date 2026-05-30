"""Model Enhancement Agent - Detects when Power BI model changes are needed for Tableau table calculations"""
import re
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
from loguru import logger


class EnhancementType(Enum):
    """Types of model enhancements required"""
    INDEX_COLUMN = "INDEX_COLUMN"  # For LOOKUP, INDEX functions
    DATE_TABLE = "DATE_TABLE"  # For time intelligence
    SORT_COLUMN = "SORT_COLUMN"  # For custom sorting
    RELATIONSHIP = "RELATIONSHIP"  # For cross-table calculations
    NONE = "NONE"  # No enhancement needed


@dataclass
class ModelEnhancement:
    """Recommended model change for a table calculation"""
    enhancement_type: EnhancementType
    reason: str
    m_code: Optional[str]  # Power Query M code to add to model
    dax_code: Optional[str]  # DAX measure/column using the enhancement
    manual_steps: List[str]  # Human-readable instructions
    table_name: str  # Table to apply enhancement to
    affected_calculation: str  # Original Tableau calculation name


class ModelEnhancementAgent:
    """
    Analyzes Tableau table calculations and determines if Power BI model changes are needed

    Philosophy:
    - Tableau table calculations operate at the VISUAL layer (post-aggregation)
    - Power BI DAX operates at the MODEL layer
    - Some Tableau patterns are IMPOSSIBLE with DAX measures alone
    - Solution: Modify the Power BI model to enable equivalent DAX

    Handles:
    1. LOOKUP(expr, offset) → Needs Index column
    2. INDEX() → Needs Row Number column
    3. RUNNING_SUM/RUNNING_AVG with dates → Needs Date table
    4. RANK with custom sort → Needs Sort column
    """

    def __init__(self):
        logger.info("Model Enhancement Agent initialized")

    # ============================================
    # Main Assessment Methods
    # ============================================

    def assess_table_calculation(
        self,
        tableau_formula: str,
        calc_name: str,
        partition_by: List[str],
        sort_by: List[str],
        table_name: str = "YourTable"
    ) -> Optional[ModelEnhancement]:
        """
        Determine if a Tableau table calculation needs Power BI model enhancement

        Args:
            tableau_formula: Original Tableau formula
            calc_name: Calculation name
            partition_by: Grouping dimensions (from visual context)
            sort_by: Sort order (from visual context)
            table_name: Target table name in Power BI

        Returns:
            ModelEnhancement if model change needed, None if DAX measure is sufficient
        """
        formula_upper = tableau_formula.upper()

        # Pattern 1: LOOKUP with offset
        if "LOOKUP(" in formula_upper:
            return self._handle_lookup(tableau_formula, calc_name, partition_by, sort_by, table_name)

        # Pattern 2: INDEX() function
        if "INDEX()" in formula_upper or "INDEX (" in formula_upper:
            return self._handle_index(calc_name, table_name)

        # Pattern 3: PREVIOUS_VALUE
        if "PREVIOUS_VALUE(" in formula_upper:
            return self._handle_previous_value(tableau_formula, calc_name, table_name)

        # Pattern 4: Running totals with date partitioning
        if any(func in formula_upper for func in ["RUNNING_SUM(", "RUNNING_AVG(", "RUNNING_MIN(", "RUNNING_MAX("]):
            return self._handle_running_total(tableau_formula, calc_name, partition_by, sort_by, table_name)

        # Pattern 5: WINDOW functions with offsets
        if any(func in formula_upper for func in ["WINDOW_SUM(", "WINDOW_AVG(", "WINDOW_MIN(", "WINDOW_MAX("]):
            return self._handle_window_function(tableau_formula, calc_name, partition_by, sort_by, table_name)

        # Pattern 6: FIRST() or LAST()
        if "FIRST()" in formula_upper or "LAST()" in formula_upper:
            return self._handle_first_last(calc_name, table_name)

        # No enhancement needed - standard DAX measure should work
        return None

    # ============================================
    # Pattern-Specific Handlers
    # ============================================

    def _handle_lookup(
        self,
        tableau_formula: str,
        calc_name: str,
        partition_by: List[str],
        sort_by: List[str],
        table_name: str
    ) -> ModelEnhancement:
        """
        LOOKUP(expr, offset) requires an Index column to identify rows

        Example Tableau: LOOKUP(SUM([Sales]), -1)  → Previous row's sales
        Power BI Solution: Add Index column in Power Query, use calculated column
        """
        # Extract offset from formula
        match = re.search(r'LOOKUP\(.+?,\s*(-?\d+)\)', tableau_formula)
        offset = int(match.group(1)) if match else 0

        # Determine partition and sort columns
        partition_col = partition_by[0] if partition_by else None
        sort_col = sort_by[0] if sort_by else "Date"

        # Generate M code to add Index
        m_code = self._generate_index_m_code(table_name, partition_col, sort_col)

        # Generate DAX calculated column (NOT a measure!)
        dax_code = f"""
-- Calculated Column for LOOKUP (offset: {offset})
-- IMPORTANT: This is a COLUMN, not a MEASURE
{calc_name}_LookupValue =
VAR CurrentIndex = '{table_name}'[RowIndex]
VAR TargetIndex = CurrentIndex + ({offset})
VAR TargetValue =
    CALCULATE(
        SUM('{table_name}'[YourMeasureColumn]),  -- Replace with actual column
        FILTER(
            ALL('{table_name}'),
            '{table_name}'[RowIndex] = TargetIndex
        )
    )
RETURN
    TargetValue
""".strip()

        return ModelEnhancement(
            enhancement_type=EnhancementType.INDEX_COLUMN,
            reason=f"LOOKUP with offset {offset} requires a Row Index column to identify target rows. "
                   f"DAX measures cannot access 'previous' or 'next' rows without an index.",
            m_code=m_code,
            dax_code=dax_code,
            manual_steps=[
                "1. Open Power BI Desktop and go to 'Transform Data' (Power Query Editor)",
                f"2. Select the '{table_name}' table",
                "3. Click 'Add Column' → 'Index Column' → 'From 1'",
                "4. Name it 'RowIndex'",
                "5. Click 'Close & Apply'",
                "6. In Power BI, create a NEW CALCULATED COLUMN (not measure) using the DAX above",
                "7. Use this column in your visual instead of trying to use a measure"
            ],
            table_name=table_name,
            affected_calculation=calc_name
        )

    def _handle_index(self, calc_name: str, table_name: str) -> ModelEnhancement:
        """
        INDEX() returns the row number in the partition

        Power BI Solution: Add Index column in Power Query
        """
        m_code = self._generate_simple_index_m_code(table_name)

        return ModelEnhancement(
            enhancement_type=EnhancementType.INDEX_COLUMN,
            reason="INDEX() function returns the row number. Power BI requires an explicit Index column for this.",
            m_code=m_code,
            dax_code=None,  # Just use the RowIndex column directly
            manual_steps=[
                "1. Open Power Query Editor (Transform Data)",
                f"2. Select '{table_name}' table",
                "3. Add Column → Index Column → From 1",
                "4. Rename to 'RowIndex'",
                "5. Close & Apply",
                "6. Use [RowIndex] column directly in your visuals"
            ],
            table_name=table_name,
            affected_calculation=calc_name
        )

    def _handle_previous_value(
        self,
        tableau_formula: str,
        calc_name: str,
        table_name: str
    ) -> ModelEnhancement:
        """
        PREVIOUS_VALUE(expr) requires iterating over sorted rows

        Similar to LOOKUP, needs Index column
        """
        m_code = self._generate_simple_index_m_code(table_name)

        dax_code = f"""
-- Calculated Column for PREVIOUS_VALUE
{calc_name}_PreviousValue =
VAR CurrentIndex = '{table_name}'[RowIndex]
VAR PreviousIndex = CurrentIndex - 1
RETURN
    IF(
        PreviousIndex >= 1,
        CALCULATE(
            SUM('{table_name}'[YourColumn]),  -- Replace with actual column
            FILTER(
                ALL('{table_name}'),
                '{table_name}'[RowIndex] = PreviousIndex
            )
        ),
        BLANK()  -- First row has no previous value
    )
""".strip()

        return ModelEnhancement(
            enhancement_type=EnhancementType.INDEX_COLUMN,
            reason="PREVIOUS_VALUE requires accessing the prior row, which needs a Row Index column.",
            m_code=m_code,
            dax_code=dax_code,
            manual_steps=[
                "1. Add Index column in Power Query (see M code)",
                "2. Create calculated column (not measure) with DAX above",
                "3. Use the calculated column in visuals"
            ],
            table_name=table_name,
            affected_calculation=calc_name
        )

    def _handle_running_total(
        self,
        tableau_formula: str,
        calc_name: str,
        partition_by: List[str],
        sort_by: List[str],
        table_name: str
    ) -> Optional[ModelEnhancement]:
        """
        RUNNING_SUM/AVG/etc can be done with DAX measures in simple cases
        But complex partitioning or date-based running totals benefit from a Date table

        Simple case: RUNNING_SUM(SUM([Sales])) sorted by date
        → DAX measure works: CALCULATE(SUM(...), FILTER(ALL(Date), Date <= MAX(Date)))

        Complex case: Multiple partitions or custom date logic
        → Recommend Date table for best practice
        """
        # Check if partition includes date-like columns
        has_date_partition = any("date" in dim.lower() for dim in (partition_by + sort_by))

        if has_date_partition and len(partition_by) <= 1:
            # Recommend Date table for time intelligence
            return ModelEnhancement(
                enhancement_type=EnhancementType.DATE_TABLE,
                reason="Running totals over time should use a proper Date dimension table for accurate and performant calculations.",
                m_code=self._generate_date_table_m(),
                dax_code=f"""
-- Running Total Measure (requires Date table)
{calc_name} =
CALCULATE(
    SUM('{table_name}'[Amount]),  -- Replace with actual measure
    FILTER(
        ALLSELECTED(DateTable[Date]),
        DateTable[Date] <= MAX(DateTable[Date])
    )
)
""".strip(),
                manual_steps=[
                    "1. Create Date table using M code above",
                    "2. Create relationship: DateTable[Date] → " + table_name + "[OrderDate]",
                    "3. Mark DateTable as a Date Table (Table tools → Mark as Date Table)",
                    "4. Use the DAX measure above",
                    "5. IMPORTANT: Use DateTable[Date] in your visual axes, not the original date column"
                ],
                table_name="DateTable",
                affected_calculation=calc_name
            )

        # Simple running total - no enhancement needed, DAX measure is fine
        return None

    def _handle_window_function(
        self,
        tableau_formula: str,
        calc_name: str,
        partition_by: List[str],
        sort_by: List[str],
        table_name: str
    ) -> Optional[ModelEnhancement]:
        """
        WINDOW_SUM/AVG/etc with offsets

        Example: WINDOW_SUM(SUM([Sales]), -2, 0)  → Sum of current + 2 previous rows

        If window has start/end offsets, needs Index column
        If window is full partition (no offsets), DAX measure works
        """
        # Check if formula has offset parameters
        match = re.search(r'WINDOW_\w+\(.+?,\s*(-?\d+),\s*(-?\d+)\)', tableau_formula)

        if match:
            start_offset = int(match.group(1))
            end_offset = int(match.group(2))

            # If both offsets are 0 or cover full partition, DAX measure works
            if start_offset == 0 and end_offset == 0:
                return None

            # Otherwise, needs Index column
            m_code = self._generate_index_m_code(table_name, partition_by[0] if partition_by else None, sort_by[0] if sort_by else None)

            return ModelEnhancement(
                enhancement_type=EnhancementType.INDEX_COLUMN,
                reason=f"WINDOW function with offsets ({start_offset}, {end_offset}) requires Row Index to define the window range.",
                m_code=m_code,
                dax_code=f"""
-- Calculated Column for WINDOW function
{calc_name}_WindowValue =
VAR CurrentIndex = '{table_name}'[RowIndex]
VAR WindowStart = CurrentIndex + ({start_offset})
VAR WindowEnd = CurrentIndex + ({end_offset})
RETURN
    CALCULATE(
        SUM('{table_name}'[YourColumn]),  -- Replace with actual aggregation
        FILTER(
            ALL('{table_name}'),
            '{table_name}'[RowIndex] >= WindowStart &&
            '{table_name}'[RowIndex] <= WindowEnd
        )
    )
""".strip(),
                manual_steps=[
                    "1. Add Index column using M code",
                    "2. Create calculated column (not measure) with DAX above",
                    "3. Use in visual"
                ],
                table_name=table_name,
                affected_calculation=calc_name
            )

        # No offsets or simple window - DAX measure works
        return None

    def _handle_first_last(self, calc_name: str, table_name: str) -> ModelEnhancement:
        """
        FIRST() or LAST() returns first/last value in partition

        Needs Index to identify first/last row
        """
        m_code = self._generate_simple_index_m_code(table_name)

        dax_code = f"""
-- Calculated Column for FIRST() or LAST()
{calc_name}_FirstOrLast =
VAR MinIndex = CALCULATE(MIN('{table_name}'[RowIndex]), ALLEXCEPT('{table_name}', '{table_name}'[PartitionColumn]))
VAR MaxIndex = CALCULATE(MAX('{table_name}'[RowIndex]), ALLEXCEPT('{table_name}', '{table_name}'[PartitionColumn]))
VAR IsFirst = '{table_name}'[RowIndex] = MinIndex
VAR IsLast = '{table_name}'[RowIndex] = MaxIndex
RETURN
    IF(IsFirst, "FIRST", IF(IsLast, "LAST", BLANK()))
""".strip()

        return ModelEnhancement(
            enhancement_type=EnhancementType.INDEX_COLUMN,
            reason="FIRST() and LAST() require identifying the first/last row in the partition, which needs a Row Index.",
            m_code=m_code,
            dax_code=dax_code,
            manual_steps=[
                "1. Add Index column in Power Query",
                "2. Create calculated column with DAX above",
                "3. Adjust DAX to return actual values instead of 'FIRST'/'LAST' labels"
            ],
            table_name=table_name,
            affected_calculation=calc_name
        )

    # ============================================
    # M Code Generators
    # ============================================

    def _generate_index_m_code(
        self,
        table_name: str,
        partition_col: Optional[str],
        sort_col: Optional[str]
    ) -> str:
        """Generate M code to add Index column with proper sorting"""

        sort_step = ""
        if partition_col and sort_col:
            sort_step = f"""
    // Sort by partition and sort columns
    Sorted = Table.Sort(Source, {{
        {{"{partition_col}", Order.Ascending}},
        {{"{sort_col}", Order.Ascending}}
    }}),
"""
        elif sort_col:
            sort_step = f"""
    // Sort by sort column
    Sorted = Table.Sort(Source, {{{{"{sort_col}", Order.Ascending}}}}),
"""
        else:
            sort_step = """
    // No explicit sort - using natural order
    Sorted = Source,
"""

        return f"""
// Add Row Index for Table Calculations
let
    Source = #"Previous Step",
{sort_step}
    // Add Index Column
    AddedIndex = Table.AddIndexColumn(Sorted, "RowIndex", 1, 1, Int64.Type)
in
    AddedIndex
""".strip()

    def _generate_simple_index_m_code(self, table_name: str) -> str:
        """Generate simple Index column M code"""
        return f"""
// Add Row Index Column
let
    Source = #"Previous Step",
    AddedIndex = Table.AddIndexColumn(Source, "RowIndex", 1, 1, Int64.Type)
in
    AddedIndex
""".strip()

    def _generate_date_table_m(self) -> str:
        """Generate comprehensive Date table M code"""
        return """
// Create Date Dimension Table
let
    // Define date range
    StartDate = #date(2020, 1, 1),
    EndDate = #date(2030, 12, 31),
    NumberOfDays = Duration.Days(EndDate - StartDate) + 1,

    // Generate date list
    DateList = List.Dates(StartDate, NumberOfDays, #duration(1, 0, 0, 0)),
    DateTable = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}),
    ChangedType = Table.TransformColumnTypes(DateTable, {{"Date", type date}}),

    // Add calendar columns
    AddYear = Table.AddColumn(ChangedType, "Year", each Date.Year([Date]), Int64.Type),
    AddQuarter = Table.AddColumn(AddYear, "Quarter", each Date.QuarterOfYear([Date]), Int64.Type),
    AddMonth = Table.AddColumn(AddQuarter, "Month", each Date.Month([Date]), Int64.Type),
    AddMonthName = Table.AddColumn(AddMonth, "MonthName", each Date.MonthName([Date]), type text),
    AddDay = Table.AddColumn(AddMonthName, "Day", each Date.Day([Date]), Int64.Type),
    AddDayOfWeek = Table.AddColumn(AddDay, "DayOfWeek", each Date.DayOfWeek([Date]), Int64.Type),
    AddDayName = Table.AddColumn(AddDayOfWeek, "DayName", each Date.DayOfWeekName([Date]), type text),

    // Add fiscal year (adjust offset as needed)
    AddFiscalYear = Table.AddColumn(AddDayName, "FiscalYear",
        each if Date.Month([Date]) >= 7 then Date.Year([Date]) + 1 else Date.Year([Date]), Int64.Type),

    // Add ISO week
    AddWeekNum = Table.AddColumn(AddFiscalYear, "WeekNum", each Date.WeekOfYear([Date]), Int64.Type),

    // Add formatted columns for display
    AddYearMonth = Table.AddColumn(AddWeekNum, "YearMonth",
        each Date.ToText([Date], "yyyy-MM"), type text),
    AddMonthYear = Table.AddColumn(AddYearMonth, "MonthYear",
        each Date.ToText([Date], "MMM yyyy"), type text)
in
    AddMonthYear
""".strip()

    # ============================================
    # Utility Methods
    # ============================================

    def requires_model_change(self, tableau_formula: str) -> bool:
        """Quick check if formula likely needs model enhancement"""
        formula_upper = tableau_formula.upper()

        table_calc_functions = [
            "LOOKUP(", "INDEX()", "PREVIOUS_VALUE(",
            "RUNNING_SUM(", "RUNNING_AVG(", "RUNNING_MIN(", "RUNNING_MAX(",
            "WINDOW_SUM(", "WINDOW_AVG(", "WINDOW_MIN(", "WINDOW_MAX(",
            "FIRST()", "LAST()"
        ]

        return any(func in formula_upper for func in table_calc_functions)
