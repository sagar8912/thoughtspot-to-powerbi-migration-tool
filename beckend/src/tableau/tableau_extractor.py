"""
tableau_extractor.py — Structured Tableau Metadata Extractor
=============================================================
Parses a Tableau .twbx workbook into a complete structured model dict,
covering all metadata needed for a full Tableau → Power BI migration.

Output: tableau_model (dict) that can be serialised to JSON and consumed
        by downstream generators for:
          - Power BI model.tmdl (tables, columns, relationships, measures)
          - DAX measures
          - Visual/report layout config

Usage:
    from tableau_extractor import extract_tableau_model
    model = extract_tableau_model("path/to/workbook.twbx")
    import json
    print(json.dumps(model, indent=2, default=str))
"""

import zipfile
import re
import json
from pathlib import Path
from lxml import etree


# ── Tableau shelf derivation constants ─────────────────────────────────────────
TABLEAU_DERIVATIONS = (
    'none','sum','usr','yr','qr','wk','mn','dy',
    'cnt','cntd','min','max','attr','avg','med',
    'var','varp','stdev','stdevp','collect','percentile'
)
DERIV_RE = re.compile(r'^(' + '|'.join(TABLEAU_DERIVATIONS) + r'):', re.IGNORECASE)

# ── Helper utilities ────────────────────────────────────────────────────────────

def _load_xml(path: str) -> etree._Element:
    """Load Tableau XML from either a .twbx ZIP archive or a plain .twb file."""
    p = Path(path)
    if p.suffix.lower() == '.twbx':
        with zipfile.ZipFile(path, 'r') as zf:
            twb_name = next(f for f in zf.namelist() if f.endswith('.twb'))
            return etree.fromstring(zf.read(twb_name))
    # Plain .twb XML file
    return etree.parse(path).getroot()


def detect_model_type(root: etree._Element) -> str:
    """
    Detect whether the workbook uses:
      - 'JOIN'         — physical SQL joins (Tableau legacy model)
      - 'RELATIONSHIP' — logical relationships (Tableau 2020.2+ object model)
      - 'FLAT'         — single table, no joins or relationships
    """
    if root.xpath("//relation[@type='join']"):
        return "JOIN"
    if root.xpath("//*[local-name()='relationships']/*[local-name()='relationship']"):
        return "RELATIONSHIP"
    return "FLAT"


def _infer_cardinality(relationships: list) -> str:
    """
    Infer overall cardinality from the extracted relationships list.
    Returns 'many-to-many' if any relationship is explicitly many-to-many,
    otherwise 'many-to-one' (Tableau XML default — cardinality is not stored).
    """
    for r in relationships:
        if r.get("cardinality") in ("many-to-many", "*:*"):
            return "many-to-many"
    return "many-to-one"


def _build_ds_prefixes(root: etree._Element) -> list:
    prefixes = []
    for ds in root.xpath("//datasource[@name]"):
        name = ds.get("name", "")
        if name and name != "Parameters":
            prefixes.append(f"[{name}].")
            prefixes.append(f"{name}].")
    return prefixes


def _normalize_table_name(raw_name: str) -> str:
    """
    Normalize a Tableau table name strictly to a unified clean form.
    Handles 'Extract.Meeting_C95B...', 'gcrm!opportunity!2020...', 'Gcrm_Opportunity_2020...'
    and also updates field names like 'Product Group (Gcrm_Opportunity_2020...)' -> 'Product Group (Opportunity)'
    """
    if not raw_name or not isinstance(raw_name, str):
        return raw_name

    def clean_table(t: str) -> str:
        # Strip "Extract." prefix
        if '.' in t:
            t = t.split('.')[-1]
        t = t.strip('"').strip("'")
        
        # Strip 32-char GUID or >=8 char GUID
        t = re.sub(r'_[A-Fa-f0-9]{8,}$', '', t)
        
        # If it looks like a Tableau joined/extracted namespace (gcrm!opportunity!timestamp or Gcrm_Opportunity_timestamp)
        parts = re.split(r'[!_]', t)
        meaningful = [p for p in parts if not re.match(r'^\d+$', p) and p]
        
        if len(meaningful) >= 2 and meaningful[0].lower() in ['gcrm', 'extract', 'logical']:
            t = meaningful[-1]
        elif '!' in t:
            t = meaningful[-1] if meaningful else t
            
        # Capitalize gracefully
        return t.title() if t.islower() else t

    # Handle (TableName) suffix in field/dimension names
    def _repl_table(match):
        return f"({clean_table(match.group(1))})"

    if '(' in raw_name and ')' in raw_name:
        return re.sub(r'\(([^)]+)\)', _repl_table, raw_name)

    return clean_table(raw_name)


def _clean_field(s: str, ds_prefixes: list) -> str:
    s = s.strip("[]")
    if '__tableau_internal_object_id__' in s:
        m = re.search(r'cnt:([A-Za-z][A-Za-z_ ]+?)_[A-F0-9]{10,}', s)
        return f"COUNT({m.group(1)})" if m else "COUNT(table)"
    for prefix in ds_prefixes:
        if prefix in s:
            s = s.split(prefix, 1)[-1].strip("[]")
            break
    s = DERIV_RE.sub('', s)
    s = re.sub(r':(nk|qk|ok|tk)', '', s, flags=re.IGNORECASE)
    return s


def _resolve_calc_ids(text: str, caption_map: dict) -> str:
    """Replace [Calculation_XXXXX] with captions (bracket form)."""
    def _rep(m):
        cap = caption_map.get(f"Calculation_{m.group(1)}", f"Calculation_{m.group(1)}")
        return f"[{cap}]"
    return re.sub(r'\[Calculation_(\d+)\]', _rep, text)


def _resolve_field(s: str, caption_map: dict) -> str:
    """Resolve a bare field name: direct caption_map lookup first, then regex."""
    return caption_map.get(s, _resolve_calc_ids(s, caption_map))


def _classify_formula(formula: str) -> str:
    f = formula.upper()
    if re.search(r'\{[^}]*(FIXED|INCLUDE|EXCLUDE)', f):
        return 'LOD'
    if any(k in f for k in ['RUNNING_SUM','WINDOW_SUM','RANK(','INDEX(','FIRST(','LAST(','SIZE(']):
        return 'TABLE_CALC'
    return 'STANDARD'


def _tableau_to_dax(formula: str, caption_map: dict,
                    model_type: str = "FLAT",
                    cardinality: str = "many-to-one") -> dict:
    """
    Convert a Tableau formula to approximate DAX, using the correct pattern
    for the workbook's model type and relationship cardinality.

    Decision tree:
      LOD FIXED  → CALCULATE + ALLEXCEPT
      LOD INCLUDE → AVERAGEX + VALUES
      LOD EXCLUDE → CALCULATE + ALL
      RUNNING_SUM / WINDOW_SUM → CALCULATE + FILTER (running total)
      RANK        → RANKX
      COUNTD      → DISTINCTCOUNT  (always safe)
      SUM/AVG
        JOIN | FLAT | RELATIONSHIP many-to-one  → SUM() directly
        RELATIONSHIP many-to-many               → SUMX + VALUES

    Returns {"dax": str, "note": str, "confidence": str, "pattern": str}.
    """
    readable = _resolve_calc_ids(formula, caption_map)
    for cid, cap in caption_map.items():
        readable = readable.replace(f"[{cid}]", f"[{cap}]")

    upper = readable.strip().upper()

    # ── LOD: FIXED ──────────────────────────────────────────────────────────
    fixed_m = re.search(
        r'\{\s*FIXED\s+\[([^\]]+)\]\s*:\s*(.+?)\}',
        readable.strip(), re.IGNORECASE | re.DOTALL
    )
    if fixed_m:
        dim  = fixed_m.group(1).strip()
        expr = fixed_m.group(2).strip()
        # Extract inner aggregation
        agg_m = re.match(r'(SUM|AVG|COUNT|COUNTD|MIN|MAX)\(\[([^\]]+)\]\)', expr, re.IGNORECASE)
        if agg_m:
            agg_fn  = agg_m.group(1).upper().replace("COUNTD", "DISTINCTCOUNT").replace("AVG", "AVERAGE")
            col     = agg_m.group(2)
            dax_str = (f"CALCULATE(\n"
                       f"    {agg_fn}(TableName[{col}]),\n"
                       f"    ALLEXCEPT(TableName, TableName[{dim}])\n)")
        else:
            dax_str = f"CALCULATE({expr}, ALLEXCEPT(TableName, TableName[{dim}]))"
        return {"dax": dax_str,
                "note": "FIXED LOD → CALCULATE + ALLEXCEPT. Replace TableName.",
                "confidence": "high", "pattern": "CALCULATE_ALLEXCEPT"}

    # ── LOD: INCLUDE ────────────────────────────────────────────────────────
    include_m = re.search(
        r'\{\s*INCLUDE\s+\[([^\]]+)\]\s*:\s*(AVG|AVERAGE)\(\[([^\]]+)\]\)\s*\}',
        readable.strip(), re.IGNORECASE
    )
    if include_m:
        dim = include_m.group(1).strip()
        col = include_m.group(3).strip()
        dax_str = (f"AVERAGEX(\n"
                   f"    VALUES(TableName[{dim}]),\n"
                   f"    CALCULATE(AVERAGE(TableName[{col}]))\n)")
        return {"dax": dax_str,
                "note": "INCLUDE LOD → AVERAGEX + VALUES. Replace TableName.",
                "confidence": "high", "pattern": "AVERAGEX_VALUES"}

    include_gen_m = re.search(
        r'\{\s*INCLUDE\s+\[([^\]]+)\]\s*:\s*(.+?)\}',
        readable.strip(), re.IGNORECASE | re.DOTALL
    )
    if include_gen_m:
        dim  = include_gen_m.group(1).strip()
        expr = include_gen_m.group(2).strip()
        dax_str = f"AVERAGEX(VALUES(TableName[{dim}]), CALCULATE({expr}))"
        return {"dax": dax_str,
                "note": "INCLUDE LOD → AVERAGEX + VALUES. Replace TableName.",
                "confidence": "medium", "pattern": "AVERAGEX_VALUES"}

    # ── LOD: EXCLUDE ────────────────────────────────────────────────────────
    exclude_m = re.search(
        r'\{\s*EXCLUDE\s+\[([^\]]+)\]\s*:\s*(.+?)\}',
        readable.strip(), re.IGNORECASE | re.DOTALL
    )
    if exclude_m:
        dim  = exclude_m.group(1).strip()
        expr = exclude_m.group(2).strip()
        agg_m = re.match(r'(SUM|AVG|COUNT|COUNTD|MIN|MAX)\(\[([^\]]+)\]\)', expr, re.IGNORECASE)
        if agg_m:
            agg_fn  = agg_m.group(1).upper().replace("COUNTD", "DISTINCTCOUNT").replace("AVG", "AVERAGE")
            col     = agg_m.group(2)
            dax_str = f"CALCULATE({agg_fn}(TableName[{col}]), ALL(TableName[{dim}]))"
        else:
            dax_str = f"CALCULATE({expr}, ALL(TableName[{dim}]))"
        return {"dax": dax_str,
                "note": "EXCLUDE LOD → CALCULATE + ALL. Replace TableName.",
                "confidence": "high", "pattern": "CALCULATE_ALL"}

    # ── Table Calculations: RUNNING_SUM / WINDOW_SUM ─────────────────────────
    if re.search(r'\b(RUNNING_SUM|WINDOW_SUM)\b', upper):
        col_m = re.search(r'(?:RUNNING_SUM|WINDOW_SUM)\((?:SUM\()?\[([^\]]+)\]', readable, re.IGNORECASE)
        col = col_m.group(1) if col_m else "Amount"
        dax_str = (f"CALCULATE(\n"
                   f"    SUM(TableName[{col}]),\n"
                   f"    FILTER(ALL(TableName), TableName[Date] <= MAX(TableName[Date]))\n)")
        return {"dax": dax_str,
                "note": "Running total pattern. Replace TableName and Date column.",
                "confidence": "medium", "pattern": "RUNNING_TOTAL"}

    # ── Table Calculations: RANK ─────────────────────────────────────────────
    if re.search(r'\bRANK\s*\(', upper):
        return {
            "dax": "RANKX(ALL(TableName[Dimension]), [MeasureName])",
            "note": "RANK() → RANKX. Replace TableName, Dimension, and MeasureName.",
            "confidence": "medium", "pattern": "RANKX"
        }

    # ── COUNTD → DISTINCTCOUNT ───────────────────────────────────────────────
    # Safe for any model type
    countd_m = re.match(r'COUNTD\(\[([^\]]+)\]\)', readable.strip(), re.IGNORECASE)
    if countd_m:
        col = countd_m.group(1)
        return {"dax": f"DISTINCTCOUNT(TableName[{col}])",
                "note": "COUNTD → DISTINCTCOUNT. Replace TableName.",
                "confidence": "high", "pattern": "DIRECT_AGG"}

    # ── SUM — model-type and cardinality aware ────────────────────────────────
    sum_m = re.match(r'SUM\(\[([^\]]+)\]\)', readable.strip(), re.IGNORECASE)
    if sum_m:
        col = sum_m.group(1)
        if model_type == "RELATIONSHIP" and cardinality == "many-to-many":
            dax_str = (f"SUMX(\n"
                       f"    VALUES(TableName[JoinKey]),\n"
                       f"    CALCULATE(SUM(TableName[{col}]))\n)")
            return {"dax": dax_str,
                    "note": "many-to-many RELATIONSHIP → SUMX + VALUES. Replace TableName and JoinKey.",
                    "confidence": "high", "pattern": "SUMX_VALUES"}
        return {"dax": f"SUM(TableName[{col}])",
                "note": "Direct SUM — safe for JOIN / many-to-one RELATIONSHIP. Replace TableName.",
                "confidence": "high", "pattern": "DIRECT_AGG"}

    # ── AVG — model-type and cardinality aware ────────────────────────────────
    avg_m = re.match(r'(?:AVG|AVERAGE)\(\[([^\]]+)\]\)', readable.strip(), re.IGNORECASE)
    if avg_m:
        col = avg_m.group(1)
        if model_type == "RELATIONSHIP" and cardinality == "many-to-many":
            dax_str = (f"AVERAGEX(\n"
                       f"    VALUES(TableName[JoinKey]),\n"
                       f"    CALCULATE(AVERAGE(TableName[{col}]))\n)")
            return {"dax": dax_str,
                    "note": "many-to-many RELATIONSHIP → AVERAGEX + VALUES. Replace TableName and JoinKey.",
                    "confidence": "high", "pattern": "AVERAGEX_VALUES"}
        return {"dax": f"AVERAGE(TableName[{col}])",
                "note": "Direct AVERAGE — safe for JOIN / many-to-one. Replace TableName.",
                "confidence": "high", "pattern": "DIRECT_AGG"}

    # ── Combined SUM+SUM (cross-table) ────────────────────────────────────────
    add_m = re.match(
        r'SUM\(\[([^\]]+)\]\)\s*\+\s*SUM\(\[([^\]]+)\]\)',
        readable.strip(), re.IGNORECASE
    )
    if add_m:
        if model_type == "RELATIONSHIP" and cardinality == "many-to-many":
            dax_str = (f"SUMX(\n"
                       f"    VALUES(FactTable[JoinKey]),\n"
                       f"    CALCULATE(SUM(Table1[{add_m.group(1)}])) + CALCULATE(SUM(Table2[{add_m.group(2)}]))\n)")
            return {"dax": dax_str,
                    "note": "Cross-table sum in many-to-many → SUMX + VALUES pattern. Replace table names.",
                    "confidence": "medium", "pattern": "SUMX_VALUES"}
        return {"dax": f"[{add_m.group(1)}] + [{add_m.group(2)}]",
                "note": "Combine two measures. Create each SUM as a separate measure first.",
                "confidence": "high", "pattern": "DIRECT_AGG"}

    # ── Percentage: (SUM(A)/SUM(B))*100 ──────────────────────────────────────
    pct_m = re.match(
        r'\(SUM\(\[([^\]]+)\]\)\s*/\s*SUM\(\[([^\]]+)\]\)\)\s*\*\s*100',
        readable.strip(), re.IGNORECASE
    )
    if pct_m:
        return {"dax": f"DIVIDE([{pct_m.group(1)}], [{pct_m.group(2)}]) * 100",
                "note": "DIVIDE() avoids division-by-zero errors.",
                "confidence": "high", "pattern": "DIRECT_AGG"}

    # ── Row-level IF conditional ──────────────────────────────────────────────
    cond_m = re.match(
        r'IF\s+\[([^\]]+)\]\s*=\s*"([^"]+)"\s+THEN\s+\[([^\]]+)\]\s+END',
        readable.strip(), re.IGNORECASE
    )
    if cond_m:
        dim, val, meas = cond_m.group(1), cond_m.group(2), cond_m.group(3)
        return {
            "dax": f'CALCULATE(SUM(TableName[{meas}]), TableName[{dim}] = "{val}")',
            "note": "Row-level filter → CALCULATE + filter. Replace TableName.",
            "confidence": "medium", "pattern": "CALCULATE_FILTER"
        }

    # ── General fallback substitution ─────────────────────────────────────────
    dax = readable
    SIMPLE_MAP = {
        r'\bAVG\(':       'AVERAGE(',
        r'\bCOUNTD\(':    'DISTINCTCOUNT(',
        r'\bIFNULL\(':    'IF(ISBLANK(',
        r'\bZN\(':        'IF(ISBLANK(',
        r'\bISNULL\(':    'ISBLANK(',
        r'\bIIF\(':       'IF(',
        r'\bCONTAINS\(':  'CONTAINSSTRING(',
    }
    for pat, repl in SIMPLE_MAP.items():
        dax = re.sub(pat, repl, dax, flags=re.IGNORECASE)
    dax = re.sub(r'\bIF\s+(.+?)\s+THEN\s+(.+?)\s+END',
                 r'IF(\1, \2, BLANK())', dax, flags=re.IGNORECASE | re.DOTALL)

    changed = dax.strip() != readable.strip()
    return {
        "dax": dax.strip(),
        "note": "Partial substitution — review required." if changed else "Manual conversion needed.",
        "confidence": "medium" if changed else "low",
        "pattern": "FALLBACK"
    }


# ── Cols/map alias → source-table helpers ──────────────────────────────────────

def _build_cols_alias_map(root: etree._Element) -> dict:
    """
    Build a reverse lookup from the <cols>/<map> section of the datasource.
    Returns: {alias_key (no brackets): {"table": str, "column": str}}

    Example entries from XML:
      key='[Amount (Fees)]'   value='[Fees].[Amount]'
      key='[income_class]'    value='[Brokage].[income_class]'
    After parsing:
      'Amount (Fees)'  -> {"table": "Fees",    "column": "Amount"}
      'income_class'   -> {"table": "Brokage", "column": "income_class"}
    """
    alias_map = {}
    for m in root.xpath("//datasource[not(@name='Parameters')]//cols/map"):
        key = m.get("key", "").strip("[]")
        val = m.get("value", "")
        # val may look like '[Fees].[Amount]' or 'Fees_GUID].[Amount]'
        parts = re.match(r'\[?([^\]]+)\]?\.\[?([^\]]+)\]?', val.strip())
        if parts and key:
            table_raw = parts.group(1).strip()
            # Normalize using the shared function for consistency with extract_tables
            table_clean = _normalize_table_name(table_raw)
            alias_map[key] = {
                "table":  table_clean,
                "column": parts.group(2).strip(),
            }
    return alias_map


def _infer_source_tables(formula: str, alias_map: dict) -> list:
    """
    Scan all [bracketed] field references in a Tableau formula and resolve
    each one through the alias_map to its physical source table.

    Returns a sorted list of distinct table names found.
    References that are Calculation_xxx IDs (other CFs) are skipped —
    those CFs are table-agnostic aggregates.

    Examples:
      'IF [income_class (Fees)]=...' -> ['Fees']
      'if [income_class]=... then [Amount] end' -> ['Brokage']
      'sum([Calc_A]) + sum([Calc_B])' -> []   (cross-CF aggregate)
    """
    tables = set()
    for bracket_ref in re.findall(r'\[([^\]]+)\]', formula):
        # Skip Calculation_XXXXXXX IDs — those are other calculated fields, not table aliases
        if re.match(r'Calculation_\d+', bracket_ref, re.IGNORECASE):
            continue
        info = alias_map.get(bracket_ref)
        if info:
            tables.add(info["table"])
    return sorted(tables)


# ── Individual Extraction Functions ────────────────────────────────────────────

def extract_connections(root, ds_prefixes):
    """1. Data source connection details (file paths, DB server, type)."""
    connections = []
    for nc in root.xpath("//named-connections/named-connection"):
        caption = nc.get("caption", "")
        conn = nc.find("connection")
        if conn is not None:
            connections.append({
                "caption":   caption,
                "type":      conn.get("class", ""),
                "filename":  conn.get("filename", ""),
                "server":    conn.get("server", ""),
                "database":  conn.get("database", ""),
                "schema":    conn.get("schema", ""),
                "port":      conn.get("port", ""),
            })
    return connections


def extract_tables(root, ds_prefixes):
    """2. Source tables with columns. Skips Tableau extract cache duplicates but attaches their hyper table names."""
    tables = []
    seen = set()
    
    # 1. First sweep: collect all hyper extract table names
    extract_alias_map = {}
    for rel in root.xpath("//relation[@type='table' or @type='text']"):
        name = rel.get("name", "")
        if re.search(r'_[A-Fa-f0-9]{32}$', name) or "[Extract]." in rel.get("table", ""):
            # Normalized form maps back to original for hyper lookup
            base_name = re.sub(r'_[A-Fa-f0-9]{32}$', '', name)
            extract_alias_map[base_name] = name
            extract_alias_map[base_name.replace('!', '_')] = name

    # 2. Second sweep: build final table definitions, skipping the physical hyper duplicates
    for rel in root.xpath("//relation[@type='table' or @type='text']"):
        name  = rel.get("name", "")
        rtype = rel.get("type", "")
        
        # Skip extract cache tables for the main list to prevent duplicates
        if re.search(r'_[A-Fa-f0-9]{32}$', name) or "[Extract]." in rel.get("table", ""):
            continue

        # Normalize name consistently across the system
        normalized = _normalize_table_name(name)
            
        if normalized in seen:
            continue
        seen.add(normalized)
        
        # Match back the hyper table name collected earlier
        hyper_alias = extract_alias_map.get(name, "")
        if not hyper_alias:
            hyper_alias = extract_alias_map.get(name.replace('_', '!'), "")
        
        if rtype == "text":
            tables.append({
                "name":          normalized,    # normalized, consistent name
                "raw_name":      name,          # original XML name for debugging
                "source":        rel.get("table", ""),
                "type":          "custom_sql",
                "sql":           (rel.text or "").strip(),
                "columns":       [],
                "hyper_alias":   hyper_alias
            })
        else:
            cols = [c.get("name","") for c in rel.xpath(".//column")]
            alias_keys = root.xpath(f"//cols/map[contains(@value,'[{name}].')]/@key")
            aliases = [k.strip("[]") for k in alias_keys if k.strip("[]") not in cols]
            tables.append({
                "name":            normalized,  # normalized, consistent name
                "raw_name":        name,        # original XML name for debugging
                "source":          rel.get("table", ""),
                "type":            "table",
                "columns":         cols,
                "tableau_aliases": aliases,
                "hyper_alias":     hyper_alias,
            })
    return tables


def extract_joins(root, ds_prefixes):
    """
    3. Physical join conditions from the legacy join model.
    XPath: relation[@type='join'] → clause[@type='join'] → expression[@op='='] → expression[op]
    Each child expression carries the column ref in its @op attribute (e.g. '[Table].[col]').
    """
    joins = []

    def _parse_table_col(raw: str) -> dict:
        """Split '[TableName].[column]' into {table, column}."""
        s = raw.strip().strip("[]")
        # Pattern: [Table].[col] or Table].[col or [Table].col
        m = re.match(r'\[?([^\]]+)\]?\.\[?([^\]]+)\]?', s)
        if m:
            return {"table": m.group(1).strip(), "column": m.group(2).strip()}
        # Fallback: no dot separator
        return {"table": "", "column": s}

    for rel in root.xpath("//relation[@type='join']"):
        join_type = rel.get("join", "inner")
        # Tableau stores the join clause inside <clause type='join'>
        clause = rel.find(".//clause[@type='join']")
        if clause is None:
            continue
        eq_expr = clause.find(".//expression[@op='=']")
        if eq_expr is None:
            continue
        child_exprs = eq_expr.findall("expression")
        if len(child_exprs) < 2:
            continue
        # Column refs are in @op attribute of each child expression
        left_raw  = child_exprs[0].get("op", child_exprs[0].text or "")
        right_raw = child_exprs[1].get("op", child_exprs[1].text or "")
        left  = _parse_table_col(left_raw)
        right = _parse_table_col(right_raw)
        joins.append({
            "model":        "explicit_join",
            "join_type":    join_type,
            "left_table":   left["table"],
            "left_column":  left["column"],
            "right_table":  right["table"],
            "right_column": right["column"],
        })
    return joins


def extract_relationships(root, ds_prefixes):
    """
    2b. Logical relationships (Tableau 2020.2+ object model).
    Separate from physical joins. Lives under <_.fcp.ObjectModelTableType> or <model><relationships>.
    """
    relationships = []

    def _table_from_oid(ep):
        """
        Extract a clean, normalized table name from an endpoint object-id attribute.
        Uses _normalize_table_name() for consistency with extract_tables output.
        """
        if ep is None:
            return ""
        oid = ep.get("object-id", "")
        return _normalize_table_name(oid)

    for rel in root.xpath("//*[local-name()='relationships']/*[local-name()='relationship']"):
        expr = rel.find("expression")
        left_col = right_col = ""
        if expr is not None:
            ops = expr.findall("expression")
            if len(ops) >= 2:
                left_col  = _clean_field(ops[0].get("op", ops[0].text or ""), ds_prefixes)
                right_col = _clean_field(ops[1].get("op", ops[1].text or ""), ds_prefixes)

        # Bug 4 fix: strip Tableau UI disambiguation suffix e.g. 'Account Executive (Fees)' → 'Account Executive'
        left_col  = re.sub(r'\s+\([^)]+\)$', '', left_col).strip()
        right_col = re.sub(r'\s+\([^)]+\)$', '', right_col).strip()

        fp = rel.find("first-end-point")
        sp = rel.find("second-end-point")
        relationships.append({
            "table1":              _table_from_oid(fp),
            "table2":              _table_from_oid(sp),
            "table1_column":       left_col,
            "table2_column":       right_col,
            "relationship_type":   "many-to-one",   # Tableau default; cardinality not stored in XML
            "cardinality":         rel.get("cardinality", "many-to-one"),
            "note":                "Verify cardinality before building Power BI data model"
        })
    return relationships



def extract_columns(root, ds_prefixes, caption_map, alias_map=None):
    """4. All column definitions with datatype, role, type (discrete/continuous), aggregation, format."""
    alias_map = alias_map or {}
    columns = []
    seen = set()
    for col in root.xpath("//datasource[not(@name='Parameters')]/column"):
        name    = col.get("name","").strip("[]")
        caption = col.get("caption","")
        dtype   = col.get("datatype","")
        role    = col.get("role","")             # 'dimension' | 'measure'
        ctype   = col.get("type","")             # 'discrete' | 'continuous' | 'ordinal'
        agg     = col.get("default-aggregation","")
        fmt     = col.get("default-format","")
        hidden  = col.get("hidden","false")
        geo_role = col.get("geo-role","")        # 'country', 'state', 'city', etc.
        if name in seen:
            continue
        seen.add(name)
        calc     = col.find("calculation")
        formula  = calc.get("formula","") if calc is not None else ""
        readable = _resolve_calc_ids(formula, caption_map) if formula else ""
        # Resolve source tables: scan formula for alias-key references → table names
        source_tables = _infer_source_tables(formula, alias_map) if formula else []
        columns.append({
            "internal_name":      name,
            "caption":            caption or name,
            "datatype":           dtype,
            "role":               role,            # dimension | measure
            "type":               ctype,           # discrete | continuous
            "default_aggregation": agg,
            "format":             fmt,
            "hidden":             hidden == "true",
            "geographic_role":    geo_role,
            "formula":            readable,
            "formula_type":       _classify_formula(formula) if formula else "",
            "source_tables":      source_tables,   # e.g. ["Fees"] / ["Brokage"] / [] for cross-CF
        })
    return columns


def extract_lod_calculations(root, caption_map, alias_map=None,
                             model_type: str = "FLAT",
                             cardinality: str = "many-to-one"):
    """5. LOD (fixed/include/exclude) calculations with DAX hints."""
    alias_map = alias_map or {}
    lods = []
    seen = set()
    for col in root.xpath("//datasource[not(@name='Parameters')]/column[@caption]/calculation"):
        parent  = col.getparent()
        name    = parent.get("name","").strip("[]")
        formula = col.get("formula","")
        if name in seen or not formula:
            continue
        if _classify_formula(formula) != 'LOD':
            continue
        seen.add(name)
        readable = _resolve_calc_ids(formula, caption_map)
        dax_info = _tableau_to_dax(formula, caption_map,
                                   model_type=model_type,
                                   cardinality=cardinality)
        # Parse LOD type
        lod_type = "FIXED"
        m = re.search(r'\{\s*(FIXED|INCLUDE|EXCLUDE)', formula, re.IGNORECASE)
        if m:
            lod_type = m.group(1).upper()
        dimension_match = re.search(r'\{[^:]*:\s*(.+)\}', formula)
        lods.append({
            "caption":      parent.get("caption",""),
            "lod_type":     lod_type,
            "formula":      readable,
            "dax_hint":     dax_info["dax"],
            "dax_note":     dax_info["note"],
            "dax_pattern":  dax_info.get("pattern", ""),
            "source_tables": _infer_source_tables(formula, alias_map),
        })
    return lods


def extract_table_calcs(root, caption_map, alias_map=None):
    """6. Table calculations (RUNNING_SUM, RANK, etc.)."""
    alias_map = alias_map or {}
    calcs = []
    seen = set()
    for col in root.xpath("//datasource[not(@name='Parameters')]/column[@caption]/calculation"):
        parent  = col.getparent()
        name    = parent.get("name","").strip("[]")
        formula = col.get("formula","")
        if name in seen or not formula:
            continue
        if _classify_formula(formula) != 'TABLE_CALC':
            continue
        seen.add(name)
        # Try to get table-calc sub-element
        tc = col.find("table-calc")
        calcs.append({
            "caption":       parent.get("caption",""),
            "formula":       _resolve_calc_ids(formula, caption_map),
            "tc_function":   tc.get("function","") if tc is not None else "",
            "source_tables": _infer_source_tables(formula, alias_map),
            "pbi_note":      "Table calcs → visual calculations in Power BI (no direct measure equivalent)"
        })
    return calcs


def extract_hierarchies(root, ds_prefixes):
    """7. Drill-down hierarchies."""
    hierarchies = []
    for h in root.xpath("//hierarchy"):
        levels = [_clean_field(lvl.get("field",""), ds_prefixes)
                  for lvl in h.xpath(".//level")]
        hierarchies.append({
            "name":   h.get("name",""),
            "levels": levels
        })
    return hierarchies


def extract_groups(root, ds_prefixes):
    """8. Tableau groups (manually defined member sets). Skips internal Exclusions filter groups."""
    groups = []
    for g in root.xpath("//group"):
        name = g.get("name","")
        # Skip internal Tableau filter groups and null placeholders
        if not name or name.startswith("[Exclusions") or "%null%" in name:
            continue
        members = [_clean_field(m.text or "", ds_prefixes) for m in g.xpath(".//member")]
        groups.append({
            "name":    name,
            "field":   _clean_field(g.get("field",""), ds_prefixes),
            "members": members
        })
    return groups


def extract_sets(root, ds_prefixes):
    """9. Named sets."""
    sets = []
    for s in root.xpath("//set"):
        sets.append({
            "name":       s.get("name",""),
            "field":      _clean_field(s.get("field",""), ds_prefixes),
            "condition":  s.get("condition",""),
        })
    return sets


def extract_bins(root, ds_prefixes):
    """
    10. Bins — Tableau stores these as child <bin> elements under <column>,
    or as <calculation> with INT([Field]/size)*size pattern.
    Both forms are detected.
    """
    bins = []
    seen = set()
    # Form A: explicit <bin field="[Age]" size="10"> element
    for b in root.xpath("//bin"):
        field = _clean_field(b.get("field",""), ds_prefixes)
        size  = b.get("size","")
        if field and field not in seen:
            seen.add(field)
            bins.append({
                "field":       field,
                "size":        size,
                "source":      "bin_element",
                "pbi_note":    "Replicate with a calculated column: FLOOR([Field], size) in Power BI"
            })
    # Form B: column with INT(…)/size calculation (histogram pattern)
    for col in root.xpath("//column[@datatype]"):
        caption = col.get("caption", col.get("name",""))
        if caption in seen:
            continue
        calc = col.find("calculation")
        if calc is None:
            continue
        f = calc.get("formula","")
        # Match: INT([Field]/N)*N  or  INT([Field] / N) * N
        if re.search(r'\bINT\s*\(\s*\[.+?\]\s*/\s*(\d+)\s*\)\s*\*\s*\1', f, re.IGNORECASE):
            seen.add(caption)
            m = re.search(r'INT\s*\(\s*(\[.+?\])\s*/\s*(\d+)', f, re.IGNORECASE)
            bins.append({
                "field":    _clean_field(m.group(1), ds_prefixes) if m else caption,
                "size":     m.group(2) if m else "",
                "source":   "calculated_bin",
                "formula":  f,
                "pbi_note": "FLOOR([Field], size) in Power BI"
            })
    return bins


def extract_parameters(root, ds_prefixes):
    """
    11. Parameters — Tableau stores these in the special 'Parameters' datasource.
    Each parameter is a <column param-domain-type='...'> element.
    Allowable values can be: list (members), range (min/max/step), or all.
    """
    params = []
    seen = set()
    for ds in root.xpath("//datasource[@name='Parameters']"):
        for col in ds.xpath(".//column[@param-domain-type]"):
            name = col.get("caption") or col.get("name","")
            name = name.strip("[]")
            if name in seen:
                continue
            seen.add(name)
            domain_type = col.get("param-domain-type","")  # 'list', 'range', 'all'
            members = [
                {"alias": m.get("alias",""), "value": m.get("value","")}
                for m in col.xpath(".//member")
            ]
            params.append({
                "name":             name,
                "datatype":         col.get("datatype",""),
                "current_value":    col.get("value","").strip('"'),
                "domain_type":      domain_type,
                "range_min":        col.get("range-min",""),
                "range_max":        col.get("range-max",""),
                "step":             col.get("range-step",""),
                "allowable_values": members,
                "pbi_note":         "Numeric range → What-if parameter in Power BI; list → Slicer table",
            })
    # Fallback: some older workbooks use <parameter> elements at top level
    for p in root.xpath("//parameter"):
        name = p.get("name","").strip("[]")
        if name and name not in seen:
            seen.add(name)
            params.append({
                "name":             name,
                "datatype":         p.get("datatype",""),
                "current_value":    p.get("value",""),
                "domain_type":      p.get("param-domain-type",""),
                "allowable_values": [],
                "pbi_note":         "Older format — verify in workbook XML",
            })
    return params


def extract_dashboard_actions(root):
    """
    12. Filter / highlight / URL / parameter actions between sheets.
    Tableau stores actions under <actions> or <action-list> depending on version.
    """
    actions = []
    seen_names = set()
    # Try multiple XPath locations — varies by Tableau version
    action_nodes = (
        root.xpath("//actions/action") or
        root.xpath("//action-list/action") or
        root.xpath("//action[not(ancestor::filter)]")
    )
    for act in action_nodes:
        atype  = act.get("type", act.get("action-type",""))
        name   = act.get("caption", act.get("name",""))
        if name in seen_names:
            continue
        seen_names.add(name)
        source = act.xpath("./source-sheet-name/text()")
        target = act.xpath("./target-sheet-name/text()")
        fields = act.xpath(".//field/text()")
        url    = act.get("url", act.xpath("./url/text()")[0] if act.xpath("./url/text()") else "")
        actions.append({
            "name":    name,
            "type":    atype,
            "source":  source[0] if source else "",
            "target":  list(target),
            "fields":  list(fields),
            "url":     url,
            "pbi_note": {
                "filter":    "→ Power BI cross-filter (Edit Interactions)",
                "highlight": "→ Power BI cross-highlight (Edit Interactions)",
                "url":       "→ Power BI web URL drill-through",
                "parameter": "→ Power BI slicer / what-if parameter",
            }.get(atype, "→ Review in Power BI")
        })
    return actions


def extract_cross_filter_highlights(root, ds_prefixes, caption_map):
    """13. Per-sheet highlight actions from window viewpoints."""
    highlights = []
    for win in root.xpath("//window[@class='worksheet' and @name and not(ancestor::dashboard)]"):
        sheet  = win.get("name","")
        fields = win.xpath("viewpoint/highlight/color-one-way/field/text()")
        if fields:
            cleaned = [
                _resolve_field(_clean_field(f, ds_prefixes), caption_map)
                for f in fields
            ]
            highlights.append({
                "sheet":  sheet,
                "fields": cleaned,
                "pbi_note": "Set as cross-highlight in Power BI Edit Interactions"
            })
    return highlights


def extract_tooltips(root, ds_prefixes, caption_map):
    """14. Tooltip templates per worksheet."""
    tooltips = []
    for ws in root.xpath("//worksheet"):
        ws_name = ws.get("name","")
        tt = ws.find(".//tooltip")
        if tt is not None:
            raw = tt.text or ""
            # Resolve any calc IDs in tooltip text
            resolved = _resolve_calc_ids(raw, caption_map)
            if resolved.strip():
                tooltips.append({
                    "sheet":   ws_name,
                    "tooltip": resolved.strip()
                })
    return tooltips


def extract_number_formats(root, ds_prefixes, caption_map):
    """15. Number format strings per field per sheet."""
    formats = []
    for ws in root.xpath("//worksheet"):
        ws_name = ws.get("name","")
        for fmt in ws.xpath(".//style-rule[@element='cell']/format[@attr='text-format']"):
            field = _clean_field(fmt.get("field",""), ds_prefixes)
            field = _resolve_field(field, caption_map)
            val   = fmt.get("value","")
            if field and val:
                formats.append({
                    "sheet":        ws_name,
                    "field":        field,
                    "tableau_fmt":  val,
                    "pbi_fmt":      _translate_format(val),
                })
    return formats


def _translate_format(tableau_fmt: str) -> str:
    """Heuristic translation of Tableau format strings to Power BI equivalents."""
    if "M" in tableau_fmt and "0" in tableau_fmt:
        return "#,##0,,\" M\""       # millions
    if "%" in tableau_fmt:
        return "0.00%"
    if "#,##0" in tableau_fmt:
        return "#,##0"
    if "0.00" in tableau_fmt:
        return "#,##0.00"
    return tableau_fmt


def extract_color_palette(root, ds_prefixes, caption_map):
    """16. Global color palette definitions."""
    palettes = []
    for enc in root.xpath("//datasource/style/style-rule[@element='mark']/encoding[@attr='color']"):
        field = _resolve_field(_clean_field(enc.get("field",""), ds_prefixes), caption_map)
        mappings = []
        for m in enc.xpath("./map"):
            color  = m.get("to","")
            bucket = (m.findtext("bucket") or "").strip('"')
            mappings.append({"value": bucket, "color": color})
        palettes.append({"field": field, "mappings": mappings})
    return palettes


def extract_sorts(root, ds_prefixes, caption_map):
    """
    NEW. Explicit <sort> elements (datasource-level sort rules),
    distinct from per-sheet manual-sort. Captures field sorts, nested sorts.
    XML: //sort[@field], //sort[@column]
    """
    sorts = []
    for s in root.xpath("//sort[@field or @column]"):
        field = s.get("field") or s.get("column","")
        field = _resolve_field(_clean_field(field, ds_prefixes), caption_map)
        direction  = s.get("direction", s.get("increasing",""))
        sort_type  = s.get("type", "field")   # 'field', 'manual', 'nested', 'data_source_order'
        sort_field = _resolve_field(
            _clean_field(s.get("sort-field", s.get("aggregation-field","")), ds_prefixes),
            caption_map
        )
        sorts.append({
            "field":      field,
            "direction":  direction,
            "sort_type":  sort_type,
            "sort_field": sort_field,  # the field driving the sort
        })
    return sorts


def extract_map_layers(root, ds_prefixes, caption_map):
    """
    NEW. Map visual metadata: geographic roles on columns, lat/lon references,
    and any <map-layer> definitions.
    """
    map_layers = []
    # Collect columns with geographic roles
    geo_cols = []
    for col in root.xpath("//column[@geo-role]"):
        geo_cols.append({
            "caption":          col.get("caption", col.get("name","")),
            "geographic_role":  col.get("geo-role",""),
            "datatype":         col.get("datatype",""),
        })
    # Detect map worksheets (mark type = 'map')
    for ws in root.xpath("//worksheet"):
        mark = (ws.xpath(".//pane/mark/@class") or [""])[0]
        if mark.lower() != "map":
            continue
        table_el = ws.find(".//table")
        rows_raw = cols_raw = ""
        if table_el is not None:
            rows_raw = "".join(table_el.xpath("rows//text()")).strip()
            cols_raw = "".join(table_el.xpath("cols//text()")).strip()
        # Detect explicit lat/lon encodings
        lat_col = lon_col = ""
        for pane in ws.xpath(".//pane"):
            for enc in pane.xpath("encodings/*"):
                col_val = _resolve_field(_clean_field(enc.get("column",""), ds_prefixes), caption_map)
                tag = enc.tag.lower()
                if "latitude" in tag or "lat" in col_val.lower():
                    lat_col = col_val
                elif "longitude" in tag or "lon" in col_val.lower() or "long" in col_val.lower():
                    lon_col = col_val
        map_layers.append({
            "worksheet":          ws.get("name",""),
            "latitude_field":     lat_col,
            "longitude_field":    lon_col,
            "rows_field":         _resolve_field(_clean_field(rows_raw, ds_prefixes), caption_map),
            "cols_field":         _resolve_field(_clean_field(cols_raw, ds_prefixes), caption_map),
            "geographic_columns": geo_cols,
            "pbi_note":           "→ Power BI Map visual or ArcGIS Maps; use lat/lon or geo field",
        })
    return map_layers


def extract_blends(root, ds_prefixes):
    """
    NEW. Data Source Blending detection.
    Uses named-connection captions (the actual source names like 'insurance', 'Opportunity')
    rather than the internal federated datasource GUID name.
    """
    blends = []
    # Get actual source names from named-connections (not the federated wrapper name)
    connections = root.xpath("//named-connections/named-connection")
    if len(connections) <= 1:
        return blends  # single source, no blending
    # Map caption → connection type for each source
    source_info = []
    for nc in connections:
        conn = nc.find("connection")
        source_info.append({
            "name":     nc.get("caption", nc.get("name","")),
            "type":     conn.get("class","") if conn is not None else "",
            "filename": conn.get("filename","") if conn is not None else "",
        })
    # The primary source is typically the first datasource listed
    # Detect blend linking fields from cols/map cross-source references
    link_map = {}
    for m in root.xpath("//cols/map"):
        key = m.get("key","").strip("[]")
        val = m.get("value","").strip("[]")
        # Cross-source: key (Tableau alias) maps to value (actual table column)
        # The parenthetical in key e.g. 'Account Executive (Fees)' indicates blending source
        src_match = re.search(r'\(([^)]+)\)$', key)
        if src_match:
            secondary = src_match.group(1)
            link_map.setdefault(secondary, []).append({
                "alias":       key,
                "source_col":  val.split("].")[-1].strip("[]")
            })
    if len(source_info) > 1:
        primary = source_info[0]
        for sec in source_info[1:]:
            blends.append({
                "primary_source":   primary["name"],
                "secondary_source": sec["name"],
                "primary_type":     primary["type"],
                "secondary_type":   sec["type"],
                "linking_fields":   link_map.get(sec["name"], [])[:5],
                "pbi_note":         "Define explicit relationship in Power BI data model",
            })
    return blends


def extract_worksheets(root, ds_prefixes, caption_map):
    """17. Full worksheet metadata including encodings, filters, formats, sorts."""
    worksheets = []
    
    # Pre-build dashboard card encodings
    card_encs = {}
    for zone in root.xpath("//dashboard//zone[@type-v2 and @param and @name]"):
        sheet = zone.get("name")
        ztype = zone.get("type-v2")
        param = _resolve_field(_clean_field(zone.get("param",""), ds_prefixes), caption_map)
        if sheet and ztype in ("color","size","filter","text") and param:
            card_encs.setdefault(sheet, {})[ztype] = param

    # Pre-build window card encodings
    win_card_encs = {}
    for win in root.xpath("//window[@class='worksheet']"):
        wname = win.get("name","")
        for card in win.xpath(".//card[@type and @param]"):
            ctype = card.get("type")
            param = _resolve_field(_clean_field(card.get("param",""), ds_prefixes), caption_map)
            if ctype in ("color","size","filter","text") and param:
                win_card_encs.setdefault(wname, {})[ctype] = param

    for ws in root.xpath("//worksheet"):
        ws_name = ws.get("name","")
        title   = " ".join(ws.xpath(".//layout-options/title/formatted-text/run/text()")).strip()
        mark    = (ws.xpath(".//pane/mark/@class") or ["auto"])[0]

        table_el = ws.find(".//table")
        rows_raw = cols_raw = pages_raw = ""
        if table_el is not None:
            rows_raw  = "".join(table_el.xpath("rows//text()")).strip()
            cols_raw  = "".join(table_el.xpath("cols//text()")).strip()
            pages_raw = "".join(table_el.xpath("pages//text()")).strip()

        def _normalize_shelf(text):
            """Convert [federated.123].[sum:Calc_4:qk] to SUM([Caption])."""
            if not text: return []
            fields = []
            # Extract standard [federated...].[colname] patterns
            for m in re.finditer(r'\[([^\]]+)\]\.\[([^\]]+)\]', text):
                raw_col = m.group(2)
                agg_prefix = ""
                if raw_col.startswith("sum:"): agg_prefix = "SUM("
                elif raw_col.startswith("avg:"): agg_prefix = "AVG("
                elif raw_col.startswith("cnt:"): agg_prefix = "COUNT("
                elif raw_col.startswith("cntd:"): agg_prefix = "DISTINCTCOUNT("
                elif raw_col.startswith("min:"): agg_prefix = "MIN("
                elif raw_col.startswith("max:"): agg_prefix = "MAX("
                elif raw_col.startswith("yr:"): agg_prefix = "YEAR("
                elif raw_col.startswith("mn:"): agg_prefix = "MONTH("

                clean_col = _clean_field(raw_col, ds_prefixes)
                resolved = _resolve_field(clean_col, caption_map)

                if agg_prefix:
                    fields.append(f"{agg_prefix}[{resolved}])")
                else:
                    fields.append(f"[{resolved}]")
            return fields

        rows_norm = _normalize_shelf(rows_raw)
        cols_norm = _normalize_shelf(cols_raw)

        # Pane encodings (all panes)
        pane_encodings = []
        for i, pane in enumerate(ws.xpath(".//pane")):
            pe = {}
            for enc in pane.xpath("encodings/*"):
                col = _resolve_field(_clean_field(enc.get("column",""), ds_prefixes), caption_map)
                if col:
                    if "Multiple Values" in col:
                        col += "  [multi-measure shelf]"
                    pe[enc.tag] = col
            if pe:
                pane_encodings.append({"pane_id": pane.get("id", str(i)), "encodings": pe})

        # Filters
        filters = [
            {
                "field":   _resolve_field(_clean_field(f.get("column",""), ds_prefixes), caption_map),
                "type":    f.get("class",""),
                "context": f.get("is-context","false") == "true",
            }
            for f in ws.xpath(".//filter") if f.get("column")
        ]

        # Sort orders
        sorts = []
        for ms in ws.xpath(".//manual-sort"):
            col_s = _resolve_field(_clean_field(ms.get("column",""), ds_prefixes), caption_map)
            direction = ms.get("direction","ASC")
            buckets = []
            for b in ms.xpath(".//bucket"):
                raw = (b.text or "").strip().strip('"')
                cleaned_b = _resolve_field(_clean_field(raw, ds_prefixes), caption_map)
                buckets.append(cleaned_b)
            sorts.append({"column": col_s, "direction": direction, "values": buckets})

        # Formats
        sheet_formats = {}
        for fmt in ws.xpath(".//style-rule[@element='cell']/format[@attr='text-format']"):
            field = _resolve_field(_clean_field(fmt.get("field",""), ds_prefixes), caption_map)
            sheet_formats[field] = fmt.get("value","")

        bg = ws.xpath(".//table/style/style-rule[@element='table']/format[@attr='background-color']/@value")

        worksheets.append({
            "name":            ws_name,
            "title":           title,
            "mark_type":       mark,
            "rows_raw":        rows_raw,
            "cols_raw":        cols_raw,
            "rows":            rows_norm,
            "cols":            cols_norm,
            "pages":           pages_raw,
            "pane_encodings":  pane_encodings,
            "window_cards":    win_card_encs.get(ws_name, {}),
            "dashboard_cards": card_encs.get(ws_name, {}),
            "filters":         filters,
            "sorts":           sorts,
            "formats":         sheet_formats,
            "background_color": bg[0] if bg else "",
        })
    return worksheets


def extract_dashboards(root):
    """18. Dashboard layout with desktop and phone zones."""
    dashboards = []
    for db in root.xpath("//dashboard"):
        # Dashboard root layout size
        size_node = db.find(".//size")
        db_w = size_node.get("maxwidth", "") if size_node is not None else ""
        db_h = size_node.get("maxheight", "") if size_node is not None else ""
        
        # Desktop zones
        desktop_zones = []
        seen_d = set()
        for zone in db.xpath("./zones//zone[@name]"):
            key = (zone.get("name"), zone.get("x"), zone.get("y"))
            if key in seen_d: continue
            seen_d.add(key)
            desktop_zones.append({
                "name":     zone.get("name"),
                "x":        zone.get("x",""),
                "y":        zone.get("y",""),
                "w":        zone.get("w",""),
                "h":        zone.get("h",""),
                "type":     zone.get("type-v2","sheet"),
                "floating": zone.get("is-fixed", "false") == "false" and zone.get("x") is not None,
            })
        # Phone zones
        phone_zones = []
        seen_p = set()
        for zone in db.xpath(".//devicelayout[@name='Phone']//zone[@name]"):
            key = (zone.get("name"), zone.get("x"), zone.get("y"))
            if key in seen_p: continue
            seen_p.add(key)
            phone_zones.append({
                "name":     zone.get("name"),
                "x":        zone.get("x",""),
                "y":        zone.get("y",""),
                "w":        zone.get("w",""),
                "h":        zone.get("h",""),
                "floating": zone.get("is-fixed", "false") == "false" and zone.get("x") is not None,
            })
        dashboards.append({
            "name":          db.get("name",""),
            "width":         db_w,
            "height":        db_h,
            "desktop_zones": desktop_zones,
            "phone_zones":   phone_zones,
        })
    return dashboards


# ── Master extraction function ──────────────────────────────────────────────────

def extract_tableau_model(twbx_path: str) -> dict:
    """
    Parse a .twbx workbook and return a complete structured metadata model.
    Covers all Tableau XML metadata categories needed for Power BI migration.
    """
    root        = _load_xml(twbx_path)
    ds_prefixes = _build_ds_prefixes(root)

    # Build caption map early — used by every extractor
    caption_map = {}
    for col in root.xpath("//datasource[not(@name='Parameters')]/column[@caption]"):
        internal = col.get("name","").strip("[]")
        caption  = col.get("caption","")
        caption_map[internal] = caption

    # Build alias map once — used by all CF extractors to resolve table names
    alias_map = _build_cols_alias_map(root)

    # Detect model type once — used by DAX conversion logic throughout
    joins_raw         = extract_joins(root, ds_prefixes)
    relationships_raw = extract_relationships(root, ds_prefixes)
    model_type        = detect_model_type(root)
    cardinality       = _infer_cardinality(relationships_raw)

    model = {
        "_meta": {
            "source_file":     str(Path(twbx_path).name),
            "extractor":       "tableau_extractor.py v2",
            "extraction_time": __import__("datetime").datetime.now().isoformat(),
        },

        # ── Model type (JOIN | RELATIONSHIP | FLAT) ────────────────────────
        "model_type":       model_type,
        "cardinality":      cardinality,

        # ── Source / Connection layer ─────────────────────────────────────
        "connections":      extract_connections(root, ds_prefixes),
        "tables":           extract_tables(root, ds_prefixes),
        "joins":            joins_raw,                                 # physical joins
        "relationships":    relationships_raw,                         # logical model
        "blends":           extract_blends(root, ds_prefixes),        # data blending

        # ── Semantic / Column layer ───────────────────────────────────────
        "columns":          extract_columns(root, ds_prefixes, caption_map, alias_map),
        "lod_calcs":        extract_lod_calculations(root, caption_map, alias_map,
                                                     model_type=model_type,
                                                     cardinality=cardinality),
        "table_calcs":      extract_table_calcs(root, caption_map, alias_map),
        "hierarchies":      extract_hierarchies(root, ds_prefixes),
        "groups":           extract_groups(root, ds_prefixes),
        "sets":             extract_sets(root, ds_prefixes),
        "bins":             extract_bins(root, ds_prefixes),
        "parameters":       extract_parameters(root, ds_prefixes),

        # ── Visual / Report layer ────────────────────────────────────────
        "worksheets":       extract_worksheets(root, ds_prefixes, caption_map),
        "dashboards":       extract_dashboards(root),
        "actions":          extract_dashboard_actions(root),
        "highlights":       extract_cross_filter_highlights(root, ds_prefixes, caption_map),
        "tooltips":         extract_tooltips(root, ds_prefixes, caption_map),
        "number_formats":   extract_number_formats(root, ds_prefixes, caption_map),
        "color_palettes":   extract_color_palette(root, ds_prefixes, caption_map),
        "sort_rules":       extract_sorts(root, ds_prefixes, caption_map),
        "map_layers":       extract_map_layers(root, ds_prefixes, caption_map),

        # ── Lookup index (for downstream DAX generator) ───────────────────
        "caption_map":      caption_map,
    }
    return model


# ── CLI entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Extract a generic JSON schema model from a Tableau workbook.")
    parser.add_argument("path", help="Path to the .twbx or .twb file")
    args = parser.parse_args()
    
    path = args.path
    if not Path(path).exists():
        print(f"Error: Target workbook {path} does not exist.")
        sys.exit(1)

    print(f"Extracting: {Path(path).name}", flush=True)
    model = extract_tableau_model(path)

    out_path = Path(path).with_suffix(".model.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n✅ Model saved → {out_path}")
    print(f"\nCoverage summary:")
    schema_keys = [
        ("connections",   "Source connections"),
        ("tables",        "Source tables"),
        ("joins",         "Physical joins"),
        ("relationships", "Logical relationships"),
        ("blends",        "Data blends"),
        ("columns",       "Columns (all)"),
        ("lod_calcs",     "LOD calculations"),
        ("table_calcs",   "Table calculations"),
        ("hierarchies",   "Hierarchies"),
        ("groups",        "Groups"),
        ("sets",          "Sets"),
        ("bins",          "Bins"),
        ("parameters",    "Parameters"),
        ("worksheets",    "Worksheets"),
        ("dashboards",    "Dashboards"),
        ("actions",       "Dashboard actions"),
        ("highlights",    "Cross-filter highlights"),
        ("tooltips",      "Tooltip templates"),
        ("number_formats","Number formats"),
        ("color_palettes","Color palettes"),
        ("sort_rules",    "Sort rules"),
        ("map_layers",    "Map layers"),
    ]
    for key, label in schema_keys:
        count = len(model.get(key, []))
        status = "✅" if count > 0 else "⚪"
        print(f"  {status} {label:<30} {count}")
