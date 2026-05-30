"""
API configuration settings for ThoughtSpot -> Power BI Migration Tool.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class APIConfig(BaseSettings):
    """
    Configuration for FastAPI application.
    Values can be overridden from the .env file.
    """

    # ============================================================
    # API Settings
    # ============================================================

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    API_TITLE: str = "ThoughtSpot to Power BI Migration API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = (
        "API for migrating ThoughtSpot metadata, worksheets, answers, "
        "liveboards, formulas, and relationships into Power BI-compatible outputs."
    )

    # ============================================================
    # File Upload Settings
    # ============================================================

    MAX_FILE_SIZE_MB: int = 100
    MAX_FILES_PER_JOB: int = 20

    # ThoughtSpot export files can be TML, YAML, JSON, ZIP, CSV, or Excel metadata files
    ALLOWED_EXTENSIONS: List[str] = [
        ".tml",
        ".yaml",
        ".yml",
        ".json",
        ".zip",
        ".csv",
        ".xlsx",
        ".xls",
    ]

    UPLOAD_DIR: str = "data/uploads"
    RESULT_DIR: str = "data/results"
    TEMP_DIR: str = "data/temp"

    # Output folders
    POWERBI_OUTPUT_DIR: str = "output/powerbi"
    REPORT_JSON_DIR: str = "output/reports"
    DAX_OUTPUT_DIR: str = "output/dax"

    # ============================================================
    # Database Settings
    # ============================================================

    DATABASE_PATH: str = "data/jobs.db"

    # ============================================================
    # ThoughtSpot Settings
    # ============================================================

    THOUGHTSPOT_BASE_URL: Optional[str] = None
    THOUGHTSPOT_USERNAME: Optional[str] = None
    THOUGHTSPOT_PASSWORD: Optional[str] = None
    THOUGHTSPOT_BEARER_TOKEN: Optional[str] = None
    THOUGHTSPOT_ORG_ID: Optional[str] = None

    # ============================================================
    # Power BI / Azure Settings
    # ============================================================

    POWERBI_TENANT_ID: Optional[str] = None
    POWERBI_CLIENT_ID: Optional[str] = None
    POWERBI_CLIENT_SECRET: Optional[str] = None
    POWERBI_WORKSPACE_ID: Optional[str] = None

    POWERBI_AUTHORITY_URL: str = "https://login.microsoftonline.com"
    POWERBI_API_BASE_URL: str = "https://api.powerbi.com/v1.0/myorg"

    # ============================================================
    # Migration Settings
    # ============================================================

    ENABLE_LLM_CONVERSION: bool = True
    ENABLE_DAX_GENERATION: bool = True
    ENABLE_RELATIONSHIP_DETECTION: bool = True
    ENABLE_REPORT_GENERATION: bool = True
    ENABLE_POWERBI_PUBLISHING: bool = False

    DEFAULT_OUTPUT_FORMAT: str = "json"

    SUPPORTED_THOUGHTSPOT_OBJECTS: List[str] = [
        "table",
        "worksheet",
        "answer",
        "liveboard",
        "connection",
    ]

    # ============================================================
    # Job Execution Settings
    # ============================================================

    JOB_TIMEOUT_SECONDS: int = 1800  # 30 minutes
    MAX_CONCURRENT_JOBS: int = 3

    # ============================================================
    # WebSocket Settings
    # ============================================================

    WS_HEARTBEAT_INTERVAL: int = 30
    WS_PING_TIMEOUT: int = 60

    # ============================================================
    # CORS Settings
    # ============================================================

    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # ============================================================
    # Cleanup Settings
    # ============================================================

    DELETE_FILES_ON_JOB_DELETE: bool = True
    AUTO_CLEANUP_OLD_JOBS_DAYS: int = 7

    # ============================================================
    # Logging Settings
    # ============================================================

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "data/logs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    def ensure_directories(self):
        """
        Ensure all required directories exist.
        Call this when the API starts.
        """

        directories = [
            self.UPLOAD_DIR,
            self.RESULT_DIR,
            self.TEMP_DIR,
            self.POWERBI_OUTPUT_DIR,
            self.REPORT_JSON_DIR,
            self.DAX_OUTPUT_DIR,
            self.LOG_DIR,
            os.path.dirname(self.DATABASE_PATH),
        ]

        for directory in directories:
            if directory:
                os.makedirs(directory, exist_ok=True)


# Global config instance
config = APIConfig()