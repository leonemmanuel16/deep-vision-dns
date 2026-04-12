"""
Query Executor — Safely executes read-only SQL against PostgreSQL.

Security:
- Only allows SELECT statements
- Enforces LIMIT
- Runs with read-only transaction
- Timeout protection
"""

import re
import logging

import psycopg2
import psycopg2.extras

from config import settings

logger = logging.getLogger(__name__)

# Dangerous SQL patterns
FORBIDDEN_PATTERNS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bCREATE\b", r"\bTRUNCATE\b", r"\bGRANT\b",
    r"\bREVOKE\b", r"\bEXECUTE\b", r"\bCOPY\b",
]


def validate_sql(sql: str) -> bool:
    """Validate that SQL is read-only."""
    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False

    # Check for forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, sql_upper):
            return False

    return True


def ensure_limit(sql: str, max_limit: int = 100) -> str:
    """Ensure SQL has a LIMIT clause."""
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + f" LIMIT {max_limit};"
    return sql


def execute_query(sql: str) -> dict:
    """
    Execute a validated read-only SQL query.
    Returns: {columns: [...], rows: [...], row_count: int}
    """
    # Validate
    if not validate_sql(sql):
        return {"error": "Query rejected: only SELECT statements are allowed."}

    # Ensure limit
    sql = ensure_limit(sql)

    try:
        conn = psycopg2.connect(settings.database_url)
        conn.set_session(readonly=True, autocommit=True)

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SET statement_timeout = '10s';")
            cur.execute(sql)

            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [dict(row) for row in cur.fetchall()]

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }

    except psycopg2.errors.QueryCanceled:
        return {"error": "Query timed out (max 10 seconds)."}
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        return {"error": f"Query error: {str(e)}"}
    finally:
        if conn:
            conn.close()


def extract_sql(llm_response: str) -> str | None:
    """Extract SQL from LLM response (between <sql> tags)."""
    match = re.search(r"<sql>(.*?)</sql>", llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: look for SELECT statement
    match = re.search(r"(SELECT\s+.*?;)", llm_response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None
