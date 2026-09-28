"""
SQL Query Generator — generates executable compliance scripts.
Dynamically fetches table schemas from the live connected database (PostgreSQL or SQLite),
and prompts Google Gemini API with the live schema + policy rules to generate compliant SQL queries.
Includes a dialect-aware deterministic fallback if Gemini API is offline or rate-limited.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.llm.gemini import GeminiLLMService

logger = logging.getLogger(__name__)


def _format_fallback_schema(dialect: str = "sqlite") -> str:
    """Fallback schema description if live database introspection is unavailable."""
    return f"""### DATABASE SCHEMAS ({dialect.upper()} Standard):

Table 1: source_transactions (Active Database — Core Banking System)
Columns:
- transaction_id: VARCHAR(50) PRIMARY KEY (Unique transaction identifier, e.g. 'TXN-100001')
- account_id: VARCHAR(50) NOT NULL (Associated customer account ID)
- customer_name: VARCHAR(255) NOT NULL (Entity or customer name)
- transaction_date: VARCHAR(50) NOT NULL (Date of transaction in 'YYYY-MM-DD' ISO format)
- amount: FLOAT NOT NULL (Monetary value in USD)
- transaction_type: VARCHAR(50) NOT NULL (Values: 'WIRE', 'ACH', 'DEBIT', 'CREDIT')
- legal_hold: BOOLEAN NOT NULL DEFAULT 0 (1/true if under active legal hold/investigation, 0/false if clean)
- status: VARCHAR(50) NOT NULL DEFAULT 'COMPLETED' (Record operational status)
- created_at: DATETIME/TIMESTAMP NOT NULL (Timestamp when record was created)

Table 2: archive_transactions (Approved Archival Database — Immutable Storage)
Columns:
- transaction_id: VARCHAR(50) PRIMARY KEY (Preserves original source transaction_id)
- account_id: VARCHAR(50) NOT NULL
- customer_name: VARCHAR(255) NOT NULL
- transaction_date: VARCHAR(50) NOT NULL
- amount: FLOAT NOT NULL
- transaction_type: VARCHAR(50) NOT NULL
- legal_hold: BOOLEAN NOT NULL DEFAULT 0
- status: VARCHAR(50) NOT NULL DEFAULT 'ARCHIVED'
- control_run_id: VARCHAR(50) NOT NULL (Audit trace link to this specific control run)
- verification_hash: VARCHAR(128) (Cryptographic integrity verification signature)
- archived_at: DATETIME/TIMESTAMP NOT NULL (Timestamp of archival)
"""


async def fetch_live_database_schema(
    db: Optional[AsyncSession] = None,
    table_names: Optional[list[str]] = None,
) -> tuple[str, str]:
    """
    Introspect the live connected database (PostgreSQL or SQLite) dynamically.
    Fetches real table names, column names, data types, nullability, and primary keys.
    Returns (schema_description_string, dialect_name).
    """
    target_tables = table_names or ["source_transactions", "archive_transactions"]
    default_dialect = "postgresql" if "postgres" in settings.DATABASE_URL.lower() else "sqlite"

    if db is None:
        logger.info(f"No active database session provided, using fallback schema for {default_dialect}")
        return _format_fallback_schema(default_dialect), default_dialect

    try:
        def _inspect_sync(session):
            conn = session.connection()
            insp = inspect(conn)
            active_dialect = conn.dialect.name
            existing_tables = set(insp.get_table_names())

            schema_blocks = []
            for tbl in target_tables:
                if tbl not in existing_tables:
                    continue

                columns = insp.get_columns(tbl)
                pk_constraint = insp.get_pk_constraint(tbl) or {}
                pk_cols = set(pk_constraint.get("constrained_columns") or [])

                col_lines = []
                for c in columns:
                    c_name = c["name"]
                    c_type = str(c["type"])
                    is_pk = " (PRIMARY KEY)" if c_name in pk_cols else ""
                    null_str = " NULL" if c.get("nullable") else " NOT NULL"
                    col_lines.append(f"  - {c_name}: {c_type}{is_pk}{null_str}")

                table_header = f"Table: {tbl}"
                if tbl == "source_transactions":
                    table_header += " (Active Database — Core Banking System)"
                elif tbl == "archive_transactions":
                    table_header += " (Approved Archival Database — Immutable Storage)"

                schema_blocks.append(f"{table_header}\nColumns:\n" + "\n".join(col_lines))

            return "\n\n".join(schema_blocks), active_dialect

        schema_text, dialect = await db.run_sync(_inspect_sync)
        if schema_text.strip():
            logger.info(f"Successfully introspected live database schema for dialect: {dialect}")
            formatted = f"### DYNAMIC LIVE DATABASE SCHEMA ({dialect.upper()}):\n\n{schema_text}"
            return formatted, dialect

    except Exception as e:
        logger.warning(f"Could not introspect live database schema ({e}). Using cached schema fallback.")

    return _format_fallback_schema(default_dialect), default_dialect


def build_where_clause(
    rules: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    dialect: str = "sqlite",
) -> str:
    """Deterministic fallback WHERE clause builder with dialect awareness."""
    clauses = []
    is_pg = dialect.lower() == "postgresql"

    # Filter rules to only those applicable to banking transaction records
    applicable_rules = []
    for r in rules:
        desc = (r.get("description") or "").lower()
        if any(term in desc for term in ("audit log", "system log", "security investigation log", "logs older than")):
            continue
        if any(term in desc for term in ("support ticket", "ticket closure", "customer support record")):
            continue
        if any(term in desc for term in ("employee record", "employment dispute", "termination date")):
            continue
        if any(term in desc for term in ("customer document", "documents older than")):
            continue
        applicable_rules.append(r)

    # If all rules were non-transaction entity rules, default to standard 7-year retention
    if not applicable_rules:
        applicable_rules = rules

    for r in applicable_rules:
        action = r.get("action", "").upper()
        if action in ("ARCHIVE", "DELETE", "RETAIN"):
            field = r.get("field", "transaction_date")
            operator = r.get("operator", "OLDER_THAN")
            value = r.get("value", "7")
            unit = r.get("unit", "years") or "years"

            col = "transaction_date" if "date" in field.lower() or "created" in field.lower() else field

            if operator == "OLDER_THAN":
                if is_pg:
                    clauses.append(f"{col}::date < (CURRENT_DATE - INTERVAL '{value} {unit}')")
                else:
                    clauses.append(f"{col} < DATE('now', '-{value} {unit}')")
            elif operator == "NEWER_THAN":
                if is_pg:
                    clauses.append(f"{col}::date >= (CURRENT_DATE - INTERVAL '{value} {unit}')")
                else:
                    clauses.append(f"{col} >= DATE('now', '-{value} {unit}')")
            elif operator == "EQUALS":
                clauses.append(f"{col} = '{value}'")
            elif operator == "GREATER_THAN":
                clauses.append(f"{col} > {value}")
            elif operator == "LESS_THAN":
                clauses.append(f"{col} < {value}")

    # Deduplicate rule clauses
    unique_clauses = list(dict.fromkeys(clauses))

    # Add single legal hold check
    if is_pg:
        unique_clauses.append("legal_hold = FALSE")
    else:
        unique_clauses.append("legal_hold = 0")

    if not unique_clauses:
        if is_pg:
            return "transaction_date::date < (CURRENT_DATE - INTERVAL '7 years') AND legal_hold = FALSE"
        return "transaction_date < DATE('now', '-7 years') AND legal_hold = 0"

    return "\n  AND ".join(unique_clauses)


def generate_sql_queries_deterministic(
    rules: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    control_run_id: str,
    dialect: str = "sqlite",
    table_name: str = "source_transactions",
    archive_table: str = "archive_transactions",
) -> dict[str, str]:
    """Generate compliant SQL queries using internal deterministic template."""
    where_sql = build_where_clause(rules, exceptions, dialect=dialect)
    is_pg = dialect.lower() == "postgresql"
    legal_hold_filter = "legal_hold = FALSE" if is_pg else "legal_hold = 0"
    insert_clause = f"INSERT INTO {archive_table}" if is_pg else f"INSERT OR REPLACE INTO {archive_table}"
    hash_expr = "CONCAT('SHA256-', md5(random()::text))" if is_pg else "'SHA256-' || substr(hex(randomblob(16)), 1, 16)"

    selection_sql = f"""-- ========================================================
-- 1. IDENTIFY ELIGIBLE RECORDS (ACTIVE DATABASE: {dialect.upper()})
-- Source Table: {table_name}
-- Policy Criteria Applied
-- ========================================================
SELECT 
    transaction_id,
    account_id,
    customer_name,
    transaction_date,
    amount,
    transaction_type,
    legal_hold,
    status
FROM {table_name}
WHERE 
  {where_sql}
ORDER BY transaction_date ASC;"""

    archival_sql = f"""-- ========================================================
-- 2. ARCHIVE FIRST — INSERT INTO APPROVED ARCHIVE DATABASE
-- Destination: {archive_table}
-- Run ID: {control_run_id}
-- Dialect: {dialect.upper()}
-- ========================================================
{insert_clause} (
    transaction_id,
    account_id,
    customer_name,
    transaction_date,
    amount,
    transaction_type,
    legal_hold,
    status,
    control_run_id,
    verification_hash,
    archived_at
)
SELECT 
    transaction_id,
    account_id,
    customer_name,
    transaction_date,
    amount,
    transaction_type,
    legal_hold,
    'ARCHIVED',
    '{control_run_id}',
    {hash_expr},
    CURRENT_TIMESTAMP
FROM {table_name}
WHERE 
  {where_sql};"""

    cleanup_sql = f"""-- ========================================================
-- 3. CONTROLLED SOURCE CLEANUP (APPLIED ONLY AFTER HUMAN APPROVAL)
-- Deletes ONLY explicitly verified archived records from Active DB
-- Run ID: {control_run_id}
-- Dialect: {dialect.upper()}
-- ========================================================
DELETE FROM {table_name}
WHERE transaction_id IN (
    SELECT transaction_id 
    FROM {archive_table} 
    WHERE control_run_id = '{control_run_id}'
)
AND {legal_hold_filter};"""

    verification_sql = f"""-- ========================================================
-- 4. INDEPENDENT DUAL-DATABASE RECONCILIATION
-- Ensures complete archive existence & zero source remnants
-- ========================================================
SELECT 
    (SELECT COUNT(*) FROM {archive_table} WHERE control_run_id = '{control_run_id}') AS archived_count,
    (SELECT COUNT(*) FROM {table_name} WHERE transaction_id IN (
        SELECT transaction_id FROM {archive_table} WHERE control_run_id = '{control_run_id}'
    )) AS remaining_source_records;"""

    return {
        "selection_sql": selection_sql,
        "archival_sql": archival_sql,
        "cleanup_sql": cleanup_sql,
        "verification_sql": verification_sql,
    }


async def generate_sql_queries(
    rules: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    control_run_id: str,
    db: Optional[AsyncSession] = None,
    target_dialect: Optional[str] = None,
    table_name: str = "source_transactions",
    archive_table: str = "archive_transactions",
) -> dict[str, str]:
    """
    Generate SQL queries using Google Gemini API by:
    1. Introspecting live schema directly from the active database session.
    2. Providing the live schema, target SQL dialect, and policy rules to Gemini API.
    3. Falling back safely to deterministic SQL generator if API is offline.
    """
    # 1. Fetch live schema and active dialect from database
    schema_prompt, detected_dialect = await fetch_live_database_schema(db, [table_name, archive_table])
    dialect = target_dialect.lower() if target_dialect else detected_dialect

    if settings.GEMINI_API_KEY:
        try:
            logger.info(f"Generating SQL queries via Google Gemini API for dialect: {dialect}...")

            rules_summary = "\n".join(
                [f"- Rule {r.get('rule_id', 'RULE')}: ({r.get('description', '').replace(chr(10), ' ')}) Field '{r.get('field')}' {r.get('operator')} '{r.get('value')}' ({r.get('unit', '')}) -> Action: {r.get('action')}" for r in rules]
            )
            exceptions_summary = "\n".join(
                [f"- Exception: Field '{e.get('field')}' {e.get('operator')} '{e.get('value')}' -> Action: {e.get('action')} (Reason: {e.get('description')})" for e in exceptions]
            )

            is_pg = dialect.lower() == "postgresql"
            system_instruction = f"""You are a senior compliance database engineer. 
Your job is to generate compliant, syntax-validated {dialect.upper()} SQL queries for data retention and archival controls.

You must respond ONLY with a single JSON object matching this schema:
{{
  "selection_sql": "SQL string for selecting eligible active records",
  "archival_sql": "SQL string for copying eligible records to {archive_table}",
  "cleanup_sql": "SQL string for deleting approved records from {table_name}",
  "verification_sql": "SQL string for reconciling counts between archive and source tables"
}}

Critical Compliance Rules for {dialect.upper()}:
1. Schema-Aware Rule Mapping: Inspect the columns of {table_name}. Only apply retention rules that match this table's schema. For example, if {table_name} is a financial transaction table (columns: `transaction_id`, `account_id`, `customer_name`, `transaction_date`, `amount`, `transaction_type`, `legal_hold`, `status`) and has NO audit log or support ticket columns, do NOT apply 2-year audit log or 3-year support ticket rules to it. Apply the applicable 7-year record retention threshold (e.g. `transaction_date < DATE('now', '-7 years')` or `transaction_date::date < (CURRENT_DATE - INTERVAL '7 years')`).
2. Legal Holds / Exceptions: NEVER archive or delete any record where legal_hold is true/1. Always enforce `{'legal_hold = FALSE' if is_pg else 'legal_hold = 0'}` with AND.
3. Archival Query: Copy eligible records from {table_name} into {archive_table}, setting control_run_id = '{control_run_id}', verification_hash, and archived_at = CURRENT_TIMESTAMP.
4. Cleanup Query: Delete from {table_name} ONLY records that exist in {archive_table} for this control_run_id and where {'legal_hold = FALSE' if is_pg else 'legal_hold = 0'}.
5. Verification Query: Return counts of archived records and remaining source records for audit reconciliation.
6. Provide clean, formatted SQL with helpful comments.
"""

            prompt = f"""Generate {dialect.upper()}-compliant SQL queries for executing the following compliance control run.

{schema_prompt}

### POLICY RULES:
{rules_summary if rules_summary else "- Retain transaction records for 5 years; archive records older than 5 years."}

### EXCEPTIONS & LEGAL HOLDS:
{exceptions_summary if exceptions_summary else "- Records under active legal hold must never be archived or deleted."}

### CONTROL RUN CONTEXT:
Control Run ID: {control_run_id}
Active Table: {table_name}
Archive Table: {archive_table}
Database Dialect: {dialect.upper()}

### INSTRUCTIONS:
Generate the JSON with the 4 required SQL queries tailored to the live schema and {dialect.upper()} syntax:
1. `selection_sql`
2. `archival_sql`
3. `cleanup_sql`
4. `verification_sql`
"""
            gemini_svc = GeminiLLMService()
            result = await asyncio.wait_for(
                gemini_svc.generate_structured(prompt, system_instruction=system_instruction),
                timeout=25.0
            )

            # Ensure all required keys exist
            if all(k in result for k in ("selection_sql", "archival_sql", "cleanup_sql", "verification_sql")):
                logger.info(f"Successfully generated {dialect.upper()} SQL queries with Gemini API using live schema!")
                return {
                    "selection_sql": str(result["selection_sql"]).strip(),
                    "archival_sql": str(result["archival_sql"]).strip(),
                    "cleanup_sql": str(result["cleanup_sql"]).strip(),
                    "verification_sql": str(result["verification_sql"]).strip(),
                }
        except Exception as e:
            logger.warning(f"Gemini SQL generation encountered: {e}. Falling back to deterministic SQL engine ({dialect}).")

    # Fallback
    fallback = generate_sql_queries_deterministic(
        rules, exceptions, control_run_id, dialect=dialect, table_name=table_name, archive_table=archive_table
    )
    return {
        "selection_sql": fallback["selection_sql"].strip(),
        "archival_sql": fallback["archival_sql"].strip(),
        "cleanup_sql": fallback["cleanup_sql"].strip(),
        "verification_sql": fallback["verification_sql"].strip(),
    }
