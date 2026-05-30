"""Table Calculation Converter - Convert Tableau table calculations to Power BI DAX"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from src.powerbi.pbix_injector import Measure, CalculatedColumn


class TableCalcType(Enum):
    """Types of Tableau table calculations"""
    RUNNING_TOTAL = "running_total"
    RUNNING_AVG = "running_avg"
    RUNNING_MIN = "running_min"
    RUNNING_MAX = "running_max"
    RANK = "rank"
    RANK_DENSE = "rank_dense"
    RANK_PERCENTILE = "rank_percentile"
    PERCENT_OF_TOTAL = "percent_of_total"
    PERCENT_DIFFERENCE = "percent_difference"
    MOVING_AVG = "moving_avg"
    MOVING_SUM = "moving_sum"
    DIFFERENCE = "difference"
    PERCENT_CHANGE = "percent_change"
    INDEX = "index"
    FIRST = "first"
    LAST = "last"
    WINDOW_SUM = "window_sum"
    WINDOW_AVG = "window_avg"


@dataclass
class TableCalcContext:
    """Context for table calculation conversion"""
    calc_type: TableCalcType
    base_measure: str  # The measure being aggregated (e.g., "SUM([Sales])")
    partition_by: List[str]  # Dimensions for partitioning (e.g., ["Region"])
    order_by: List[str]  # Dimensions for ordering (e.g., ["Date"])
    window_size: Optional[int] = None  # For moving calculations
    offset: Optional[int] = None  # For LAG/LEAD operations


class TableCalculationConverter:
    """
    Convert Tableau table calculations to Power BI DAX

    Handles all major table calculation types with proper DAX context
    """

    def __init__(self):
        pass

    # ============================================
    # Main Conversion Method
    # ============================================

    def convert_table_calculation(
        self,
        tableau_formula: str,
        calc_name: str,
        partition_by: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        table_name: str = "Sales"
    ) -> Dict[str, Any]:
        """
        Convert Tableau table calculation to DAX

        Args:
            tableau_formula: Original Tableau table calc formula
            calc_name: Name of the calculation
            partition_by: Partitioning dimensions
            order_by: Ordering dimensions
            table_name: Target table name

        Returns:
            Dictionary with:
            - dax_measures: List of DAX measures
            - helper_columns: List of helper calculated columns (if needed)
            - requires_model_change: Boolean indicating if model changes needed
        """
        partition_by = partition_by or []
        order_by = order_by or []

        # Detect table calculation type
        calc_context = self._detect_table_calc_type(
            tableau_formula,
            partition_by=partition_by,
            order_by=order_by
        )

        if not calc_context:
            logger.warning(f"Could not detect table calculation type: {tableau_formula}")
            return {
                "dax_measures": [],
                "helper_columns": [],
                "requires_model_change": False
            }

        # Convert based on type
        converter_map = {
            TableCalcType.RUNNING_TOTAL: self._convert_running_total,
            TableCalcType.RUNNING_AVG: self._convert_running_avg,
            TableCalcType.RANK: self._convert_rank,
            TableCalcType.RANK_DENSE: self._convert_rank_dense,
            TableCalcType.PERCENT_OF_TOTAL: self._convert_percent_of_total,
            TableCalcType.MOVING_AVG: self._convert_moving_average,
            TableCalcType.MOVING_SUM: self._convert_moving_sum,
            TableCalcType.DIFFERENCE: self._convert_difference,
            TableCalcType.PERCENT_CHANGE: self._convert_percent_change,
            TableCalcType.WINDOW_SUM: self._convert_window_sum,
            TableCalcType.WINDOW_AVG: self._convert_window_avg,
        }

        converter = converter_map.get(calc_context.calc_type)

        if not converter:
            logger.warning(f"No converter for {calc_context.calc_type.value}")
            return {
                "dax_measures": [],
                "helper_columns": [],
                "requires_model_change": False
            }

        return converter(calc_context, calc_name, table_name)

    def _detect_table_calc_type(
        self,
        tableau_formula: str,
        partition_by: List[str],
        order_by: List[str]
    ) -> Optional[TableCalcContext]:
        """
        Detect table calculation type from Tableau formula

        Tableau table calc functions:
        - RUNNING_SUM()
        - RUNNING_AVG()
        - RANK()
        - INDEX()
        - LOOKUP()
        - WINDOW_SUM()
        - etc.
        """
        import re

        formula_upper = tableau_formula.upper()

        # Extract base measure (what's being calculated)
        # Example: RUNNING_SUM(SUM([Sales])) -> base = "SUM([Sales])"
        base_pattern = r'\(([^)]+)\)'
        base_match = re.search(base_pattern, tableau_formula)
        base_measure = base_match.group(1) if base_match else "VALUE"

        # Running calculations
        if "RUNNING_SUM" in formula_upper or "RUNSUM" in formula_upper:
            return TableCalcContext(
                calc_type=TableCalcType.RUNNING_TOTAL,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by
            )

        if "RUNNING_AVG" in formula_upper or "RUNAVG" in formula_upper:
            return TableCalcContext(
                calc_type=TableCalcType.RUNNING_AVG,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by
            )

        # Ranking
        if "RANK_DENSE" in formula_upper:
            return TableCalcContext(
                calc_type=TableCalcType.RANK_DENSE,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by
            )

        if "RANK(" in formula_upper or "RANK_UNIQUE" in formula_upper:
            return TableCalcContext(
                calc_type=TableCalcType.RANK,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by
            )

        # Percent of total
        if "TOTAL(" in formula_upper and "/" in formula_upper:
            return TableCalcContext(
                calc_type=TableCalcType.PERCENT_OF_TOTAL,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by
            )

        # Moving calculations
        moving_pattern = r'WINDOW_(SUM|AVG)\(.*?,\s*(-?\d+),\s*(-?\d+)\)'
        moving_match = re.search(moving_pattern, formula_upper)

        if moving_match:
            func_type = moving_match.group(1)
            start_offset = int(moving_match.group(2))
            end_offset = int(moving_match.group(3))

            window_size = abs(end_offset - start_offset) + 1

            calc_type = TableCalcType.MOVING_AVG if func_type == "AVG" else TableCalcType.MOVING_SUM

            return TableCalcContext(
                calc_type=calc_type,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by,
                window_size=window_size
            )

        # Difference (YoY, MoM, etc.)
        if "LOOKUP" in formula_upper and "-" in formula_upper:
            return TableCalcContext(
                calc_type=TableCalcType.DIFFERENCE,
                base_measure=base_measure,
                partition_by=partition_by,
                order_by=order_by,
                offset=-1  # Previous period
            )

        return None

    # ============================================
    # Running Total Conversion
    # ============================================

    def _convert_running_total(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Convert Tableau running total to DAX

        Tableau: RUNNING_SUM(SUM([Sales]))
        DAX: CALCULATE(SUM(Sales[Sales]), FILTER(ALL(Sales[Date]), Sales[Date] <= MAX(Sales[Date])))

        Requires: Proper ordering context
        """
        # Extract measure name from base_measure (e.g., "SUM([Sales])" -> "Sales")
        measure_column = self._extract_column_name(context.base_measure)

        # Build partition context
        partition_dims = ", ".join([f'{table_name}[{dim}]' for dim in context.partition_by])
        order_dim = context.order_by[0] if context.order_by else "Date"

        # DAX pattern for running total
        if context.partition_by:
            # Running total partitioned by dimensions (e.g., by Region)
            dax_formula = f"""
CALCULATE(
    SUM({table_name}[{measure_column}]),
    FILTER(
        ALLSELECTED({table_name}[{order_dim}]),
        {table_name}[{order_dim}] <= MAX({table_name}[{order_dim}])
    ),
    VALUES({partition_dims})
)
"""
        else:
            # Simple running total (no partitioning)
            dax_formula = f"""
CALCULATE(
    SUM({table_name}[{measure_column}]),
    FILTER(
        ALLSELECTED({table_name}[{order_dim}]),
        {table_name}[{order_dim}] <= MAX({table_name}[{order_dim}])
    )
)
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip(),
            display_folder="Table Calculations",
            description="Running total (migrated from Tableau)"
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],
            "requires_model_change": False
        }

    def _convert_running_avg(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Convert Tableau running average to DAX"""
        measure_column = self._extract_column_name(context.base_measure)
        order_dim = context.order_by[0] if context.order_by else "Date"

        dax_formula = f"""
CALCULATE(
    AVERAGE({table_name}[{measure_column}]),
    FILTER(
        ALLSELECTED({table_name}[{order_dim}]),
        {table_name}[{order_dim}] <= MAX({table_name}[{order_dim}])
    )
)
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip(),
            display_folder="Table Calculations"
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],
            "requires_model_change": False
        }

    # ============================================
    # Ranking Conversion
    # ============================================

    def _convert_rank(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Convert Tableau RANK to DAX RANKX

        Tableau: RANK(SUM([Sales]))
        DAX: RANKX(ALL(Sales), [Total Sales], , DESC, DENSE)
        """
        measure_column = self._extract_column_name(context.base_measure)

        # Create a base measure for ranking
        base_measure_name = f"_Base_{calc_name}"

        base_measure = Measure(
            name=base_measure_name,
            expression=f"SUM({table_name}[{measure_column}])",
            display_folder="Table Calculations/_Helpers"
        )

        # Create rank measure
        if context.partition_by:
            # Partitioned ranking
            partition_dims = ", ".join([f'{table_name}[{dim}]' for dim in context.partition_by])

            rank_dax = f"""
RANKX(
    ALLSELECTED({partition_dims}),
    [{base_measure_name}],
    ,
    DESC,
    SKIP
)
"""
        else:
            # Simple ranking (no partition)
            rank_dax = f"""
RANKX(
    ALLSELECTED({table_name}),
    [{base_measure_name}],
    ,
    DESC,
    SKIP
)
"""

        rank_measure = Measure(
            name=calc_name,
            expression=rank_dax.strip(),
            display_folder="Table Calculations"
        )

        return {
            "dax_measures": [base_measure, rank_measure],
            "helper_columns": [],
            "requires_model_change": False
        }

    def _convert_rank_dense(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Convert Tableau RANK_DENSE to DAX RANKX with DENSE"""
        measure_column = self._extract_column_name(context.base_measure)

        base_measure_name = f"_Base_{calc_name}"

        base_measure = Measure(
            name=base_measure_name,
            expression=f"SUM({table_name}[{measure_column}])"
        )

        rank_dax = f"""
RANKX(
    ALLSELECTED({table_name}),
    [{base_measure_name}],
    ,
    DESC,
    DENSE
)
"""

        rank_measure = Measure(
            name=calc_name,
            expression=rank_dax.strip()
        )

        return {
            "dax_measures": [base_measure, rank_measure],
            "helper_columns": [],
            "requires_model_change": False
        }

    # ============================================
    # Percent of Total Conversion
    # ============================================

    def _convert_percent_of_total(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Convert Tableau percent of total to DAX

        Tableau: SUM([Sales]) / TOTAL(SUM([Sales]))
        DAX: DIVIDE([Sales], CALCULATE([Sales], ALL(Table)))
        """
        measure_column = self._extract_column_name(context.base_measure)

        if context.partition_by:
            # Percent of total within partition
            partition_dims = ", ".join([f'{table_name}[{dim}]' for dim in context.partition_by])

            dax_formula = f"""
DIVIDE(
    SUM({table_name}[{measure_column}]),
    CALCULATE(
        SUM({table_name}[{measure_column}]),
        ALLEXCEPT({table_name}, {partition_dims})
    ),
    0
)
"""
        else:
            # Percent of grand total
            dax_formula = f"""
DIVIDE(
    SUM({table_name}[{measure_column}]),
    CALCULATE(
        SUM({table_name}[{measure_column}]),
        ALL({table_name})
    ),
    0
)
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip(),
            format_string="0.00%"
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],
            "requires_model_change": False
        }

    # ============================================
    # Moving Average / Sum Conversion
    # ============================================

    def _convert_moving_average(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Convert Tableau moving average to DAX

        Tableau: WINDOW_AVG(SUM([Sales]), -2, 0)  # 3-period MA
        DAX: AVERAGEX(DATESINPERIOD(...), [Sales])

        Requires: Date table for date intelligence
        """
        measure_column = self._extract_column_name(context.base_measure)
        window_size = context.window_size or 3
        order_dim = context.order_by[0] if context.order_by else "Date"

        # This requires a date table - generate helper column approach instead
        helper_column = CalculatedColumn(
            table_name=table_name,
            column_name=f"_{calc_name}_Helper",
            expression=f"SUM({table_name}[{measure_column}])",
            description="Helper for moving average calculation"
        )

        # DAX using AVERAGEX with OFFSET
        dax_formula = f"""
AVERAGEX(
    TOPN(
        {window_size},
        CALCULATETABLE(
            VALUES({table_name}[{order_dim}]),
            ALLSELECTED({table_name}[{order_dim}]),
            {table_name}[{order_dim}] <= MAX({table_name}[{order_dim}])
        ),
        {table_name}[{order_dim}],
        DESC
    ),
    CALCULATE(SUM({table_name}[{measure_column}]))
)
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip(),
            display_folder="Table Calculations"
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],  # Helper column not strictly needed with this approach
            "requires_model_change": True  # May need proper date table
        }

    def _convert_moving_sum(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Convert Tableau moving sum to DAX"""
        measure_column = self._extract_column_name(context.base_measure)
        window_size = context.window_size or 3
        order_dim = context.order_by[0] if context.order_by else "Date"

        dax_formula = f"""
SUMX(
    TOPN(
        {window_size},
        CALCULATETABLE(
            VALUES({table_name}[{order_dim}]),
            ALLSELECTED({table_name}[{order_dim}]),
            {table_name}[{order_dim}] <= MAX({table_name}[{order_dim}])
        ),
        {table_name}[{order_dim}],
        DESC
    ),
    CALCULATE(SUM({table_name}[{measure_column}]))
)
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip()
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],
            "requires_model_change": False
        }

    # ============================================
    # Difference / Percent Change Conversion
    # ============================================

    def _convert_difference(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Convert Tableau difference to DAX

        Tableau: ZN(SUM([Sales])) - LOOKUP(ZN(SUM([Sales])), -1)
        DAX: [Current Value] - [Previous Value] (using CALCULATE + PREVIOUSMONTH)
        """
        measure_column = self._extract_column_name(context.base_measure)
        order_dim = context.order_by[0] if context.order_by else "Date"

        # This assumes a date table exists
        # For non-date dimensions, we'd need a different approach

        dax_formula = f"""
VAR CurrentValue = SUM({table_name}[{measure_column}])
VAR PreviousValue =
    CALCULATE(
        SUM({table_name}[{measure_column}]),
        PREVIOUSMONTH({table_name}[{order_dim}])
    )
RETURN
    CurrentValue - PreviousValue
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip()
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],
            "requires_model_change": True  # Needs date table
        }

    def _convert_percent_change(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Convert Tableau percent change to DAX"""
        measure_column = self._extract_column_name(context.base_measure)
        order_dim = context.order_by[0] if context.order_by else "Date"

        dax_formula = f"""
VAR CurrentValue = SUM({table_name}[{measure_column}])
VAR PreviousValue =
    CALCULATE(
        SUM({table_name}[{measure_column}]),
        PREVIOUSMONTH({table_name}[{order_dim}])
    )
RETURN
    DIVIDE(CurrentValue - PreviousValue, PreviousValue, 0)
"""

        measure = Measure(
            name=calc_name,
            expression=dax_formula.strip(),
            format_string="0.00%"
        )

        return {
            "dax_measures": [measure],
            "helper_columns": [],
            "requires_model_change": True
        }

    # ============================================
    # Window Calculations
    # ============================================

    def _convert_window_sum(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Convert Tableau WINDOW_SUM to DAX"""
        # Similar to moving sum
        return self._convert_moving_sum(context, calc_name, table_name)

    def _convert_window_avg(
        self,
        context: TableCalcContext,
        calc_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Convert Tableau WINDOW_AVG to DAX"""
        # Similar to moving average
        return self._convert_moving_average(context, calc_name, table_name)

    # ============================================
    # Utility Methods
    # ============================================

    def _extract_column_name(self, base_measure: str) -> str:
        """
        Extract column name from Tableau formula

        Examples:
        - "SUM([Sales])" -> "Sales"
        - "AVG([Profit])" -> "Profit"
        - "[Revenue]" -> "Revenue"
        """
        import re

        # Pattern: [ColumnName]
        pattern = r'\[([^\]]+)\]'
        match = re.search(pattern, base_measure)

        if match:
            return match.group(1)

        # Fallback: assume it's already a column name
        return base_measure.strip()
