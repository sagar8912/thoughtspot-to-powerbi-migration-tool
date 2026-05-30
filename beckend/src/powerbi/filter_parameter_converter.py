"""Filter & Parameter Converter - Convert Tableau filters and parameters to Power BI"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger



class PowerBIFilterScope(Enum):
    """Power BI filter scope"""
    REPORT = "report"  # Report-level filter (affects all pages)
    PAGE = "page"  # Page-level filter (affects one page)
    VISUAL = "visual"  # Visual-level filter (affects one visual)


class PowerBIFilterType(Enum):
    """Power BI filter types"""
    BASIC = "basic"  # Simple include/exclude
    ADVANCED = "advanced"  # Complex conditions
    TOP_N = "topN"  # Top N filtering
    RELATIVE_DATE = "relativeDate"  # Last 7 days, etc.


@dataclass
class PowerBIFilter:
    """Power BI filter definition"""
    target_table: str
    target_column: str
    filter_type: PowerBIFilterType
    scope: PowerBIFilterScope
    values: Optional[List[Any]] = None
    operator: str = "In"  # In, NotIn, Is, IsNot, GreaterThan, etc.
    is_required: bool = False


@dataclass
class WhatIfParameter:
    """Power BI What-If parameter definition"""
    name: str
    min_value: float
    max_value: float
    increment: float
    default_value: float
    format: str = "0"


@dataclass
class SlicerTable:
    """Disconnected slicer table for parameters"""
    name: str
    values: List[Any]
    default_value: Optional[Any] = None


class FilterParameterConverter:
    """
    Convert Tableau filters and parameters to Power BI equivalents

    Conversion mappings:
    - Tableau Context Filter → Report/Page-level filter
    - Tableau Regular Filter → Visual-level filter
    - Tableau Parameter (numeric) → What-If parameter
    - Tableau Parameter (text/list) → Disconnected slicer table
    """

    def __init__(self):
        pass

    # ============================================
    # Filter Conversion
    # ============================================

    def convert_filters(
        self,
        tableau_filters: List[Dict[str, Any]],
        worksheets: Optional[List[str]] = None
    ) -> List[PowerBIFilter]:
        """
        Convert Tableau filters to Power BI filters

        Args:
            tableau_filters: List of Tableau filters
            worksheets: Optional list of worksheet names for scope determination

        Returns:
            List of Power BI filters
        """
        logger.info(f"Converting {len(tableau_filters)} Tableau filters...")

        powerbi_filters = []

        for tf in tableau_filters:
            try:
                pbi_filter = self._convert_single_filter(tf)

                if pbi_filter:
                    powerbi_filters.append(pbi_filter)
                    logger.debug(
                        f"  Converted filter: {tf.get('field')} ({tf.get('filter_type')}) "
                        f"-> {pbi_filter.scope.value}-level"
                    )

            except Exception as e:
                logger.warning(f"Failed to convert filter {tf.get('field')}: {e}")

        logger.info(f"Converted {len(powerbi_filters)} filters")

        return powerbi_filters

    def _convert_single_filter(self, tableau_filter: Dict[str, Any]) -> Optional[PowerBIFilter]:
        """Convert a single Tableau filter to Power BI filter"""

        # Determine scope based on context filter flag
        is_context = tableau_filter.get("is_context_filter", False)
        if is_context:
            # Context filters → Report-level (affects everything)
            scope = PowerBIFilterScope.REPORT
        else:
            # Regular filters → Page-level (or visual-level if worksheet-specific)
            scope = PowerBIFilterScope.PAGE

        # Determine filter type
        filter_type = self._map_filter_type(tableau_filter.get("filter_type", "categorical"))

        # Map operator
        operator = self._map_filter_operator(tableau_filter.get("operator", "In"))

        # Extract table and column from field name
        # Tableau format: "TableName.FieldName" or just "FieldName"
        table_name, column_name = self._parse_field_name(tableau_filter.get("field", ""))

        powerbi_filter = PowerBIFilter(
            target_table=table_name,
            target_column=column_name,
            filter_type=filter_type,
            scope=scope,
            values=tableau_filter.get("values", []),
            operator=operator,
            is_required=is_context
        )

        return powerbi_filter

    def _map_filter_type(self, tableau_filter_type: str) -> PowerBIFilterType:
        """Map Tableau filter type to Power BI filter type"""
        mapping = {
            "categorical": PowerBIFilterType.BASIC,
            "quantitative": PowerBIFilterType.ADVANCED,
            "relative-date": PowerBIFilterType.RELATIVE_DATE,
            "top": PowerBIFilterType.TOP_N,
        }

        return mapping.get(tableau_filter_type.lower(), PowerBIFilterType.BASIC)

    def _map_filter_operator(self, tableau_operator: Optional[str]) -> str:
        """Map Tableau filter operator to Power BI operator"""
        if not tableau_operator:
            return "In"

        mapping = {
            "=": "Is",
            "!=": "IsNot",
            ">": "GreaterThan",
            ">=": "GreaterThanOrEqual",
            "<": "LessThan",
            "<=": "LessThanOrEqual",
            "in": "In",
            "not in": "NotIn",
            "contains": "Contains",
            "startswith": "StartsWith",
            "endswith": "EndsWith",
        }

        return mapping.get(tableau_operator.lower(), "In")

    def _parse_field_name(self, field: str) -> tuple[str, str]:
        """
        Parse field name into table and column

        Examples:
        - "Sales.Region" -> ("Sales", "Region")
        - "Region" -> ("", "Region")
        """
        if "." in field:
            parts = field.split(".", 1)
            return parts[0], parts[1]
        else:
            return "", field

    # ============================================
    # Parameter Conversion
    # ============================================

    def convert_parameters(
        self,
        tableau_parameters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Convert Tableau parameters to Power BI equivalents

        Returns:
            Dictionary with:
            - whatif_parameters: List of What-If parameters
            - slicer_tables: List of disconnected slicer tables
        """
        logger.info(f"Converting {len(tableau_parameters)} Tableau parameters...")

        whatif_parameters = []
        slicer_tables = []

        for tp in tableau_parameters:
            try:
                if self._is_numeric_parameter(tp):
                    # Numeric parameters → What-If parameter
                    whatif = self._convert_to_whatif(tp)
                    whatif_parameters.append(whatif)

                    logger.debug(f"  Converted parameter '{tp.get('name')}' to What-If parameter")

                else:
                    # Text/List parameters → Disconnected slicer table
                    slicer_table = self._convert_to_slicer_table(tp)
                    slicer_tables.append(slicer_table)

                    logger.debug(f"  Converted parameter '{tp.get('name')}' to slicer table")

            except Exception as e:
                logger.warning(f"Failed to convert parameter {tp.get('name')}: {e}")

        logger.info(
            f"Converted {len(whatif_parameters)} What-If parameters, "
            f"{len(slicer_tables)} slicer tables"
        )

        return {
            "whatif_parameters": whatif_parameters,
            "slicer_tables": slicer_tables
        }

    def _is_numeric_parameter(self, param: Dict[str, Any]) -> bool:
        """Check if parameter is numeric"""
        numeric_types = ["integer", "int", "real", "number", "decimal", "float"]
        return param.get("datatype", "").lower() in numeric_types

    def _convert_to_whatif(self, param: Dict[str, Any]) -> WhatIfParameter:
        """
        Convert numeric Tableau parameter to What-If parameter

        What-If parameters in Power BI:
        - Create a disconnected table with a single column
        - Use DAX: GENERATESERIES(min, max, increment)
        - User selects value via slicer
        """
        # Extract min/max from allowable values
        allowable_values = param.get("allowable_values", [])
        numeric_values = [float(v) for v in allowable_values if self._is_numeric(v)]

        if numeric_values:
            min_value = min(numeric_values)
            max_value = max(numeric_values)

            # Infer increment
            if len(numeric_values) > 1:
                sorted_values = sorted(numeric_values)
                increment = sorted_values[1] - sorted_values[0]
            else:
                increment = 1.0
        else:
            # No allowable values specified - use defaults
            min_value = 0.0
            max_value = 100.0
            increment = 1.0

        # Parse default value
        current_value = param.get("current_value", "")
        default_value = float(current_value) if self._is_numeric(current_value) else min_value

        whatif = WhatIfParameter(
            name=param.get("name", "UnknownParameter"),
            min_value=min_value,
            max_value=max_value,
            increment=increment,
            default_value=default_value,
            format="0" if increment >= 1 else "0.00"
        )

        return whatif

    def _convert_to_slicer_table(self, param: Dict[str, Any]) -> SlicerTable:
        """
        Convert text Tableau parameter to disconnected slicer table

        Creates a single-column table with allowed values
        """
        slicer_table = SlicerTable(
            name=f"Param_{param.get('name', 'Unknown')}",
            values=param.get("allowable_values", []),
            default_value=param.get("current_value", None)
        )

        return slicer_table

    def _is_numeric(self, value: Any) -> bool:
        """Check if value can be converted to number"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    # ============================================
    # DAX Generation for Parameters
    # ============================================

    def generate_whatif_parameter_dax(self, whatif: WhatIfParameter) -> str:
        """
        Generate DAX to create What-If parameter table

        Power BI What-If parameters are created via:
        1. New Parameter → Creates a table automatically
        2. Manual DAX table creation (for programmatic approach)
        """
        dax = f"""
{whatif.name} =
GENERATESERIES(
    {whatif.min_value},
    {whatif.max_value},
    {whatif.increment}
)
"""

        return dax.strip()

    def generate_slicer_table_dax(self, slicer: SlicerTable) -> str:
        """
        Generate DAX to create disconnected slicer table

        Creates a single-column table with values
        """
        # Format values for DAX
        formatted_values = []

        for value in slicer.values:
            if isinstance(value, str):
                # Escape quotes
                escaped = value.replace('"', '""')
                formatted_values.append(f'"{escaped}"')
            else:
                formatted_values.append(str(value))

        values_str = ", ".join(formatted_values)

        dax = f"""
{slicer.name} =
{{
    {values_str}
}}
"""

        return dax.strip()

    # ============================================
    # Power BI Report JSON Generation
    # ============================================

    def generate_filter_json(self, filter: PowerBIFilter) -> Dict[str, Any]:
        """
        Generate Power BI Report JSON for a filter

        This JSON structure is used in .pbix report files
        """
        filter_json = {
            "name": f"{filter.target_table}_{filter.target_column}",
            "type": filter.filter_type.value,
            "target": {
                "table": filter.target_table,
                "column": filter.target_column
            },
            "filterType": 1,  # Basic filter
            "operator": filter.operator,
            "isRequired": filter.is_required
        }

        # Add values if present
        if filter.values:
            filter_json["values"] = filter.values

        # Add scope
        if filter.scope == PowerBIFilterScope.REPORT:
            filter_json["scope"] = "Report"
        elif filter.scope == PowerBIFilterScope.PAGE:
            filter_json["scope"] = "Page"
        else:
            filter_json["scope"] = "Visual"

        return filter_json

    # ============================================
    # Migration Report Generation
    # ============================================

    def generate_conversion_report(
        self,
        tableau_filters: List[Dict[str, Any]],
        tableau_parameters: List[Dict[str, Any]],
        powerbi_filters: List[PowerBIFilter],
        whatif_parameters: List[WhatIfParameter],
        slicer_tables: List[SlicerTable]
    ) -> str:
        """
        Generate markdown report of filter/parameter conversion

        Useful for documentation and manual verification
        """
        lines = []

        lines.append("# Filter & Parameter Conversion Report")
        lines.append("")

        # Filters section
        lines.append("## Filters")
        lines.append("")
        lines.append(f"**Tableau Filters:** {len(tableau_filters)}")
        lines.append(f"**Power BI Filters:** {len(powerbi_filters)}")
        lines.append("")

        lines.append("| Tableau Field | Type | Context | Power BI Scope | Operator |")
        lines.append("|---------------|------|---------|----------------|----------|")

        for i, tf in enumerate(tableau_filters):
            pbi_filter = powerbi_filters[i] if i < len(powerbi_filters) else None

            if pbi_filter:
                is_context = tf.get("is_context_filter", False)
                lines.append(
                    f"| {tf.get('field', '')} | {tf.get('filter_type', '')} | "
                    f"{'Yes' if is_context else 'No'} | "
                    f"{pbi_filter.scope.value} | {pbi_filter.operator} |"
                )

        lines.append("")

        # Parameters section
        lines.append("## Parameters")
        lines.append("")
        lines.append(f"**Tableau Parameters:** {len(tableau_parameters)}")
        lines.append(f"**What-If Parameters:** {len(whatif_parameters)}")
        lines.append(f"**Slicer Tables:** {len(slicer_tables)}")
        lines.append("")

        # What-If parameters
        if whatif_parameters:
            lines.append("### What-If Parameters")
            lines.append("")
            lines.append("| Name | Min | Max | Increment | Default |")
            lines.append("|------|-----|-----|-----------|---------|")

            for whatif in whatif_parameters:
                lines.append(
                    f"| {whatif.name} | {whatif.min_value} | {whatif.max_value} | "
                    f"{whatif.increment} | {whatif.default_value} |"
                )

            lines.append("")

        # Slicer tables
        if slicer_tables:
            lines.append("### Disconnected Slicer Tables")
            lines.append("")
            lines.append("| Table Name | Values Count | Default |")
            lines.append("|-----------|--------------|---------|")

            for slicer in slicer_tables:
                default = str(slicer.default_value) if slicer.default_value else "N/A"
                lines.append(f"| {slicer.name} | {len(slicer.values)} | {default} |")

            lines.append("")

        # Implementation notes
        lines.append("## Implementation Notes")
        lines.append("")
        lines.append("### Filters")
        lines.append("- **Context filters** are converted to report-level filters (affect all visuals)")
        lines.append("- **Regular filters** are converted to page-level filters")
        lines.append("- Manual adjustment may be needed for visual-specific filters")
        lines.append("")

        lines.append("### Parameters")
        lines.append("- **Numeric parameters** → What-If parameters (use Modeling tab)")
        lines.append("- **Text/List parameters** → Disconnected slicer tables")
        lines.append("- Update measures to reference parameter values via SELECTEDVALUE()")
        lines.append("")

        return "\n".join(lines)
