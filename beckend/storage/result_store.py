"""
Result storage management for ThoughtSpot -> Power BI Migration Tool.

This store manages:
- Job result JSON files
- Migration summary reports
- Power BI artifact metadata
- DAX conversion reports
- Relationship reports
- Export package metadata
- Complete downloadable ZIP package
"""

import csv
import json
import shutil
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from loguru import logger

from api.config import config


class ResultStore:
    """
    Manages ThoughtSpot -> Power BI migration result storage.
    """

    def __init__(self):
        Path(config.RESULT_DIR).mkdir(parents=True, exist_ok=True)

        if hasattr(config, "POWERBI_OUTPUT_DIR"):
            Path(config.POWERBI_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        if hasattr(config, "REPORT_JSON_DIR"):
            Path(config.REPORT_JSON_DIR).mkdir(parents=True, exist_ok=True)

        if hasattr(config, "DAX_OUTPUT_DIR"):
            Path(config.DAX_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Internal Helpers
    # ============================================================

    @staticmethod
    def _safe_json_dump(data: Dict[str, Any], file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

    @staticmethod
    def _safe_json_load(file_path: Path) -> Optional[Dict[str, Any]]:
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load JSON file {file_path}: {e}", exc_info=True)
            return None

    @staticmethod
    def _safe_write_text(file_path: Path, content: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _job_result_dir(self, job_id: str) -> Path:
        return Path(config.RESULT_DIR) / job_id

    def _migration_result_dir(self, migration_id: str) -> Path:
        return Path(config.RESULT_DIR) / "migrations" / migration_id

    def _get_export_dir(self, job_id: str) -> Path:
        export_dir = self._job_result_dir(job_id) / "export_package"
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    # ============================================================
    # Job Result
    # ============================================================

    def save_result(self, job_id: str, result: Dict[str, Any]) -> str:
        """
        Save main job result.
        """

        job_dir = self._job_result_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        final_result = {
            "job_id": job_id,
            "migration_id": result.get("migration_id") or job_id,
            "type": "thoughtspot_powerbi_migration_result",
            "generated_at": datetime.utcnow().isoformat(),
            **result,
        }

        result_file = job_dir / "report.json"
        self._safe_json_dump(final_result, result_file)

        logger.info(f"Saved migration result for job {job_id} to {result_file}")

        return str(result_file)

    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        result_file = self._job_result_dir(job_id) / "report.json"

        if not result_file.exists():
            logger.warning(f"Result file not found for job {job_id}")
            return None

        return self._safe_json_load(result_file)

    def update_result(self, job_id: str, result: Dict[str, Any]) -> bool:
        result_file = self._job_result_dir(job_id) / "report.json"

        if not result_file.exists():
            logger.warning(f"Result file not found for job {job_id}, cannot update")
            return False

        try:
            existing_result = self._safe_json_load(result_file) or {}

            existing_result.update(
                {
                    **result,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )

            self._safe_json_dump(existing_result, result_file)

            logger.info(f"Updated result for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update result for job {job_id}: {e}", exc_info=True)
            return False

    def result_exists(self, job_id: str) -> bool:
        result_file = self._job_result_dir(job_id) / "report.json"
        return result_file.exists()

    def delete_result(self, job_id: str) -> bool:
        job_dir = self._job_result_dir(job_id)

        if not job_dir.exists():
            return False

        try:
            shutil.rmtree(job_dir)
            logger.info(f"Deleted result directory for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete result for job {job_id}: {e}", exc_info=True)
            return False

    # ============================================================
    # Migration Result
    # ============================================================

    def save_migration_result(self, migration_id: str, result: Dict[str, Any]) -> str:
        migration_dir = self._migration_result_dir(migration_id)
        migration_dir.mkdir(parents=True, exist_ok=True)

        final_result = {
            "migration_id": migration_id,
            "job_id": result.get("job_id") or migration_id,
            "type": "thoughtspot_powerbi_migration_result",
            "generated_at": datetime.utcnow().isoformat(),
            **result,
        }

        result_file = migration_dir / "migration_report.json"
        self._safe_json_dump(final_result, result_file)

        logger.info(f"Saved migration result for {migration_id} to {result_file}")

        return str(result_file)

    def get_migration_result(self, migration_id: str) -> Optional[Dict[str, Any]]:
        result_file = self._migration_result_dir(migration_id) / "migration_report.json"

        if not result_file.exists():
            logger.warning(f"Migration result file not found for {migration_id}")
            return None

        return self._safe_json_load(result_file)

    def delete_migration_result(self, migration_id: str) -> bool:
        migration_dir = self._migration_result_dir(migration_id)

        if not migration_dir.exists():
            return False

        try:
            shutil.rmtree(migration_dir)
            logger.info(f"Deleted migration result directory for {migration_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to delete migration result for {migration_id}: {e}",
                exc_info=True,
            )
            return False

    # ============================================================
    # Report Save Methods
    # ============================================================

    def save_thoughtspot_objects_report(
        self,
        migration_id: str,
        objects: List[Dict[str, Any]],
    ) -> str:
        file_path = self._migration_result_dir(migration_id) / "thoughtspot_objects.json"

        payload = {
            "migration_id": migration_id,
            "generated_at": datetime.utcnow().isoformat(),
            "object_count": len(objects),
            "objects": objects,
        }

        self._safe_json_dump(payload, file_path)

        return str(file_path)

    def save_formulas_report(
        self,
        migration_id: str,
        formulas: List[Dict[str, Any]],
    ) -> str:
        file_path = self._migration_result_dir(migration_id) / "thoughtspot_formulas.json"

        payload = {
            "migration_id": migration_id,
            "generated_at": datetime.utcnow().isoformat(),
            "formula_count": len(formulas),
            "formulas": formulas,
        }

        self._safe_json_dump(payload, file_path)

        return str(file_path)

    def save_dax_conversions_report(
        self,
        migration_id: str,
        conversions: List[Dict[str, Any]],
    ) -> str:
        file_path = self._migration_result_dir(migration_id) / "dax_conversions.json"

        payload = {
            "migration_id": migration_id,
            "generated_at": datetime.utcnow().isoformat(),
            "conversion_count": len(conversions),
            "conversions": conversions,
        }

        self._safe_json_dump(payload, file_path)

        return str(file_path)

    def save_relationships_report(
        self,
        migration_id: str,
        relationships: List[Dict[str, Any]],
    ) -> str:
        file_path = self._migration_result_dir(migration_id) / "relationships.json"

        payload = {
            "migration_id": migration_id,
            "generated_at": datetime.utcnow().isoformat(),
            "relationship_count": len(relationships),
            "relationships": relationships,
        }

        self._safe_json_dump(payload, file_path)

        return str(file_path)

    def save_powerbi_output_report(
        self,
        migration_id: str,
        powerbi_output: Dict[str, Any],
    ) -> str:
        file_path = self._migration_result_dir(migration_id) / "powerbi_output.json"

        payload = {
            "migration_id": migration_id,
            "generated_at": datetime.utcnow().isoformat(),
            "powerbi_output": powerbi_output,
        }

        self._safe_json_dump(payload, file_path)

        return str(file_path)

    def save_model_bim(
        self,
        migration_id: str,
        model_bim: Dict[str, Any],
    ) -> str:
        migration_dir = self._migration_result_dir(migration_id)
        migration_dir.mkdir(parents=True, exist_ok=True)

        file_path = migration_dir / "model.bim"
        self._safe_json_dump(model_bim, file_path)

        return str(file_path)

    def save_report_json(
        self,
        migration_id: str,
        report_json: Dict[str, Any],
    ) -> str:
        migration_dir = self._migration_result_dir(migration_id)
        migration_dir.mkdir(parents=True, exist_ok=True)

        file_path = migration_dir / "report.json"
        self._safe_json_dump(report_json, file_path)

        return str(file_path)

    def save_complete_migration_package_metadata(
        self,
        migration_id: str,
        metadata: Dict[str, Any],
    ) -> str:
        file_path = self._migration_result_dir(migration_id) / "package_metadata.json"

        payload = {
            "migration_id": migration_id,
            "generated_at": datetime.utcnow().isoformat(),
            "package_type": "thoughtspot_powerbi_migration_package",
            **metadata,
        }

        self._safe_json_dump(payload, file_path)

        return str(file_path)

    def list_migration_result_files(self, migration_id: str) -> List[Dict[str, Any]]:
        migration_dir = self._migration_result_dir(migration_id)

        if not migration_dir.exists():
            return []

        files = []

        for file_path in migration_dir.rglob("*"):
            if file_path.is_file():
                files.append(
                    {
                        "filename": file_path.name,
                        "relative_path": str(file_path.relative_to(migration_dir)),
                        "file_path": str(file_path),
                        "size_bytes": file_path.stat().st_size,
                        "modified_at": datetime.utcfromtimestamp(
                            file_path.stat().st_mtime
                        ).isoformat(),
                    }
                )

        return files

    # ============================================================
    # Improved Export Helpers
    # ============================================================

    def _build_model_bim(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a simple Power BI Tabular model.bim compatible JSON structure.
        """

        tables = result.get("tables") or []
        conversions = result.get("conversions") or []
        relationships = result.get("relationships") or result.get("suggested_relationships") or []

        model_tables = []

        for table in tables:
            table_name = (
                table.get("table_name")
                or table.get("name")
                or table.get("display_name")
                or "UnknownTable"
            )

            raw_columns = table.get("column_details") or table.get("columns") or []

            columns = []

            for column in raw_columns:
                if isinstance(column, dict):
                    column_name = column.get("name") or column.get("display_name") or "Column"
                    data_type = column.get("data_type") or column.get("datatype") or "string"
                else:
                    column_name = str(column)
                    data_type = "string"

                columns.append(
                    {
                        "name": column_name,
                        "dataType": self._powerbi_data_type(data_type),
                        "sourceColumn": column_name,
                    }
                )

            model_tables.append(
                {
                    "name": table_name,
                    "columns": columns,
                    "partitions": [
                        {
                            "name": f"{table_name} Partition",
                            "mode": "import",
                            "source": {
                                "type": "m",
                                "expression": f'let Source = "{table_name}" in Source',
                            },
                        }
                    ],
                }
            )

        measure_table = {
            "name": "ThoughtSpot Measures",
            "columns": [
                {
                    "name": "Measure Group",
                    "dataType": "string",
                    "sourceColumn": "Measure Group",
                }
            ],
            "measures": [],
            "partitions": [
                {
                    "name": "ThoughtSpot Measures Partition",
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": 'let Source = #table({"Measure Group"}, {{"ThoughtSpot"}}) in Source',
                    },
                }
            ],
        }

        for conversion in conversions:
            measure_name = (
                conversion.get("source_calculated_field")
                or conversion.get("source_name")
                or conversion.get("name")
                or "Converted Measure"
            )

            dax_formula = (
                conversion.get("dax_formula")
                or conversion.get("converted_dax_formula")
                or conversion.get("target_formula")
                or "BLANK()"
            )

            measure_table["measures"].append(
                {
                    "name": measure_name,
                    "expression": dax_formula,
                    "formatString": "General",
                    "description": f"Converted from ThoughtSpot formula: {conversion.get('source_formula', '')}",
                }
            )

        model_tables.append(measure_table)

        model_relationships = []

        for index, relationship in enumerate(relationships):
            source_table = relationship.get("source_table") or relationship.get("from_table")
            target_table = relationship.get("target_table") or relationship.get("to_table")
            source_column = relationship.get("source_column") or relationship.get("from_column")
            target_column = relationship.get("target_column") or relationship.get("to_column")

            if not all([source_table, target_table, source_column, target_column]):
                continue

            model_relationships.append(
                {
                    "name": relationship.get("relationship_id") or f"Relationship_{index + 1}",
                    "fromTable": source_table,
                    "fromColumn": source_column,
                    "toTable": target_table,
                    "toColumn": target_column,
                    "crossFilteringBehavior": "oneDirection",
                    "isActive": True,
                }
            )

        return {
            "name": "ThoughtSpot Power BI Migration Model",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "tables": model_tables,
                "relationships": model_relationships,
            },
        }

    @staticmethod
    def _powerbi_data_type(data_type: str) -> str:
        text = str(data_type or "").lower()

        if text in ["integer", "int", "bigint", "smallint"]:
            return "int64"

        if text in ["double", "float", "decimal", "numeric", "number", "currency"]:
            return "double"

        if text in ["date", "datetime", "timestamp"]:
            return "dateTime"

        if text in ["bool", "boolean"]:
            return "boolean"

        return "string"

    def _write_migration_report_csv(self, file_path: Path, result: Dict[str, Any]) -> None:
        """
        Create CSV report for presentation and validation.
        """

        file_path.parent.mkdir(parents=True, exist_ok=True)

        conversions = result.get("conversions") or []

        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(
                [
                    "Source Calculated Field",
                    "Source Formula",
                    "Converted DAX Formula",
                    "Conversion Method",
                    "Status",
                    "Confidence Score",
                    "Warnings",
                ]
            )

            for conversion in conversions:
                writer.writerow(
                    [
                        conversion.get("source_calculated_field")
                        or conversion.get("source_name")
                        or "",
                        conversion.get("source_formula") or "",
                        conversion.get("dax_formula")
                        or conversion.get("converted_dax_formula")
                        or "",
                        conversion.get("conversion_method") or "",
                        conversion.get("status") or "",
                        conversion.get("confidence_score") or "",
                        "; ".join(conversion.get("warnings") or []),
                    ]
                )

    def _build_readme(self, result: Dict[str, Any]) -> str:
        summary = result.get("summary") or {}

        return f"""ThoughtSpot to Power BI Migration Package
Generated At: {datetime.utcnow().isoformat()}

============================================================
Migration Summary
============================================================

Source: ThoughtSpot
Target: Power BI

Dashboards: {summary.get("total_dashboards") or summary.get("object_count") or 0}
Worksheets: {summary.get("total_worksheets") or 0}
Tables: {summary.get("total_tables") or 0}
Calculated Fields: {summary.get("total_calculated_fields") or summary.get("formula_count") or 0}
Relationships: {summary.get("relationship_count") or 0}
DAX Conversions: {summary.get("conversion_count") or 0}
Validated Conversions: {summary.get("validated_conversion_count") or 0}
Manual Review Required: {summary.get("manual_review_count") or 0}

============================================================
Files Included
============================================================

1. migration_summary.json
   Complete migration summary.

2. migration_report.csv
   Human-readable DAX conversion report.

3. source_metadata/files.json
   Uploaded source file details.

4. source_metadata/workbooks.json
   Extracted ThoughtSpot workbook/liveboard metadata.

5. source_metadata/tables.json
   Extracted table and column metadata.

6. source_metadata/calculated_fields.json
   Extracted ThoughtSpot calculated fields.

7. powerbi/dax_conversions.json
   Converted DAX formulas.

8. powerbi/model.bim
   Power BI semantic model starter file.

9. relationships.json
   Detected or suggested table relationships.

10. README.txt
   This instruction file.

============================================================
How to Use model.bim
============================================================

1. Open Power BI Desktop.
2. Open your target Power BI report.
3. Open Tabular Editor from External Tools.
4. Open the generated model.bim file.
5. Review tables, measures, relationships, and DAX expressions.
6. Save changes back to Power BI.

============================================================
Important Note
============================================================

This package is generated for migration assistance.
Please review complex formulas, relationships, and semantic model changes
before using them in production.
"""

    # ============================================================
    # Complete Package Builder
    # ============================================================

    def create_complete_migration_package(self, job_id: str) -> Optional[str]:
        """
        Create complete downloadable ZIP package for a completed migration job.

        Returns:
            ZIP file path or None.
        """

        result = self.get_result(job_id)

        if not result:
            logger.error(f"Cannot create package. Result not found for job {job_id}")
            return None

        export_dir = self._get_export_dir(job_id)

        if export_dir.exists():
            shutil.rmtree(export_dir)

        export_dir.mkdir(parents=True, exist_ok=True)

        source_metadata_dir = export_dir / "source_metadata"
        powerbi_dir = export_dir / "powerbi"

        source_metadata_dir.mkdir(parents=True, exist_ok=True)
        powerbi_dir.mkdir(parents=True, exist_ok=True)

        summary = result.get("summary") or {}
        files = result.get("files") or []
        workbooks = result.get("workbooks") or result.get("objects") or []
        tables = result.get("tables") or []
        calculated_fields = result.get("calculations") or result.get("formulas") or []
        conversions = result.get("conversions") or []
        relationships = result.get("relationships") or result.get("suggested_relationships") or []

        # Main JSON files
        self._safe_json_dump(summary, export_dir / "migration_summary.json")
        self._safe_json_dump(files, source_metadata_dir / "files.json")
        self._safe_json_dump(workbooks, source_metadata_dir / "workbooks.json")
        self._safe_json_dump(tables, source_metadata_dir / "tables.json")
        self._safe_json_dump(calculated_fields, source_metadata_dir / "calculated_fields.json")
        self._safe_json_dump(conversions, powerbi_dir / "dax_conversions.json")
        self._safe_json_dump(relationships, export_dir / "relationships.json")

        # Power BI model.bim
        model_bim = self._build_model_bim(result)
        self._safe_json_dump(model_bim, powerbi_dir / "model.bim")

        # CSV report
        self._write_migration_report_csv(export_dir / "migration_report.csv", result)

        # README
        self._safe_write_text(export_dir / "README.txt", self._build_readme(result))

        # Package metadata
        package_metadata = {
            "job_id": job_id,
            "migration_id": result.get("migration_id") or job_id,
            "generated_at": datetime.utcnow().isoformat(),
            "package_type": "thoughtspot_powerbi_migration_package",
            "file_count": 10,
            "summary": summary,
        }

        self._safe_json_dump(package_metadata, export_dir / "package_metadata.json")

        zip_path = self._job_result_dir(job_id) / "thoughtspot_powerbi_migration_package.zip"

        if zip_path.exists():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in export_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(export_dir)
                    zip_file.write(file_path, arcname)

        logger.info(f"Created complete migration package for job {job_id}: {zip_path}")

        return str(zip_path)

    def get_or_create_complete_package(self, job_id: str) -> Optional[str]:
        """
        Return existing package if available, otherwise create it.
        """

        zip_path = self._job_result_dir(job_id) / "thoughtspot_powerbi_migration_package.zip"

        if zip_path.exists():
            return str(zip_path)

        return self.create_complete_migration_package(job_id)


# Global result store instance
result_store = ResultStore()