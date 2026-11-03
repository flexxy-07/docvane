ALLOWLISTED_TABLES = {"invoices", "contracts", "documents", "extracted_fields"}

DATABASE_SCHEMA_DESCRIPTION = """
You are querying a PostgreSQL database for Docvane. Only query these allowlisted tables:

1. Table: invoices
   Columns:
   - id: UUID (Primary Key)
   - tenant_id: UUID (Foreign Key to tenants)
   - document_id: UUID (Foreign Key to documents)
   - vendor_name: VARCHAR(255) (Name of seller/vendor)
   - customer_name: VARCHAR(255) (Name of buyer/client)
   - invoice_number: VARCHAR(100) (Invoice identification number)
   - invoice_date: VARCHAR(50) (e.g. '2024-03-15')
   - due_date: VARCHAR(50) (e.g. '2024-04-15')
   - currency: VARCHAR(10) (e.g. 'USD', 'EUR')
   - subtotal: FLOAT (Amount before tax)
   - tax_amount: FLOAT (Total tax charged)
   - total_amount: FLOAT (Net total amount due)

2. Table: contracts
   Columns:
   - id: UUID (Primary Key)
   - tenant_id: UUID (Foreign Key to tenants)
   - document_id: UUID (Foreign Key to documents)
   - title: VARCHAR(255) (Title of the contract)
   - parties: JSON (Array of party names as strings)
   - effective_date: VARCHAR(50)
   - expiration_date: VARCHAR(50)
   - term_length: VARCHAR(100)
   - governing_law: VARCHAR(100)

3. Table: documents
   Columns:
   - id: UUID (Primary Key)
   - tenant_id: UUID (Foreign Key to tenants)
   - filename: VARCHAR(255)
   - file_type: VARCHAR(50) ('pdf', 'png', etc.)
   - doc_type: VARCHAR(50) ('invoice', 'contract', etc.)
   - status: VARCHAR(50) ('ready', 'needs_review', etc.)
   - file_size_bytes: INTEGER
   - page_count: INTEGER

4. Table: extracted_fields
   Columns:
   - id: UUID (Primary Key)
   - tenant_id: UUID (Foreign Key to tenants)
   - document_id: UUID (Foreign Key to documents)
   - field_name: VARCHAR(100)
   - field_value: TEXT
   - confidence: FLOAT (0.0 to 1.0)
   - status: VARCHAR(50) ('auto', 'needs_review', 'corrected')

CRITICAL SQL RULES:
1. ONLY write SELECT statements.
2. ALWAYS filter by tenant_id = '{tenant_id}'.
3. Use ILIKE for case-insensitive vendor/name matching (e.g. vendor_name ILIKE '%acme%').
4. ALWAYS add LIMIT 100 to avoid excessive result payloads.
5. Return ONLY executable SQL. Do NOT add markdown blocks, comments, or explanations.
"""

FEW_SHOT_SQL_EXAMPLES = [
    {
        "question": "What is the total amount invoiced across all vendors in 2024?",
        "sql": (
            "SELECT COALESCE(SUM(total_amount), 0.0) AS total_invoiced "
            "FROM invoices "
            "WHERE tenant_id = '{tenant_id}' AND invoice_date LIKE '2024%' "
            "LIMIT 100;"
        ),
    },
    {
        "question": "How many invoices were uploaded last month?",
        "sql": (
            "SELECT COUNT(*) AS invoice_count "
            "FROM invoices "
            "WHERE tenant_id = '{tenant_id}' "
            "LIMIT 100;"
        ),
    },
    {
        "question": "What is the sum of tax paid to Acme Corp?",
        "sql": (
            "SELECT COALESCE(SUM(tax_amount), 0.0) AS total_tax "
            "FROM invoices "
            "WHERE tenant_id = '{tenant_id}' AND vendor_name ILIKE '%acme%' "
            "LIMIT 100;"
        ),
    },
    {
        "question": "How many contracts have expired?",
        "sql": (
            "SELECT COUNT(*) AS expired_contract_count "
            "FROM contracts "
            "WHERE tenant_id = '{tenant_id}' AND expiration_date < CURRENT_DATE::text "
            "LIMIT 100;"
        ),
    },
]
