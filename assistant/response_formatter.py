"""
Response Formatter — Formats query results into natural language.

Takes the raw SQL results and the LLM's response template
to generate a human-readable answer in Spanish.
"""

import json
from datetime import datetime, date


def format_value(value) -> str:
    """Format a single value for display."""
    if value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_results(query_result: dict, question: str) -> str:
    """
    Format query results into a readable response.
    """
    if "error" in query_result:
        return f"Lo siento, hubo un error al consultar: {query_result['error']}"

    rows = query_result.get("rows", [])
    columns = query_result.get("columns", [])
    count = query_result.get("row_count", 0)

    if count == 0:
        return "No se encontraron resultados para tu consulta."

    # Single value result (COUNT, SUM, etc.)
    if count == 1 and len(columns) == 1:
        value = format_value(rows[0][columns[0]])
        return f"**{value}**"

    # Single row with multiple columns
    if count == 1:
        row = rows[0]
        parts = []
        for col in columns:
            parts.append(f"- **{col}**: {format_value(row[col])}")
        return "\n".join(parts)

    # Multiple rows — build a summary
    lines = []
    lines.append(f"Se encontraron **{count}** resultados:\n")

    # Show up to 10 rows
    for i, row in enumerate(rows[:10]):
        row_parts = []
        for col in columns[:5]:  # Max 5 columns
            row_parts.append(f"{col}: {format_value(row[col])}")
        lines.append(f"{i+1}. {' | '.join(row_parts)}")

    if count > 10:
        lines.append(f"\n... y {count - 10} resultados mas.")

    return "\n".join(lines)


def build_final_response(
    question: str,
    sql: str,
    query_result: dict,
    llm_template: str = "",
) -> dict:
    """Build the complete response object."""
    formatted = format_results(query_result, question)

    return {
        "question": question,
        "answer": formatted,
        "sql": sql,
        "row_count": query_result.get("row_count", 0),
        "raw_data": query_result.get("rows", [])[:20],
    }
