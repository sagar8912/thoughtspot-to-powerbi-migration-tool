"""
Configuration management for Excel Relationship Discovery System.
All tunable parameters and settings are defined here.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """System configuration with all tunable parameters."""
    
    # =============================================================================
    # PROFILING SETTINGS
    # =============================================================================
    
    # Sample size for large file profiling (rows)
    SAMPLE_SIZE_FOR_PROFILING: int = 10000
    
    # Number of top values to capture per column
    TOP_VALUES_COUNT: int = 20
    
    # Number of sample values to include in JSON output
    SAMPLE_VALUES_COUNT: int = 5
    
    # =============================================================================
    # RELATIONSHIP DETECTION THRESHOLDS
    # =============================================================================
    
    # High confidence overlap threshold (80%+)
    HIGH_CONFIDENCE_OVERLAP_THRESHOLD: float = 0.80
    
    # Medium confidence overlap threshold (60%+)
    MEDIUM_CONFIDENCE_OVERLAP_THRESHOLD: float = 0.60
    
    # Low confidence threshold (40%+)
    LOW_CONFIDENCE_OVERLAP_THRESHOLD: float = 0.40
    
    # Fuzzy string matching threshold
    FUZZY_MATCH_THRESHOLD: float = 0.85
    
    # Semantic similarity threshold (for embeddings)
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.85
    
    # =============================================================================
    # KEY DETECTION
    # =============================================================================
    
    # Uniqueness threshold for primary key detection (95%+)
    UNIQUE_THRESHOLD_FOR_PK: float = 0.95
    
    # Uniqueness threshold for foreign key detection (70%+)
    UNIQUE_THRESHOLD_FOR_FK: float = 0.70
    
    # Minimum cardinality for key candidates
    MIN_CARDINALITY_FOR_KEY: int = 10
    
    # =============================================================================
    # DATA QUALITY
    # =============================================================================
    
    # Maximum acceptable NULL percentage (5%)
    MAX_ACCEPTABLE_NULL_PERCENT: float = 5.0
    
    # Maximum acceptable orphan percentage (5%)
    MAX_ACCEPTABLE_ORPHAN_PERCENT: float = 5.0
    
    # Row explosion risk multiplier threshold
    ROW_EXPLOSION_RISK_THRESHOLD: int = 10
    
    # =============================================================================
    # LLM SETTINGS - AZURE OPENAI (LANGCHAIN)
    # =============================================================================
    
    # LLM provider
    LLM_PROVIDER: str = "azure_openai"
    
    # Azure OpenAI credentials
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

    # Maximum tokens for LLM response
    # INCREASED FROM 800 TO 4000 to prevent formula truncation
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))

    # Temperature for deterministic output
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    # Enable LLM validation (set to False to disable LLM entirely)
    ENABLE_LLM_VALIDATION: bool = os.getenv("ENABLE_LLM_VALIDATION", "true").lower() == "true"

    # High overlap LLM validation - NEW!
    # For columns with 50-80% overlap, use LLM to check semantic relationship
    ENABLE_HIGH_OVERLAP_LLM_VALIDATION: bool = os.getenv("ENABLE_HIGH_OVERLAP_LLM_VALIDATION", "true").lower() == "true"
    HIGH_OVERLAP_LLM_MIN_THRESHOLD: float = 0.50  # 50% minimum overlap to trigger LLM check
    HIGH_OVERLAP_LLM_MIN_CONFIDENCE: float = 0.60  # 60% LLM confidence required

    # Semantic duplicate detection thresholds
    SEMANTIC_DUPLICATE_MIN_OVERLAP: float = 0.80  # 80% value overlap required
    SEMANTIC_DUPLICATE_MIN_CONFIDENCE: float = 0.80  # 80% LLM confidence required
    ENABLE_SEMANTIC_DUPLICATE_DETECTION: bool = os.getenv("ENABLE_SEMANTIC_DUPLICATE_DETECTION", "true").lower() == "true"

    # =============================================================================
    # PERFORMANCE - OPTIMIZED FOR MAX 5 FILES
    # =============================================================================
    
    # Enable caching
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    
    # Enable parallel processing
    PARALLEL_PROCESSING: bool = os.getenv("PARALLEL_PROCESSING", "true").lower() == "true"
    
    # Maximum worker threads (conservative for 5 files)
    MAX_WORKERS: int = 3
    
    # Maximum files allowed
    MAX_FILES_LIMIT: int = int(os.getenv("MAX_FILES_LIMIT", "5"))
    
    # Chunk size for large file processing
    CHUNK_SIZE: int = 10000
    
    # =============================================================================
    # LOGGING
    # =============================================================================
    
    # Log level
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Enable progress bars
    SHOW_PROGRESS: bool = True
    
    # =============================================================================
    # OUTPUT
    # =============================================================================
    
    # Output directory for reports
    OUTPUT_DIR: str = "output"
    
    # Output filename pattern
    OUTPUT_FILENAME_PATTERN: str = "relationship_report_{timestamp}.json"
    
    # Pretty print JSON
    PRETTY_PRINT_JSON: bool = True
    
    # Include sample data in output
    INCLUDE_SAMPLE_DATA: bool = True
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate configuration settings.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If required settings are missing or invalid
        """
        errors = []
        
        # Validate LLM settings if enabled
        if cls.ENABLE_LLM_VALIDATION:
            if not cls.AZURE_OPENAI_ENDPOINT:
                errors.append("AZURE_OPENAI_ENDPOINT is required when LLM validation is enabled")
            if not cls.AZURE_OPENAI_API_KEY:
                errors.append("AZURE_OPENAI_API_KEY is required when LLM validation is enabled")
            if not cls.AZURE_OPENAI_DEPLOYMENT_NAME:
                errors.append("AZURE_OPENAI_DEPLOYMENT_NAME is required when LLM validation is enabled")
        
        # Validate thresholds
        if not (0 <= cls.HIGH_CONFIDENCE_OVERLAP_THRESHOLD <= 1):
            errors.append("HIGH_CONFIDENCE_OVERLAP_THRESHOLD must be between 0 and 1")
        if not (0 <= cls.MEDIUM_CONFIDENCE_OVERLAP_THRESHOLD <= 1):
            errors.append("MEDIUM_CONFIDENCE_OVERLAP_THRESHOLD must be between 0 and 1")
        
        # Validate file limit
        if cls.MAX_FILES_LIMIT < 1:
            errors.append("MAX_FILES_LIMIT must be at least 1")
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"- {e}" for e in errors))
        
        return True
    
    @classmethod
    def summary(cls) -> str:
        """Get a summary of current configuration."""
        return f"""
Excel Relationship Discovery System - Configuration Summary
============================================================

PROFILING:
  Sample Size: {cls.SAMPLE_SIZE_FOR_PROFILING:,} rows
  Top Values: {cls.TOP_VALUES_COUNT}
  Sample Values in Output: {cls.SAMPLE_VALUES_COUNT}

THRESHOLDS:
  High Confidence Overlap: {cls.HIGH_CONFIDENCE_OVERLAP_THRESHOLD:.0%}
  Medium Confidence Overlap: {cls.MEDIUM_CONFIDENCE_OVERLAP_THRESHOLD:.0%}
  PK Uniqueness: {cls.UNIQUE_THRESHOLD_FOR_PK:.0%}
  FK Uniqueness: {cls.UNIQUE_THRESHOLD_FOR_FK:.0%}

LLM (Azure OpenAI):
  Enabled: {cls.ENABLE_LLM_VALIDATION}
  Deployment: {cls.AZURE_OPENAI_DEPLOYMENT_NAME}
  Endpoint: {cls.AZURE_OPENAI_ENDPOINT or 'Not Set'}

PERFORMANCE:
  Max Files: {cls.MAX_FILES_LIMIT}
  Max Workers: {cls.MAX_WORKERS}
  Caching: {cls.ENABLE_CACHING}
  Parallel Processing: {cls.PARALLEL_PROCESSING}

OUTPUT:
  Directory: {cls.OUTPUT_DIR}
  Include Sample Data: {cls.INCLUDE_SAMPLE_DATA}
  Pretty Print: {cls.PRETTY_PRINT_JSON}
============================================================
"""


# Validate configuration on import
try:
    Config.validate()
except ValueError as e:
    print(f"⚠️  Configuration Warning: {e}")
    print("Set ENABLE_LLM_VALIDATION=false to disable LLM validation")
