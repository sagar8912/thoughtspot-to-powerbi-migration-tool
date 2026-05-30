"""
Data type inference and normalization utilities.
"""

import pandas as pd
import numpy as np
from typing import Any, List, Optional
import re


class DataTypeInferrer:
    """Infer and normalize data types from pandas columns."""
    
    @staticmethod
    def infer_type(series: pd.Series) -> str:
        """
        Infer semantic data type from pandas series.
        
        Returns:
            str: One of 'int', 'float', 'string', 'datetime', 'boolean', 'mixed'
        """
        # Handle empty series
        if len(series) == 0 or series.isna().all():
            return "unknown"
        
        # Drop NaN values for type inference
        non_null = series.dropna()
        
        if len(non_null) == 0:
            return "unknown"
        
        # Check pandas dtype first
        dtype = series.dtype
        
        # Integer
        if pd.api.types.is_integer_dtype(dtype):
            return "int"
        
        # Float
        if pd.api.types.is_float_dtype(dtype):
            # Check if all values are actually integers
            if non_null.apply(lambda x: float(x).is_integer()).all():
                return "int"
            return "float"
        
        # Boolean
        if pd.api.types.is_bool_dtype(dtype):
            return "boolean"
        
        # Datetime
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "datetime"
        
        # String/Object - need deeper inspection
        if pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(dtype):
            return DataTypeInferrer._infer_object_type(non_null)
        
        return "mixed"
    
    @staticmethod
    def _infer_object_type(series: pd.Series) -> str:
        """Infer type for object/string columns."""
        sample = series.head(min(100, len(series)))
        
        # Try to parse as datetime
        try:
            pd.to_datetime(sample, errors='raise')
            return "datetime"
        except (ValueError, TypeError):
            pass
        
        # Try to parse as numeric
        numeric_count = 0
        for val in sample:
            try:
                float(str(val))
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        
        # If >90% can be parsed as numeric, consider it numeric
        if numeric_count / len(sample) > 0.9:
            # Check if integers
            try:
                int_vals = sample.apply(lambda x: float(str(x)))
                if int_vals.apply(lambda x: x.is_integer()).all():
                    return "int"
                return "float"
            except:
                pass
        
        return "string"
    
    @staticmethod
    def looks_like_id(series: pd.Series, column_name: str) -> bool:
        """Check if column looks like an ID/key."""
        name_lower = column_name.lower()
        
        # Check name patterns
        id_patterns = ['id', 'key', 'code', 'number', '_no', '_num']
        if any(pattern in name_lower for pattern in id_patterns):
            return True
        
        # Check values
        if len(series) == 0:
            return False
        
        sample = series.dropna().head(100).astype(str)
        
        # Check for sequential numbers
        if DataTypeInferrer.is_sequential(series):
            return True
        
        # Check for ID-like patterns
        id_regex_patterns = [
            r'^[A-Z]{2,4}\d+$',  # CUST12345
            r'^\d{4,}$',          # 123456
            r'^[A-Z]-\d+$',       # A-12345
        ]
        
        for pattern in id_regex_patterns:
            matches = sample.str.match(pattern).sum()
            if matches / len(sample) > 0.8:
                return True
        
        return False
    
    @staticmethod
    def is_sequential(series: pd.Series) -> bool:
        """Check if numeric series is sequential (1, 2, 3, ...)."""
        if len(series) == 0:
            return False
        
        try:
            numeric = pd.to_numeric(series.dropna(), errors='coerce')
            if numeric.isna().all():
                return False
            
            numeric = numeric.dropna().sort_values()
            
            if len(numeric) < 2:
                return False
            
            # Check if differences are all 1
            diffs = numeric.diff().dropna()
            return (diffs == 1).sum() / len(diffs) > 0.95
        except:
            return False
    
    @staticmethod
    def extract_pattern(series: pd.Series) -> Optional[str]:
        """
        Extract regex pattern from string series.
        
        Returns:
            str: Regex pattern or None
        """
        if len(series) == 0:
            return None
        
        sample = series.dropna().head(100).astype(str)
        
        if len(sample) == 0:
            return None
        
        # Get first value as template
        template = sample.iloc[0]
        
        # Build pattern from template
        pattern_parts = []
        for char in template:
            if char.isdigit():
                pattern_parts.append(r'\d')
            elif char.isalpha():
                if char.isupper():
                    pattern_parts.append(r'[A-Z]')
                else:
                    pattern_parts.append(r'[a-z]')
            else:
                pattern_parts.append(re.escape(char))
        
        pattern = ''.join(pattern_parts)
        
        # Test pattern against sample
        try:
            matches = sample.str.match(f'^{pattern}$').sum()
            if matches / len(sample) > 0.8:
                return pattern
        except:
            pass
        
        return None


def normalize_column_name(name: str) -> str:
    """
    Normalize column name for comparison.
    
    Examples:
        'CustomerID' -> 'customerid'
        'customer_id' -> 'customerid'
        'Customer ID' -> 'customerid'
    """
    return name.lower().replace('_', '').replace(' ', '').replace('-', '')


def get_common_abbreviations() -> dict:
    """Get dictionary of common abbreviations."""
    return {
        "id": ["identifier", "id", "key"],
        "cust": ["customer", "cust", "client"],
        "prod": ["product", "prod", "item"],
        "qty": ["quantity", "qty", "count", "amount"],
        "amt": ["amount", "amt", "value", "total"],
        "dt": ["date", "dt", "day", "time"],
        "loc": ["location", "loc", "place", "site"],
        "cat": ["category", "cat", "type", "class"],
        "desc": ["description", "desc", "details"],
        "num": ["number", "num", "no", "#"],
        "addr": ["address", "addr"],
        "tel": ["telephone", "tel", "phone"],
        "email": ["email", "mail"],
        "acct": ["account", "acct"],
        "dept": ["department", "dept"],
        "mgr": ["manager", "mgr"],
        "emp": ["employee", "emp"],
        "org": ["organization", "org", "company"],
    }


def expand_abbreviation(name: str) -> List[str]:
    """
    Expand abbreviations in column name to possible full forms.

    Examples:
        'cust_id' -> ['custid', 'customerid', 'clientid', ...]
        'prod_id' -> ['prodid', 'productid', 'itemid', ...]
        'ProductID' -> ['productid'] (already expanded, no change)
    """
    import re

    abbrevs = get_common_abbreviations()
    name_lower = name.lower()

    # Normalize: remove underscores, spaces, dashes for comparison
    normalized = normalize_column_name(name_lower)
    expansions = [normalized]

    # Split name into word parts (by underscore, space, dash, or camelCase)
    # This creates tokens like: "prod_id" -> ["prod", "id"]
    #                           "ProductID" -> ["product", "id"]
    parts = re.split(r'[_\s-]+', name_lower)

    # Also handle camelCase: "ProductID" -> ["product", "id"]
    split_parts = []
    for part in parts:
        # Split by camelCase boundaries (lowercase followed by uppercase)
        subparts = re.sub(r'([a-z])([A-Z])', r'\1 \2', part).split()
        split_parts.extend([p.lower() for p in subparts])

    # Now expand each part if it's an abbreviation
    for abbrev, full_forms in abbrevs.items():
        if abbrev in split_parts:
            # Replace the abbreviation with each possible expansion
            for full_form in full_forms:
                if full_form != abbrev:
                    # Create new parts list with expansion
                    new_parts = [full_form if p == abbrev else p for p in split_parts]
                    # Join and normalize
                    expanded = ''.join(new_parts)
                    if expanded not in expansions:
                        expansions.append(expanded)

    return expansions
