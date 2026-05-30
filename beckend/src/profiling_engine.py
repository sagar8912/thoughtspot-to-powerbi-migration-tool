"""
Deep Data Profiling Engine.
Performs exhaustive deterministic profiling - the foundation of relationship discovery.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from loguru import logger
from tqdm import tqdm

from src.config import Config
from src.utils.data_types import (
    DataTypeInferrer,
    normalize_column_name,
    expand_abbreviation
)
from src.utils.pattern_matching import (
    extract_prefix_suffix,
    detect_date_format,
    detect_composite_key_candidates
)


class ProfilingEngine:
    """
    Deep data profiling engine that generates comprehensive metadata
    for each column across all files.
    """
    
    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.type_inferrer = DataTypeInferrer()
    
    def profile_all_files(
        self,
        dataframes: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Profile all files and generate comprehensive metadata.
        
        Args:
            dataframes: Dictionary mapping file paths to DataFrames
            
        Returns:
            Dictionary of file profiles
        """
        logger.info("Starting deep data profiling...")
        
        for file_path, df in tqdm(dataframes.items(), desc="Profiling files"):
            self.profiles[file_path] = self.profile_dataframe(df, file_path)
        
        logger.success(f"Profiled {len(self.profiles)} files")
        return self.profiles
    
    def _sanitize_for_json(self, obj):
        """Convert numpy/pandas types to native Python types for JSON serialization."""
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._sanitize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_for_json(item) for item in obj]
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    def profile_dataframe(
        self,
        df: pd.DataFrame,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Profile a single DataFrame.
        
        Args:
            df: DataFrame to profile
            file_path: Source file path
            
        Returns:
            Dictionary containing file-level and column-level profiles
        """
        from pathlib import Path
        
        file_profile = {
            "file_name": Path(file_path).name,
            "file_path": file_path,
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / (1024 * 1024),
            "columns": {}
        }
        
        # Profile each column
        for column in tqdm(df.columns, desc=f"  Columns", leave=False):
            file_profile["columns"][column] = self._profile_column(
                df[column],
                column,
                file_path
            )
        
        # Detect composite keys
        file_profile["composite_key_candidates"] = self._detect_composite_keys(df)
        
        return file_profile
    
    def _profile_column(
        self,
        series: pd.Series,
        column_name: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Profile a single column with comprehensive metadata.
        
        Args:
            series: Pandas series to profile
            column_name: Name of the column
            file_path: Source file path
            
        Returns:
            Dictionary containing column profile
        """
        profile = {}
        
        # =====================================================================
        # 1. BASIC METADATA
        # =====================================================================
        profile["name"] = column_name
        profile["normalized_name"] = normalize_column_name(column_name)
        profile["name_variations"] = expand_abbreviation(column_name)
        profile["data_type"] = self.type_inferrer.infer_type(series)
        profile["pandas_dtype"] = str(series.dtype)
        profile["row_count"] = len(series)
        
        # =====================================================================
        # 2. STATISTICAL PROFILE
        # =====================================================================
        
        # Completeness
        null_count = series.isna().sum()
        profile["null_count"] = int(null_count)
        profile["null_percent"] = float((null_count / len(series)) * 100) if len(series) > 0 else 0.0
        
        # For string columns, also count empty strings
        if profile["data_type"] == "string":
            empty_count = (series == "").sum()
            profile["empty_string_count"] = int(empty_count)
            profile["empty_string_percent"] = float((empty_count / len(series)) * 100) if len(series) > 0 else 0.0
        
        # Uniqueness
        non_null = series.dropna()
        unique_count = non_null.nunique()
        profile["unique_count"] = int(unique_count)
        profile["cardinality"] = int(unique_count)
        profile["unique_percent"] = float((unique_count / len(non_null)) * 100) if len(non_null) > 0 else 0.0
        
        # Duplicate info
        profile["has_duplicates"] = unique_count < len(non_null)
        profile["duplicate_count"] = int(len(non_null) - unique_count)
        
        # =====================================================================
        # 3. VALUE DISTRIBUTION
        # =====================================================================
        
        # Sample values (for JSON output)
        if Config.INCLUDE_SAMPLE_DATA:
            sample_values = non_null.head(Config.SAMPLE_VALUES_COUNT).tolist()
            profile["sample_values"] = sample_values
            profile["sample_strings"] = [str(v) for v in sample_values]
        
        # Top values with frequency
        value_counts = non_null.value_counts()
        top_values = value_counts.head(Config.TOP_VALUES_COUNT)
        profile["top_values"] = {
            str(k): int(v) for k, v in top_values.items()
        }
        
        # For sample data output, include distribution of top 5
        if Config.INCLUDE_SAMPLE_DATA:
            profile["value_distribution"] = {
                str(k): int(v) for k, v in value_counts.head(5).items()
            }
        
        # =====================================================================
        # 4. TYPE-SPECIFIC STATISTICS
        # =====================================================================
        
        if profile["data_type"] in ["int", "float"]:
            # Numeric statistics
            profile["min"] = float(non_null.min()) if len(non_null) > 0 else None
            profile["max"] = float(non_null.max()) if len(non_null) > 0 else None
            profile["mean"] = float(non_null.mean()) if len(non_null) > 0 else None
            profile["median"] = float(non_null.median()) if len(non_null) > 0 else None
            profile["std"] = float(non_null.std()) if len(non_null) > 1 else None
            
            # Check if sequential (convert to native Python bool)
            profile["is_sequential"] = bool(self.type_inferrer.is_sequential(series))
            
        elif profile["data_type"] == "string":
            # String statistics
            str_series = non_null.astype(str)
            lengths = str_series.str.len()
            profile["min_length"] = int(lengths.min()) if len(lengths) > 0 else None
            profile["max_length"] = int(lengths.max()) if len(lengths) > 0 else None
            profile["avg_length"] = float(lengths.mean()) if len(lengths) > 0 else None
            
        elif profile["data_type"] == "datetime":
            # DateTime statistics
            try:
                dt_series = pd.to_datetime(non_null, errors='coerce')
                dt_series = dt_series.dropna()
                if len(dt_series) > 0:
                    profile["min_date"] = str(dt_series.min())
                    profile["max_date"] = str(dt_series.max())
                    profile["date_range_days"] = int((dt_series.max() - dt_series.min()).days)
            except:
                pass
        
        # =====================================================================
        # 5. PATTERN ANALYSIS
        # =====================================================================
        
        pattern_info = {}
        
        if profile["data_type"] == "string":
            # Extract patterns
            extracted_pattern = self.type_inferrer.extract_pattern(non_null)
            if extracted_pattern:
                pattern_info["regex_pattern"] = extracted_pattern
            
            # Prefix/suffix analysis
            prefix_suffix = extract_prefix_suffix(non_null)
            pattern_info.update(prefix_suffix)
            
            # Case pattern
            sample_str = non_null.head(100).astype(str)
            if sample_str.str.isupper().all():
                pattern_info["case_pattern"] = "UPPER"
            elif sample_str.str.islower().all():
                pattern_info["case_pattern"] = "LOWER"
            elif sample_str.str.istitle().all():
                pattern_info["case_pattern"] = "TITLE"
            else:
                pattern_info["case_pattern"] = "MIXED"
            
            # Detect date format if looks like date
            date_format = detect_date_format(non_null)
            if date_format:
                pattern_info["date_format"] = date_format
        
        elif profile["data_type"] in ["int", "float"]:
            # Numeric patterns
            if profile["is_sequential"]:
                pattern_info["pattern_type"] = "SEQUENTIAL"
            elif profile["unique_percent"] > 95:
                pattern_info["pattern_type"] = "UNIQUE_NUMERIC"
            else:
                pattern_info["pattern_type"] = "NON_UNIQUE_NUMERIC"
        
        profile["pattern_analysis"] = pattern_info
        
        # =====================================================================
        # 6. KEY CHARACTERISTICS
        # =====================================================================
        
        key_features = {}
        
        # Is unique?
        key_features["is_unique"] = profile["unique_percent"] >= 99.9
        key_features["is_mostly_unique"] = profile["unique_percent"] >= Config.UNIQUE_THRESHOLD_FOR_PK
        
        # Primary key candidate
        key_features["primary_key_candidate"] = (
            key_features["is_unique"] and
            profile["null_percent"] < 1.0 and
            profile["cardinality"] >= Config.MIN_CARDINALITY_FOR_KEY
        )
        
        # Foreign key candidate
        key_features["foreign_key_candidate"] = (
            not key_features["is_unique"] and
            profile["unique_percent"] >= Config.UNIQUE_THRESHOLD_FOR_FK and
            profile["cardinality"] >= Config.MIN_CARDINALITY_FOR_KEY
        )
        
        # Natural vs surrogate key
        if profile["data_type"] == "int" and profile.get("is_sequential"):
            key_features["surrogate_key"] = True
            key_features["natural_key"] = False
        elif self.type_inferrer.looks_like_id(series, column_name):
            key_features["surrogate_key"] = False
            key_features["natural_key"] = True
        else:
            key_features["surrogate_key"] = False
            key_features["natural_key"] = False
        
        profile["key_features"] = key_features
        
        # =====================================================================
        # 7. SEMANTIC HINTS (for LLM)
        # =====================================================================
        
        semantic_hints = {}
        
        # Column name tokens
        tokens = column_name.lower().replace('_', ' ').replace('-', ' ').split()
        semantic_hints["column_name_tokens"] = tokens
        
        # Inferred entity
        if 'customer' in tokens or 'client' in tokens:
            semantic_hints["likely_entity"] = "Customer"
        elif 'product' in tokens or 'item' in tokens:
            semantic_hints["likely_entity"] = "Product"
        elif 'order' in tokens:
            semantic_hints["likely_entity"] = "Order"
        elif 'transaction' in tokens:
            semantic_hints["likely_entity"] = "Transaction"
        else:
            semantic_hints["likely_entity"] = "Unknown"
        
        # Looks like specific data types
        semantic_hints["looks_like_id"] = self.type_inferrer.looks_like_id(series, column_name)
        semantic_hints["looks_like_email"] = any('email' in t or 'mail' in t for t in tokens)
        semantic_hints["looks_like_phone"] = any('phone' in t or 'tel' in t for t in tokens)
        semantic_hints["looks_like_address"] = any('address' in t or 'addr' in t for t in tokens)
        semantic_hints["looks_like_code"] = any('code' in t for t in tokens)
        semantic_hints["looks_like_name"] = any('name' in t for t in tokens)
        
        profile["semantic_hints"] = semantic_hints
        
        # Sanitize all values for JSON serialization
        return self._sanitize_for_json(profile)
    
    def _detect_composite_keys(self, df: pd.DataFrame) -> List[List[str]]:
        """
        Detect potential composite key combinations.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            List of column combinations that form composite keys
        """
        # Only consider columns with moderate uniqueness
        candidate_cols = []
        for col in df.columns:
            uniqueness = df[col].nunique() / len(df)
            if 0.1 < uniqueness < 0.95:  # Not too unique, not too common
                candidate_cols.append(col)
        
        if len(candidate_cols) < 2:
            return []
        
        # Detect composite keys
        composite_keys = detect_composite_key_candidates(df, candidate_cols[:10])  # Limit to 10 to avoid explosion
        
        return [list(combo) for combo in composite_keys]
    
    def get_cross_file_analysis(self) -> Dict[str, Any]:
        """
        Analyze columns across all files to find potential relationships.
        
        Returns:
            Dictionary mapping normalized column names to files containing them
        """
        column_index = {}
        
        for file_path, file_profile in self.profiles.items():
            for column_name, column_profile in file_profile["columns"].items():
                normalized = column_profile["normalized_name"]
                
                if normalized not in column_index:
                    column_index[normalized] = []
                
                column_index[normalized].append({
                    "file": file_path,
                    "original_name": column_name,
                    "data_type": column_profile["data_type"],
                    "cardinality": column_profile["cardinality"],
                    "is_pk_candidate": column_profile["key_features"]["primary_key_candidate"],
                    "is_fk_candidate": column_profile["key_features"]["foreign_key_candidate"]
                })
        
        # Filter to only columns that appear in multiple files
        cross_file_columns = {
            k: v for k, v in column_index.items()
            if len(v) > 1
        }
        
        return cross_file_columns
