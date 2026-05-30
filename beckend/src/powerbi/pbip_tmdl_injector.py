"""
PBIP TMDL Injector
==================
Writes native Power BI TMDL (Tabular Model Definition Language) files
directly into a .pbip SemanticModel folder — no Tabular Editor required.

Usage
-----
from src.powerbi.pbip_tmdl_injector import PBIPTmdlInjector
import pandas as pd
from pathlib import Path

injector = PBIPTmdlInjector()
injected = injector.inject(
    sm_folder=Path("exports/mig_001/pbip_output/template.SemanticModel"),
    tables={"Sales": df_sales, "Budget": df_budget},
    measures=[
        {"name": "Total Sales", "dax": "SUM('Sales'[Amount])", "formatString": "#,##0"},
    ]
)
"""
import re
import uuid
import os
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_tmdl_datatype(dtype) -> str:
    """Map a pandas dtype to a TMDL / DAX datatype name."""
    if not _PANDAS_AVAILABLE:
        return "string"
    if pd.api.types.is_float_dtype(dtype):
        return "double"
    if pd.api.types.is_integer_dtype(dtype):
        return "int64"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "dateTime"
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    return "string"


def _clean_column_name(name: str) -> str:
    """Strip all quote characters and extra whitespace from a column name."""
    name = str(name)
    name = re.sub(r'["\'`]', '', name)
    return name.strip()


def _format_cell_value(val) -> str:
    """Convert a Python value to its DAX DATATABLE literal."""
    if _PANDAS_AVAILABLE and pd.isna(val):
        return "BLANK()"
    if val is None:
        return "BLANK()"
    if isinstance(val, float):
        # Emit integer if value is whole number (cleaner DAX)
        if val == int(val):
            return str(int(val))
        return str(val)
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int,)):
        return str(val)
    # String — double the double-quotes for DAX escaping
    safe = str(val).replace('"', '""')
    return f'"{safe}"'


def _indent_dax(dax: str) -> str:
    """
    Indent a multi-line DAX formula for TMDL.
    Single-line formulas are returned as-is (no leading whitespace added).
    Multi-line formulas get continuation lines indented with 3 tabs.
    """
    dax = dax.strip()
    if "\n" not in dax:
        return dax
    lines = dax.splitlines()
    result = [lines[0]]
    for line in lines[1:]:
        result.append("\t\t\t" + line.lstrip())
    return "\n".join(result)


def _make_tmdl_table_name(name: str) -> str:
    """
    Return the TMDL table-name token.
    Names with spaces or special characters are wrapped in single quotes.
    """
    if re.search(r"[\s\-\.\(\)'!#]", name):
        # Escape any inner single-quotes by doubling them
        safe = name.replace("'", "''")
        return f"'{safe}'"
    return name


# ─────────────────────────────────────────────────────────────────────────────
# TMDL builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_datatable_dax(df) -> str:
    """
    Render a pandas DataFrame as a DAX DATATABLE() expression (tab-indented for TMDL).
    Returns an empty DATATABLE with headers only if the DataFrame has no rows.
    """
    if not _PANDAS_AVAILABLE:
        raise RuntimeError("pandas is required for TMDL DATATABLE generation")

    # ── Build header type list ──────────────────────────────────────────────
    headers = []
    for col in df.columns:
        tmdl_type = _get_tmdl_datatype(df[col].dtype)
        dax_type_map = {
            "int64":    "INTEGER",
            "double":   "DOUBLE",
            "dateTime": "DATETIME",
            "boolean":  "BOOLEAN",
            "string":   "STRING",
        }
        dax_type = dax_type_map.get(tmdl_type, "STRING")
        headers.append(f'"{col}", {dax_type}')

    header_str = ",\n\t\t\t\t".join(headers)

    # ── Build row data ──────────────────────────────────────────────────────
    row_strings: List[str] = []
    for _, row in df.iterrows():
        vals = [_format_cell_value(v) for v in row]
        row_strings.append(f"\t\t\t\t{{ {', '.join(vals)} }}")

    if row_strings:
        rows_str = ",\n".join(row_strings)
        body = f"{{\n{rows_str}\n\t\t\t\t}}"
    else:
        # Empty table — valid DATATABLE with zero rows
        body = "{{ }}"

    return (
        f"\t\t\tDATATABLE (\n"
        f"\t\t\t\t{header_str},\n"
        f"\t\t\t\t{body}\n"
        f"\t\t\t)"
    )


def _build_tmdl_content(
    table_name: str,
    df,           # pd.DataFrame or None
    measures: List[Dict[str, str]],
) -> str:
    """
    Build the full content of a <TableName>.tmdl file.

    - If `df` is provided (even empty): writes columns + calculated DATATABLE partition.
    - If `df` is None: writes only a dummy partition (for MeasuresTable pattern).
    - `measures` list: each dict must have 'name' and 'dax'; 'formatString' is optional.
    """
    lines: List[str] = []
    tmdl_token = _make_tmdl_table_name(table_name)

    # ── Table header ────────────────────────────────────────────────────────
    lines.append(f"table {tmdl_token}")
    lines.append(f"\tlineageTag: {uuid.uuid4()}")
    lines.append("")

    # ── Columns ─────────────────────────────────────────────────────────────
    if df is not None:
        for col in df.columns:
            dtype = _get_tmdl_datatype(df[col].dtype)
            lines.append(f"\tcolumn '{col}'")
            lines.append(f"\t\tdataType: {dtype}")
            lines.append(f"\t\tlineageTag: {uuid.uuid4()}")
            lines.append(f"\t\tsummarizeBy: {'none' if dtype == 'string' else 'sum'}")
            lines.append(f"\t\tsourceColumn: [{col}]")
            lines.append("")

    # ── Measures ─────────────────────────────────────────────────────────────
    for m in measures:
        m_name       = m.get("name", "").strip()
        m_dax        = m.get("dax",  "0").strip()
        m_format     = m.get("formatString", "0")

        if not m_name or not m_dax:
            logger.warning(f"Skipping measure with missing name/dax: {m}")
            continue

        indented_dax = _indent_dax(m_dax)

        if "\n" in indented_dax:
            lines.append(f"\tmeasure '{m_name}' =")
            lines.append(f"\t\t\t{indented_dax}")
        else:
            lines.append(f"\tmeasure '{m_name}' = {indented_dax}")

        lines.append(f"\t\tformatString: {m_format}")
        lines.append(f"\t\tlineageTag: {uuid.uuid4()}")
        lines.append("")

    # ── Partition ────────────────────────────────────────────────────────────
    lines.append(f"\tpartition {tmdl_token} = calculated")
    lines.append(f"\t\tmode: import")
    lines.append(f"\t\texpression =")

    if df is not None:
        try:
            datatable_dax = _build_datatable_dax(df)
            lines.append(datatable_dax)
        except Exception as e:
            logger.error(f"Failed to build DATATABLE for '{table_name}': {e}")
            # Fallback: single-row dummy so TMDL remains valid
            lines.append('\t\t\tDATATABLE ( "_dummy", STRING, { { "" } } )')
    else:
        # MeasuresTable dummy partition
        lines.append('\t\t\tDATATABLE ( "Dummy", STRING, { { "1" } } )')

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main injector class
# ─────────────────────────────────────────────────────────────────────────────

class PBIPTmdlInjector:
    """
    Injects tables and measures into a Power BI Project (.pbip) SemanticModel.

    Writes:
    - One <TableName>.tmdl file per table under definition/tables/
    - One MeasuresTable.tmdl containing all DAX measures
    - Appends `ref table` lines to definition/model.tmdl (idempotent)
    """

    def inject(
        self,
        sm_folder: Path,
        tables: Dict[str, "pd.DataFrame"],
        measures: List[Dict[str, str]],
    ) -> List[str]:
        """
        Inject all tables and measures into the SemanticModel folder.

        Parameters
        ----------
        sm_folder : Path
            Absolute path to the *.SemanticModel directory (already copied from template).
        tables : dict
            Mapping of table_name → pandas DataFrame.  An empty DataFrame is valid.
        measures : list of dict
            Each dict: {"name": str, "dax": str, "formatString": str (optional)}.

        Returns
        -------
        List of table names that were successfully injected.
        """
        tables_dir = sm_folder / "definition" / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)

        injected: List[str] = []

        # ── 1. Write one .tmdl per data table ───────────────────────────────
        for table_name, df in tables.items():
            clean_name = _clean_column_name(table_name) if table_name else "Table"
            if not clean_name:
                logger.warning("Skipping table with empty name")
                continue

            # Clean column names in the DataFrame
            if df is not None and not df.empty:
                df = df.copy()
                df.columns = [_clean_column_name(c) for c in df.columns]

            try:
                content = _build_tmdl_content(
                    table_name=table_name,
                    df=df,
                    measures=[],   # data tables never carry measures
                )
                safe_filename = re.sub(r'[<>:"/\\|?*]', '_', table_name)
                tmdl_path = tables_dir / f"{safe_filename}.tmdl"
                tmdl_path.write_text(content, encoding="utf-8")
                injected.append(table_name)
                logger.info(f"  ✓ Written table TMDL: {tmdl_path.name} "
                            f"({len(df) if df is not None else 0} rows)")
            except Exception as e:
                logger.error(f"  ✗ Failed to write TMDL for '{table_name}': {e}")

        # ── 2. Write MeasuresTable.tmdl (all DAX measures) ──────────────────
        if measures:
            valid_measures = [
                m for m in measures
                if m.get("name", "").strip() and m.get("dax", "").strip()
            ]
            try:
                content = _build_tmdl_content(
                    table_name="MeasuresTable",
                    df=None,           # no data — dummy partition
                    measures=valid_measures,
                )
                mt_path = tables_dir / "MeasuresTable.tmdl"
                mt_path.write_text(content, encoding="utf-8")
                injected.append("MeasuresTable")
                logger.info(f"  ✓ Written MeasuresTable.tmdl ({len(valid_measures)} measures)")
            except Exception as e:
                logger.error(f"  ✗ Failed to write MeasuresTable.tmdl: {e}")
        else:
            logger.warning("  ⚠ No measures provided — MeasuresTable.tmdl skipped")

        # ── 3. Append ref table entries to model.tmdl (idempotent) ───────────
        self._update_model_tmdl(sm_folder, injected)

        return injected

    # ─────────────────────────────────────────────────────────────────────────
    def _update_model_tmdl(self, sm_folder: Path, table_names: List[str]) -> None:
        """
        Append `ref table 'X'` lines to definition/model.tmdl.
        Skips any that are already present (safe for re-runs).
        """
        model_tmdl = sm_folder / "definition" / "model.tmdl"
        if not model_tmdl.exists():
            logger.error(f"model.tmdl not found at {model_tmdl}")
            return

        current_content = model_tmdl.read_text(encoding="utf-8")

        new_refs: List[str] = []
        for name in table_names:
            tmdl_token  = _make_tmdl_table_name(name)
            ref_line    = f"ref table {tmdl_token}"
            # Both quoted and unquoted forms
            if ref_line not in current_content and f"ref table '{name}'" not in current_content:
                new_refs.append(ref_line)

        if new_refs:
            with open(model_tmdl, "a", encoding="utf-8") as f:
                for ref in new_refs:
                    f.write(f"\n{ref}\n")
            logger.info(f"  ✓ Added {len(new_refs)} ref table entries to model.tmdl")
        else:
            logger.info("  ✓ model.tmdl already up-to-date (no new refs needed)")
