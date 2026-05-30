"""
Duplicate column detector with multiple detection algorithms.
Detects duplicate columns using exact name match, suffix patterns, content similarity, fuzzy matching, and LLM semantic analysis.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import re
from loguru import logger
from difflib import SequenceMatcher

from src.utils.data_types import normalize_column_name
from src.llm_reasoner import LLMReasoner


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate columns"""
    group_id: str
    detection_type: str  # "exact_name" | "suffix_pattern" | "content_similar" | "fuzzy_name" | "llm_semantic"
    similarity_score: float  # 0-100
    columns: List[str]
    content_identical: List[bool]  # Whether each column has identical content
    sample_comparison: Dict[str, List[Any]]  # Sample values for UI preview
    recommendation: str  # AI-generated recommendation
    metadata: Dict[str, Any] = field(default_factory=dict)


class DuplicateDetector:
    """
    Detects duplicate columns in pandas DataFrames using multiple algorithms.
    """

    def __init__(self, enable_llm: bool = True):
        """
        Initialize duplicate detector.

        Args:
            enable_llm: Enable LLM semantic matching for ambiguous cases
        """
        self.enable_llm = enable_llm
        self.llm_reasoner = LLMReasoner() if enable_llm else None

    def detect_duplicates(
        self,
        df: pd.DataFrame,
        sample_size: int = 1000
    ) -> List[DuplicateGroup]:
        """
        Detect duplicate columns in a DataFrame.

        Args:
            df: DataFrame to analyze
            sample_size: Number of rows to sample for content comparison

        Returns:
            List of DuplicateGroup objects
        """
        logger.info(f"Detecting duplicates in DataFrame with {len(df.columns)} columns")

        all_duplicates = []
        processed_columns = set()

        # Sample DataFrame for performance
        df_sample = df.head(min(sample_size, len(df)))

        # Algorithm 1: Exact name match (after normalization)
        exact_dupes = self._detect_exact_name_duplicates(df_sample, processed_columns)
        all_duplicates.extend(exact_dupes)

        # Algorithm 2: Suffix pattern match
        suffix_dupes = self._detect_suffix_patterns(df_sample, processed_columns)
        all_duplicates.extend(suffix_dupes)

        # Algorithm 3: Content similarity match
        content_dupes = self._detect_content_similarity(df_sample, processed_columns)
        all_duplicates.extend(content_dupes)

        # Algorithm 3.5: LLM Semantic + Overlap (NEW - high confidence duplicates)
        if self.enable_llm and self.llm_reasoner and self.llm_reasoner.llm:
            from src.config import Config
            if Config.ENABLE_SEMANTIC_DUPLICATE_DETECTION:
                semantic_overlap_dupes = self._detect_llm_semantic_with_overlap(df_sample, processed_columns)
                all_duplicates.extend(semantic_overlap_dupes)

        # Algorithm 4: Fuzzy name match
        fuzzy_dupes = self._detect_fuzzy_name_matches(df_sample, processed_columns)
        all_duplicates.extend(fuzzy_dupes)

        # Algorithm 5: LLM semantic match (only for ambiguous cases)
        if self.enable_llm and self.llm_reasoner and self.llm_reasoner.llm:
            llm_dupes = self._detect_llm_semantic_matches(df_sample, processed_columns, all_duplicates)
            all_duplicates.extend(llm_dupes)

        logger.info(f"Found {len(all_duplicates)} duplicate groups")
        return all_duplicates

    def _detect_exact_name_duplicates(
        self,
        df: pd.DataFrame,
        processed_columns: set
    ) -> List[DuplicateGroup]:
        """
        Detect columns with identical normalized names.
        Example: 'Address', 'address', 'ADDRESS' → same group
        """
        groups = []
        name_groups = defaultdict(list)

        # Group columns by normalized name
        for col in df.columns:
            if col not in processed_columns:
                normalized = normalize_column_name(col)
                name_groups[normalized].append(col)

        # Find groups with duplicates
        for normalized_name, columns in name_groups.items():
            if len(columns) > 1:
                # IMPORTANT: Only flag as duplicate if content is also similar
                # Check if at least some columns have identical content
                content_identical = self._check_content_identical(df, columns)

                # Skip if ALL content is different (no identical pairs)
                if not any(content_identical):
                    logger.debug(f"Skipping exact name match for {columns}: same names but ALL content is different")
                    continue

                group_id = f"dup_exact_{len(groups) + 1}"

                # Get sample values
                sample_comparison = self._get_sample_comparison(df, columns)

                # Generate recommendation
                recommendation = self._generate_recommendation(columns, content_identical, "exact_name")

                group = DuplicateGroup(
                    group_id=group_id,
                    detection_type="exact_name",
                    similarity_score=100.0,
                    columns=columns,
                    content_identical=content_identical,
                    sample_comparison=sample_comparison,
                    recommendation=recommendation,
                    metadata={"normalized_name": normalized_name}
                )

                groups.append(group)
                processed_columns.update(columns)

        logger.debug(f"Exact name: Found {len(groups)} duplicate groups")
        return groups

    def _detect_suffix_patterns(
        self,
        df: pd.DataFrame,
        processed_columns: set
    ) -> List[DuplicateGroup]:
        """
        Detect pandas auto-renamed columns with _1, _2 suffixes.
        Example: 'Email', 'Email_1', 'Email_2'
        """
        groups = []
        suffix_pattern = re.compile(r'^(.+?)(_\d+|_copy|\(\d+\))$')
        base_groups = defaultdict(list)

        # Group columns by base name (without suffix)
        for col in df.columns:
            if col not in processed_columns:
                match = suffix_pattern.match(col)
                if match:
                    base_name = match.group(1)
                    base_groups[base_name].append(col)
                else:
                    # Also consider the column as a potential base
                    base_groups[col].append(col)

        # Find suffix patterns
        for base_name, columns in base_groups.items():
            # Check if base exists and has suffixed versions
            if len(columns) > 1 or (base_name in df.columns and any(c != base_name for c in columns)):
                # Collect all related columns (base + suffixed)
                all_cols = [base_name] if base_name in df.columns else []
                all_cols.extend([c for c in columns if c != base_name])

                if len(all_cols) > 1:
                    # IMPORTANT: Only flag as duplicate if content is also similar
                    content_identical = self._check_content_identical(df, all_cols)

                    # Skip if ALL content is different
                    if not any(content_identical):
                        logger.debug(f"Skipping suffix pattern for {all_cols}: same base name but ALL content is different")
                        continue

                    group_id = f"dup_suffix_{len(groups) + 1}"

                    # Get sample values
                    sample_comparison = self._get_sample_comparison(df, all_cols)

                    # Generate recommendation
                    recommendation = self._generate_recommendation(all_cols, content_identical, "suffix_pattern")

                    group = DuplicateGroup(
                        group_id=group_id,
                        detection_type="suffix_pattern",
                        similarity_score=100.0,
                        columns=all_cols,
                        content_identical=content_identical,
                        sample_comparison=sample_comparison,
                        recommendation=recommendation,
                        metadata={"base_name": base_name}
                    )

                    groups.append(group)
                    processed_columns.update(all_cols)

        logger.debug(f"Suffix pattern: Found {len(groups)} duplicate groups")
        return groups

    def _detect_content_similarity(
        self,
        df: pd.DataFrame,
        processed_columns: set,
        threshold: float = 0.95
    ) -> List[DuplicateGroup]:
        """
        Detect columns with highly similar content (95%+ identical values).
        """
        groups = []
        remaining_cols = [c for c in df.columns if c not in processed_columns]

        if len(remaining_cols) < 2:
            return groups

        # Compare all pairs of columns
        compared = set()

        for i, col1 in enumerate(remaining_cols):
            similar_cols = [col1]

            for col2 in remaining_cols[i+1:]:
                pair = tuple(sorted([col1, col2]))
                if pair in compared:
                    continue
                compared.add(pair)

                # Calculate similarity
                similarity = self._calculate_content_similarity(df[col1], df[col2])

                if similarity >= threshold:
                    # IMPORTANT: Check if column names are semantically related
                    # to avoid false positives like "record_id" vs "Agent_ID"
                    # or "total_calls" vs "inbound_calls"
                    if not self._are_column_names_semantically_similar(col1, col2):
                        logger.debug(f"Skipping {col1} vs {col2}: high content similarity ({similarity:.2%}) but semantically different names")
                        continue

                    if col2 not in similar_cols:
                        similar_cols.append(col2)

            if len(similar_cols) > 1:
                group_id = f"dup_content_{len(groups) + 1}"

                # Check content identical
                content_identical = self._check_content_identical(df, similar_cols)

                # Get sample values
                sample_comparison = self._get_sample_comparison(df, similar_cols)

                # Generate recommendation
                recommendation = self._generate_recommendation(similar_cols, content_identical, "content_similar")

                group = DuplicateGroup(
                    group_id=group_id,
                    detection_type="content_similar",
                    similarity_score=threshold * 100,
                    columns=similar_cols,
                    content_identical=content_identical,
                    sample_comparison=sample_comparison,
                    recommendation=recommendation
                )

                groups.append(group)
                processed_columns.update(similar_cols)

        logger.debug(f"Content similarity: Found {len(groups)} duplicate groups")
        return groups

    def _are_column_names_semantically_similar(self, col1: str, col2: str) -> bool:
        """
        Check if two column names are semantically similar enough to be considered duplicates.

        This prevents false positives like:
        - "record_id" vs "Agent_ID" (different entity types)
        - "total_calls" vs "inbound_calls" (different metrics)
        - "CustomerID" vs "OrderID" (different business entities)

        Returns:
            True if names are semantically similar (likely duplicates)
            False if names are semantically different (likely NOT duplicates)
        """
        # Normalize names
        name1 = normalize_column_name(col1)
        name2 = normalize_column_name(col2)

        # Calculate name similarity using Levenshtein distance
        name_similarity = SequenceMatcher(None, name1, name2).ratio()

        # If names are very similar (>70%), they're likely duplicates
        # e.g., "mistake_id" vs "mistakeid", "CustomerName" vs "customer_name"
        if name_similarity >= 0.70:
            return True

        # Extract key words from column names (split by underscore, camelCase, etc.)
        words1 = set(self._extract_column_name_words(col1))
        words2 = set(self._extract_column_name_words(col2))

        # Check word overlap
        common_words = words1.intersection(words2)
        total_words = words1.union(words2)

        if not total_words:
            return False

        word_overlap = len(common_words) / len(total_words)

        # If they share significant words, they might be related
        # e.g., "total_calls" and "inbound_calls" share "calls"
        # BUT we need to check if they have DIFFERENT qualifiers
        unique_words1 = words1 - words2
        unique_words2 = words2 - words1

        # Define words that indicate different metrics/entities
        differentiating_words = {
            'total', 'sum', 'count', 'avg', 'average', 'mean', 'median', 'min', 'max',
            'inbound', 'outbound', 'incoming', 'outgoing',
            'first', 'last', 'start', 'end', 'begin', 'final',
            'primary', 'secondary', 'tertiary',
            'source', 'target', 'destination',
            'customer', 'agent', 'user', 'record', 'order', 'product', 'invoice',
            'id', 'identifier', 'code', 'key', 'number'
        }

        # If one has a differentiating word that the other doesn't, they're different
        for word in unique_words1:
            if word.lower() in differentiating_words:
                logger.debug(f"'{col1}' vs '{col2}': Different metrics detected ('{word}')")
                return False

        for word in unique_words2:
            if word.lower() in differentiating_words:
                logger.debug(f"'{col1}' vs '{col2}': Different metrics detected ('{word}')")
                return False

        # If word overlap is high (>50%) and no differentiating words, likely duplicates
        return word_overlap >= 0.5

    def _extract_column_name_words(self, column_name: str) -> List[str]:
        """Extract individual words from column name (handles snake_case, camelCase, etc.)"""
        # Split by underscores and spaces
        words = re.split(r'[_\s]+', column_name)

        # Split camelCase (e.g., "CustomerID" -> ["Customer", "ID"])
        all_words = []
        for word in words:
            # Insert space before uppercase letters (camelCase splitting)
            spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', word)
            all_words.extend(spaced.split())

        # Filter out empty strings and normalize
        return [w.lower() for w in all_words if w and len(w) > 1]

    def _detect_llm_semantic_with_overlap(
        self,
        df: pd.DataFrame,
        processed_columns: set
    ) -> List[DuplicateGroup]:
        """
        Detect semantically duplicate columns using LLM + overlap threshold.

        This is the NEW semantic duplicate detection that combines:
        - Same/compatible data types
        - High value overlap (>= 80%)
        - LLM semantic validation

        Args:
            df: DataFrame to analyze
            processed_columns: Set of already processed column names

        Returns:
            List of DuplicateGroup objects
        """
        from src.config import Config

        groups = []
        remaining_cols = [col for col in df.columns if col not in processed_columns]

        if len(remaining_cols) < 2:
            return groups

        logger.debug(f"LLM semantic overlap: Checking {len(remaining_cols)} columns")

        # Group columns by compatible data types
        type_groups = self._group_by_compatible_types(df, remaining_cols)

        for type_name, cols in type_groups.items():
            if len(cols) < 2:
                continue

            # Check all pairs in this type group
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    col1, col2 = cols[i], cols[j]

                    # Calculate value overlap
                    overlap_percent = self._calculate_content_similarity(
                        df[col1], df[col2]
                    )

                    # Only proceed if overlap meets threshold
                    if overlap_percent < Config.SEMANTIC_DUPLICATE_MIN_OVERLAP:
                        continue

                    # Prepare data for LLM
                    col1_data = {
                        'name': col1,
                        'data_type': str(df[col1].dtype),
                        'samples': df[col1].dropna().head(10).tolist(),
                        'overlap_percent': overlap_percent * 100
                    }

                    col2_data = {
                        'name': col2,
                        'data_type': str(df[col2].dtype),
                        'samples': df[col2].dropna().head(10).tolist()
                    }

                    # Call LLM to check semantic match
                    llm_result = self.llm_reasoner.check_semantic_duplicate(
                        col1_data, col2_data
                    )

                    # Check if LLM confirms semantic match with high confidence
                    if (llm_result.get('semantic_match', False) and
                        llm_result.get('confidence', 0) >= Config.SEMANTIC_DUPLICATE_MIN_CONFIDENCE * 100):

                        # Calculate combined similarity score
                        similarity_score = (overlap_percent * 100 + llm_result['confidence']) / 2

                        # Check content identity
                        are_identical = self._check_exact_content_match(df[col1], df[col2])

                        group = DuplicateGroup(
                            group_id=f"dup_semantic_overlap_{len(groups) + 1}",
                            detection_type="semantic_overlap",
                            similarity_score=similarity_score,
                            columns=[col1, col2],
                            content_identical=[True, are_identical],
                            sample_comparison={
                                col1: df[col1].dropna().head(5).tolist(),
                                col2: df[col2].dropna().head(5).tolist()
                            },
                            recommendation=llm_result.get('recommendation', 'Keep first, review second'),
                            metadata={
                                'llm_reasoning': llm_result.get('reasoning', ''),
                                'overlap_percent': overlap_percent * 100,
                                'llm_confidence': llm_result['confidence']
                            }
                        )

                        groups.append(group)
                        processed_columns.update([col1, col2])

                        logger.info(f"Semantic duplicate found: {col1} <-> {col2} (overlap: {overlap_percent*100:.1f}%, LLM confidence: {llm_result['confidence']}%)")

        logger.debug(f"LLM semantic overlap: Found {len(groups)} duplicate groups")
        return groups

    def _group_by_compatible_types(
        self,
        df: pd.DataFrame,
        columns: List[str]
    ) -> Dict[str, List[str]]:
        """Group columns by compatible data types to reduce unnecessary LLM calls."""
        type_groups = defaultdict(list)

        for col in columns:
            dtype = df[col].dtype

            # Categorize into broad type groups
            if pd.api.types.is_numeric_dtype(dtype):
                type_groups['numeric'].append(col)
            elif pd.api.types.is_string_dtype(dtype) or pd.api.types.is_object_dtype(dtype):
                type_groups['string'].append(col)
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                type_groups['datetime'].append(col)
            else:
                type_groups['other'].append(col)

        return dict(type_groups)

    def _detect_fuzzy_name_matches(
        self,
        df: pd.DataFrame,
        processed_columns: set,
        threshold: float = 0.85
    ) -> List[DuplicateGroup]:
        """
        Detect columns with similar names using Levenshtein distance.
        Example: 'Customer_Name' vs 'CustomerName', 'Email' vs 'E-mail'
        """
        groups = []
        remaining_cols = [c for c in df.columns if c not in processed_columns]

        if len(remaining_cols) < 2:
            return groups

        compared = set()

        for i, col1 in enumerate(remaining_cols):
            similar_cols = [col1]

            for col2 in remaining_cols[i+1:]:
                pair = tuple(sorted([col1, col2]))
                if pair in compared:
                    continue
                compared.add(pair)

                # Calculate name similarity
                similarity = SequenceMatcher(None, col1.lower(), col2.lower()).ratio()

                if similarity >= threshold:
                    if col2 not in similar_cols:
                        similar_cols.append(col2)

            if len(similar_cols) > 1:
                # IMPORTANT: Only flag as duplicate if content is also similar
                content_identical = self._check_content_identical(df, similar_cols)

                # Skip if ALL content is different
                if not any(content_identical):
                    logger.debug(f"Skipping fuzzy name match for {similar_cols}: similar names but ALL content is different")
                    continue

                group_id = f"dup_fuzzy_{len(groups) + 1}"

                # Get sample values
                sample_comparison = self._get_sample_comparison(df, similar_cols)

                # Calculate average similarity
                avg_similarity = 0
                count = 0
                for j in range(len(similar_cols)):
                    for k in range(j+1, len(similar_cols)):
                        avg_similarity += SequenceMatcher(None, similar_cols[j].lower(), similar_cols[k].lower()).ratio()
                        count += 1
                avg_similarity = (avg_similarity / count * 100) if count > 0 else threshold * 100

                # Generate recommendation
                recommendation = self._generate_recommendation(similar_cols, content_identical, "fuzzy_name")

                group = DuplicateGroup(
                    group_id=group_id,
                    detection_type="fuzzy_name",
                    similarity_score=avg_similarity,
                    columns=similar_cols,
                    content_identical=content_identical,
                    sample_comparison=sample_comparison,
                    recommendation=recommendation
                )

                groups.append(group)
                processed_columns.update(similar_cols)

        logger.debug(f"Fuzzy name: Found {len(groups)} duplicate groups")
        return groups

    def _detect_llm_semantic_matches(
        self,
        df: pd.DataFrame,
        processed_columns: set,
        existing_groups: List[DuplicateGroup]
    ) -> List[DuplicateGroup]:
        """
        Use LLM to detect semantically duplicate columns.
        Only runs on ambiguous cases (columns with 60-90% similarity).
        Example: 'Order_Date' vs 'Purchase_Date'
        """
        groups = []
        remaining_cols = [c for c in df.columns if c not in processed_columns]

        if len(remaining_cols) < 2:
            return groups

        # Find ambiguous pairs (moderate similarity in name or content)
        ambiguous_pairs = []
        compared = set()

        for i, col1 in enumerate(remaining_cols):
            for col2 in remaining_cols[i+1:]:
                pair = tuple(sorted([col1, col2]))
                if pair in compared:
                    continue
                compared.add(pair)

                # Check name similarity
                name_sim = SequenceMatcher(None, col1.lower(), col2.lower()).ratio()

                # Check content similarity
                content_sim = self._calculate_content_similarity(df[col1], df[col2])

                # Ambiguous if 60-90% similar
                if 0.6 <= name_sim <= 0.9 or 0.6 <= content_sim <= 0.9:
                    ambiguous_pairs.append((col1, col2, max(name_sim, content_sim)))

        # Limit LLM calls to top 10 most ambiguous pairs
        ambiguous_pairs = sorted(ambiguous_pairs, key=lambda x: x[2], reverse=True)[:10]

        logger.info(f"Found {len(ambiguous_pairs)} ambiguous column pairs for LLM analysis")

        # Use LLM to analyze each pair
        for col1, col2, similarity in ambiguous_pairs:
            try:
                is_duplicate, confidence, reasoning = self._llm_check_semantic_duplicate(
                    df, col1, col2
                )

                if is_duplicate and confidence >= 0.7:
                    group_id = f"dup_llm_{len(groups) + 1}"

                    similar_cols = [col1, col2]
                    content_identical = self._check_content_identical(df, similar_cols)
                    sample_comparison = self._get_sample_comparison(df, similar_cols)

                    recommendation = f"LLM analysis: {reasoning}"

                    group = DuplicateGroup(
                        group_id=group_id,
                        detection_type="llm_semantic",
                        similarity_score=confidence * 100,
                        columns=similar_cols,
                        content_identical=content_identical,
                        sample_comparison=sample_comparison,
                        recommendation=recommendation,
                        metadata={"llm_reasoning": reasoning}
                    )

                    groups.append(group)
                    processed_columns.update(similar_cols)

            except Exception as e:
                logger.warning(f"LLM analysis failed for {col1} vs {col2}: {e}")
                continue

        logger.debug(f"LLM semantic: Found {len(groups)} duplicate groups")
        return groups

    def _llm_check_semantic_duplicate(
        self,
        df: pd.DataFrame,
        col1: str,
        col2: str
    ) -> Tuple[bool, float, str]:
        """
        Use LLM to check if two columns are semantically duplicate.

        Returns:
            (is_duplicate, confidence, reasoning)
        """
        # Get sample values
        samples1 = df[col1].dropna().head(5).tolist()
        samples2 = df[col2].dropna().head(5).tolist()

        prompt = f"""
Analyze if these two columns are semantically duplicate (same meaning, just different naming).

Column 1: '{col1}'
Sample values: {samples1}

Column 2: '{col2}'
Sample values: {samples2}

Answer in this format:
DUPLICATE: yes/no
CONFIDENCE: 0.0-1.0
REASONING: brief explanation

Consider:
- Do they represent the same data/concept?
- Are the values similar in meaning?
- Would keeping both columns be redundant?
"""

        try:
            from langchain_core.messages import HumanMessage
            response = self.llm_reasoner.llm.invoke([HumanMessage(content=prompt)])
            result = response.content.strip()

            # Parse response
            is_duplicate = "yes" in result.split("DUPLICATE:")[1].split("\n")[0].lower()
            confidence_str = result.split("CONFIDENCE:")[1].split("\n")[0].strip()
            confidence = float(re.search(r'[\d.]+', confidence_str).group())
            reasoning = result.split("REASONING:")[1].strip()

            return is_duplicate, confidence, reasoning

        except Exception as e:
            logger.error(f"LLM parsing error: {e}")
            return False, 0.0, "LLM analysis failed"

    def _calculate_content_similarity(self, series1: pd.Series, series2: pd.Series) -> float:
        """
        Calculate content similarity between two series.

        Returns:
            Similarity score 0.0-1.0
        """
        # Drop NaN values
        s1 = series1.dropna()
        s2 = series2.dropna()

        if len(s1) == 0 or len(s2) == 0:
            return 0.0

        # Align by index
        common_idx = s1.index.intersection(s2.index)
        if len(common_idx) == 0:
            return 0.0

        s1_aligned = s1.loc[common_idx]
        s2_aligned = s2.loc[common_idx]

        # Check if both are numeric
        if pd.api.types.is_numeric_dtype(s1_aligned) and pd.api.types.is_numeric_dtype(s2_aligned):
            # IMPORTANT: Use value matching, NOT correlation
            # Correlation can show high similarity for columns with DIFFERENT values
            # (e.g., inbound_calls=[75,34,46] vs outbound_calls=[12,14,19] might correlate)

            # Instead, check how many values are actually identical or very close
            # For exact duplicates, we want the actual values to match
            matches = 0
            for v1, v2 in zip(s1_aligned, s2_aligned):
                # Consider values matching if they're equal or within 0.1% tolerance
                if abs(v1 - v2) < 0.001 * max(abs(v1), abs(v2), 1):
                    matches += 1

            return matches / len(s1_aligned)

        # For string/object columns, use Jaccard similarity
        set1 = set(s1_aligned.astype(str))
        set2 = set(s2_aligned.astype(str))

        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        return intersection / union if union > 0 else 0.0

    def _check_content_identical(self, df: pd.DataFrame, columns: List[str]) -> List[bool]:
        """
        Check if each column's content is identical to the first column.

        Returns:
            List of booleans, one for each column
        """
        if len(columns) == 0:
            return []

        base_col = df[columns[0]]
        identical = [True]  # First column is always identical to itself

        for col in columns[1:]:
            # Compare values
            is_identical = df[col].equals(base_col)
            identical.append(is_identical)

        return identical

    def _get_sample_comparison(self, df: pd.DataFrame, columns: List[str], n: int = 5) -> Dict[str, List[Any]]:
        """
        Get sample values from each column for UI preview.

        Returns:
            Dict mapping column name to list of sample values
        """
        samples = {}

        for col in columns:
            # Get non-null values
            non_null = df[col].dropna()

            # Get first n values
            sample_values = non_null.head(n).tolist()

            # Convert to JSON-serializable types
            sample_values = [
                str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
                for v in sample_values
            ]

            samples[col] = sample_values

        return samples

    def _generate_recommendation(
        self,
        columns: List[str],
        content_identical: List[bool],
        detection_type: str
    ) -> str:
        """
        Generate a recommendation for handling duplicates.
        """
        if len(columns) == 0:
            return "No columns to process"

        # Count identical content
        identical_count = sum(content_identical)

        if identical_count == len(columns):
            # All columns have identical content
            keep = columns[0]
            delete = columns[1:]
            return f"Keep '{keep}', delete {', '.join(repr(c) for c in delete)} (identical content)"

        elif identical_count > 1:
            # Some columns have identical content
            keep = columns[0]
            identical_cols = [columns[i] for i, is_id in enumerate(content_identical) if is_id and i > 0]
            different_cols = [columns[i] for i, is_id in enumerate(content_identical) if not is_id and i > 0]

            msg = f"Keep '{keep}'"
            if identical_cols:
                msg += f", delete {', '.join(repr(c) for c in identical_cols)} (identical)"
            if different_cols:
                msg += f", review {', '.join(repr(c) for c in different_cols)} (different content)"
            return msg

        else:
            # No identical content
            return f"Review all columns: {', '.join(repr(c) for c in columns)} (similar names but different content)"
