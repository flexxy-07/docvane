import re
from dataclasses import dataclass

from backend.app.services.rag.sql.schema import ALLOWLISTED_TABLES


@dataclass
class ValidationResult:
    is_valid: bool
    sanitized_sql: str
    error: str | None = None


class SqlValidator:
    """
    Security guardrail validating LLM-generated SQL queries before execution:
    1. Blocks non-SELECT / destructive statements (DROP, DELETE, UPDATE, INSERT, ALTER, etc.).
    2. Blocks multiple statement injection (semicolons separating queries).
    3. Restricts table access strictly to ALLOWLISTED_TABLES.
    4. Enforces multi-tenant isolation (tenant_id in WHERE clause).
    5. Enforces MAX row limit of 100.
    """

    FORBIDDEN_KEYWORDS = [
        r"\bdrop\b",
        r"\bdelete\b",
        r"\bupdate\b",
        r"\binsert\b",
        r"\balter\b",
        r"\btruncate\b",
        r"\bexec\b",
        r"\bexecute\b",
        r"\bcreate\b",
        r"\bgrant\b",
        r"\brevoke\b",
        r"\bpg_\w+",
        r"\binformation_schema\b",
        r"\busers\b",
        r"\bmemberships\b",
    ]

    def validate_and_sanitize(self, sql: str, tenant_id: str) -> ValidationResult:
        query = sql.strip()
        # Strip markdown code blocks if the LLM output wrapped them
        if query.startswith("```"):
            lines = query.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            query = "\n".join(lines).strip()

        # Remove trailing semicolon
        query = query.rstrip(";").strip()

        # 1. Must be a SELECT or WITH statement
        if not re.match(r"^(select|with)\b", query, flags=re.IGNORECASE):
            return ValidationResult(
                is_valid=False,
                sanitized_sql=query,
                error="Security violation: Only SELECT queries are permitted.",
            )

        # 2. Check for multiple statements (semicolon inside query)
        if ";" in query:
            return ValidationResult(
                is_valid=False,
                sanitized_sql=query,
                error="Security violation: Multiple SQL statements are not permitted.",
            )

        # 3. Check for destructive or forbidden keywords
        lower_q = query.lower()
        for pattern in self.FORBIDDEN_KEYWORDS:
            if re.search(pattern, lower_q):
                return ValidationResult(
                    is_valid=False,
                    sanitized_sql=query,
                    error=f"Security violation: Forbidden term matching '{pattern}'.",
                )

        # 4. Check that only allowlisted tables are queried
        # Find all table references after FROM or JOIN
        table_matches = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", lower_q)
        for tbl in table_matches:
            if tbl not in ALLOWLISTED_TABLES:
                return ValidationResult(
                    is_valid=False,
                    sanitized_sql=query,
                    error=f"Access denied: Table '{tbl}' is not allowlisted for text-to-SQL.",
                )

        # 5. Enforce tenant_id isolation
        if f"tenant_id = '{tenant_id}'" not in query and f'tenant_id = "{tenant_id}"' not in query:
            # Check if tenant_id appears in where clause
            if "where" in lower_q:
                # Inject tenant_id into existing where clause
                query = re.sub(
                    r"\bwhere\b",
                    f"WHERE tenant_id = '{tenant_id}' AND (",
                    query,
                    count=1,
                    flags=re.IGNORECASE,
                )
                # Find limit or end to close parenthesis
                if re.search(r"\blimit\b", query, flags=re.IGNORECASE):
                    query = re.sub(
                        r"(\s+limit\b)",
                        r")\1",
                        query,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                else:
                    query = f"{query})"
            else:
                # Append where clause before limit/order by or at end
                if re.search(r"\b(limit|order\s+by|group\s+by)\b", query, flags=re.IGNORECASE):
                    query = re.sub(
                        r"(\s+(?:order\s+by|group\s+by|limit)\b)",
                        f" WHERE tenant_id = '{tenant_id}'\\1",
                        query,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                else:
                    query = f"{query} WHERE tenant_id = '{tenant_id}'"

        # 6. Enforce LIMIT <= 100
        limit_match = re.search(r"\blimit\s+(\d+)", query, flags=re.IGNORECASE)
        if limit_match:
            val = int(limit_match.group(1))
            if val > 100:
                query = re.sub(
                    r"\blimit\s+\d+",
                    "LIMIT 100",
                    query,
                    flags=re.IGNORECASE,
                )
        else:
            query = f"{query} LIMIT 100"

        return ValidationResult(
            is_valid=True,
            sanitized_sql=f"{query};",
            error=None,
        )
