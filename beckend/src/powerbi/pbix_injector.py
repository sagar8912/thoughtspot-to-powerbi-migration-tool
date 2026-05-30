"""PBIX Injector - Programmatically modify Power BI models using Tabular Editor"""
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class Measure:
    """Power BI Measure definition"""
    name: str
    expression: str  # DAX formula
    display_folder: Optional[str] = None
    format_string: Optional[str] = None
    description: Optional[str] = None


@dataclass
class Relationship:
    """Power BI Relationship definition"""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str  # "OneToMany", "ManyToOne", "OneToOne", "ManyToMany"
    cross_filter_direction: str  # "SingleDirection", "BothDirections"
    is_active: bool = True


@dataclass
class CalculatedColumn:
    """Power BI Calculated Column definition"""
    table_name: str
    column_name: str
    expression: str  # DAX formula
    data_type: str = "String"  # String, Int64, Double, DateTime, Boolean
    format_string: Optional[str] = None
    description: Optional[str] = None


class PBIXInjector:
    """
    Programmatically modify Power BI models using Tabular Editor CLI

    Supports:
    1. Adding/updating DAX measures
    2. Creating relationships
    3. Adding calculated columns
    4. Modifying model properties

    Technologies used:
    - Tabular Editor 2 CLI (free, open-source)
    - TMSL (Tabular Model Scripting Language) via C# scripts
    """

    def __init__(self, tabular_editor_path: Optional[str] = None):
        """
        Initialize PBIX Injector

        Args:
            tabular_editor_path: Path to TabularEditor.exe
                                 If None, searches in standard locations
        """
        self.tabular_editor_path = self._find_tabular_editor(tabular_editor_path)

        if not self.tabular_editor_path:
            logger.warning("Tabular Editor not found - PBIX injection will not work")
            logger.info("Download from: https://github.com/TabularEditor/TabularEditor/releases")
        else:
            logger.info(f"Using Tabular Editor: {self.tabular_editor_path}")

    def _find_tabular_editor(self, custom_path: Optional[str]) -> Optional[Path]:
        """Find Tabular Editor installation"""
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                return path

        # Common installation paths
        search_paths = [
            Path(r"C:\Program Files (x86)\Tabular Editor\TabularEditor.exe"),
            Path(r"C:\Program Files\Tabular Editor\TabularEditor.exe"),
            Path.home() / "AppData/Local/TabularEditor/TabularEditor.exe",
            Path("./tools/TabularEditor/TabularEditor.exe"),  # Local tools folder
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None

    # ============================================
    # Main Injection Method
    # ============================================

    def create_pbix_from_scratch(
        self,
        output_path: str,
        measures: List[Measure],
        relationships: Optional[List[Relationship]] = None,
        calculated_columns: Optional[List[CalculatedColumn]] = None
    ) -> Path:
        """
        Create a new PBIX file from scratch using Tabular Editor

        This bypasses the template PBIX issue by creating the model directly

        Args:
            output_path: Path for output PBIX file
            measures: List of DAX measures to add
            relationships: List of relationships to create
            calculated_columns: List of calculated columns to add

        Returns:
            Path to created PBIX file
        """
        if not self.tabular_editor_path:
            raise RuntimeError("Tabular Editor not found - cannot create PBIX")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating PBIX from scratch: {output_path.name}")

        # Generate C# script to build model from scratch
        script_content = self._generate_create_from_scratch_script(
            measures=measures or [],
            relationships=relationships or [],
            calculated_columns=calculated_columns or []
        )

        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csx', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            script_path = Path(f.name)

        try:
            # Create a new blank database and save as PBIX
            # Tabular Editor can create a new database with -D flag
            result = subprocess.run(
                [
                    str(self.tabular_editor_path),
                    "-D",  # Create new database
                    "-S", str(script_path),  # Run script
                    "-O", str(output_path)  # Output PBIX
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"Tabular Editor failed:")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                raise RuntimeError(f"Tabular Editor execution failed: {result.stdout}")

            logger.info(f"✅ Successfully created PBIX: {output_path}")

            return output_path

        finally:
            # Clean up temp script
            if script_path.exists():
                script_path.unlink()

    def _generate_create_from_scratch_script(
        self,
        measures: List[Measure],
        relationships: List[Relationship],
        calculated_columns: List[CalculatedColumn]
    ) -> str:
        """Generate C# script to create a model from scratch"""
        lines = []

        lines.append("// Auto-generated script to create Power BI model from scratch")
        lines.append("using System;")
        lines.append("using System.Linq;")
        lines.append("using TabularEditor.TOMWrapper;")
        lines.append("")

        # Create base model structure
        lines.append("// Create Measures table")
        lines.append("var measuresTable = Model.AddTable(\"Measures\");")
        lines.append("measuresTable.IsHidden = true;")
        lines.append("var placeholderCol = measuresTable.AddDataColumn(\"_Placeholder\");")
        lines.append("placeholderCol.DataType = DataType.String;")
        lines.append("placeholderCol.IsHidden = true;")
        lines.append("placeholderCol.SourceColumn = \"_Placeholder\";")
        lines.append("")

        # Set partition for Measures table
        lines.append("var partition = measuresTable.AddMPartition(\"Partition\");")
        lines.append("partition.Expression = \"#table({\\\"_Placeholder\\\"}, {{\\\"\\\"}})\";")
        lines.append("")

        # Add measures
        if measures:
            lines.append("// ============================================")
            lines.append("// Add DAX Measures")
            lines.append("// ============================================")
            lines.append("")

            for measure in measures:
                lines.extend(self._generate_measure_code_for_new_model(measure))
                lines.append("")

        lines.append("// Set compatibility level")
        lines.append("Model.Database.CompatibilityLevel = 1500;")

        return "\n".join(lines)

    def _generate_measure_code_for_new_model(self, measure: Measure) -> List[str]:
        """Generate C# code to create a measure in a new model"""
        lines = []

        # Escape quotes in DAX formula
        safe_expression = measure.expression.replace('"', '""')
        safe_name = measure.name.replace('"', '""')

        lines.append(f"// Add measure: {measure.name}")
        lines.append(f'var measure_{hash(measure.name) % 10000} = measuresTable.AddMeasure("{safe_name}");')
        lines.append(f'measure_{hash(measure.name) % 10000}.Expression = @"{safe_expression}";')

        if measure.display_folder:
            safe_folder = measure.display_folder.replace('"', '""')
            lines.append(f'measure_{hash(measure.name) % 10000}.DisplayFolder = "{safe_folder}";')

        if measure.format_string:
            safe_format = measure.format_string.replace('"', '""')
            lines.append(f'measure_{hash(measure.name) % 10000}.FormatString = "{safe_format}";')

        if measure.description:
            safe_desc = measure.description.replace('"', '""')
            lines.append(f'measure_{hash(measure.name) % 10000}.Description = "{safe_desc}";')

        return lines

    def inject_into_pbix(
        self,
        pbix_path: str,
        measures: Optional[List[Measure]] = None,
        relationships: Optional[List[Relationship]] = None,
        calculated_columns: Optional[List[CalculatedColumn]] = None,
        output_path: Optional[str] = None
    ) -> Path:
        """
        Inject measures, relationships, and columns into a PBIX file

        Args:
            pbix_path: Path to source PBIX file
            measures: List of measures to add
            relationships: List of relationships to create
            calculated_columns: List of calculated columns to add
            output_path: Path for output PBIX (if None, overwrites input)

        Returns:
            Path to modified PBIX file
        """
        if not self.tabular_editor_path:
            raise RuntimeError("Tabular Editor not found - cannot inject into PBIX")

        pbix_path = Path(pbix_path)

        if not pbix_path.exists():
            raise FileNotFoundError(f"PBIX file not found: {pbix_path}")

        output_path = Path(output_path) if output_path else pbix_path

        logger.info(f"Injecting into PBIX: {pbix_path.name}")

        # Generate C# script for Tabular Editor
        script_content = self._generate_csharp_script(
            measures=measures or [],
            relationships=relationships or [],
            calculated_columns=calculated_columns or []
        )

        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csx', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            script_path = Path(f.name)

        try:
            # Execute Tabular Editor with script
            self._execute_tabular_editor(
                pbix_path=pbix_path,
                script_path=script_path,
                output_path=output_path
            )

            logger.info(f"✅ Successfully injected into PBIX: {output_path}")

            return output_path

        finally:
            # Clean up temp script
            if script_path.exists():
                script_path.unlink()

    # ============================================
    # C# Script Generation
    # ============================================

    def _generate_csharp_script(
        self,
        measures: List[Measure],
        relationships: List[Relationship],
        calculated_columns: List[CalculatedColumn]
    ) -> str:
        """
        Generate C# script for Tabular Editor

        Tabular Editor uses C# scripting to modify the TOM (Tabular Object Model)
        """
        lines = []

        lines.append("// Auto-generated script for Power BI migration")
        lines.append("using System;")
        lines.append("using System.Linq;")
        lines.append("using TabularEditor.TOMWrapper;")
        lines.append("")

        # Add measures
        if measures:
            lines.append("// ============================================")
            lines.append("// Add DAX Measures")
            lines.append("// ============================================")
            lines.append("")

            for measure in measures:
                lines.extend(self._generate_measure_code(measure))
                lines.append("")

        # Add calculated columns
        if calculated_columns:
            lines.append("// ============================================")
            lines.append("// Add Calculated Columns")
            lines.append("// ============================================")
            lines.append("")

            for column in calculated_columns:
                lines.extend(self._generate_column_code(column))
                lines.append("")

        # Add relationships
        if relationships:
            lines.append("// ============================================")
            lines.append("// Add Relationships")
            lines.append("// ============================================")
            lines.append("")

            for rel in relationships:
                lines.extend(self._generate_relationship_code(rel))
                lines.append("")

        lines.append("// Save changes")
        lines.append("Model.Database.Compatibility.Level = 1500;  // SQL Server 2019 / Power BI")

        return "\n".join(lines)

    def _generate_measure_code(self, measure: Measure) -> List[str]:
        """Generate C# code to create a measure"""
        lines = []

        # Escape quotes in DAX formula
        safe_expression = measure.expression.replace('"', '""')
        safe_name = measure.name.replace('"', '""')

        # Get or create the table (assume first table or "Measures" table)
        lines.append("// Add measure: " + measure.name)
        lines.append("var measureTable = Model.Tables.FirstOrDefault(t => t.Name == \"Measures\") ?? Model.Tables.First();")

        # Check if measure already exists
        lines.append(f'var existingMeasure = measureTable.Measures.FirstOrDefault(m => m.Name == "{safe_name}");')
        lines.append("if (existingMeasure != null) {")
        lines.append("    existingMeasure.Delete();")
        lines.append("}")

        # Create measure
        lines.append(f'var measure = measureTable.AddMeasure("{safe_name}");')
        lines.append(f'measure.Expression = @"{safe_expression}";')

        if measure.display_folder:
            safe_folder = measure.display_folder.replace('"', '""')
            lines.append(f'measure.DisplayFolder = "{safe_folder}";')

        if measure.format_string:
            safe_format = measure.format_string.replace('"', '""')
            lines.append(f'measure.FormatString = "{safe_format}";')

        if measure.description:
            safe_desc = measure.description.replace('"', '""')
            lines.append(f'measure.Description = "{safe_desc}";')

        return lines

    def _generate_column_code(self, column: CalculatedColumn) -> List[str]:
        """Generate C# code to create a calculated column"""
        lines = []

        safe_expression = column.expression.replace('"', '""')
        safe_name = column.column_name.replace('"', '""')
        safe_table = column.table_name.replace('"', '""')

        lines.append(f"// Add calculated column: {column.table_name}[{column.column_name}]")
        lines.append(f'var table = Model.Tables["{safe_table}"];')

        # Check if column exists
        lines.append(f'var existingColumn = table.Columns.FirstOrDefault(c => c.Name == "{safe_name}");')
        lines.append("if (existingColumn != null && existingColumn is CalculatedColumn) {")
        lines.append("    existingColumn.Delete();")
        lines.append("}")

        # Create calculated column
        lines.append(f'var column = table.AddCalculatedColumn("{safe_name}");')
        lines.append(f'column.Expression = @"{safe_expression}";')
        lines.append(f'column.DataType = DataType.{column.data_type};')

        if column.format_string:
            safe_format = column.format_string.replace('"', '""')
            lines.append(f'column.FormatString = "{safe_format}";')

        if column.description:
            safe_desc = column.description.replace('"', '""')
            lines.append(f'column.Description = "{safe_desc}";')

        return lines

    def _generate_relationship_code(self, rel: Relationship) -> List[str]:
        """Generate C# code to create a relationship"""
        lines = []

        safe_from_table = rel.from_table.replace('"', '""')
        safe_from_col = rel.from_column.replace('"', '""')
        safe_to_table = rel.to_table.replace('"', '""')
        safe_to_col = rel.to_column.replace('"', '""')

        lines.append(f"// Add relationship: {rel.from_table}[{rel.from_column}] -> {rel.to_table}[{rel.to_column}]")
        lines.append(f'var fromTable = Model.Tables["{safe_from_table}"];')
        lines.append(f'var toTable = Model.Tables["{safe_to_table}"];')
        lines.append(f'var fromColumn = fromTable.Columns["{safe_from_col}"];')
        lines.append(f'var toColumn = toTable.Columns["{safe_to_col}"];')

        # Check if relationship exists
        lines.append("var existingRel = Model.Relationships.FirstOrDefault(r => ")
        lines.append(f'    r.FromTable.Name == "{safe_from_table}" && ')
        lines.append(f'    r.FromColumn.Name == "{safe_from_col}" && ')
        lines.append(f'    r.ToTable.Name == "{safe_to_table}" && ')
        lines.append(f'    r.ToColumn.Name == "{safe_to_col}"')
        lines.append(");")
        lines.append("if (existingRel != null) {")
        lines.append("    existingRel.Delete();")
        lines.append("}")

        # Create relationship
        lines.append("var relationship = Model.AddRelationship();")
        lines.append("relationship.FromColumn = fromColumn;")
        lines.append("relationship.ToColumn = toColumn;")
        lines.append(f"relationship.FromCardinality = RelationshipEndCardinality.{self._get_from_cardinality(rel.cardinality)};")
        lines.append(f"relationship.ToCardinality = RelationshipEndCardinality.{self._get_to_cardinality(rel.cardinality)};")
        lines.append(f"relationship.CrossFilteringBehavior = CrossFilteringBehavior.{rel.cross_filter_direction};")
        lines.append(f"relationship.IsActive = {str(rel.is_active).lower()};")

        return lines

    def _get_from_cardinality(self, cardinality: str) -> str:
        """Convert cardinality to FROM side enum"""
        mapping = {
            "OneToMany": "One",
            "ManyToOne": "Many",
            "OneToOne": "One",
            "ManyToMany": "Many"
        }
        return mapping.get(cardinality, "Many")

    def _get_to_cardinality(self, cardinality: str) -> str:
        """Convert cardinality to TO side enum"""
        mapping = {
            "OneToMany": "Many",
            "ManyToOne": "One",
            "OneToOne": "One",
            "ManyToMany": "Many"
        }
        return mapping.get(cardinality, "Many")

    # ============================================
    # Tabular Editor Execution
    # ============================================

    def _execute_tabular_editor(
        self,
        pbix_path: Path,
        script_path: Path,
        output_path: Path
    ):
        """
        Execute Tabular Editor CLI

        Command format:
        TabularEditor.exe "model.pbix" -S "script.csx" -O "output.pbix"
        """
        cmd = [
            str(self.tabular_editor_path),
            str(pbix_path),
            "-S", str(script_path),
            "-O", str(output_path)
        ]

        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"Tabular Editor failed:")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                raise RuntimeError(f"Tabular Editor execution failed: {result.stderr}")

            logger.debug(f"Tabular Editor output: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise RuntimeError("Tabular Editor execution timed out (>2 minutes)")
        except FileNotFoundError:
            raise RuntimeError(f"Tabular Editor not found at: {self.tabular_editor_path}")

    # ============================================
    # Convenience Methods
    # ============================================

    def add_measures_from_conversions(
        self,
        pbix_path: str,
        conversions: List[Dict[str, Any]],
        output_path: Optional[str] = None
    ) -> Path:
        """
        Add measures from DAX conversions

        Args:
            pbix_path: Source PBIX file
            conversions: List of conversion dictionaries with 'calc_name' and 'dax_formula'
            output_path: Output PBIX path

        Returns:
            Path to modified PBIX
        """
        measures = []

        for conv in conversions:
            measure = Measure(
                name=conv.get("calc_name", "Measure"),
                expression=conv.get("dax_formula", "0"),
                display_folder="Migrated from Tableau",
                description=f"Original Tableau formula: {conv.get('tableau_formula', 'N/A')}"
            )
            measures.append(measure)

        return self.inject_into_pbix(
            pbix_path=pbix_path,
            measures=measures,
            output_path=output_path
        )

    def create_date_table(
        self,
        pbix_path: str,
        start_year: int = 2020,
        end_year: int = 2030,
        output_path: Optional[str] = None
    ) -> Path:
        """
        Add a standard date table to the model

        Uses CALENDAR() and ADDCOLUMNS() DAX pattern
        """
        # DAX for date table
        date_table_dax = f"""
        ADDCOLUMNS(
            CALENDAR(DATE({start_year}, 1, 1), DATE({end_year}, 12, 31)),
            "Year", YEAR([Date]),
            "Month", FORMAT([Date], "MMMM"),
            "MonthNumber", MONTH([Date]),
            "Quarter", "Q" & FORMAT([Date], "Q"),
            "Day", DAY([Date]),
            "DayOfWeek", FORMAT([Date], "dddd"),
            "YearMonth", FORMAT([Date], "YYYY-MM"),
            "IsWeekend", WEEKDAY([Date], 2) >= 6
        )
        """

        # Create via C# script (would need to add table creation support)
        # For now, return as-is with warning
        logger.warning("Date table creation requires manual setup in template PBIX")

        return Path(pbix_path)


# ============================================
# Utility Functions
# ============================================

def download_tabular_editor(target_dir: str = "./tools/TabularEditor") -> Path:
    """
    Download Tabular Editor 2 portable edition

    Returns:
        Path to TabularEditor.exe
    """
    import urllib.request
    import zipfile

    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    # Tabular Editor 2 portable download URL
    download_url = "https://github.com/TabularEditor/TabularEditor/releases/latest/download/TabularEditor.Portable.zip"

    zip_path = target_path / "TabularEditor.zip"

    logger.info(f"Downloading Tabular Editor from {download_url}...")

    urllib.request.urlretrieve(download_url, zip_path)

    logger.info(f"Extracting to {target_path}...")

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(target_path)

    zip_path.unlink()  # Remove zip file

    exe_path = target_path / "TabularEditor.exe"

    if exe_path.exists():
        logger.info(f"✅ Tabular Editor installed: {exe_path}")
        return exe_path
    else:
        raise RuntimeError("Failed to extract TabularEditor.exe")
