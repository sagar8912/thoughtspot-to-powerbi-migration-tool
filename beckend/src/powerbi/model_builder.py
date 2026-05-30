"""Power BI Data Model Builder - Convert Tableau data models to Power BI"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from src.powerbi.pbix_injector import Relationship, CalculatedColumn


class Cardinality(Enum):
    """Relationship cardinality"""
    ONE_TO_MANY = "OneToMany"
    MANY_TO_ONE = "ManyToOne"
    ONE_TO_ONE = "OneToOne"
    MANY_TO_MANY = "ManyToMany"


class FilterDirection(Enum):
    """Cross-filter direction"""
    SINGLE = "SingleDirection"
    BOTH = "BothDirections"


@dataclass
class TableSchema:
    """Power BI table schema"""
    name: str
    columns: List[Dict[str, str]]  # [{"name": "ProductID", "type": "Int64"}, ...]
    is_date_table: bool = False


@dataclass
class DateTableConfig:
    """Date table configuration"""
    table_name: str = "Calendar"
    start_year: int = 2020
    end_year: int = 2030
    include_fiscal_calendar: bool = False
    fiscal_year_start_month: int = 1


class PowerBIModelBuilder:
    """
    Build Power BI data models from Tableau metadata

    Handles:
    1. Relationship detection and creation
    2. Cardinality inference
    3. Date table generation
    4. Filter direction optimization
    """

    def __init__(self):
        pass

    # ============================================
    # Relationship Building
    # ============================================

    def build_relationships_from_tableau(
        self,
        data_sources: List[Dict[str, Any]],
        hyper_profiles: Optional[Dict[str, Any]] = None
    ) -> List[Relationship]:
        """
        Convert Tableau data source relationships to Power BI relationships

        Args:
            data_sources: List of Tableau data sources with join info
            hyper_profiles: Optional data profiles for cardinality inference

        Returns:
            List of Power BI relationships
        """
        logger.info(f"Building relationships from {len(data_sources)} Tableau data sources")

        relationships = []

        for ds in data_sources:
            # Parse Tableau relationships
            for rel_info in ds.get("relationships", []):
                try:
                    # Extract join information from Tableau metadata
                    tableau_rel = self._parse_tableau_relationship(rel_info)

                    if tableau_rel:
                        # Infer cardinality
                        cardinality = self._infer_cardinality(
                            from_table=tableau_rel["from_table"],
                            from_column=tableau_rel["from_column"],
                            to_table=tableau_rel["to_table"],
                            to_column=tableau_rel["to_column"],
                            hyper_profiles=hyper_profiles
                        )

                        # Determine filter direction
                        filter_direction = self._determine_filter_direction(
                            cardinality=cardinality,
                            join_type=tableau_rel.get("join_type", "inner")
                        )

                        relationship = Relationship(
                            from_table=tableau_rel["from_table"],
                            from_column=tableau_rel["from_column"],
                            to_table=tableau_rel["to_table"],
                            to_column=tableau_rel["to_column"],
                            cardinality=cardinality.value,
                            cross_filter_direction=filter_direction.value,
                            is_active=True
                        )

                        relationships.append(relationship)

                        logger.info(
                            f"  Created relationship: {relationship.from_table}[{relationship.from_column}] "
                            f"-> {relationship.to_table}[{relationship.to_column}] ({cardinality.value})"
                        )

                except Exception as e:
                    logger.warning(f"Failed to parse relationship: {e}")

        logger.info(f"Built {len(relationships)} relationships")

        return relationships

    def _parse_tableau_relationship(self, rel_info: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Parse Tableau relationship metadata

        Tableau join expression format:
        "[Orders].[CustomerID] = [Customers].[CustomerID]"
        """
        expression = rel_info.get("expression", "")
        join_type = rel_info.get("type", "inner")

        if not expression:
            return None

        # Parse join expression
        # Example: "[Orders].[CustomerID] = [Customers].[CustomerID]"
        parts = expression.split("=")

        if len(parts) != 2:
            logger.warning(f"Cannot parse join expression: {expression}")
            return None

        left_side = parts[0].strip()
        right_side = parts[1].strip()

        # Extract table.column from "[Table].[Column]"
        from_table, from_column = self._extract_table_column(left_side)
        to_table, to_column = self._extract_table_column(right_side)

        if not all([from_table, from_column, to_table, to_column]):
            logger.warning(f"Incomplete relationship info: {expression}")
            return None

        # Gap 5: normalize table names — strip UUID suffixes, schema prefixes, ! separators
        from src.tableau.hyper_profiler import HyperDataProfiler
        from_table = HyperDataProfiler.normalize_hyper_table_name(from_table)
        to_table = HyperDataProfiler.normalize_hyper_table_name(to_table)

        return {
            "from_table": from_table,
            "from_column": from_column,
            "to_table": to_table,
            "to_column": to_column,
            "join_type": join_type
        }

    def _extract_table_column(self, expression: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract table and column from "[Table].[Column]" format

        Returns:
            (table_name, column_name) or (None, None) if parse fails
        """
        import re

        # Pattern: [Table].[Column]
        pattern = r'\[([^\]]+)\]\.\[([^\]]+)\]'
        match = re.search(pattern, expression)

        if match:
            return match.group(1), match.group(2)

        return None, None

    def _infer_cardinality(
        self,
        from_table: str,
        from_column: str,
        to_table: str,
        to_column: str,
        hyper_profiles: Optional[Dict[str, Any]] = None
    ) -> Cardinality:
        """
        Infer relationship cardinality

        Logic:
        1. Check for primary key indicators (ID columns, unique constraints)
        2. Use data profiling (distinct count ratio)
        3. Default to Many-to-One (fact to dimension)

        Args:
            from_table: Source table name
            from_column: Source column name
            to_table: Target table name
            to_column: Target column name
            hyper_profiles: Optional data profiles with distinct counts

        Returns:
            Inferred cardinality
        """
        # Strategy 1: Check column naming conventions
        if self._is_primary_key_column(to_column):
            # Joining to a PK → Many-to-One
            return Cardinality.MANY_TO_ONE

        if self._is_primary_key_column(from_column):
            # Joining from a PK → One-to-Many
            return Cardinality.ONE_TO_MANY

        # Strategy 2: Use data profiling (if available)
        if hyper_profiles:
            cardinality = self._infer_from_data_profile(
                from_table, from_column, to_table, to_column, hyper_profiles
            )
            if cardinality:
                return cardinality

        # Strategy 3: Default heuristics
        # Fact tables typically join to dimension tables (many-to-one)
        if self._is_likely_fact_table(from_table) and self._is_likely_dimension_table(to_table):
            return Cardinality.MANY_TO_ONE

        # Default: Many-to-One (most common in star schema)
        logger.debug(f"Using default Many-to-One cardinality for {from_table} -> {to_table}")
        return Cardinality.MANY_TO_ONE

    def _is_primary_key_column(self, column_name: str) -> bool:
        """Check if column name indicates a primary key"""
        pk_indicators = ["id", "key", "code", "pk"]
        column_lower = column_name.lower()

        # Exact matches
        if column_lower in pk_indicators:
            return True

        # Suffix matches (e.g., "CustomerID", "ProductKey")
        for indicator in pk_indicators:
            if column_lower.endswith(indicator):
                return True

        return False

    def _is_likely_fact_table(self, table_name: str) -> bool:
        """Check if table name suggests a fact table"""
        fact_indicators = ["fact", "sales", "orders", "transactions", "events", "f_"]
        table_lower = table_name.lower()

        for indicator in fact_indicators:
            if indicator in table_lower:
                return True

        return False

    def _is_likely_dimension_table(self, table_name: str) -> bool:
        """Check if table name suggests a dimension table"""
        dim_indicators = ["dim", "dimension", "customer", "product", "date", "time", "category", "d_"]
        table_lower = table_name.lower()

        for indicator in dim_indicators:
            if indicator in table_lower:
                return True

        return False

    def _infer_from_data_profile(
        self,
        from_table: str,
        from_column: str,
        to_table: str,
        to_column: str,
        hyper_profiles: Dict[str, Any]
    ) -> Optional[Cardinality]:
        """
        Infer cardinality from data profiling

        Uses distinct count ratio to determine uniqueness
        """
        # TODO: Implement when data profiling includes distinct counts per column
        return None

    def _determine_filter_direction(
        self,
        cardinality: Cardinality,
        join_type: str
    ) -> FilterDirection:
        """
        Determine optimal cross-filter direction

        Rules:
        1. One-to-Many: Single direction (from "one" side)
        2. Many-to-Many: Both directions (usually)
        3. One-to-One: Single direction (arbitrary)
        """
        if cardinality == Cardinality.MANY_TO_MANY:
            # Many-to-Many typically needs bidirectional filtering
            return FilterDirection.BOTH

        # Default: Single direction (filters flow from "one" to "many")
        return FilterDirection.SINGLE

    # ============================================
    # Date Table Generation
    # ============================================

    def generate_date_table_dax(
        self,
        config: Optional[DateTableConfig] = None
    ) -> CalculatedColumn:
        """
        Generate DAX for a date table

        Creates a comprehensive date dimension with:
        - Date, Year, Quarter, Month, Week, Day
        - Fiscal calendar (optional)
        - Weekday/weekend flags
        - Prior period calculations
        """
        if config is None:
            config = DateTableConfig()

        # Base calendar table
        dax_formula = f"""
ADDCOLUMNS(
    CALENDAR(DATE({config.start_year}, 1, 1), DATE({config.end_year}, 12, 31)),
    "Year", YEAR([Date]),
    "YearMonth", FORMAT([Date], "YYYY-MM"),
    "Quarter", "Q" & FORMAT([Date], "Q"),
    "QuarterNumber", QUARTER([Date]),
    "Month", FORMAT([Date], "MMMM"),
    "MonthNumber", MONTH([Date]),
    "MonthShort", FORMAT([Date], "MMM"),
    "Week", WEEKNUM([Date]),
    "DayOfWeek", FORMAT([Date], "dddd"),
    "DayOfWeekNumber", WEEKDAY([Date], 2),
    "Day", DAY([Date]),
    "IsWeekend", WEEKDAY([Date], 2) >= 6,
    "IsWorkday", WEEKDAY([Date], 2) < 6
"""

        # Add fiscal calendar if requested
        if config.include_fiscal_calendar:
            fiscal_start = config.fiscal_year_start_month

            dax_formula += f""",
    "FiscalYear", IF(MONTH([Date]) >= {fiscal_start}, YEAR([Date]) + 1, YEAR([Date])),
    "FiscalQuarter", "FQ" & ROUNDUP((MONTH([Date]) - {fiscal_start} + 13) / 3, 0),
    "FiscalMonth", MOD(MONTH([Date]) - {fiscal_start} + 12, 12) + 1
"""

        dax_formula += "\n)"

        # Note: This returns a table expression, not a calculated column
        # In practice, this would be used with AddTable() in Tabular Editor

        logger.info(f"Generated date table DAX ({config.start_year}-{config.end_year})")

        return CalculatedColumn(
            table_name=config.table_name,
            column_name="Date",
            expression=dax_formula,
            description="Auto-generated date table for time intelligence"
        )

    def create_date_relationships(
        self,
        date_table_name: str,
        fact_tables: List[str],
        date_column_name: str = "Date"
    ) -> List[Relationship]:
        """
        Create relationships from date table to fact tables

        Args:
            date_table_name: Name of the date dimension table
            fact_tables: List of fact table names that have date columns
            date_column_name: Name of the date column in fact tables

        Returns:
            List of date relationships
        """
        relationships = []

        for fact_table in fact_tables:
            relationship = Relationship(
                from_table=fact_table,
                from_column=date_column_name,
                to_table=date_table_name,
                to_column="Date",
                cardinality=Cardinality.MANY_TO_ONE.value,
                cross_filter_direction=FilterDirection.SINGLE.value,
                is_active=True
            )

            relationships.append(relationship)

            logger.info(f"Created date relationship: {fact_table}[{date_column_name}] -> {date_table_name}[Date]")

        return relationships

    # ============================================
    # Model Optimization
    # ============================================

    def optimize_model_relationships(
        self,
        relationships: List[Relationship]
    ) -> List[Relationship]:
        """
        Optimize relationship configuration for performance

        Optimizations:
        1. Detect ambiguous relationships (multiple paths)
        2. Mark one as inactive to avoid circular dependencies
        3. Prefer single-direction filtering where possible
        """
        optimized = []

        # Group relationships by table pairs
        table_pairs: Dict[Tuple[str, str], List[Relationship]] = {}

        for rel in relationships:
            key = (rel.from_table, rel.to_table)

            if key not in table_pairs:
                table_pairs[key] = []

            table_pairs[key].append(rel)

        # Process each table pair
        for (from_table, to_table), rels in table_pairs.items():
            if len(rels) > 1:
                logger.warning(
                    f"Multiple relationships between {from_table} and {to_table} - "
                    f"marking all but first as inactive to avoid ambiguity"
                )

                # Keep first active, mark others inactive
                optimized.append(rels[0])

                for rel in rels[1:]:
                    rel.is_active = False
                    optimized.append(rel)
            else:
                optimized.append(rels[0])

        return optimized

    # ============================================
    # Utility Methods
    # ============================================

    def generate_model_diagram(
        self,
        relationships: List[Relationship],
        output_path: str
    ):
        """
        Generate Mermaid diagram of the data model

        Useful for documentation and review
        """
        lines = []

        lines.append("```mermaid")
        lines.append("erDiagram")

        for rel in relationships:
            # Convert cardinality to Mermaid notation
            if rel.cardinality == Cardinality.ONE_TO_MANY.value:
                notation = "||--o{"
            elif rel.cardinality == Cardinality.MANY_TO_ONE.value:
                notation = "}o--||"
            elif rel.cardinality == Cardinality.ONE_TO_ONE.value:
                notation = "||--||"
            else:  # Many-to-Many
                notation = "}o--o{"

            lines.append(
                f"    {rel.from_table} {notation} {rel.to_table} : \"{rel.from_column} -> {rel.to_column}\""
            )

        lines.append("```")

        with open(output_path, 'w') as f:
            f.write("\n".join(lines))

        logger.info(f"Generated model diagram: {output_path}")
