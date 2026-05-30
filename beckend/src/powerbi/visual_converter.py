"""Visual Converter - Convert Tableau worksheets to Power BI visuals"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import uuid
from loguru import logger



class PowerBIVisualType(Enum):
    """Power BI visual types"""
    CARD = "card"
    TABLE = "table"
    MATRIX = "pivotTable"
    CLUSTERED_BAR_CHART = "clusteredBarChart"
    CLUSTERED_COLUMN_CHART = "clusteredColumnChart"
    LINE_CHART = "lineChart"
    AREA_CHART = "areaChart"
    PIE_CHART = "pieChart"
    DONUT_CHART = "donutChart"
    SCATTER_CHART = "scatterChart"
    MAP = "map"
    SLICER = "slicer"


@dataclass
class VisualLayout:
    """Visual positioning and size"""
    x: float
    y: float
    width: float
    height: float
    z_index: int = 0


@dataclass
class PowerBIVisual:
    """Power BI visual definition"""
    visual_type: PowerBIVisualType
    name: str
    title: str
    layout: VisualLayout
    data_roles: Dict[str, List[str]]  # e.g., {"Category": ["Region"], "Values": ["Sales"]}
    filters: Optional[List[Dict]] = None


class VisualConverter:
    """
    Convert Tableau worksheets to Power BI visuals

    Handles:
    - Visual type mapping
    - Field assignment (rows → axis, columns → legend, etc.)
    - Layout generation
    - Basic visual properties
    """

    # Standard visual dimensions (Power BI canvas is 1280x720)
    CANVAS_WIDTH = 1280
    CANVAS_HEIGHT = 720

    # Default visual sizes
    DEFAULT_VISUAL_WIDTH = 400
    DEFAULT_VISUAL_HEIGHT = 300

    CARD_WIDTH = 200
    CARD_HEIGHT = 150

    def __init__(self):
        pass

    # ============================================
    # Main Conversion Method
    # ============================================

    def convert_worksheets_to_visuals(
        self,
        worksheets: List[Dict[str, Any]],
        auto_layout: bool = True
    ) -> List[PowerBIVisual]:
        """
        Convert Tableau worksheets to Power BI visuals

        Args:
            worksheets: List of Tableau worksheets
            auto_layout: Automatically arrange visuals on canvas

        Returns:
            List of Power BI visuals with layout
        """
        logger.info(f"Converting {len(worksheets)} worksheets to Power BI visuals...")

        powerbi_visuals = []

        for i, worksheet in enumerate(worksheets):
            try:
                visual = self._convert_single_worksheet(worksheet)

                if visual:
                    # Apply auto-layout if enabled
                    if auto_layout:
                        layout = self._calculate_auto_layout(i, len(worksheets))
                        visual.layout = layout

                    powerbi_visuals.append(visual)

                    logger.debug(
                        f"  Converted worksheet '{worksheet.get('name', 'Unknown')}' "
                        f"({worksheet.get('mark_type', 'Unknown')} → {visual.visual_type.value})"
                    )

            except Exception as e:
                logger.warning(f"Failed to convert worksheet {worksheet.get('name', 'Unknown')}: {e}")

        logger.info(f"Converted {len(powerbi_visuals)} visuals")

        return powerbi_visuals

    def _convert_single_worksheet(self, worksheet: Dict[str, Any]) -> Optional[PowerBIVisual]:
        """Convert a single Tableau worksheet to Power BI visual"""

        # Map visual type
        powerbi_visual_type = self._map_visual_type(None, worksheet.get("mark_type", "Unknown"))

        # Extract marks
        marks_fields = []
        for pane in worksheet.get("pane_encodings", []):
            for enc_type, field in pane.get("encodings", {}).items():
                marks_fields.append(field)

        # Map fields to data roles
        data_roles = self._map_fields_to_data_roles(
            visual_type=powerbi_visual_type,
            rows=worksheet.get("rows", []),
            columns=worksheet.get("cols", []),
            marks=marks_fields
        )

        name = worksheet.get("name", "Unknown Sheet")

        # Create visual
        visual = PowerBIVisual(
            visual_type=powerbi_visual_type,
            name=name,
            title=name,
            layout=VisualLayout(x=0, y=0, width=self.DEFAULT_VISUAL_WIDTH, height=self.DEFAULT_VISUAL_HEIGHT),
            data_roles=data_roles,
            filters=[]
        )

        return visual

    def _map_visual_type(self, tableau_type: Any, mark_type: str) -> PowerBIVisualType:
        """
        Map Tableau visual type to Power BI visual type

        Tableau → Power BI mappings:
        - TEXT_TABLE → Table
        - MATRIX → Matrix
        - BAR_CHART → Clustered Bar Chart
        - LINE_CHART → Line Chart
        - CARD → Card
        - etc.
        """
        if tableau_type:
            mapping = {
                "CARD": PowerBIVisualType.CARD,
                "TEXT_TABLE": PowerBIVisualType.TABLE,
                "MATRIX": PowerBIVisualType.MATRIX,
                "BAR_CHART": PowerBIVisualType.CLUSTERED_BAR_CHART,
                "LINE_CHART": PowerBIVisualType.LINE_CHART,
                "AREA_CHART": PowerBIVisualType.AREA_CHART,
                "PIE_CHART": PowerBIVisualType.PIE_CHART,
                "SCATTER": PowerBIVisualType.SCATTER_CHART,
                "MAP": PowerBIVisualType.MAP,
            }

            powerbi_type = mapping.get(str(tableau_type).split(".")[-1])
            if powerbi_type:
                return powerbi_type

        # Fallback: Use mark type
        mark_mapping = {
            "bar": PowerBIVisualType.CLUSTERED_COLUMN_CHART,
            "line": PowerBIVisualType.LINE_CHART,
            "area": PowerBIVisualType.AREA_CHART,
            "circle": PowerBIVisualType.SCATTER_CHART,
            "text": PowerBIVisualType.TABLE,
        }

        return mark_mapping.get(mark_type, PowerBIVisualType.TABLE)

    def _map_fields_to_data_roles(
        self,
        visual_type: PowerBIVisualType,
        rows: List[str],
        columns: List[str],
        marks: List[str]
    ) -> Dict[str, List[str]]:
        """
        Map Tableau shelf fields to Power BI data roles

        Power BI data roles vary by visual type:
        - Bar Chart: Axis, Values, Legend
        - Line Chart: Axis, Values, Legend
        - Card: Fields
        - Table: Values
        - Matrix: Rows, Columns, Values
        """
        data_roles = {}

        if visual_type == PowerBIVisualType.CARD:
            # Card: Single value
            # Use first measure from marks or columns
            data_roles["Fields"] = marks[:1] if marks else columns[:1]

        elif visual_type == PowerBIVisualType.TABLE:
            # Table: All fields as columns
            data_roles["Values"] = rows + columns + marks

        elif visual_type == PowerBIVisualType.MATRIX:
            # Matrix: Rows, Columns, Values
            data_roles["Rows"] = rows
            data_roles["Columns"] = columns
            data_roles["Values"] = marks

        elif visual_type in [
            PowerBIVisualType.CLUSTERED_BAR_CHART,
            PowerBIVisualType.CLUSTERED_COLUMN_CHART,
            PowerBIVisualType.LINE_CHART,
            PowerBIVisualType.AREA_CHART
        ]:
            # Charts: Axis (from rows), Values (from marks), Legend (from columns)
            data_roles["Axis"] = rows
            data_roles["Values"] = marks
            if columns:
                data_roles["Legend"] = columns

        elif visual_type == PowerBIVisualType.PIE_CHART:
            # Pie: Values, Legend
            data_roles["Values"] = marks[:1] if marks else []
            data_roles["Legend"] = rows + columns

        elif visual_type == PowerBIVisualType.SCATTER_CHART:
            # Scatter: X, Y, Details
            x_fields = rows[:1] if rows else []
            y_fields = marks[:1] if marks else []

            data_roles["X"] = x_fields
            data_roles["Y"] = y_fields
            data_roles["Details"] = columns

        else:
            # Default: Put everything in Values
            data_roles["Values"] = rows + columns + marks

        return data_roles

    def _calculate_auto_layout(self, index: int, total: int) -> VisualLayout:
        """
        Calculate automatic layout for visuals

        Simple grid layout:
        - 2 columns for < 4 visuals
        - 3 columns for >= 4 visuals
        """
        # Determine grid dimensions
        if total <= 2:
            cols = 1
        elif total <= 4:
            cols = 2
        else:
            cols = 3

        # Calculate position
        row = index // cols
        col = index % cols

        # Calculate visual size with padding
        padding = 20
        visual_width = (self.CANVAS_WIDTH - padding * (cols + 1)) / cols
        visual_height = 300  # Fixed height

        x = padding + col * (visual_width + padding)
        y = padding + row * (visual_height + padding)

        return VisualLayout(
            x=x,
            y=y,
            width=visual_width,
            height=visual_height,
            z_index=index
        )

    # ============================================
    # Power BI Report JSON Generation
    # ============================================

    def generate_visual_json(self, visual: PowerBIVisual) -> Dict[str, Any]:
        """
        Generate Power BI Report JSON for a visual

        This JSON structure is embedded in Power BI .pbix report files
        """
        visual_json = {
            "name": str(uuid.uuid4()),
            "type": visual.visual_type.value,
            "title": visual.title,
            "x": visual.layout.x,
            "y": visual.layout.y,
            "z": visual.layout.z_index,
            "width": visual.layout.width,
            "height": visual.layout.height,
            "config": json.dumps({
                "name": str(uuid.uuid4()),
                "layouts": [
                    {
                        "id": 0,
                        "position": {
                            "x": visual.layout.x,
                            "y": visual.layout.y,
                            "z": visual.layout.z_index,
                            "width": visual.layout.width,
                            "height": visual.layout.height
                        }
                    }
                ],
                "singleVisual": {
                    "visualType": visual.visual_type.value,
                    "dataRoles": self._format_data_roles(visual.data_roles),
                    "objects": {}
                }
            })
        }

        return visual_json

    def _format_data_roles(self, data_roles: Dict[str, List[str]]) -> List[Dict]:
        """Format data roles for Power BI JSON"""
        formatted = []

        for role_name, fields in data_roles.items():
            for field in fields:
                formatted.append({
                    "name": role_name,
                    "displayName": role_name,
                    "kind": 0,  # Grouping
                    "field": {
                        "Column": {
                            "Expression": {
                                "SourceRef": {
                                    "Source": "t"  # Table reference
                                }
                            },
                            "Property": field
                        }
                    }
                })

        return formatted

    def generate_page_json(
        self,
        page_name: str,
        visuals: List[PowerBIVisual]
    ) -> Dict[str, Any]:
        """
        Generate Power BI Report page JSON

        A page contains multiple visuals
        """
        page_json = {
            "name": page_name,
            "displayName": page_name,
            "width": self.CANVAS_WIDTH,
            "height": self.CANVAS_HEIGHT,
            "displayOption": 0,  # Fit to page
            "ordinal": 0,
            "config": json.dumps({
                "layouts": [],
                "objects": [self.generate_visual_json(v) for v in visuals]
            }),
            "filters": "[]"
        }

        return page_json

    # ============================================
    # Conversion Report
    # ============================================

    def generate_visual_conversion_report(
        self,
        worksheets: List[Dict[str, Any]],
        visuals: List[PowerBIVisual]
    ) -> str:
        """
        Generate markdown report of visual conversion

        Useful for documentation and verification
        """
        lines = []

        lines.append("# Visual Conversion Report")
        lines.append("")
        lines.append(f"**Tableau Worksheets:** {len(worksheets)}")
        lines.append(f"**Power BI Visuals:** {len(visuals)}")
        lines.append("")

        lines.append("## Visual Mapping")
        lines.append("")
        lines.append("| Tableau Worksheet | Tableau Type | Power BI Visual | Data Roles |")
        lines.append("|-------------------|--------------|-----------------|------------|")

        for i, worksheet in enumerate(worksheets):
            if i < len(visuals):
                visual = visuals[i]
                ws_name = worksheet.get("name", "Unknown")
                ws_mark = worksheet.get("mark_type", "Unknown")

                # Format data roles
                roles_str = ", ".join([
                    f"{role}: {len(fields)}" for role, fields in visual.data_roles.items()
                ])

                lines.append(
                    f"| {ws_name} | {ws_mark} | "
                    f"{visual.visual_type.value} | {roles_str} |"
                )

        lines.append("")

        # Implementation notes
        lines.append("## Implementation Notes")
        lines.append("")
        lines.append("### Visual Conversion")
        lines.append("- Tableau worksheets are converted to Power BI visuals")
        lines.append("- Field mappings: Rows → Axis, Columns → Legend, Marks → Values")
        lines.append("- Layout is auto-generated in a grid pattern")
        lines.append("")

        lines.append("### Manual Adjustments Needed")
        lines.append("- Visual positioning and sizing")
        lines.append("- Color schemes and formatting")
        lines.append("- Tooltips and drill-through actions")
        lines.append("- Custom visual replacements (if Tableau uses custom viz)")
        lines.append("")

        return "\n".join(lines)
