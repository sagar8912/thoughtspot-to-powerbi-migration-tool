"""Pattern Loader - Load and manage Tableau-to-DAX conversion patterns"""
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class ConversionPattern:
    """Conversion pattern model"""
    pattern_id: str
    tableau: str
    dax: str
    confidence: float
    tags: List[str]
    notes: str
    context: Dict[str, Any]


class PatternLoader:
    """
    Simple YAML-based pattern loader (no vector DB)

    Design: Load all patterns at startup and pass directly to LLM.
    This avoids the complexity of RAG/vector embeddings for MVP.
    """

    def __init__(self, patterns_file: str = "data/conversion_patterns/patterns.yaml"):
        """
        Initialize pattern loader

        Args:
            patterns_file: Path to YAML pattern file (relative to project root)
        """
        # Handle both absolute and relative paths
        self.patterns_file = Path(patterns_file)

        # If relative, resolve from project root
        if not self.patterns_file.is_absolute():
            # Assume we're running from bknd/ directory
            project_root = Path(__file__).parent.parent.parent
            self.patterns_file = project_root / patterns_file

        if not self.patterns_file.exists():
            raise FileNotFoundError(f"Pattern file not found: {self.patterns_file}")

        self.patterns: List[ConversionPattern] = []
        self.patterns_by_id: Dict[str, ConversionPattern] = {}
        self.patterns_by_tag: Dict[str, List[ConversionPattern]] = {}
        self.metadata: Dict[str, Any] = {}

        self._load_patterns()

    def _load_patterns(self):
        """Load all patterns from YAML file"""
        logger.info(f"Loading conversion patterns from: {self.patterns_file}")

        with open(self.patterns_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Load metadata
        self.metadata = data.get('metadata', {})

        # Parse patterns
        pattern_dicts = data.get('patterns', [])

        for p in pattern_dicts:
            pattern = ConversionPattern(
                pattern_id=p['pattern_id'],
                tableau=p['tableau'],
                dax=p['dax'],
                confidence=p.get('confidence', 1.0),
                tags=p.get('tags', []),
                notes=p.get('notes', ''),
                context=p.get('context', {})
            )

            self.patterns.append(pattern)
            self.patterns_by_id[pattern.pattern_id] = pattern

            # Index by tags
            for tag in pattern.tags:
                if tag not in self.patterns_by_tag:
                    self.patterns_by_tag[tag] = []
                self.patterns_by_tag[tag].append(pattern)

        logger.info(f"Loaded {len(self.patterns)} conversion patterns")
        logger.debug(f"Pattern coverage: {self.metadata.get('coverage', {})}")

    # ============================================
    # Query Methods
    # ============================================

    def get_all_patterns(self) -> List[ConversionPattern]:
        """Get all patterns (for direct LLM prompting)"""
        return self.patterns.copy()

    def get_pattern_by_id(self, pattern_id: str) -> Optional[ConversionPattern]:
        """Get specific pattern by ID"""
        return self.patterns_by_id.get(pattern_id)

    def get_patterns_by_tag(self, tag: str) -> List[ConversionPattern]:
        """Get patterns matching a specific tag"""
        return self.patterns_by_tag.get(tag, []).copy()

    def get_patterns_by_tags(self, tags: List[str]) -> List[ConversionPattern]:
        """Get patterns matching ANY of the given tags"""
        matched = set()

        for tag in tags:
            patterns = self.patterns_by_tag.get(tag, [])
            matched.update(patterns)

        return list(matched)

    def search_patterns(self, keyword: str) -> List[ConversionPattern]:
        """
        Search patterns by keyword in tableau formula, dax, or notes

        Args:
            keyword: Search term (case-insensitive)

        Returns:
            List of matching patterns
        """
        keyword_lower = keyword.lower()
        matched = []

        for pattern in self.patterns:
            if (keyword_lower in pattern.tableau.lower() or
                keyword_lower in pattern.dax.lower() or
                keyword_lower in pattern.notes.lower()):
                matched.append(pattern)

        return matched

    # ============================================
    # Export Methods for LLM Prompting
    # ============================================

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Export all patterns as list of dictionaries

        Used for JSON serialization in LLM prompts.
        """
        return [
            {
                "pattern_id": p.pattern_id,
                "tableau": p.tableau,
                "dax": p.dax,
                "confidence": p.confidence,
                "tags": p.tags,
                "notes": p.notes,
                "context": p.context
            }
            for p in self.patterns
        ]

    def to_formatted_prompt_text(self) -> str:
        """
        Export patterns as formatted text for LLM prompt

        Returns:
            Multiline string with all patterns formatted for LLM
        """
        lines = []
        lines.append("# TABLEAU-TO-DAX CONVERSION PATTERNS")
        lines.append("")

        # Group by tags
        for category, count in self.metadata.get('coverage', {}).items():
            category_tag = category.replace('_', ' ').title()
            lines.append(f"## {category_tag}")
            lines.append("")

            # Find patterns in this category
            category_patterns = [
                p for p in self.patterns
                if any(tag in p.tags for tag in category.split('_'))
            ]

            for pattern in category_patterns[:count]:  # Limit to metadata count
                lines.append(f"### Pattern: {pattern.pattern_id}")
                lines.append("")
                lines.append(f"**Tableau:**")
                lines.append(f"```")
                lines.append(pattern.tableau)
                lines.append(f"```")
                lines.append("")
                lines.append(f"**DAX:**")
                lines.append(f"```dax")
                lines.append(pattern.dax)
                lines.append(f"```")
                lines.append("")
                lines.append(f"**Notes:** {pattern.notes}")
                lines.append(f"**Confidence:** {pattern.confidence}")
                lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def get_pattern_summary(self) -> Dict[str, Any]:
        """Get summary statistics about patterns"""
        return {
            "total_patterns": len(self.patterns),
            "coverage": self.metadata.get('coverage', {}),
            "difficulty_levels": self.metadata.get('difficulty_levels', {}),
            "tags": list(self.patterns_by_tag.keys())
        }

    def get_difficulty_patterns(self, difficulty: str) -> List[ConversionPattern]:
        """
        Get patterns by difficulty level

        Args:
            difficulty: "easy", "medium", or "hard"

        Returns:
            List of patterns at that difficulty
        """
        difficulty_map = self.metadata.get('difficulty_levels', {})
        pattern_ids = difficulty_map.get(difficulty, [])

        return [
            self.patterns_by_id[pid]
            for pid in pattern_ids
            if pid in self.patterns_by_id
        ]

    # ============================================
    # Pattern Matching Helpers
    # ============================================

    def find_best_match(self, tableau_formula: str, threshold: float = 0.5) -> Optional[ConversionPattern]:
        """
        Find best matching pattern for a Tableau formula

        Uses simple string similarity (not semantic).
        For semantic matching, use LLM directly.

        Args:
            tableau_formula: Tableau formula to match
            threshold: Minimum similarity score (0-1)

        Returns:
            Best matching pattern or None
        """
        from difflib import SequenceMatcher

        best_pattern = None
        best_score = 0

        for pattern in self.patterns:
            # Calculate string similarity
            similarity = SequenceMatcher(
                None,
                tableau_formula.upper(),
                pattern.tableau.upper()
            ).ratio()

            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_pattern = pattern

        if best_pattern:
            logger.debug(f"Best pattern match: {best_pattern.pattern_id} (score: {best_score:.2f})")

        return best_pattern

    def suggest_patterns(self, tableau_formula: str, top_n: int = 3) -> List[tuple]:
        """
        Suggest top N matching patterns

        Args:
            tableau_formula: Tableau formula
            top_n: Number of suggestions to return

        Returns:
            List of (pattern, score) tuples
        """
        from difflib import SequenceMatcher

        scores = []

        for pattern in self.patterns:
            similarity = SequenceMatcher(
                None,
                tableau_formula.upper(),
                pattern.tableau.upper()
            ).ratio()

            scores.append((pattern, similarity))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_n]
