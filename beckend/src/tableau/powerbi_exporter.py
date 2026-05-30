"""Power BI Exporter - Generate Power BI migration artifacts"""
import json
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from storage.migration_store import MigrationStore
from api.config import config


class PowerBIExporter:
    """
    Export migration results to Power BI artifacts

    Generates:
    1. DAX measures file (.dax)
    2. Power Query M code (.m)
    3. Semantic model (model.bim)
    4. Power BI Project (.pbip structure)
    5. Migration report (PDF)
    """

    def __init__(self):
        self.migration_store = MigrationStore()

    def export_migration(
        self,
        migration_id: str,
        output_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Export complete migration to Power BI artifacts

        Args:
            migration_id: Migration ID
            output_dir: Output directory (defaults to config.UPLOAD_DIR)

        Returns:
            Dictionary mapping artifact names to file paths
        """
        logger.info(f"Exporting migration {migration_id} to Power BI artifacts")

        # Get migration data
        migration = self.migration_store.get_migration(migration_id)
        workbooks = self.migration_store.get_workbooks_by_migration(migration_id)
        conversions = self.migration_store.get_conversions_by_migration(migration_id)

        if not migration:
            raise ValueError(f"Migration {migration_id} not found")

        # Determine output directory
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        export_path = Path(output_dir) / f"{migration_id}_export"
        export_path.mkdir(parents=True, exist_ok=True)

        artifacts = {}

        # 1. Generate DAX measures file
        dax_file = self._create_dax_measures_file(
            conversions,
            export_path / "measures.dax"
        )
        artifacts["dax_measures"] = str(dax_file)

        # 2. Generate Power Query M code
        m_file = self._create_power_query_m_file(
            workbooks,
            export_path / "queries.m"
        )
        artifacts["power_query"] = str(m_file)

        # 3. Generate semantic model (model.bim)
        bim_file = self._create_semantic_model(
            migration_id,
            conversions,
            export_path / "model.bim"
        )
        artifacts["semantic_model"] = str(bim_file)

        # 4. Create .pbip project structure
        pbip_path = self._create_pbip_project(
            migration_id,
            export_path,
            artifacts
        )
        artifacts["pbip_project"] = str(pbip_path)

        # 5. Generate migration report
        report_file = self._create_migration_report(
            migration,
            workbooks,
            conversions,
            export_path / "migration_report.md"
        )
        artifacts["report"] = str(report_file)

        # 6. Create ZIP archive
        zip_file = self._create_zip_archive(
            export_path,
            Path(output_dir) / f"{migration_id}_artifacts.zip"
        )
        artifacts["zip_archive"] = str(zip_file)

        logger.info(f"Exported {len(artifacts)} artifacts to {export_path}")

        return artifacts

    # ============================================
    # DAX Measures File
    # ============================================

    def _create_dax_measures_file(
        self,
        conversions: List,
        output_path: Path
    ) -> Path:
        """
        Create DAX measures file

        Format:
        ```dax
        -- Measure: Profit Ratio
        -- Original Tableau: SUM([Profit]) / SUM([Sales])
        -- Confidence: 95%
        -- Status: Validated
        Profit Ratio = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Sales]), 0)

        -- Measure: Total Sales
        -- ...
        ```
        """
        logger.info(f"Creating DAX measures file: {output_path}")

        lines = []

        lines.append("/* ============================================")
        lines.append("   POWER BI DAX MEASURES")
        lines.append("   Generated from Tableau Migration")
        lines.append(f"   Generated: {datetime.now().isoformat()}")
        lines.append("   ============================================ */")
        lines.append("")

        for conversion in conversions:
            # Get calculation details
            calculation = self.migration_store.get_calculation_by_id(conversion.calc_id)

            if not calculation:
                continue

            lines.append(f"-- Measure: {calculation.calc_name}")
            lines.append(f"-- Original Tableau: {calculation.calc_formula}")
            lines.append(f"-- Conversion Method: {conversion.conversion_method.value}")
            lines.append(f"-- Confidence: {int(conversion.confidence_score * 100)}%")
            lines.append(f"-- Status: {conversion.status.value}")

            if conversion.warnings:
                lines.append(f"-- Warnings: {', '.join(conversion.warnings)}")

            lines.append("")
            lines.append(conversion.dax_formula)
            lines.append("")
            lines.append("")

        # Write file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        logger.info(f"Created DAX measures file with {len(conversions)} measures")

        return output_path

    # ============================================
    # Power Query M Code
    # ============================================

    def _create_power_query_m_file(
        self,
        workbooks: List,
        output_path: Path
    ) -> Path:
        """
        Create Power Query M code for data connections

        Includes:
        - Calendar table generation
        - Data source connections (placeholder)
        - Table transformations
        """
        logger.info(f"Creating Power Query M file: {output_path}")

        lines = []

        lines.append("/* ============================================")
        lines.append("   POWER QUERY M CODE")
        lines.append("   Generated from Tableau Migration")
        lines.append(f"   Generated: {datetime.now().isoformat()}")
        lines.append("   ============================================ */")
        lines.append("")

        # 1. Calendar table (always useful)
        lines.append("// Calendar Table")
        lines.append("let")
        lines.append("    StartDate = #date(2020, 1, 1),")
        lines.append("    EndDate = #date(2025, 12, 31),")
        lines.append("    NumberOfDays = Duration.Days(EndDate - StartDate) + 1,")
        lines.append("    Dates = List.Dates(StartDate, NumberOfDays, #duration(1, 0, 0, 0)),")
        lines.append("    #\"Converted to Table\" = Table.FromList(Dates, Splitter.SplitByNothing(), {\"Date\"}, null, ExtraValues.Error),")
        lines.append("    #\"Changed Type\" = Table.TransformColumnTypes(#\"Converted to Table\", {{\"Date\", type date}}),")
        lines.append("    #\"Added Year\" = Table.AddColumn(#\"Changed Type\", \"Year\", each Date.Year([Date]), Int64.Type),")
        lines.append("    #\"Added Quarter\" = Table.AddColumn(#\"Added Year\", \"Quarter\", each Date.QuarterOfYear([Date]), Int64.Type),")
        lines.append("    #\"Added Month\" = Table.AddColumn(#\"Added Quarter\", \"Month\", each Date.Month([Date]), Int64.Type),")
        lines.append("    #\"Added Month Name\" = Table.AddColumn(#\"Added Month\", \"Month Name\", each Date.MonthName([Date]), type text),")
        lines.append("    #\"Added Day\" = Table.AddColumn(#\"Added Month Name\", \"Day\", each Date.Day([Date]), Int64.Type),")
        lines.append("    #\"Added Day of Week\" = Table.AddColumn(#\"Added Day\", \"Day of Week\", each Date.DayOfWeek([Date]), Int64.Type),")
        lines.append("    #\"Added Day Name\" = Table.AddColumn(#\"Added Day of Week\", \"Day Name\", each Date.DayOfWeekName([Date]), type text)")
        lines.append("in")
        lines.append("    #\"Added Day Name\"")
        lines.append("")
        lines.append("")

        # 2. Data source connections (placeholder)
        lines.append("// TODO: Add data source connections based on Tableau data sources")
        lines.append("// Example:")
        lines.append("// let")
        lines.append("//     Source = Sql.Database(\"server\", \"database\"),")
        lines.append("//     SalesTable = Source{[Schema=\"dbo\",Item=\"Sales\"]}[Data]")
        lines.append("// in")
        lines.append("//     SalesTable")
        lines.append("")

        # Write file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        logger.info("Created Power Query M file")

        return output_path

    # ============================================
    # Semantic Model (model.bim)
    # ============================================

    def _create_semantic_model(
        self,
        migration_id: str,
        conversions: List,
        output_path: Path
    ) -> Path:
        """
        Create semantic model file (Tabular Object Model JSON)

        Simplified version - includes:
        - Model metadata
        - Table definitions (placeholder)
        - Measure definitions
        """
        logger.info(f"Creating semantic model: {output_path}")

        model = {
            "name": f"TableauMigration_{migration_id}",
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "tables": [
                    {
                        "name": "Calendar",
                        "columns": [
                            {"name": "Date", "dataType": "dateTime", "isKey": True},
                            {"name": "Year", "dataType": "int64"},
                            {"name": "Quarter", "dataType": "int64"},
                            {"name": "Month", "dataType": "int64"},
                            {"name": "Month Name", "dataType": "string"},
                            {"name": "Day", "dataType": "int64"}
                        ],
                        "partitions": [
                            {
                                "name": "Calendar",
                                "mode": "import",
                                "source": {
                                    "type": "m",
                                    "expression": "Calendar"
                                }
                            }
                        ]
                    }
                ],
                "relationships": [],
                "measures": []
            }
        }

        # Add measures from conversions
        for conversion in conversions:
            calculation = self.migration_store.get_calculation_by_id(conversion.calc_id)

            if calculation:
                measure = {
                    "name": calculation.calc_name,
                    "expression": conversion.dax_formula,
                    "formatString": "#,##0.00"
                }

                model["model"]["measures"].append(measure)

        # Write JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2)

        logger.info(f"Created semantic model with {len(model['model']['measures'])} measures")

        return output_path

    # ============================================
    # .pbip Project Structure
    # ============================================

    def _create_pbip_project(
        self,
        migration_id: str,
        export_path: Path,
        artifacts: Dict[str, str]
    ) -> Path:
        """
        Create complete Power BI Project (.pbip) structure per Microsoft spec

        Structure:
        {migration_id}.pbip/
        ├── {migration_id}.pbip             # Root project file
        ├── .gitignore
        ├── {migration_id}.Report/          # Report layer
        │   ├── report.json
        │   ├── semanticModelDiagramLayout.json
        │   └── .pbi/
        │       └── localSettings.json
        └── {migration_id}.SemanticModel/   # Data model layer
            ├── definition.pbism
            ├── model.bim
            ├── diagramLayout.json
            └── .pbi/
                └── localSettings.json
        """
        logger.info("🏗️  Creating complete PBIP project structure")

        # Use migration_id as project name (no special characters)
        project_name = migration_id

        # Create root PBIP folder
        pbip_root = export_path / f"{project_name}.pbip"
        pbip_root.mkdir(parents=True, exist_ok=True)

        # Create subfolder structure
        report_folder = pbip_root / f"{project_name}.Report"
        semantic_model_folder = pbip_root / f"{project_name}.SemanticModel"

        report_folder.mkdir(parents=True, exist_ok=True)
        semantic_model_folder.mkdir(parents=True, exist_ok=True)

        # Create .pbi subfolders
        (report_folder / ".pbi").mkdir(exist_ok=True)
        (semantic_model_folder / ".pbi").mkdir(exist_ok=True)

        # 1. Create root .pbip file (project definition)
        pbip_file = pbip_root / f"{project_name}.pbip"

        # NOTE: Root .pbip file only references the Report artifact
        # The Report's definition.pbir file links to the SemanticModel
        pbip_content = {
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{project_name}.Report"
                    }
                }
            ]
        }

        with open(pbip_file, 'w', encoding='utf-8') as f:
            json.dump(pbip_content, f, indent=2)

        # 2. Create Report/definition.pbir (Report definition with dataset reference)
        definition_pbir_file = report_folder / "definition.pbir"

        pbir_content = {
            "version": "1.0",
            "datasetReference": {
                "byPath": {
                    "path": f"../{project_name}.SemanticModel"
                }
            }
        }

        with open(definition_pbir_file, 'w', encoding='utf-8') as f:
            json.dump(pbir_content, f, indent=2)

        # 3. Create Report/report.json (Report layout and visuals)
        report_file = report_folder / "report.json"

        report_content = {
            "version": "1.0",
            "name": project_name,
            "config": json.dumps({
                "version": "5.49",
                "themeCollection": {
                    "baseTheme": {
                        "name": "CY24SU06"
                    }
                },
                "activeSectionIndex": 0,
                "defaultDrillFilterOtherVisuals": True,
                "sections": [
                    {
                        "name": "ReportSection",
                        "displayName": "Page 1",
                        "filters": "[]",
                        "ordinal": 0,
                        "visualContainers": []  # No visuals - user adds in Power BI Desktop
                    }
                ]
            })
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_content, f, indent=2)

        # 4. Create Report/semanticModelDiagramLayout.json (empty)
        self._create_semantic_model_diagram_layout(report_folder / "semanticModelDiagramLayout.json")

        # 5. Create Report/.pbi/localSettings.json (empty)
        with open(report_folder / ".pbi" / "localSettings.json", 'w', encoding='utf-8') as f:
            json.dump({}, f)

        # 6. Create SemanticModel/definition.pbism
        self._create_definition_pbism(project_name, semantic_model_folder / "definition.pbism")

        # 7. Move model.bim to SemanticModel folder
        source_bim = Path(artifacts.get("semantic_model", ""))
        target_bim = semantic_model_folder / "model.bim"

        if source_bim.exists():
            import shutil
            shutil.copy(source_bim, target_bim)
            logger.info(f"✅ Copied model.bim to {target_bim}")
        else:
            logger.warning(f"⚠️  model.bim not found at {source_bim}, will be generated inline")

        # 8. Create SemanticModel/diagramLayout.json (empty)
        self._create_diagram_layout(semantic_model_folder / "diagramLayout.json")

        # 9. Create SemanticModel/.pbi/localSettings.json (empty)
        with open(semantic_model_folder / ".pbi" / "localSettings.json", 'w', encoding='utf-8') as f:
            json.dump({}, f)

        # 10. Create root .gitignore
        self._create_pbip_gitignore(pbip_root / ".gitignore")

        logger.info(f"✅ Created complete PBIP project at {pbip_root}")

        return pbip_root

    # ============================================
    # Migration Report
    # ============================================

    def _create_migration_report(
        self,
        migration,
        workbooks: List,
        conversions: List,
        output_path: Path
    ) -> Path:
        """
        Create migration summary report (Markdown)
        """
        logger.info(f"Creating migration report: {output_path}")

        lines = []

        lines.append("# Tableau to Power BI Migration Report")
        lines.append("")
        lines.append(f"**Migration ID:** {migration.migration_id}")
        lines.append(f"**Created:** {migration.created_at}")
        lines.append(f"**Completed:** {migration.completed_at or 'In Progress'}")
        lines.append(f"**Status:** {migration.status.value}")
        lines.append("")

        # Summary statistics
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Workbooks:** {len(workbooks)}")
        lines.append(f"- **Total Calculations:** {migration.calculation_count}")
        lines.append(f"- **DAX Conversions:** {len(conversions)}")

        # Conversion breakdown
        validated = sum(1 for c in conversions if c.status.value == "validated")
        pending = sum(1 for c in conversions if c.status.value == "pending")
        failed = sum(1 for c in conversions if c.status.value == "failed")

        lines.append("")
        lines.append("### Conversion Status")
        lines.append("")
        lines.append(f"- ✅ Validated: {validated}")
        lines.append(f"- ⏳ Pending: {pending}")
        lines.append(f"- ❌ Failed: {failed}")
        lines.append("")

        # Confidence distribution
        high_conf = sum(1 for c in conversions if c.confidence_score >= 0.9)
        medium_conf = sum(1 for c in conversions if 0.7 <= c.confidence_score < 0.9)
        low_conf = sum(1 for c in conversions if c.confidence_score < 0.7)

        lines.append("### Confidence Scores")
        lines.append("")
        lines.append(f"- High (≥90%): {high_conf}")
        lines.append(f"- Medium (70-89%): {medium_conf}")
        lines.append(f"- Low (<70%): {low_conf}")
        lines.append("")

        # Workbook details
        lines.append("## Workbooks")
        lines.append("")

        for wb in workbooks:
            lines.append(f"### {wb.filename}")
            lines.append("")
            lines.append(f"- Worksheets: {wb.worksheet_count}")
            lines.append(f"- Dashboards: {wb.dashboard_count}")
            lines.append(f"- Data Sources: {wb.data_source_count}")
            lines.append("")

        # Next steps
        lines.append("## Next Steps")
        lines.append("")
        lines.append("1. Open the generated `.pbip` project in Power BI Desktop")
        lines.append("2. Configure data source connections")
        lines.append("3. Review DAX measures in `measures.dax`")
        lines.append("4. Test measures with sample data")
        lines.append("5. Build report visuals")
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*Generated by Tableau-to-Power BI AI Migration Engine*")

        # Write file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        logger.info("Created migration report")

        return output_path

    # ============================================
    # PBIP Helper Methods
    # ============================================

    def _create_definition_pbism(
        self,
        project_name: str,
        output_path: Path
    ) -> Path:
        """
        Create definition.pbism file (semantic model metadata)

        This file contains metadata about the semantic model configuration
        """
        pbism_content = {
            "version": "1.0.0",
            "name": project_name,
            "compatibilityLevel": 1604,
            "model": {
                "culture": "en-US",
                "dataAccessOptions": {
                    "legacyRedirects": True,
                    "returnErrorValuesAsNull": True
                }
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(pbism_content, f, indent=2)

        logger.debug(f"Created definition.pbism at {output_path}")

        return output_path

    def _create_diagram_layout(self, output_path: Path) -> Path:
        """
        Create diagramLayout.json (empty is fine for new projects)

        This file stores the visual layout of tables in the Model view
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)

        logger.debug(f"Created diagramLayout.json at {output_path}")

        return output_path

    def _create_semantic_model_diagram_layout(self, output_path: Path) -> Path:
        """
        Create semanticModelDiagramLayout.json

        Stores diagram preferences for the semantic model view
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)

        logger.debug(f"Created semanticModelDiagramLayout.json at {output_path}")

        return output_path

    def _create_pbip_gitignore(self, output_path: Path) -> Path:
        """
        Create .gitignore for PBIP project

        Excludes local settings, cache files, and OS-specific files
        """
        gitignore_content = """# Power BI local settings
.pbi/localSettings.json
*.pbi/localSettings.json

# Cache files
*.cache.abf
cache.abf

# Unapplied changes
unappliedChanges.json

# OS files
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(gitignore_content.strip())

        logger.debug(f"Created .gitignore at {output_path}")

        return output_path

    # ============================================
    # ZIP Archive
    # ============================================

    def _create_zip_archive(
        self,
        source_dir: Path,
        output_zip: Path
    ) -> Path:
        """Create ZIP archive of all artifacts"""
        logger.info(f"Creating ZIP archive: {output_zip}")

        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir.parent)
                    zipf.write(file_path, arcname)

        logger.info(f"Created ZIP archive: {output_zip}")

        return output_zip
