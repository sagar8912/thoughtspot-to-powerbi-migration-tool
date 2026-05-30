"""
Excel file loader and validator.
Handles loading Excel files with robust error handling and validation.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
import openpyxl
from src.config import Config


class ExcelLoader:
    """Load and validate Excel files."""
    
    def __init__(self):
        self.loaded_files: Dict[str, pd.DataFrame] = {}
        self.file_metadata: Dict[str, dict] = {}
    
    def load_files(self, file_paths: List[str]) -> Dict[str, pd.DataFrame]:
        """
        Load multiple Excel files.
        
        Args:
            file_paths: List of paths to Excel files
            
        Returns:
            Dict mapping file paths to DataFrames
            
        Raises:
            ValueError: If file count exceeds limit or files are invalid
        """
        logger.info(f"Loading {len(file_paths)} Excel files...")
        
        # Validate file count
        if len(file_paths) > Config.MAX_FILES_LIMIT:
            raise ValueError(
                f"File count ({len(file_paths)}) exceeds maximum limit ({Config.MAX_FILES_LIMIT})"
            )
        
        # Load each file
        for file_path in file_paths:
            try:
                df = self._load_single_file(file_path)
                if df is not None:
                    self.loaded_files[file_path] = df
                    logger.success(f"✓ Loaded {Path(file_path).name}: {len(df):,} rows, {len(df.columns)} columns")
            except Exception as e:
                logger.error(f"✗ Failed to load {Path(file_path).name}: {e}")
                raise
        
        if not self.loaded_files:
            raise ValueError("No files were successfully loaded")
        
        logger.info(f"Successfully loaded {len(self.loaded_files)} files")
        return self.loaded_files
    
    def _load_single_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Load a single Excel file with validation.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            DataFrame or None if file is invalid
        """
        path = Path(file_path)
        
        # Validate file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file extension
        valid_extensions = ['.xlsx', '.xls', '.xlsm', '.csv']
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Invalid file extension: {path.suffix}. Must be one of {valid_extensions}")
        
        # Validate file size (warn if very large)
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > 100:
            logger.warning(f"Large file detected: {file_size_mb:.1f} MB. Processing may be slow.")
        
        # Load based on file type
        if path.suffix.lower() == '.csv':
            return self._load_csv(file_path)
        else:
            return self._load_excel(file_path)
    
    def _load_excel(self, file_path: str) -> pd.DataFrame:
        """Load Excel file (.xlsx, .xls, .xlsm)."""
        path = Path(file_path)
        
        # Detect sheets
        try:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
        except Exception as e:
            raise ValueError(f"Cannot read Excel file: {e}")
        
        if not sheet_names:
            raise ValueError("No sheets found in Excel file")
        
        # Store metadata
        self.file_metadata[file_path] = {
            "sheet_count": len(sheet_names),
            "sheet_names": sheet_names
        }
        
        # Load first sheet by default (or sheet with most data)
        sheet_to_load = self._select_best_sheet(file_path, sheet_names)
        
        logger.info(f"Loading sheet '{sheet_to_load}' from {path.name}")
        
        try:
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_to_load,
                engine='openpyxl' if path.suffix == '.xlsx' else 'xlrd'
            )
        except Exception as e:
            raise ValueError(f"Failed to read sheet '{sheet_to_load}': {e}")
        
        # Validate DataFrame
        return self._validate_dataframe(df, file_path)
    
    def _load_csv(self, file_path: str) -> pd.DataFrame:
        """Load CSV file."""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV with any common encoding")
            
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {e}")
        
        return self._validate_dataframe(df, file_path)
    
    def _select_best_sheet(self, file_path: str, sheet_names: List[str]) -> str:
        """
        Select the best sheet to load from a multi-sheet workbook.
        
        Priority:
        1. Sheet with most data
        2. Sheet named 'Data', 'Sheet1', or similar
        3. First sheet
        """
        # Try to find sheet with most rows
        max_rows = 0
        best_sheet = sheet_names[0]
        
        for sheet in sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet, nrows=10)
                # Try to get actual row count
                full_df = pd.read_excel(file_path, sheet_name=sheet)
                rows = len(full_df)
                
                if rows > max_rows:
                    max_rows = rows
                    best_sheet = sheet
            except:
                continue
        
        return best_sheet
    
    def _validate_dataframe(self, df: pd.DataFrame, file_path: str) -> pd.DataFrame:
        """
        Validate and clean DataFrame.
        
        Args:
            df: DataFrame to validate
            file_path: Source file path (for error messages)
            
        Returns:
            Cleaned DataFrame
        """
        path = Path(file_path)
        
        # Check if empty
        if df.empty:
            raise ValueError(f"File is empty: {path.name}")
        
        # Check for minimum columns
        if len(df.columns) < 2:
            raise ValueError(f"File has too few columns ({len(df.columns)}): {path.name}")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Remove completely empty columns
        df = df.dropna(axis=1, how='all')
        
        # Remove completely empty rows
        df = df.dropna(axis=0, how='all')
        
        # Handle unnamed columns
        df.columns = [
            f"Unnamed_{i}" if str(col).startswith('Unnamed') else str(col)
            for i, col in enumerate(df.columns)
        ]
        
        # Ensure unique column names
        df = self._ensure_unique_column_names(df)
        
        # Reset index
        df = df.reset_index(drop=True)
        
        logger.debug(f"Cleaned DataFrame: {len(df):,} rows, {len(df.columns)} columns")
        
        return df
    
    def _ensure_unique_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all column names are unique."""
        cols = pd.Series(df.columns)
        
        for dup in cols[cols.duplicated()].unique():
            # Find all occurrences
            dup_indices = cols[cols == dup].index
            
            # Rename duplicates
            for i, idx in enumerate(dup_indices[1:], start=1):
                cols.iloc[idx] = f"{dup}_{i}"
        
        df.columns = cols
        return df
    
    def get_file_summary(self) -> dict:
        """Get summary of loaded files."""
        summary = {
            "total_files": len(self.loaded_files),
            "files": []
        }
        
        for file_path, df in self.loaded_files.items():
            summary["files"].append({
                "file_name": Path(file_path).name,
                "file_path": file_path,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "memory_mb": df.memory_usage(deep=True).sum() / (1024 * 1024)
            })
        
        return summary
