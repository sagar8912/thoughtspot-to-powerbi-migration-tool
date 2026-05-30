"""
Relationship Detector - Rule-based relationship detection.
Applies deterministic rules to generate high-quality relationship candidates.
"""

import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
from tqdm import tqdm
from dataclasses import dataclass

from src.config import Config
from src.utils.data_types import normalize_column_name, expand_abbreviation
from src.utils.pattern_matching import (
    calculate_value_overlap,
    detect_format_mismatch,
    fuzzy_match_score
)


@dataclass
class RelationshipCandidate:
    """Represents a potential relationship between two columns."""
    
    relationship_id: str
    source_file: str
    source_column: str
    target_file: str
    target_column: str
    
    relationship_type: str  # PK-FK, SEMANTIC_MATCH, etc.
    confidence_level: str   # HIGH, MEDIUM, LOW
    confidence_score: int   # 0-100
    detection_method: str   # Rule that detected this
    
    statistics: Dict[str, Any]
    requires_llm_validation: bool = False
    transformation_needed: Optional[str] = None
    warnings: List[str] = None
    business_insights: Optional[Dict[str, Any]] = None  # Per-relationship business analysis
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "relationship_id": self.relationship_id,
            "source": {
                "file": self.source_file,
                "column": self.source_column
            },
            "target": {
                "file": self.target_file,
                "column": self.target_column
            },
            "relationship_type": self.relationship_type,
            "confidence_level": self.confidence_level,
            "confidence_score": self.confidence_score,
            "detection_method": self.detection_method,
            "statistics": self.statistics,
            "transformation_needed": self.transformation_needed,
            "warnings": self.warnings,
            "requires_llm_validation": self.requires_llm_validation,
            "business_insights": self.business_insights or {}  # Include per-relationship insights
        }


class RelationshipDetector:
    """
    Detects relationships between columns using deterministic rules.
    Implements all 30+ relationship detection cases.
    """
    
    def __init__(
        self,
        profiles: Dict[str, Dict[str, Any]],
        dataframes: Dict[str, pd.DataFrame]
    ):
        """
        Initialize relationship detector.
        
        Args:
            profiles: Column profiles from ProfilingEngine
            dataframes: Loaded DataFrames
        """
        self.profiles = profiles
        self.dataframes = dataframes
        self.candidates: List[RelationshipCandidate] = []
        self.relationship_counter = 0
    
    def generate_candidates(self) -> List[RelationshipCandidate]:
        """
        Generate all relationship candidates using deterministic rules.
        
        Returns:
            List of relationship candidates
        """
        logger.info("Generating relationship candidates...")
        
        # Get all file pairs
        file_pairs = self._get_file_pairs()
        
        for file1, file2 in tqdm(file_pairs, desc="Detecting relationships"):
            self._detect_relationships_between_files(file1, file2)
        
        logger.success(f"Generated {len(self.candidates)} relationship candidates")
        
        # Sort by confidence score
        self.candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return self.candidates
    
    def _get_file_pairs(self) -> List[Tuple[str, str]]:
        """Get all unique file pairs."""
        files = list(self.profiles.keys())
        pairs = []
        
        for i, file1 in enumerate(files):
            for file2 in files[i+1:]:
                pairs.append((file1, file2))
        
        return pairs
    
    def _detect_relationships_between_files(self, file1: str, file2: str):
        """Detect relationships between two files."""
        profile1 = self.profiles[file1]
        profile2 = self.profiles[file2]
        
        # Compare all column pairs
        for col1_name, col1_profile in profile1["columns"].items():
            for col2_name, col2_profile in profile2["columns"].items():
                # Try all detection rules
                candidate = self._apply_detection_rules(
                    file1, col1_name, col1_profile,
                    file2, col2_name, col2_profile
                )
                
                if candidate:
                    self.candidates.append(candidate)
    
    def _apply_detection_rules(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict
    ) -> Optional[RelationshipCandidate]:
        """
        Apply all detection rules in priority order.
        Returns first matching rule.
        """
        
        # CATEGORY 1: Direct Key Matching (High Confidence)
        candidate = self._check_exact_match(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile
        )
        if candidate:
            return candidate
        
        candidate = self._check_name_variation_match(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile
        )
        if candidate:
            return candidate
        
        # CATEGORY 2: Format Mismatches
        candidate = self._check_format_mismatch(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile
        )
        if candidate:
            return candidate

        # CATEGORY 2.5: High Overlap + LLM Semantic Check (NEW!)
        candidate = self._check_high_overlap_llm_validation(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile
        )
        if candidate:
            return candidate

        # CATEGORY 3: Semantic Similarity (requires LLM)
        candidate = self._check_semantic_similarity(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile
        )
        if candidate:
            return candidate

        return None
    
    # =========================================================================
    # CATEGORY 1: DIRECT KEY MATCHING
    # =========================================================================
    
    def _check_exact_match(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict
    ) -> Optional[RelationshipCandidate]:
        """
        Case 1.1: Exact column name + data type match
        """
        # Must have same name and compatible types
        if col1_name != col2_name:
            return None
        
        if col1_profile["data_type"] != col2_profile["data_type"]:
            return None
        
        # Calculate value overlap
        df1 = self.dataframes[file1]
        df2 = self.dataframes[file2]
        
        overlap_pct, exact_matches, fuzzy_matches = calculate_value_overlap(
            df1[col1_name],
            df2[col2_name]
        )
        
        # Need high overlap
        if overlap_pct < Config.HIGH_CONFIDENCE_OVERLAP_THRESHOLD * 100:
            return None
        
        # At least one side should be unique (PK)
        is_pk1 = col1_profile["key_features"]["is_unique"]
        is_pk2 = col2_profile["key_features"]["is_unique"]
        
        if not (is_pk1 or is_pk2):
            # Both are non-unique - might be M:N
            return None
        
        # Determine relationship type
        if is_pk1 and is_pk2:
            rel_type = "ONE_TO_ONE"
            cardinality = "1:1"
        elif is_pk1:
            rel_type = "PRIMARY_KEY -> FOREIGN_KEY"
            cardinality = "1:N"
        else:
            rel_type = "FOREIGN_KEY -> PRIMARY_KEY"
            cardinality = "N:1"
        
        return self._create_candidate(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile,
            relationship_type=rel_type,
            confidence_level="HIGH",
            confidence_score=95,
            detection_method="EXACT_NAME_AND_TYPE_MATCH",
            overlap_pct=overlap_pct,
            exact_matches=exact_matches,
            cardinality=cardinality
        )
    
    def _check_name_variation_match(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict
    ) -> Optional[RelationshipCandidate]:
        """
        Case 1.2: Name variation match (Customer ID vs customer_id)
        Case 1.3: Abbreviation match (cust_id vs customer_id)
        """
        # Check normalized names
        norm1 = col1_profile["normalized_name"]
        norm2 = col2_profile["normalized_name"]
        
        # Must be compatible types
        if col1_profile["data_type"] != col2_profile["data_type"]:
            return None
        
        # Check if normalized names match
        name_match = False
        if norm1 == norm2:
            name_match = True
        
        # Check if one is abbreviation of other
        if not name_match:
            variations1 = set(col1_profile["name_variations"])
            variations2 = set(col2_profile["name_variations"])
            
            if variations1 & variations2:  # Intersection
                name_match = True
        
        if not name_match:
            return None
        
        # Calculate overlap
        df1 = self.dataframes[file1]
        df2 = self.dataframes[file2]
        
        overlap_pct, exact_matches, _ = calculate_value_overlap(
            df1[col1_name],
            df2[col2_name]
        )
        
        if overlap_pct < Config.HIGH_CONFIDENCE_OVERLAP_THRESHOLD * 100:
            return None
        
        # Determine PK/FK
        is_pk1 = col1_profile["key_features"]["is_unique"]
        is_pk2 = col2_profile["key_features"]["is_unique"]
        
        if is_pk1 and not is_pk2:
            rel_type = "PRIMARY_KEY -> FOREIGN_KEY"
            cardinality = "1:N"
        elif is_pk2 and not is_pk1:
            rel_type = "FOREIGN_KEY -> PRIMARY_KEY"
            cardinality = "N:1"
        elif is_pk1 and is_pk2:
            rel_type = "ONE_TO_ONE"
            cardinality = "1:1"
        else:
            rel_type = "POTENTIAL_JOIN"
            cardinality = "UNKNOWN"
        
        return self._create_candidate(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile,
            relationship_type=rel_type,
            confidence_level="HIGH",
            confidence_score=90,
            detection_method="NAME_VARIATION_MATCH",
            overlap_pct=overlap_pct,
            exact_matches=exact_matches,
            cardinality=cardinality
        )
    
    # =========================================================================
    # CATEGORY 2: FORMAT MISMATCHES
    # =========================================================================
    
    def _check_format_mismatch(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict
    ) -> Optional[RelationshipCandidate]:
        """
        Case 4.1: Format mismatch (CUST-001 vs 001)
        Case 4.2: Case sensitivity (USA vs usa)
        """
        # Names should be similar
        if fuzzy_match_score(col1_name, col2_name) < 0.7:
            return None
        
        # Detect format mismatch
        df1 = self.dataframes[file1]
        df2 = self.dataframes[file2]
        
        format_info = detect_format_mismatch(
            df1[col1_name],
            df2[col2_name]
        )
        
        if not format_info:
            return None
        
        # Calculate overlap after transformation
        overlap_pct, exact_matches, fuzzy_matches = calculate_value_overlap(
            df1[col1_name],
            df2[col2_name],
            fuzzy=True
        )
        
        if overlap_pct < Config.MEDIUM_CONFIDENCE_OVERLAP_THRESHOLD * 100:
            return None
        
        return self._create_candidate(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile,
            relationship_type="FORMAT_MISMATCH",
            confidence_level="MEDIUM",
            confidence_score=75,
            detection_method=format_info["type"],
            overlap_pct=overlap_pct,
            exact_matches=exact_matches,
            transformation_needed=format_info["transformation"],
            cardinality="UNKNOWN"
        )

    # =========================================================================
    # CATEGORY 2.5: HIGH OVERLAP + LLM SEMANTIC VALIDATION
    # =========================================================================

    def _check_high_overlap_llm_validation(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict
    ) -> Optional[RelationshipCandidate]:
        """
        NEW: Check if columns with >50% content overlap are semantically related.
        Uses LLM to judge based on:
        1. Content overlap percentage
        2. Column name semantic meaning
        3. Sample values

        This catches relationships that rule-based methods might miss.
        """
        # Skip if LLM validation is not enabled
        if not Config.ENABLE_LLM_VALIDATION or not Config.ENABLE_HIGH_OVERLAP_LLM_VALIDATION:
            return None

        # Must be compatible data types
        if col1_profile["data_type"] != col2_profile["data_type"]:
            return None

        # Calculate value overlap
        df1 = self.dataframes[file1]
        df2 = self.dataframes[file2]

        overlap_pct, exact_matches, _ = calculate_value_overlap(
            df1[col1_name],
            df2[col2_name]
        )

        # Only proceed if overlap is above minimum threshold (50% by default)
        min_overlap = Config.HIGH_OVERLAP_LLM_MIN_THRESHOLD * 100
        if overlap_pct < min_overlap:
            return None

        # Skip if names already match (will be caught by exact/variation match)
        if col1_name == col2_name:
            return None

        # Skip if normalized names match
        norm1 = col1_profile.get("normalized_name", "")
        norm2 = col2_profile.get("normalized_name", "")
        if norm1 and norm2 and norm1 == norm2:
            return None

        # Skip if name variations overlap (will be caught by variation match)
        variations1 = set(col1_profile.get("name_variations", []))
        variations2 = set(col2_profile.get("name_variations", []))
        if variations1 & variations2:  # Intersection
            return None

        logger.debug(
            f"Checking high overlap ({overlap_pct:.1f}%) with LLM: "
            f"{col1_name} <-> {col2_name}"
        )

        # Prepare data for LLM
        col1_samples = df1[col1_name].dropna().head(10).tolist()
        col2_samples = df2[col2_name].dropna().head(10).tolist()

        # Call LLM to validate semantic relationship
        llm_result = self._ask_llm_relationship_validation(
            file1, col1_name, col1_profile, col1_samples,
            file2, col2_name, col2_profile, col2_samples,
            overlap_pct
        )

        # Check if LLM confirms relationship
        if not llm_result or not llm_result.get("is_related", False):
            logger.debug(f"LLM rejected relationship: {col1_name} <-> {col2_name}")
            return None

        # LLM confidence should be above minimum threshold
        llm_confidence = llm_result.get("confidence_score", 0)
        min_confidence = Config.HIGH_OVERLAP_LLM_MIN_CONFIDENCE * 100
        if llm_confidence < min_confidence:
            logger.debug(
                f"LLM confidence too low ({llm_confidence}% < {min_confidence}%): "
                f"{col1_name} <-> {col2_name}"
            )
            return None

        logger.success(
            f"LLM confirmed relationship ({llm_confidence}%): "
            f"{file1}.{col1_name} <-> {file2}.{col2_name}"
        )

        # Determine relationship type from LLM response
        relationship_type = llm_result.get("relationship_type", "SEMANTIC_MATCH")
        cardinality = llm_result.get("cardinality", "UNKNOWN")

        # Calculate combined confidence (overlap + LLM)
        combined_confidence = int((overlap_pct + llm_confidence) / 2)

        # Determine confidence level
        if combined_confidence >= 80:
            confidence_level = "HIGH"
        elif combined_confidence >= 60:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        return self._create_candidate(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile,
            relationship_type=relationship_type,
            confidence_level=confidence_level,
            confidence_score=combined_confidence,
            detection_method="HIGH_OVERLAP_LLM_VALIDATION",
            overlap_pct=overlap_pct,
            exact_matches=exact_matches,
            cardinality=cardinality,
            transformation_needed=llm_result.get("transformation_needed"),
            requires_llm=False  # Already validated by LLM
        )

    def _ask_llm_relationship_validation(
        self,
        file1: str, col1_name: str, col1_profile: Dict, col1_samples: list,
        file2: str, col2_name: str, col2_profile: Dict, col2_samples: list,
        overlap_pct: float
    ) -> Optional[Dict[str, Any]]:
        """
        Ask LLM to validate if two columns represent a semantic relationship.
        """
        from src.llm_reasoner import LLMReasoner

        try:
            llm_reasoner = LLMReasoner()

            if not llm_reasoner.llm:
                logger.debug("LLM not available for relationship validation")
                return None

            # Build validation request
            candidate = {
                "source": {
                    "file": file1,
                    "column": col1_name,
                    "data_type": col1_profile.get("data_type", "unknown"),
                    "sample_values": col1_samples,
                    "uniqueness": col1_profile.get("unique_percent", 0) / 100,
                    "null_percent": col1_profile.get("null_percent", 0),
                },
                "target": {
                    "file": file2,
                    "column": col2_name,
                    "data_type": col2_profile.get("data_type", "unknown"),
                    "sample_values": col2_samples,
                    "uniqueness": col2_profile.get("unique_percent", 0) / 100,
                    "null_percent": col2_profile.get("null_percent", 0),
                },
                "statistics": {
                    "value_overlap_percent": overlap_pct,
                    "orphans_in_source": 0,
                    "orphans_in_target": 0,
                }
            }

            # Call LLM validator
            result = llm_reasoner.validate_relationship(candidate)

            logger.debug(
                f"LLM validated {col1_name} <-> {col2_name}: "
                f"related={result.get('is_related', False)}, "
                f"confidence={result.get('confidence_score', 0)}%"
            )

            return result

        except Exception as e:
            logger.warning(f"LLM relationship validation failed: {e}")
            return None

    # =========================================================================
    # CATEGORY 3: SEMANTIC SIMILARITY
    # =========================================================================
    
    def _check_semantic_similarity(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict
    ) -> Optional[RelationshipCandidate]:
        """
        Case 2.1: Synonym matching (order_date vs transaction_date)
        Requires LLM validation.
        """
        # Must be same data type
        if col1_profile["data_type"] != col2_profile["data_type"]:
            return None
        
        # Use fuzzy name matching
        name_similarity = fuzzy_match_score(col1_name, col2_name)
        
        if name_similarity < 0.6:
            return None
        
        # Calculate value overlap
        df1 = self.dataframes[file1]
        df2 = self.dataframes[file2]
        
        overlap_pct, exact_matches, _ = calculate_value_overlap(
            df1[col1_name],
            df2[col2_name]
        )
        
        # Need moderate overlap
        if overlap_pct < Config.LOW_CONFIDENCE_OVERLAP_THRESHOLD * 100:
            return None
        
        # Flag for LLM validation
        return self._create_candidate(
            file1, col1_name, col1_profile,
            file2, col2_name, col2_profile,
            relationship_type="SEMANTIC_MATCH",
            confidence_level="MEDIUM" if overlap_pct > 60 else "LOW",
            confidence_score=int(50 + (overlap_pct / 2)),  # 50-100 range
            detection_method="SEMANTIC_SIMILARITY",
            overlap_pct=overlap_pct,
            exact_matches=exact_matches,
            cardinality="UNKNOWN",
            requires_llm=True
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _create_candidate(
        self,
        file1: str, col1_name: str, col1_profile: Dict,
        file2: str, col2_name: str, col2_profile: Dict,
        relationship_type: str,
        confidence_level: str,
        confidence_score: int,
        detection_method: str,
        overlap_pct: float,
        exact_matches: int,
        cardinality: str,
        transformation_needed: Optional[str] = None,
        requires_llm: bool = False
    ) -> RelationshipCandidate:
        """Create a relationship candidate."""
        
        self.relationship_counter += 1
        
        # Calculate orphan records
        df1 = self.dataframes[file1]
        df2 = self.dataframes[file2]
        
        values1 = set(df1[col1_name].dropna().unique())
        values2 = set(df2[col2_name].dropna().unique())
        
        orphans_in_1 = len(values1 - values2)
        orphans_in_2 = len(values2 - values1)
        
        statistics = {
            "value_overlap_percent": round(overlap_pct, 2),
            "exact_matches": exact_matches,
            "fuzzy_matches": 0,
            "orphans_in_source": orphans_in_1,
            "orphans_in_target": orphans_in_2,
            "source_cardinality": col1_profile["cardinality"],
            "target_cardinality": col2_profile["cardinality"],
            "cardinality": cardinality
        }
        
        warnings = []
        
        # Check for data quality issues
        if col1_profile["null_percent"] > Config.MAX_ACCEPTABLE_NULL_PERCENT:
            warnings.append(
                f"Source column has {col1_profile['null_percent']:.1f}% NULL values"
            )
        
        if col2_profile["null_percent"] > Config.MAX_ACCEPTABLE_NULL_PERCENT:
            warnings.append(
                f"Target column has {col2_profile['null_percent']:.1f}% NULL values"
            )
        
        orphan_pct = (orphans_in_1 / len(values1) * 100) if values1 else 0
        if orphan_pct > Config.MAX_ACCEPTABLE_ORPHAN_PERCENT:
            warnings.append(
                f"{orphan_pct:.1f}% orphan records in source"
            )
        
        return RelationshipCandidate(
            relationship_id=f"REL_{self.relationship_counter:03d}",
            source_file=file1,
            source_column=col1_name,
            target_file=file2,
            target_column=col2_name,
            relationship_type=relationship_type,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            detection_method=detection_method,
            statistics=statistics,
            transformation_needed=transformation_needed,
            warnings=warnings,
            requires_llm_validation=requires_llm
        )
