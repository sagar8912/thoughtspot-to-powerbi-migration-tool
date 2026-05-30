"""Logic Graph Builder - Construct dependency DAG from Tableau calculations"""
import re
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import networkx as nx
from loguru import logger


# Type Aliases
Worksheet = Dict[str, Any]


class VisualType(Enum):
    """Tableau Mark/Visual types"""
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    SQUARE = "square"
    CIRCLE = "circle"
    SHAPE = "shape"
    TEXT = "text"
    MAP = "map"
    PIE = "pie"
    GANTT = "gantt"
    POLYGON = "polygon"
    UNKNOWN = "Unknown"




@dataclass
class FieldDependency:
    """Metadata about a field dependency"""
    field_name: str
    field_type: str  # "BASE_COLUMN" | "CALCULATED_MEASURE" | "CALCULATED_COLUMN"
    original_role: str  # "measure" | "dimension" from Tableau
    is_aggregated: bool  # True if it's already an aggregate
    source_calc: 'CalculationNode' = None


class CalculationType(Enum):
    """Classification of calculation types"""
    MEASURE = "MEASURE"  # Aggregate calculation (SUM, AVG, etc.)
    CALCULATED_COLUMN = "CALCULATED_COLUMN"  # Row-level calculation
    LOD_EXPRESSION = "LOD_EXPRESSION"  # FIXED/INCLUDE/EXCLUDE
    TABLE_CALCULATION = "TABLE_CALCULATION"  # RANK, RUNNING_SUM, etc.
    PARAMETER = "PARAMETER"  # User parameter


class Granularity(Enum):
    """Calculation granularity"""
    ROW_LEVEL = "ROW_LEVEL"  # Evaluates per row
    AGGREGATE = "AGGREGATE"  # Evaluates at aggregated level
    TABLE = "TABLE"  # Table calculation (post-aggregation)


class ContextTransitionType(Enum):
    """
    Types of context transitions in Tableau → DAX conversion

    Component 2: Order of Operations
    """
    NONE = "NONE"  # No context shift
    FIXED_LOD = "FIXED_LOD"  # FIXED ignores view filters
    EXCLUDE_LOD = "EXCLUDE_LOD"  # EXCLUDE removes dimensions
    INCLUDE_LOD = "INCLUDE_LOD"  # INCLUDE adds dimensions
    CONTEXT_FILTER = "CONTEXT_FILTER"  # Context filters apply first
    TABLE_CALC = "TABLE_CALC"  # Post-aggregation calculation


@dataclass
class ContextTransition:
    """
    Metadata for context transitions (Component 2)

    Captures HOW evaluation context changes from Tableau to DAX.
    Critical for generating correct CALCULATE/ALLEXCEPT/ALL patterns.
    """
    transition_type: ContextTransitionType
    from_context: str  # Description of source context
    to_context: str  # Description of target context
    dax_pattern: str  # Recommended DAX pattern (ALLEXCEPT, ALL, CALCULATE, etc.)
    requires_allexcept: bool = False
    requires_all: bool = False
    requires_keepfilters: bool = False
    explanation: str = ""  # Human-readable explanation for LLM


@dataclass
class FilterContext:
    """Filter context for a calculation"""
    standard_filters: List[str]
    context_filters: List[str]  # Critical: context filters apply first
    is_context_dependent: bool


@dataclass
class VisualContext:
    """Visual context where calculation is used"""
    used_in_worksheets: List[str]
    visual_types: List[VisualType]  # NEW: What kind of visuals use this calc?
    partition_by: List[str]  # Grouping dimensions (like GROUP BY)
    sort_by: List[str]  # Sorting dimensions
    filters: FilterContext


@dataclass
class CalculationNode:
    """Node in the calculation dependency graph"""
    calc_id: str
    name: str
    formula: str
    calc_type: CalculationType
    granularity: Granularity
    depends_on: List[str]  # List of field names this calculation depends on
    dependency_level: int  # 0 = base field, 1 = depends on base, etc.
    visual_context: VisualContext
    is_lod: bool = False
    lod_type: str = None  # FIXED, INCLUDE, EXCLUDE
    context_transition: ContextTransition = None  # NEW: Component 2
    tableau_role: str = None  # "measure" or "dimension" from Tableau
    depends_on_metadata: Dict[str, FieldDependency] = None  # NEW: Dependency metadata
    source_tables: List[str] = None  # Physical source tables from extractor cols/map

    def __post_init__(self):
        """Initialize mutable default values"""
        if self.depends_on_metadata is None:
            self.depends_on_metadata = {}
        if self.source_tables is None:
            self.source_tables = []


class LogicGraphBuilder:
    """
    Build dependency DAG from Tableau calculations

    Responsibilities:
    - Parse formulas to extract field references
    - Build directed acyclic graph (DAG) of dependencies
    - Topological sort to determine execution order
    - Classify calculation types (Measure vs. Column)
    - Detect granularity (row-level vs. aggregate)
    - Extract visual context for DAX generation
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.calculations: Dict[str, CalculationNode] = {}
        self.base_fields: Set[str] = set()  # Non-calculated fields
        self.worksheets: List[Worksheet] = []
        self.field_roles: Dict[str, str] = {}  # NEW: Track role metadata (measure/dimension)

    def build_graph(
        self,
        tableau_model: Dict[str, Any],
        base_field_metadata: Dict[str, Dict[str, Any]]
    ) -> nx.DiGraph:
        """
        Build the dependency graph directly from the parsed JSON model.
        
        Args:
            tableau_model: The full dictionary model extracted from Tableau 
            base_field_metadata: Metadata for base fields (name -> {type, generic_type})
            
        Returns:
            NetworkX directed graph
        """
        logger.info(f"Building logic graph from native Tableau JSON model")
        
        self.base_field_metadata = base_field_metadata
        self.base_fields = set(base_field_metadata.keys())
        self.worksheets = tableau_model.get("worksheets", [])
        
        if not self.base_fields:
            logger.error(f"⚠️  CRITICAL: base_fields is EMPTY! All fields will be UNKNOWN!")

        # Extract only columns that have formulas
        calculated_fields = [
            col for col in tableau_model.get("columns", [])
            if col.get("formula")
        ]
        
        # Add table calcs that might be separate
        for tc in tableau_model.get("table_calcs", []):
            if tc.get("formula"):
                calculated_fields.append({
                    "caption": tc.get("caption", tc.get("name")),
                    "formula": tc["formula"],
                    "role": "measure"
                })

        # Build role map from calculated fields
        for calc in calculated_fields:
            name = calc.get("caption") or calc.get("internal_name") or calc.get("name")
            self.field_roles[name] = calc.get("role", "measure")

        # Step 1: Create nodes for all calculations
        for calc in calculated_fields:
            if calc.get("caption") or calc.get("internal_name") or calc.get("name"):
                self._add_calculation_node(calc)

        # Step 2: Mark LOD expressions
        import re
        for lod in tableau_model.get("lod_calcs", []):
            name = lod.get("caption") or lod.get("internal_name") or lod.get("name")
            if name and name in self.calculations:
                node = self.calculations[name]
                node.is_lod = True
                
                formula = lod.get("formula", "")
                match = re.search(r'\{(FIXED|INCLUDE|EXCLUDE)', formula, re.IGNORECASE)
                node.lod_type = match.group(1).upper() if match else "FIXED"
                
                node.calc_type = CalculationType.LOD_EXPRESSION

        # Step 3: Extract dependencies and build edges with metadata
        for calc_name, node in self.calculations.items():
            dependencies = self._extract_dependencies(node.formula)
            node.depends_on = dependencies

            # Build dependency metadata
            depends_on_metadata = {}
            for dep in dependencies:
                # Strip trailing table qualifier ` [calc (Table)]` -> `calc`
                # because self.calculations uses the base name.
                clean_dep = re.sub(r'\s*\([^\)]+\)$', '', dep).strip()

                if clean_dep in self.calculations:
                    # Reference to another calculation
                    dep_calc = self.calculations[clean_dep]

                    # Determine if it's a measure or calculated column
                    if dep_calc.calc_type == CalculationType.MEASURE:
                        field_type = "CALCULATED_MEASURE"
                        is_aggregated = True
                    else:
                        field_type = "CALCULATED_COLUMN"
                        is_aggregated = False

                    depends_on_metadata[dep] = FieldDependency(
                        field_name=clean_dep,
                        field_type=field_type,
                        original_role=self.field_roles.get(clean_dep, "unknown"),
                        is_aggregated=is_aggregated,
                        source_calc=dep_calc
                    )
                elif clean_dep in self.base_fields:
                    # Base column from data source
                    metadata = self.base_field_metadata.get(clean_dep, {})
                    generic_type = metadata.get("generic_type", "UNKNOWN")
                    
                    role = "measure" if generic_type == "NUMERIC" else "dimension"
                    
                    depends_on_metadata[dep] = FieldDependency(
                        field_name=clean_dep,
                        field_type="BASE_COLUMN",
                        original_role=role, 
                        is_aggregated=False,
                        source_calc=None
                    )
                else:
                    # Unknown field - conservative fallback
                    depends_on_metadata[dep] = FieldDependency(
                        field_name=clean_dep,
                        field_type="UNKNOWN",
                        original_role="unknown",
                        is_aggregated=False,
                        source_calc=None
                    )
                    logger.warning(f"❌ {dep} (clean: {clean_dep}) → UNKNOWN (not in calculations or base_fields!)")

            # Store metadata in node
            node.depends_on_metadata = depends_on_metadata

            # Add edges: dependency -> calculation
            for dep in dependencies:
                clean_dep = re.sub(r'\s*\([^\)]+\)$', '', dep).strip()
                if clean_dep in self.calculations:
                    # Dependency is another calculation
                    self.graph.add_edge(clean_dep, calc_name)
                else:
                    # Dependency is a base field
                    if clean_dep not in self.graph:
                        self.graph.add_node(clean_dep, type="base_field")
                    self.graph.add_edge(clean_dep, calc_name)

        # Step 4: Calculate dependency levels
        self._calculate_dependency_levels()

        # Step 4.5: Refine calculation types based on validated dependencies
        # (e.g., if a calc depends on a MEASURE, it is likely a MEASURE even without explicit aggregation keywords)
        self._refine_calculation_types()

        # Step 5: Extract visual context
        self._extract_visual_contexts()

        # Step 6: NEW - Analyze context transitions (Component 2)
        self._analyze_context_transitions()

        logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
        return self.graph

    def _refine_calculation_types(self):
        """
        Refine calculation types based on dependencies (Topological Pass)

        Fixes issue where `[Measure1] + [Measure2]` is classified as CALCULATED_COLUMN
        because it lacks explicit aggregation keywords like SUM().
        """
        try:
            sorted_nodes = list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            logger.warning("Graph cycle detected - skipping type refinement")
            return

        for node_name in sorted_nodes:
            if node_name not in self.calculations:
                continue
            
            node = self.calculations[node_name]
            
            # Skip if already explicit types
            if node.calc_type in (CalculationType.LOD_EXPRESSION, CalculationType.TABLE_CALCULATION, CalculationType.PARAMETER):
                continue

            # Check dependencies
            has_measure_dependency = False
            for dep_name in node.depends_on:
                if dep_name in self.calculations:
                    dep_node = self.calculations[dep_name]
                    if dep_node.calc_type in (CalculationType.MEASURE, CalculationType.LOD_EXPRESSION, CalculationType.TABLE_CALCULATION):
                        has_measure_dependency = True
                        break
                elif dep_name in self.base_field_metadata:
                    # Base fields used without aggregation in a formula that lacks aggregation keywords
                    # imply a row-level calculation (Calculated Column).
                    # So we purposefully do NOT upgrade to MEASURE here.
                    pass

            # Update type if it's currently a Column but depends on Measures
            if node.calc_type == CalculationType.CALCULATED_COLUMN and has_measure_dependency:
                logger.info(f"Refining type for '{node.name}': CALCULATED_COLUMN -> MEASURE (depends on measures)")
                node.calc_type = CalculationType.MEASURE
                
                # CRITICAL Propagate this change to dependents!
                # Successors need to know this is now a MEASURE so they don't wrap it in SUM()
                successors = list(self.graph.successors(node_name))
                for succ_name in successors:
                    if succ_name in self.calculations:
                        succ_node = self.calculations[succ_name]
                        if node_name in succ_node.depends_on_metadata:
                            dep = succ_node.depends_on_metadata[node_name]
                            dep.field_type = "CALCULATED_MEASURE"
                            dep.is_aggregated = True
                            logger.debug(f"  -> Updated dependency in '{succ_name}' to CALCULATED_MEASURE")


    def _add_calculation_node(self, calc: Dict[str, Any]):
        """Add a calculation node to the graph"""
        # Classify calculation type
        calc_type = self._classify_calculation_type(calc)
        granularity = self._detect_granularity(calc)

        name = calc.get("caption") or calc.get("internal_name") or calc.get("name")
        formula = calc.get("formula", "")
        role = calc.get("role", "measure")
        # source_tables is populated by tableau_extractor.py via cols/map reverse lookup
        source_tables = calc.get("source_tables", []) or []

        node = CalculationNode(
            calc_id=name,
            name=name,
            formula=formula,
            calc_type=calc_type,
            granularity=granularity,
            depends_on=[],
            dependency_level=0,
            visual_context=VisualContext(
                used_in_worksheets=[],
                visual_types=[],
                partition_by=[],
                sort_by=[],
                filters=FilterContext([], [], False)
            ),
            tableau_role=role,
            source_tables=source_tables,  # ← ground-truth table names from extractor
        )

        self.calculations[name] = node
        self.graph.add_node(name, **node.__dict__)

    def _classify_calculation_type(self, calc: Dict[str, Any]) -> CalculationType:
        """Classify the type of calculation"""
        formula = calc.get("formula", "").upper()

        # Table calculations
        table_calc_keywords = [
            'WINDOW_', 'RUNNING_', 'INDEX()', 'RANK', 'LOOKUP',
            'PREVIOUS_VALUE', 'SIZE()', 'FIRST()', 'LAST()'
        ]
        if any(kw in formula for kw in table_calc_keywords):
            return CalculationType.TABLE_CALCULATION

        # Aggregations = measures
        agg_keywords = ['SUM(', 'AVG(', 'COUNT(', 'MIN(', 'MAX(', 'STDEV(', 'VAR(']
        if any(kw in formula for kw in agg_keywords):
            return CalculationType.MEASURE

        # LOD expressions
        if re.search(r'\{(FIXED|INCLUDE|EXCLUDE)', formula, re.IGNORECASE):
            return CalculationType.LOD_EXPRESSION

        # Heuristic: If Tableau explicitly typed it as a measure, trust it over the formula
        # (e.g. IF [Col]='A' THEN [Amount] END is a row-level column, but saved as a Measure 
        # so it gets aggregated by default in views, and converted to DAX MEASUREs via rules)
        if calc.get("role") == "measure":
            return CalculationType.MEASURE

        # Default: calculated column (row-level)
        return CalculationType.CALCULATED_COLUMN

    def _detect_granularity(self, calc: Dict[str, Any]) -> Granularity:
        """Detect calculation granularity"""
        formula = calc.get("formula", "").upper()

        # Table calculations operate post-aggregation
        table_calc_keywords = ['WINDOW_', 'RUNNING_', 'INDEX()', 'RANK']
        if any(kw in formula for kw in table_calc_keywords):
            return Granularity.TABLE

        # Aggregations
        if any(agg in formula for agg in ['SUM(', 'AVG(', 'COUNT(', 'MIN(', 'MAX(']):
            return Granularity.AGGREGATE

        # Default: row-level
        return Granularity.ROW_LEVEL

    def _extract_dependencies(self, formula: str) -> List[str]:
        """
        Extract field references from formula

        Tableau field references are wrapped in [brackets]

        Example:
            "SUM([Sales]) / SUM([Profit])" -> ["Sales", "Profit"]
        """
        # Pattern: [FieldName]
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, formula)

        # Remove duplicates and clean
        dependencies = []
        for match in matches:
            cleaned = match.strip()
            if cleaned and cleaned not in dependencies:
                dependencies.append(cleaned)

        return dependencies

    def _calculate_dependency_levels(self):
        """
        Calculate dependency level for each calculation

        Level 0: Base fields (no dependencies)
        Level 1: Depends only on base fields
        Level 2: Depends on level 1 calculations
        etc.
        """
        # Topological sort to get execution order
        try:
            sorted_nodes = list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            logger.error("Calculation graph has cycles! Cannot determine execution order.")
            return

        # Assign levels
        for node_name in sorted_nodes:
            if node_name in self.base_fields:
                # Base field = level 0
                continue

            if node_name not in self.calculations:
                # Base field node
                continue

            node = self.calculations[node_name]

            # Level = max(dependency levels) + 1
            dep_levels = []
            for dep in node.depends_on:
                clean_dep = re.sub(r'\s*\([^\)]+\)$', '', dep).strip()
                if clean_dep in self.calculations:
                    dep_levels.append(self.calculations[clean_dep].dependency_level)
                else:
                    # Base field = level 0
                    dep_levels.append(0)

            node.dependency_level = max(dep_levels, default=0) + 1

        logger.debug("Calculated dependency levels")

    def _extract_visual_contexts(self):
        """Extract visual context for each calculation from worksheets"""
        for ws in self.worksheets:
            rows_fields = ws.get("rows", [])
            columns_fields = ws.get("cols", [])
            
            # Extract marks from pane_encodings
            marks_fields = []
            for pane in ws.get("pane_encodings", []):
                for enc_type, field in pane.get("encodings", {}).items():
                    marks_fields.append(field)
            
            # Clean fields to remove SUM() wrappers for dependency matching
            def clean_field(f):
                import re
                f = re.sub(r'^[A-Z]+\(\[', '[', f)
                f = re.sub(r'\]\)$', ']', f)
                return f.strip('[]')

            cleaned_rows = [clean_field(f) for f in rows_fields]
            cleaned_cols = [clean_field(f) for f in columns_fields]
            cleaned_marks = [clean_field(f) for f in marks_fields]

            all_fields = cleaned_rows + cleaned_cols + cleaned_marks
            ws_name = ws.get("name", "Unknown Sheet")
            visual_type = ws.get("mark_type", "Unknown")
            # NEW: Add visual type (mapped to Enum)
            mapped_visual_type = VisualType.UNKNOWN
            try:
                # Check if it's a valid enum value
                vt_lower = str(visual_type).lower()
                for vt in VisualType:
                    if vt.value == vt_lower:
                        mapped_visual_type = vt
                        break
            except Exception:
                pass


            for field in all_fields:
                clean_field = re.sub(r'\s*\([^\)]+\)$', '', field).strip()
                if clean_field in self.calculations:
                    node = self.calculations[clean_field]

                    # Add worksheet
                    if ws_name not in node.visual_context.used_in_worksheets:
                        node.visual_context.used_in_worksheets.append(ws_name)

                    # NEW: Add visual type
                    if mapped_visual_type not in node.visual_context.visual_types:
                        node.visual_context.visual_types.append(mapped_visual_type)

                    # Determine partition (grouping) dimensions
                    partition_dims = [
                        re.sub(r'\s*\([^\)]+\)$', '', f).strip() for f in cleaned_rows + cleaned_cols
                        if f != field and re.sub(r'\s*\([^\)]+\)$', '', f).strip() not in self.calculations
                    ]

                    for dim in partition_dims:
                        if dim not in node.visual_context.partition_by:
                            node.visual_context.partition_by.append(dim)

        logger.debug("Extracted visual contexts")

    # ============================================
    # Query Methods
    # ============================================

    def get_execution_order(self) -> List[str]:
        """
        Get calculations in execution order (topological sort)

        Returns:
            List of calculation names in dependency order
        """
        try:
            sorted_nodes = list(nx.topological_sort(self.graph))
            # Filter to only calculations (exclude base fields)
            calc_order = [n for n in sorted_nodes if n in self.calculations]
            return calc_order
        except nx.NetworkXError:
            logger.error("Graph has cycles!")
            return list(self.calculations.keys())

    def get_calculation_node(self, calc_name: str) -> CalculationNode:
        """Get calculation node by name"""
        return self.calculations.get(calc_name)

    def get_dependencies(self, calc_name: str) -> List[str]:
        """Get direct dependencies of a calculation"""
        if calc_name in self.calculations:
            return self.calculations[calc_name].depends_on
        return []

    def get_dependents(self, calc_name: str) -> List[str]:
        """Get calculations that depend on this one"""
        if calc_name not in self.graph:
            return []

        return list(self.graph.successors(calc_name))

    def get_root_calculations(self) -> List[str]:
        """Get calculations with no dependencies (level 0/1)"""
        roots = []
        for name, node in self.calculations.items():
            if node.dependency_level <= 1:
                roots.append(name)
        return roots

    def get_lod_expressions(self) -> List[CalculationNode]:
        """Get all LOD expression nodes"""
        return [node for node in self.calculations.values() if node.is_lod]

    def get_table_calculations(self) -> List[CalculationNode]:
        """Get all table calculation nodes"""
        return [
            node for node in self.calculations.values()
            if node.calc_type == CalculationType.TABLE_CALCULATION
        ]

    # ============================================
    # Export Methods
    # ============================================

    def to_dict(self) -> Dict[str, Any]:
        """Export graph as dictionary for JSON serialization"""
        nodes = []
        for calc_name, node in self.calculations.items():
            nodes.append({
                "id": node.calc_id,
                "name": node.name,
                "formula": node.formula,
                "type": node.calc_type.value,
                "granularity": node.granularity.value,
                "dependency_level": node.dependency_level,
                "depends_on": node.depends_on,
                "is_lod": node.is_lod,
                "lod_type": node.lod_type,
                "visual_context": {
                    "used_in": node.visual_context.used_in_worksheets,
                    "partition_by": node.visual_context.partition_by,
                    "sort_by": node.visual_context.sort_by
                }
            })

        edges = []
        for source, target in self.graph.edges():
            edges.append({"source": source, "target": target})

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_calculations": len(self.calculations),
                "total_dependencies": self.graph.number_of_edges(),
                "max_dependency_level": max(
                    (node.dependency_level for node in self.calculations.values()),
                    default=0
                ),
                "lod_count": len(self.get_lod_expressions()),
                "table_calc_count": len(self.get_table_calculations())
            }
        }

    def export_for_reactflow(self) -> Dict[str, Any]:
        """
        Export graph in ReactFlow format

        Returns:
            Dictionary with nodes and edges for ReactFlow visualization
        """
        reactflow_nodes = []
        reactflow_edges = []

        # Auto-layout using hierarchical positioning
        pos = nx.spring_layout(self.graph, k=2, iterations=50)

        # Create nodes
        for calc_name, node in self.calculations.items():
            x, y = pos.get(calc_name, (0, 0))

            # Determine node color based on type
            node_colors = {
                CalculationType.MEASURE: "#f59e0b",  # orange
                CalculationType.CALCULATED_COLUMN: "#3b82f6",  # blue
                CalculationType.LOD_EXPRESSION: "#8b5cf6",  # purple
                CalculationType.TABLE_CALCULATION: "#ec4899",  # pink
                CalculationType.PARAMETER: "#10b981"  # green
            }

            reactflow_nodes.append({
                "id": calc_name,
                "type": "calculationNode",
                "data": {
                    "label": node.name,
                    "formula": node.formula[:50] + "..." if len(node.formula) > 50 else node.formula,
                    "calcType": node.calc_type.value,
                    "level": node.dependency_level,
                    "isLOD": node.is_lod
                },
                "position": {"x": x * 500, "y": y * 500},
                "style": {
                    "background": node_colors.get(node.calc_type, "#6b7280"),
                    "color": "white",
                    "border": "2px solid" if node.is_lod else "1px solid",
                    "borderColor": "#8b5cf6" if node.is_lod else "#d1d5db"
                }
            })

        # Create edges
        for source, target in self.graph.edges():
            if source in self.calculations and target in self.calculations:
                reactflow_edges.append({
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "type": "smoothstep",
                    "animated": False
                })

        return {
            "nodes": reactflow_nodes,
            "edges": reactflow_edges
        }

    # ============================================
    # Component 2: Context Transition Analysis
    # ============================================

    def _analyze_context_transitions(self):
        """
        Analyze context transitions for all calculations (Component 2)

        Determines HOW evaluation context shifts from Tableau to DAX.
        Critical for generating correct CALCULATE/ALLEXCEPT/ALL patterns.
        """
        for calc_name, node in self.calculations.items():
            transition = self._determine_context_transition(node)
            node.context_transition = transition

            if transition.transition_type != ContextTransitionType.NONE:
                logger.debug(f"Context transition for '{calc_name}': {transition.transition_type.value}")

    def _determine_context_transition(self, node: CalculationNode) -> ContextTransition:
        """
        Determine context transition type for a calculation

        Returns:
            ContextTransition with metadata for DAX generation
        """
        # Pattern 1: FIXED LOD
        if node.is_lod and node.lod_type == "FIXED":
            return self._create_fixed_lod_transition(node)

        # Pattern 2: EXCLUDE LOD
        if node.is_lod and node.lod_type == "EXCLUDE":
            return self._create_exclude_lod_transition(node)

        # Pattern 3: INCLUDE LOD
        if node.is_lod and node.lod_type == "INCLUDE":
            return self._create_include_lod_transition(node)

        # Pattern 4: Context filters
        if node.visual_context.filters.context_filters:
            return self._create_context_filter_transition(node)

        # Pattern 5: Table calculations
        if node.calc_type == CalculationType.TABLE_CALCULATION:
            return self._create_table_calc_transition(node)

        # Default: No context transition
        return ContextTransition(
            transition_type=ContextTransitionType.NONE,
            from_context="View context",
            to_context="View context",
            dax_pattern="Standard measure",
            explanation="No context shift - standard aggregation"
        )

    def _create_fixed_lod_transition(self, node: CalculationNode) -> ContextTransition:
        """
        Create transition metadata for FIXED LOD

        FIXED ignores view filters except context filters.
        DAX Pattern: CALCULATE with ALLEXCEPT
        """
        partition = node.visual_context.partition_by

        if partition:
            dax_pattern = f"CALCULATE(expr, ALLEXCEPT(Table, {', '.join(partition)}))"
            explanation = f"FIXED LOD ignores view filters. Keep only dimensions: {', '.join(partition)}"
        else:
            dax_pattern = "CALCULATE(expr, ALL(Table))"
            explanation = "FIXED LOD with no dimensions = grand total (ignore all filters)"

        return ContextTransition(
            transition_type=ContextTransitionType.FIXED_LOD,
            from_context="View context (with filters)",
            to_context=f"Fixed context ({', '.join(partition) if partition else 'Grand total'})",
            dax_pattern=dax_pattern,
            requires_allexcept=bool(partition),
            requires_all=not bool(partition),
            explanation=explanation
        )

    def _create_exclude_lod_transition(self, node: CalculationNode) -> ContextTransition:
        """
        Create transition metadata for EXCLUDE LOD

        EXCLUDE removes specific dimensions from grouping.
        DAX Pattern: CALCULATE with ALL(excluded dimensions)
        """
        # Extract excluded dimensions from formula
        # Example: {EXCLUDE [Region]: SUM([Sales])} -> excludes Region
        formula_upper = node.formula.upper()
        match = re.search(r'EXCLUDE\s+\[([^\]]+)\]', formula_upper)
        excluded = match.group(1) if match else "Unknown"

        dax_pattern = f"CALCULATE(expr, ALL(Table[{excluded}]))"
        explanation = f"EXCLUDE removes {excluded} from grouping. Use ALL() to ignore that dimension."

        return ContextTransition(
            transition_type=ContextTransitionType.EXCLUDE_LOD,
            from_context=f"View context (including {excluded})",
            to_context=f"View context (excluding {excluded})",
            dax_pattern=dax_pattern,
            requires_all=True,
            explanation=explanation
        )

    def _create_include_lod_transition(self, node: CalculationNode) -> ContextTransition:
        """
        Create transition metadata for INCLUDE LOD

        INCLUDE adds dimensions to grouping.
        No direct DAX equivalent - requires restructuring.
        """
        formula_upper = node.formula.upper()
        match = re.search(r'INCLUDE\s+\[([^\]]+)\]', formula_upper)
        included = match.group(1) if match else "Unknown"

        explanation = f"INCLUDE adds {included} to grouping. No direct DAX equivalent - consider adding dimension to visual or using SUMMARIZE."

        return ContextTransition(
            transition_type=ContextTransitionType.INCLUDE_LOD,
            from_context="View context",
            to_context=f"View context (with added {included})",
            dax_pattern="SUMMARIZE or calculated table",
            explanation=explanation
        )

    def _create_context_filter_transition(self, node: CalculationNode) -> ContextTransition:
        """
        Create transition metadata for context filters

        Context filters apply BEFORE standard filters.
        DAX Pattern: KEEPFILTERS or ALLSELECTED
        """
        context_filters = node.visual_context.filters.context_filters
        filters_str = ", ".join(context_filters)

        dax_pattern = f"CALCULATE(expr, KEEPFILTERS(Table[{context_filters[0]}] = value))"
        explanation = f"Context filters ({filters_str}) apply first. Use KEEPFILTERS to preserve filter order."

        return ContextTransition(
            transition_type=ContextTransitionType.CONTEXT_FILTER,
            from_context="View context",
            to_context=f"Context-filtered ({filters_str})",
            dax_pattern=dax_pattern,
            requires_keepfilters=True,
            explanation=explanation
        )

    def _create_table_calc_transition(self, node: CalculationNode) -> ContextTransition:
        """
        Create transition metadata for table calculations

        Table calculations run AFTER aggregation.
        Often require model changes (Index columns, etc.)
        """
        explanation = "Table calculation runs post-aggregation. May require Power BI model changes (Index columns, Date table, etc.)"

        return ContextTransition(
            transition_type=ContextTransitionType.TABLE_CALC,
            from_context="Aggregated values",
            to_context="Table calculation result",
            dax_pattern="Calculated column or model enhancement",
            explanation=explanation
        )
