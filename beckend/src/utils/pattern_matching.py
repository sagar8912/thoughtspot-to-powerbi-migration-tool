"""
Pattern matching utilities for relationship detection.
"""

import re
from typing import List, Tuple, Optional
from rapidfuzz import fuzz
import pandas as pd


def fuzzy_match_score(str1: str, str2: str) -> float:
    """
    Calculate fuzzy match score between two strings.
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        float: Similarity score between 0 and 1
    """
    if not str1 or not str2:
        return 0.0
    
    # Use token sort ratio for better matching
    score = fuzz.token_sort_ratio(str1, str2)
    return score / 100.0


def calculate_value_overlap(
    series1: pd.Series,
    series2: pd.Series,
    fuzzy: bool = False
) -> Tuple[float, int, int]:
    """
    Calculate value overlap between two series.
    
    Args:
        series1: First series
        series2: Second series
        fuzzy: Use fuzzy matching for strings
        
    Returns:
        Tuple of (overlap_percent, exact_matches, fuzzy_matches)
    """
    # Get unique values
    values1 = set(series1.dropna().unique())
    values2 = set(series2.dropna().unique())
    
    if not values1 or not values2:
        return 0.0, 0, 0
    
    # Exact matches
    exact_matches = len(values1.intersection(values2))
    
    fuzzy_matches = 0
    
    if fuzzy and series1.dtype == 'object':
        # Fuzzy matching for strings
        unmatched1 = values1 - values2
        unmatched2 = values2 - values1
        
        for val1 in unmatched1:
            for val2 in unmatched2:
                if fuzzy_match_score(str(val1), str(val2)) > 0.85:
                    fuzzy_matches += 1
                    break
    
    # Calculate overlap percentage based on the smaller set
    total_matches = exact_matches + fuzzy_matches
    smaller_set_size = min(len(values1), len(values2))
    
    overlap_percent = (total_matches / smaller_set_size) * 100
    
    return overlap_percent, exact_matches, fuzzy_matches


def detect_format_mismatch(
    series1: pd.Series,
    series2: pd.Series
) -> Optional[dict]:
    """
    Detect if two series have the same values but different formats.
    
    Examples:
        'CUST-001' vs '001'
        'USA' vs 'usa'
        
    Returns:
        dict: Transformation details or None
    """
    sample1 = series1.dropna().head(100).astype(str)
    sample2 = series2.dropna().head(100).astype(str)
    
    if len(sample1) == 0 or len(sample2) == 0:
        return None
    
    # Check case sensitivity
    if sample1.str.lower().equals(sample2.str.lower()):
        return {
            "type": "CASE_MISMATCH",
            "transformation": "LOWER() or UPPER()"
        }
    
    # Check prefix/suffix differences
    # Try to detect common prefixes
    for prefix in ['CUST-', 'PROD-', 'ORD-', 'INV-']:
        stripped = sample1.str.replace(prefix, '', regex=False)
        overlap = len(set(stripped) & set(sample2)) / len(set(sample2))
        if overlap > 0.8:
            return {
                "type": "PREFIX_MISMATCH",
                "transformation": f"STRIP_PREFIX('{prefix}')",
                "prefix": prefix
            }
    
    # Check if one is substring of other
    substring_matches = 0
    for v1 in sample1[:20]:
        for v2 in sample2[:20]:
            if str(v1) in str(v2) or str(v2) in str(v1):
                substring_matches += 1
                break
    
    if substring_matches / len(sample1[:20]) > 0.8:
        return {
            "type": "PARTIAL_MATCH",
            "transformation": "SUBSTRING or EXTRACT"
        }
    
    return None


def detect_date_format(series: pd.Series) -> Optional[str]:
    """
    Detect date format in a string series.
    
    Returns:
        str: Date format string or None
    """
    sample = series.dropna().head(100).astype(str)
    
    if len(sample) == 0:
        return None
    
    # Common date patterns
    date_patterns = [
        (r'^\d{4}-\d{2}-\d{2}$', '%Y-%m-%d'),          # 2023-01-15
        (r'^\d{2}/\d{2}/\d{4}$', '%m/%d/%Y'),          # 01/15/2023
        (r'^\d{2}-\d{2}-\d{4}$', '%d-%m-%Y'),          # 15-01-2023
        (r'^\d{4}/\d{2}/\d{2}$', '%Y/%m/%d'),          # 2023/01/15
        (r'^\d{2}\.\d{2}\.\d{4}$', '%d.%m.%Y'),        # 15.01.2023
    ]
    
    for pattern, fmt in date_patterns:
        matches = sample.str.match(pattern).sum()
        if matches / len(sample) > 0.9:
            return fmt
    
    return None


def extract_prefix_suffix(series: pd.Series) -> dict:
    """
    Extract common prefix and suffix from string series.
    
    Returns:
        dict: {'prefix': str, 'suffix': str, 'has_prefix': bool, 'has_suffix': bool}
    """
    sample = series.dropna().head(100).astype(str)
    
    if len(sample) == 0:
        return {"prefix": "", "suffix": "", "has_prefix": False, "has_suffix": False}
    
    # Get first and last characters
    first_chars = sample.str[0].value_counts()
    
    result = {
        "prefix": "",
        "suffix": "",
        "has_prefix": False,
        "has_suffix": False
    }
    
    # Detect common prefix
    if len(first_chars) > 0:
        most_common_first = first_chars.index[0]
        if first_chars.iloc[0] / len(sample) > 0.9:
            # Try to find full prefix
            for length in range(1, 10):
                prefixes = sample.str[:length].value_counts()
                if len(prefixes) == 1 or (prefixes.iloc[0] / len(sample) > 0.9):
                    result["prefix"] = prefixes.index[0]
                    result["has_prefix"] = True
                else:
                    break
    
    return result


def detect_composite_key_candidates(
    df: pd.DataFrame,
    columns: List[str]
) -> List[Tuple[str, ...]]:
    """
    Detect potential composite key combinations.
    
    Args:
        df: DataFrame
        columns: List of column names to consider
        
    Returns:
        List of tuples representing composite key candidates
    """
    candidates = []
    
    # Try all 2-column combinations
    from itertools import combinations
    
    for col_combo in combinations(columns, 2):
        # Check if combination is unique
        if df[list(col_combo)].duplicated().sum() == 0:
            candidates.append(col_combo)
    
    # Try 3-column combinations if 2-column didn't work
    if not candidates:
        for col_combo in combinations(columns, 3):
            if df[list(col_combo)].duplicated().sum() == 0:
                candidates.append(col_combo)
    
    return candidates
