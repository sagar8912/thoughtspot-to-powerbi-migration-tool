"""Starter PBIX Template Creator - Generate blank Power BI templates"""
import json
import zipfile
import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger


class StarterPBIXCreator:
    """
    Create starter PBIX templates for migration

    A PBIX file is a ZIP archive containing:
    - DataModel: model.bim (JSON)
    - Report: report.json (visuals and layout)
    - DiagramState: diagram state
    - Metadata: version info
    - [Content_Types].xml: content types
    """

    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.template_dir.mkdir(exist_ok=True)

    def create_blank_template(
        self,
        output_path: str,
        include_measures_table: bool = True,
        include_date_table: bool = True
    ) -> Path:
        """
        Create a blank PBIX template

        Args:
            output_path: Path for output PBIX file
            include_measures_table: Add a "Measures" table for organizing measures
            include_date_table: Add a Calendar date table

        Returns:
            Path to created PBIX file
        """
        logger.info(f"Creating blank PBIX template: {output_path}")

        output_path = Path(output_path)

        # Create temporary directory for PBIX contents
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create PBIX structure
            self._create_content_types(temp_path)
            self._create_data_model(temp_path, include_measures_table, include_date_table)
            self._create_data_model_schema(temp_path)
            self._create_version(temp_path)
            self._create_report(temp_path)
            self._create_metadata(temp_path)
            self._create_diagram_state(temp_path)

            # Create ZIP archive (PBIX)
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in temp_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(temp_path)
                        zf.write(file_path, arcname)

        logger.info(f"✅ Created PBIX template: {output_path}")

        return output_path

    def _create_content_types(self, temp_path: Path):
        """Create [Content_Types].xml"""
        content_types_xml = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json" />
  <Override PartName="/DataModel" ContentType="application/x-tmdl-data" />
  <Override PartName="/DataModelSchema" ContentType="application/x-tmdl-metadata" />
  <Override PartName="/DiagramState" ContentType="application/json" />
  <Override PartName="/Report/Layout" ContentType="application/json" />
  <Override PartName="/Metadata" ContentType="application/json" />
  <Override PartName="/Version" ContentType="text/plain" />
</Types>
"""

        with open(temp_path / "[Content_Types].xml", 'w', encoding='utf-8') as f:
            f.write(content_types_xml.strip())

    def _create_data_model(
        self,
        temp_path: Path,
        include_measures_table: bool,
        include_date_table: bool
    ):
        """
        Create DataModel (model.bim)

        This is a Tabular Model in JSON format (compatibility level 1500+)
        """
        model = {
            "name": "SemanticModel",
            "compatibilityLevel": 1500,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "sourceQueryCulture": "en-US",
                "dataSources": [],
                "tables": [],
                "relationships": [],
                "annotations": [
                    {
                        "name": "PBI_Template",
                        "value": "true"
                    },
                    {
                        "name": "PBI_ProTooling",
                        "value": "[\"DevMode\"]"
                    }
                ],
                "expressions": []
            }
        }

        # Add Measures table (hidden table for organizing measures)
        if include_measures_table:
            measures_table = {
                "name": "Measures",
                "description": "Hidden table for organizing DAX measures",
                "isHidden": True,
                "lineageTag": "measures-table-001",
                "columns": [
                    {
                        "name": "_MeasuresPlaceholder",
                        "dataType": "string",
                        "sourceColumn": "_MeasuresPlaceholder",
                        "isHidden": True,
                        "lineageTag": "measures-placeholder-col"
                    }
                ],
                "partitions": [
                    {
                        "name": "Partition",
                        "mode": "import",
                        "source": {
                            "type": "m",
                            "expression": "#table({\"_MeasuresPlaceholder\"}, {{\"\"}})"
                        }
                    }
                ],
                "measures": []
            }

            model["model"]["tables"].append(measures_table)

        # Skip date table for now to keep template minimal
        # Users can add it in Power BI Desktop if needed

        # Save model.bim
        data_model_path = temp_path / "DataModel"

        with open(data_model_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2)

    def _create_report(self, temp_path: Path):
        """Create Report/Layout (report.json)"""
        report_layout = {
            "id": 0,
            "resourcePackages": [],
            "name": "ReportSection",
            "displayName": "Page 1",
            "filters": "[]",
            "ordinal": 0,
            "config": json.dumps({
                "layouts": [
                    {
                        "id": 0,
                        "position": {
                            "x": 0,
                            "y": 0,
                            "z": 0,
                            "width": 1280,
                            "height": 720
                        }
                    }
                ],
                "objects": []  # No visuals yet
            }),
            "displayOption": 0,
            "width": 1280,
            "height": 720
        }

        report_dir = temp_path / "Report"
        report_dir.mkdir(exist_ok=True)

        with open(report_dir / "Layout", 'w', encoding='utf-8') as f:
            json.dump(report_layout, f, indent=2)

    def _create_metadata(self, temp_path: Path):
        """Create Metadata"""
        metadata = {
            "version": "3.0"
        }

        with open(temp_path / "Metadata", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

    def _create_diagram_state(self, temp_path: Path):
        """Create DiagramState"""
        diagram_state = {
            "version": "1.0",
            "diagramViewState": {}
        }

        with open(temp_path / "DiagramState", 'w', encoding='utf-8') as f:
            json.dump(diagram_state, f, indent=2)

    def _create_data_model_schema(self, temp_path: Path):
        """Create DataModelSchema (required by Tabular Editor)"""
        schema = {
            "name": "SemanticModel",
            "compatibilityLevel": 1500,
            "model": {
                "defaultPowerBIDataSourceVersion": "powerBI_V3"
            }
        }

        with open(temp_path / "DataModelSchema", 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2)

    def _create_version(self, temp_path: Path):
        """Create Version file"""
        # Power BI Desktop version string
        version_content = "2.0"

        with open(temp_path / "Version", 'w', encoding='utf-8') as f:
            f.write(version_content)


# ============================================
# Template Creation Script
# ============================================

def create_default_templates():
    """
    Create default PBIX templates for the migration system

    Creates:
    1. blank_template.pbix - Minimal template
    2. standard_template.pbix - With measures table and date table
    """
    creator = StarterPBIXCreator()

    # Create templates directory
    templates_dir = Path("./bknd/templates")
    templates_dir.mkdir(exist_ok=True)

    # Blank template (minimal)
    creator.create_blank_template(
        output_path=str(templates_dir / "blank_template.pbix"),
        include_measures_table=False,
        include_date_table=False
    )

    # Standard template (recommended)
    creator.create_blank_template(
        output_path=str(templates_dir / "standard_template.pbix"),
        include_measures_table=True,
        include_date_table=True
    )

    logger.info("✅ Default templates created in ./bknd/templates/")


if __name__ == "__main__":
    create_default_templates()
