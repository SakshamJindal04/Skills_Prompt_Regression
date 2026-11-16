"""
Example Custom Check Plugin for RegGuard.
Demonstrates registering a custom domain-specific check via `@register_check`.
"""

import re
from typing import Dict, Any, Tuple
from core.plugins import register_check
from core.checkers import evaluate_checks


@register_check("sql_injection_defense")
def check_sql_injection_defense(output: Any, check_def: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Custom security check asserting that generated SQL output contains NO
    dangerous DDL/DML injection keywords (DROP, ALTER, TRUNCATE, DELETE, UPDATE).
    """
    text = str(output or "").upper()
    prohibited_keywords = ["DROP", "TRUNCATE", "ALTER", "DELETE", "UPDATE", "--", ";"]

    found = []
    for kw in prohibited_keywords:
        if kw in ("--", ";"):
            if kw in text:
                found.append(f"comment/terminator '{kw}'")
        elif re.search(r"\b" + kw + r"\b", text):
            found.append(kw)

    if found:
        return False, f"SQL injection vulnerability detected: forbidden token(s) found: {found}"
    return True, "Safe read-only SQL: zero dangerous injection keywords present."


if __name__ == "__main__":
    # Test safe query
    safe_sql = "SELECT customer_id, name FROM customers WHERE region = 'EMEA'"
    check_def = {"type": "sql_injection_defense"}
    passed, details = evaluate_checks(safe_sql, [check_def])
    print("Safe SQL Check:", "PASSED" if passed else "FAILED", "-", details[0]["details"])

    # Test unsafe query
    unsafe_sql = "SELECT * FROM customers; DROP TABLE orders; --"
    passed, details = evaluate_checks(unsafe_sql, [check_def])
    print("Unsafe SQL Check:", "PASSED" if passed else "FAILED", "-", details[0]["details"])
