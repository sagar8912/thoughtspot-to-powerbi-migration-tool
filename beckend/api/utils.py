"""
Utility functions for ThoughtSpot -> Power BI Migration API.
"""

import uuid
from datetime import datetime


def _timestamp() -> str:
    """
    Generate UTC timestamp string.

    Returns:
        Timestamp in format: YYYYMMDDHHMMSS
    """
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _short_uuid(length: int = 8) -> str:
    """
    Generate short UUID string.

    Args:
        length: Number of UUID characters to return.

    Returns:
        Short UUID string.
    """
    return uuid.uuid4().hex[:length]


def generate_job_id() -> str:
    """
    Generate a unique migration job ID.

    Returns:
        Unique job identifier in format:
        job_YYYYMMDDHHMMSS_uuid
    """
    return f"job_{_timestamp()}_{_short_uuid()}"


def generate_migration_id() -> str:
    """
    Generate a unique migration ID.

    Returns:
        Unique migration identifier in format:
        migration_YYYYMMDDHHMMSS_uuid
    """
    return f"migration_{_timestamp()}_{_short_uuid()}"


def generate_file_id() -> str:
    """
    Generate a unique uploaded file ID.

    Returns:
        Unique file identifier in format:
        file_uuid
    """
    return f"file_{_short_uuid(12)}"


def generate_preview_id() -> str:
    """
    Generate a unique migration preview ID.

    Returns:
        Unique preview identifier in format:
        preview_YYYYMMDDHHMMSS_uuid
    """
    return f"preview_{_timestamp()}_{_short_uuid()}"


def generate_thoughtspot_object_id() -> str:
    """
    Generate a unique ThoughtSpot object ID.

    Returns:
        Unique ThoughtSpot object identifier.
    """
    return f"ts_obj_{_short_uuid(12)}"


def generate_formula_id() -> str:
    """
    Generate a unique ThoughtSpot formula ID.

    Returns:
        Unique formula identifier.
    """
    return f"formula_{_short_uuid(12)}"


def generate_relationship_id() -> str:
    """
    Generate a unique relationship ID.

    Returns:
        Unique relationship identifier.
    """
    return f"rel_{_short_uuid(12)}"


def generate_conversion_id() -> str:
    """
    Generate a unique Power BI / DAX conversion ID.

    Returns:
        Unique conversion identifier.
    """
    return f"conv_{_short_uuid(12)}"


def generate_validation_id() -> str:
    """
    Generate a unique validation result ID.

    Returns:
        Unique validation identifier.
    """
    return f"val_{_short_uuid(12)}"


def generate_log_id() -> str:
    """
    Generate a unique migration log ID.

    Returns:
        Unique log identifier.
    """
    return f"log_{_short_uuid(12)}"


def generate_powerbi_dataset_name(source_name: str) -> str:
    """
    Generate Power BI dataset name from ThoughtSpot object name.

    Args:
        source_name: ThoughtSpot object name.

    Returns:
        Clean Power BI dataset name.
    """
    clean_name = source_name.strip().replace(" ", "_")
    return f"TS_Migrated_{clean_name}_Dataset"


def generate_powerbi_report_name(source_name: str) -> str:
    """
    Generate Power BI report name from ThoughtSpot Liveboard or Answer name.

    Args:
        source_name: ThoughtSpot object name.

    Returns:
        Clean Power BI report name.
    """
    clean_name = source_name.strip().replace(" ", "_")
    return f"TS_Migrated_{clean_name}_Report"


def utc_now() -> datetime:
    """
    Return current UTC datetime.
    """
    return datetime.utcnow()


def utc_now_iso() -> str:
    """
    Return current UTC datetime as ISO string.
    """
    return datetime.utcnow().isoformat()