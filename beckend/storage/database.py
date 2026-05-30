"""
SQLite database initialization and management for ThoughtSpot -> Power BI Migration Tool.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from api.config import config
from loguru import logger


DATABASE_SCHEMA = """
-- ============================================================
-- CORE JOB TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    progress_percent INTEGER DEFAULT 0 CHECK(progress_percent >= 0 AND progress_percent <= 100),
    current_stage TEXT,
    current_object_name TEXT,
    error_message TEXT,

    file_count INTEGER NOT NULL DEFAULT 0,
    total_objects INTEGER DEFAULT 0,
    objects_completed INTEGER DEFAULT 0,
    objects_failed INTEGER DEFAULT 0,
    objects_skipped INTEGER DEFAULT 0,

    formulas_converted INTEGER DEFAULT 0,
    relationships_created INTEGER DEFAULT 0,

    powerbi_workspace_id TEXT,
    powerbi_dataset_id TEXT,
    powerbi_report_id TEXT,
    powerbi_report_url TEXT,

    result_file_path TEXT,
    pbix_file_path TEXT,
    report_json_path TEXT
);


CREATE TABLE IF NOT EXISTS uploaded_files (
    file_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,

    file_type TEXT,
    thoughtspot_object_type TEXT,
    thoughtspot_object_name TEXT,
    thoughtspot_object_guid TEXT,

    parsed_successfully BOOLEAN DEFAULT 0,
    parse_error TEXT,

    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS job_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id TEXT,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    message TEXT,
    percent INTEGER DEFAULT 0 CHECK(percent >= 0 AND percent <= 100),
    level TEXT DEFAULT 'info',
    object_name TEXT,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- PREVIEW TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS preview_sessions (
    preview_id TEXT PRIMARY KEY,
    status TEXT CHECK(status IN ('preview_ready', 'confirmed', 'cancelled')) NOT NULL DEFAULT 'preview_ready',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_duplicates_detected INTEGER DEFAULT 0
);


CREATE TABLE IF NOT EXISTS preview_files (
    file_id TEXT PRIMARY KEY,
    preview_id TEXT NOT NULL REFERENCES preview_sessions(preview_id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    dataframe_pickle_path TEXT,
    row_count INTEGER DEFAULT 0,
    column_count INTEGER DEFAULT 0,
    metadata_json TEXT
);


-- ============================================================
-- THOUGHTSPOT -> POWER BI MIGRATION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS migration_jobs (
    migration_id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES jobs(job_id) ON DELETE CASCADE,

    status TEXT CHECK(
        status IN (
            'pending',
            'parsing',
            'discovering',
            'converting',
            'validating',
            'publishing',
            'completed',
            'failed',
            'cancelled'
        )
    ) NOT NULL DEFAULT 'pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    progress_percent INTEGER DEFAULT 0 CHECK(progress_percent >= 0 AND progress_percent <= 100),
    current_stage TEXT,
    error_message TEXT,

    object_count INTEGER DEFAULT 0,
    formula_count INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,
    report_count INTEGER DEFAULT 0,
    dashboard_count INTEGER DEFAULT 0,

    powerbi_workspace_id TEXT,
    powerbi_dataset_id TEXT,
    powerbi_report_id TEXT,
    powerbi_report_url TEXT
);


CREATE TABLE IF NOT EXISTS thoughtspot_objects (
    object_id TEXT PRIMARY KEY,
    migration_id TEXT NOT NULL REFERENCES migration_jobs(migration_id) ON DELETE CASCADE,

    object_name TEXT NOT NULL,
    object_type TEXT CHECK(
        object_type IN (
            'table',
            'worksheet',
            'answer',
            'liveboard',
            'connection',
            'unknown'
        )
    ) NOT NULL DEFAULT 'unknown',

    filename TEXT,
    file_path TEXT,
    object_guid TEXT,

    column_count INTEGER DEFAULT 0,
    formula_count INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,
    visual_count INTEGER DEFAULT 0,

    raw_tml TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS thoughtspot_formulas (
    formula_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL REFERENCES thoughtspot_objects(object_id) ON DELETE CASCADE,

    formula_name TEXT NOT NULL,
    formula_expression TEXT NOT NULL,
    formula_type TEXT CHECK(
        formula_type IN (
            'column',
            'measure',
            'formula',
            'aggregation',
            'filter',
            'parameter'
        )
    ) NOT NULL DEFAULT 'formula',

    visual_context TEXT,
    dependency_level INTEGER DEFAULT 0,

    depends_on TEXT,
    depends_on_metadata TEXT,

    used_in_answers TEXT,
    used_in_liveboards TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS thoughtspot_relationships (
    relationship_id TEXT PRIMARY KEY,
    migration_id TEXT NOT NULL REFERENCES migration_jobs(migration_id) ON DELETE CASCADE,

    source_table TEXT NOT NULL,
    source_column TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_column TEXT NOT NULL,

    join_type TEXT,
    powerbi_cardinality TEXT,
    is_active BOOLEAN DEFAULT 1,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS powerbi_conversions (
    conversion_id TEXT PRIMARY KEY,

    source_formula_id TEXT NOT NULL REFERENCES thoughtspot_formulas(formula_id) ON DELETE CASCADE,
    migration_id TEXT NOT NULL REFERENCES migration_jobs(migration_id) ON DELETE CASCADE,

    dax_formula TEXT NOT NULL,

    conversion_method TEXT CHECK(
        conversion_method IN (
            'LLM_PATTERN',
            'LLM_GENERATED',
            'RULE_BASED',
            'DIRECT_MAPPING',
            'MANUAL_OVERRIDE'
        )
    ) DEFAULT 'LLM_PATTERN',

    confidence_score REAL CHECK(confidence_score >= 0 AND confidence_score <= 1),
    reasoning TEXT,
    warnings TEXT,

    status TEXT CHECK(
        status IN (
            'pending',
            'validated',
            'failed',
            'manual_review'
        )
    ) DEFAULT 'pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    target_powerbi_object_type TEXT CHECK(
        target_powerbi_object_type IN (
            'dataset',
            'semantic_model',
            'report',
            'dashboard'
        )
    ),

    target_powerbi_object_id TEXT,
    target_powerbi_object_name TEXT
);


CREATE TABLE IF NOT EXISTS validation_results (
    validation_id TEXT PRIMARY KEY,

    conversion_id TEXT NOT NULL REFERENCES powerbi_conversions(conversion_id) ON DELETE CASCADE,

    test_slice TEXT,

    thoughtspot_value REAL,
    powerbi_value REAL,

    delta REAL,
    relative_error REAL,

    passed BOOLEAN NOT NULL,

    error_category TEXT CHECK(
        error_category IN (
            'PERFECT_MATCH',
            'ROUNDING_ERROR',
            'NULL_HANDLING',
            'CONTEXT_SHIFT',
            'SCALE_ERROR',
            'AGGREGATION_MISMATCH',
            'MISSING_VALUE',
            'UNSUPPORTED_FUNCTION'
        )
    ),

    correction_attempts INTEGER DEFAULT 0,
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS migration_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    migration_id TEXT NOT NULL REFERENCES migration_jobs(migration_id) ON DELETE CASCADE,

    stage TEXT NOT NULL,
    message TEXT,
    percent INTEGER DEFAULT 0 CHECK(percent >= 0 AND percent <= 100),

    level TEXT DEFAULT 'info',
    object_name TEXT,
    details TEXT,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- POWER BI OUTPUT ARTIFACTS
-- ============================================================

CREATE TABLE IF NOT EXISTS powerbi_outputs (
    output_id TEXT PRIMARY KEY,
    migration_id TEXT NOT NULL REFERENCES migration_jobs(migration_id) ON DELETE CASCADE,

    object_type TEXT CHECK(
        object_type IN (
            'dataset',
            'semantic_model',
            'report',
            'dashboard',
            'datamart'
        )
    ) NOT NULL,

    object_name TEXT NOT NULL,
    object_id TEXT,
    web_url TEXT,

    file_path TEXT,

    created_successfully BOOLEAN DEFAULT 0,
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- CONVERSION PATTERN LIBRARY
-- ============================================================

CREATE TABLE IF NOT EXISTS conversion_patterns (
    pattern_id TEXT PRIMARY KEY,

    pattern_name TEXT NOT NULL,

    thoughtspot_formula TEXT NOT NULL,
    dax_formula TEXT NOT NULL,

    context TEXT,
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0 AND confidence <= 1),

    tags TEXT,
    notes TEXT,

    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);


-- ============================================================
-- HIGH-FIDELITY VALIDATION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS fidelity_validations (
    validation_id TEXT PRIMARY KEY,

    migration_id TEXT REFERENCES migration_jobs(migration_id) ON DELETE CASCADE,
    conversion_id TEXT REFERENCES powerbi_conversions(conversion_id) ON DELETE SET NULL,

    overall_passed BOOLEAN NOT NULL,
    pass_rate REAL NOT NULL CHECK(pass_rate >= 0 AND pass_rate <= 1),

    correction_attempts INTEGER DEFAULT 0,
    final_dax TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS validation_test_slices (
    slice_id TEXT PRIMARY KEY,

    validation_id TEXT NOT NULL REFERENCES fidelity_validations(validation_id) ON DELETE CASCADE,

    dimensions TEXT NOT NULL,

    thoughtspot_value REAL,
    powerbi_value REAL,

    delta REAL,
    relative_error REAL,

    passed BOOLEAN NOT NULL,

    error_category TEXT CHECK(
        error_category IN (
            'PERFECT_MATCH',
            'ROUNDING_ERROR',
            'SCALE_ERROR',
            'NULL_HANDLING',
            'CONTEXT_SHIFT',
            'GRAIN_MISMATCH',
            'AGGREGATION_MISMATCH',
            'MISSING_VALUE',
            'UNSUPPORTED_FUNCTION'
        )
    )
);


CREATE TABLE IF NOT EXISTS correction_attempts (
    attempt_id TEXT PRIMARY KEY,

    validation_id TEXT NOT NULL REFERENCES fidelity_validations(validation_id) ON DELETE CASCADE,

    attempt_number INTEGER NOT NULL,

    original_dax TEXT NOT NULL,
    corrected_dax TEXT NOT NULL,

    root_cause TEXT,
    explanation TEXT,
    changes_made TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_job_id ON uploaded_files(job_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_object_type ON uploaded_files(thoughtspot_object_type);

CREATE INDEX IF NOT EXISTS idx_job_progress_job_id ON job_progress(job_id);
CREATE INDEX IF NOT EXISTS idx_job_progress_timestamp ON job_progress(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_preview_sessions_created_at ON preview_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_preview_files_preview_id ON preview_files(preview_id);

CREATE INDEX IF NOT EXISTS idx_migration_jobs_status ON migration_jobs(status);
CREATE INDEX IF NOT EXISTS idx_migration_jobs_created_at ON migration_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_migration_jobs_job_id ON migration_jobs(job_id);

CREATE INDEX IF NOT EXISTS idx_thoughtspot_objects_migration_id ON thoughtspot_objects(migration_id);
CREATE INDEX IF NOT EXISTS idx_thoughtspot_objects_type ON thoughtspot_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_thoughtspot_objects_guid ON thoughtspot_objects(object_guid);

CREATE INDEX IF NOT EXISTS idx_thoughtspot_formulas_object_id ON thoughtspot_formulas(object_id);
CREATE INDEX IF NOT EXISTS idx_thoughtspot_formulas_name ON thoughtspot_formulas(formula_name);

CREATE INDEX IF NOT EXISTS idx_thoughtspot_relationships_migration_id ON thoughtspot_relationships(migration_id);

CREATE INDEX IF NOT EXISTS idx_powerbi_conversions_migration_id ON powerbi_conversions(migration_id);
CREATE INDEX IF NOT EXISTS idx_powerbi_conversions_formula_id ON powerbi_conversions(source_formula_id);
CREATE INDEX IF NOT EXISTS idx_powerbi_conversions_status ON powerbi_conversions(status);

CREATE INDEX IF NOT EXISTS idx_validation_results_conversion_id ON validation_results(conversion_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_passed ON validation_results(passed);

CREATE INDEX IF NOT EXISTS idx_migration_progress_migration_id ON migration_progress(migration_id);
CREATE INDEX IF NOT EXISTS idx_migration_progress_timestamp ON migration_progress(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_powerbi_outputs_migration_id ON powerbi_outputs(migration_id);
CREATE INDEX IF NOT EXISTS idx_powerbi_outputs_type ON powerbi_outputs(object_type);

CREATE INDEX IF NOT EXISTS idx_fidelity_validations_migration_id ON fidelity_validations(migration_id);
CREATE INDEX IF NOT EXISTS idx_fidelity_validations_conversion_id ON fidelity_validations(conversion_id);

CREATE INDEX IF NOT EXISTS idx_validation_test_slices_validation_id ON validation_test_slices(validation_id);
CREATE INDEX IF NOT EXISTS idx_validation_test_slices_passed ON validation_test_slices(passed);

CREATE INDEX IF NOT EXISTS idx_correction_attempts_validation_id ON correction_attempts(validation_id);
"""


def init_database():
    """
    Initialize the SQLite database with the ThoughtSpot -> Power BI schema.
    """

    try:
        db_path = Path(config.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(DATABASE_SCHEMA)
        conn.commit()
        conn.close()

        logger.info(f"Database initialized at {db_path}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


@contextmanager
def get_db_connection():
    """
    Context manager for SQLite database connections.

    Usage:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM jobs").fetchall()
    """

    conn = None

    try:
        conn = sqlite3.connect(
            config.DATABASE_PATH,
            check_same_thread=False,
            timeout=30.0,
        )

        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row

        yield conn

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()

        logger.error(f"Database error: {e}", exc_info=True)
        raise

    finally:
        if conn:
            conn.close()


def execute_query(
    query: str,
    params: tuple = (),
    fetch_one: bool = False,
):
    """
    Execute a SELECT query and return rows.

    Args:
        query: SQL query string.
        params: SQL query parameters.
        fetch_one: If True, return a single row. Otherwise return all rows.

    Returns:
        sqlite3.Row or list[sqlite3.Row]
    """

    with get_db_connection() as conn:
        cursor = conn.execute(query, params)

        if fetch_one:
            return cursor.fetchone()

        return cursor.fetchall()


def execute_update(
    query: str,
    params: tuple = (),
):
    """
    Execute INSERT, UPDATE, or DELETE query.

    Args:
        query: SQL query string.
        params: SQL query parameters.

    Returns:
        Number of affected rows.
    """

    with get_db_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.rowcount


def execute_many(
    query: str,
    params_list: list,
):
    """
    Execute many INSERT/UPDATE/DELETE operations.

    Args:
        query: SQL query string.
        params_list: List of parameter tuples.

    Returns:
        Number of affected rows.
    """

    with get_db_connection() as conn:
        cursor = conn.executemany(query, params_list)
        return cursor.rowcount


def table_exists(table_name: str) -> bool:
    """
    Check whether a table exists in SQLite database.
    """

    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
    """

    row = execute_query(query, (table_name,), fetch_one=True)

    return row is not None


def cleanup_old_jobs(days: int = 7):
    """
    Delete old API jobs.

    Args:
        days: Number of days to keep completed/failed/cancelled jobs.
    """

    query = """
        DELETE FROM jobs
        WHERE created_at < datetime('now', '-' || ? || ' days')
        AND status IN ('completed', 'failed', 'cancelled')
    """

    deleted = execute_update(query, (days,))

    logger.info(f"Cleaned up {deleted} old jobs")

    return deleted


def cleanup_old_previews(hours: int = 1):
    """
    Delete old preview sessions.

    Args:
        hours: Number of hours to keep previews.
    """

    query = """
        DELETE FROM preview_sessions
        WHERE created_at < datetime('now', '-' || ? || ' hours')
    """

    deleted = execute_update(query, (hours,))

    logger.info(f"Cleaned up {deleted} old preview sessions")

    return deleted


def cleanup_old_migrations(days: int = 30):
    """
    Delete old ThoughtSpot -> Power BI migration jobs.

    Args:
        days: Number of days to keep completed/failed/cancelled migrations.
    """

    query = """
        DELETE FROM migration_jobs
        WHERE created_at < datetime('now', '-' || ? || ' days')
        AND status IN ('completed', 'failed', 'cancelled')
    """

    deleted = execute_update(query, (days,))

    logger.info(f"Cleaned up {deleted} old migration jobs")

    return deleted


def reset_database():
    """
    Drop all project tables and recreate database.

    WARNING:
        This deletes all jobs, migrations, uploaded file records, previews,
        conversion records, and validation results.

    Use only during development.
    """

    drop_schema = """
    DROP TABLE IF EXISTS correction_attempts;
    DROP TABLE IF EXISTS validation_test_slices;
    DROP TABLE IF EXISTS fidelity_validations;
    DROP TABLE IF EXISTS conversion_patterns;
    DROP TABLE IF EXISTS powerbi_outputs;
    DROP TABLE IF EXISTS migration_progress;
    DROP TABLE IF EXISTS validation_results;
    DROP TABLE IF EXISTS powerbi_conversions;
    DROP TABLE IF EXISTS thoughtspot_relationships;
    DROP TABLE IF EXISTS thoughtspot_formulas;
    DROP TABLE IF EXISTS thoughtspot_objects;
    DROP TABLE IF EXISTS migration_jobs;
    DROP TABLE IF EXISTS preview_files;
    DROP TABLE IF EXISTS preview_sessions;
    DROP TABLE IF EXISTS job_progress;
    DROP TABLE IF EXISTS uploaded_files;
    DROP TABLE IF EXISTS jobs;
    """

    with get_db_connection() as conn:
        conn.executescript(drop_schema)
        conn.executescript(DATABASE_SCHEMA)

    logger.warning("Database reset completed")