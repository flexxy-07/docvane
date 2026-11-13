# Document Intelligence Pipeline + Advanced RAG: Master Plan

> Single source of truth for requirements, decisions, architecture and build steps.
> Working agreement: build **step by step**, one small verified slice at a time. Never dump everything at once.

---

## 1. Project summary

A **web-based, production-grade, multi-tenant** system that:

1. Accepts messy scanned invoices and contracts (PDF/images).
2. Runs OCR and layout parsing (vision LLM for hard pages).
3. Extracts structured fields with **confidence scores**.
4. Sends **low-confidence fields to a human review queue**.
5. Lets users **ask questions** over the documents and extracted data, **with citations**.

**Real-world problem:** businesses still re-key data from scanned paperwork.
**Why it's interesting:** extraction quality is measurable field by field, and retrieval strategies (chunking, reranking, etc.) can be compared.

### Hard requirements
- Production grade and **shippable**: not "works on my machine" (containerized, CI/CD, deployed, monitored).
- Proper **monitoring and observability** from the start.
- **Multi-tenant**: tenants must never see each other's documents.
- Async processing with a **Redis queue + workers**, with retries.
- **Postgres + pgvector** for structured results and hybrid search (no separate vector DB).
- **Free to run**: no paid services or cards required (see section 3).
- **LangGraph** as the primary orchestration layer for all stateful agent flows (RAG pipeline, Text-to-SQL agent, sub-question decomposition, multi-hop retrieval).

### Deferred (do after core is done, but design for them now)
- **Evaluation** (field-level extraction accuracy, retrieval comparison, answer quality)
- **Security hardening** (beyond baseline tenant isolation)

---

## 2. Advanced RAG scope (all required)

| Unit | Topic | What to build in this project |
|---|---|---|
| 4.9 | Keyword + hybrid search | BM25-style keyword search + vector search, merged with **Reciprocal Rank Fusion (RRF)**. Helps most with names, IDs, invoice numbers, exact clauses. |
| 4.10 | Smarter chunks and filters | Search small / send big (parent-child chunks); contextual header on each chunk (doc + section); tables kept whole and described in words; **filters extracted from the question** (vendor, date range, doc type). |
| 4.11 | Reranking | Retrieve wide, rerank to top-k with a cross-encoder; measure latency/cost vs quality. |
| 4.12 | Query transformation | Rewrite, multi-query, RAG-Fusion, HyDE, sub-question decomposition; used selectively. |
| 4.13 | Routing / Adaptive RAG | Router chooses: answer directly / simple search / transform-and-search / SQL / both. |
| 4.14 | Self-correcting RAG | Grade retrieved passages (CRAG), check answer support (Self-RAG), multi-hop, **hard retry limits**. |
| 4.15 | RAG over structured data | **Text-to-SQL** over extracted fields: read-only, allow-listed tables, query validation, row limits, retry on error, show the query, route between docs and DB. |

---

## 3. Technology decisions (all free)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js + TypeScript | Upload, review queue, chat with citations |
| API | FastAPI (Python 3.12) | Async, typed (Pydantic) |
| Queue / workers | Celery + Upstash Redis | Serverless Redis; retries, backoff, dead-letter handling; no self-hosted instance |
| Database | **Supabase** (Postgres + pgvector + FTS) | Managed Postgres with pgvector + RLS built in; free tier; Alembic migrations still used |
| File storage | **Cloudflare R2** (S3-compatible) | 10 GB free, zero egress fees, same `boto3` code; no card required |
| OCR / layout | Docling or PaddleOCR (open source) | Vision LLM fallback for hard pages |
| LLM access | LiteLLM (provider-agnostic) | Gemini free tier or local Ollama; handle rate limits via queue |
| Embeddings | Local open-source (`bge-small` / `bge-m3`) | No API cost |
| Reranker | `bge-reranker` via Cloud Run | Cross-encoder; containerized, scales to zero |
| **Agent orchestration** | **LangGraph** | Stateful RAG pipeline graph, Text-to-SQL agent loop, sub-question fan-out (`Send()`), multi-hop retrieval; pinned to LangGraph 0.2.x |
| Observability | OpenTelemetry, Prometheus, Grafana Cloud (free tier), Langfuse Cloud (free tier) | Metrics, traces, logs, LLM traces; no self-hosted infra needed |
| Packaging | Docker + Docker Compose (dev); Cloud Run (prod) | Compose for local dev; Cloud Run for zero-cost prod deployment |
| CI/CD | GitHub Actions | Lint, test, build images, deploy to Cloud Run |
| Hosting | **Cloud Run (API + workers) + Supabase + Upstash + Cloudflare R2** | All free tiers; scales to zero; no machine needed |

**Known trade-offs:**
- Postgres FTS (`tsvector`/`ts_rank`) is not true BM25. Start with it; upgrade to ParadeDB `pg_search` later if needed.
- Supabase free tier has connection limits — use `pgbouncer` (built into Supabase) or SQLAlchemy connection pooling.
- Cloud Run cold starts (~1–2s) are acceptable for async worker tasks; the API uses min-instances=1 to avoid cold starts on the critical path.
- LangGraph adds a thin state management layer over the RAG pipeline; keep graph nodes small and testable in isolation.

---

## 4. Architecture

```
            ┌──────────────┐
            │  Next.js UI  │  upload / review / chat
            └──────┬───────┘
                   │ HTTPS
            ┌──────▼───────┐        ┌────────────┐
            │   FastAPI    │───────▶│   Redis    │ (queue, cache, rate limits)
            └──┬────────┬──┘        └─────┬──────┘
               │        │                 │
        ┌──────▼──┐  ┌──▼──────┐   ┌──────▼───────┐
        │Postgres │  │  MinIO  │◀──│ Celery worker│ OCR → extract → index
        │pgvector │  │ (files) │   └──────┬───────┘
        └─────────┘  └─────────┘          │
                                    LLM / vision LLM / embeddings / reranker

  Observability: OpenTelemetry → Prometheus/Grafana, Langfuse, structured logs
```

### Document state machine
`uploaded → queued → parsing → extracting → needs_review → reviewed → indexing → ready`
Failure branch: `failed` (with reason, retry count) → dead-letter queue → manual/auto retry.

### Query pipeline (target end state)
Implemented as a **LangGraph `StateGraph`** — each node is a testable Python function; edges are conditional based on router/grader output.

```
question
  → [LangGraph: router node] (direct | simple | transform | SQL | both)
  → [query transformation node, if needed]   ← conditional edge
  → [filter extraction node] (vendor/date/type)
  → [hybrid retrieval node] (vector + keyword, RRF) over small chunks
  → [rerank node] → expand to parent sections
  → [passage grader node] → retry/rewrite within limit  ← loop edge
  → [answer generation node] with citations
  → [answer support check node] → retry or "I don't know"  ← loop edge
  → return answer + citations (+ SQL shown if used)

  SQL branch:
  → [LangGraph: SQL agent sub-graph]
      generate SQL → validate → execute → explain → retry on error

  Sub-question branch:
  → [LangGraph: Send() fan-out] → parallel sub-retrievals → merge
```

**Hard caps enforced at graph level:** max retries, max hops, max tokens per question — graph raises `GraphRecursionError` before limits are breached.

---

## 5. Core data model (sketch)

Every table has `tenant_id` and is protected by **Row-Level Security**.

- `tenants`, `users`, `memberships` (user ↔ tenant, role)
- `documents` (id, tenant_id, type, status, storage_key, checksum, error, timestamps)
- `document_pages` (document_id, page_no, ocr_text, layout_json, ocr_engine, used_vision_fallback)
- `extraction_runs` (document_id, model, schema_version, latency, cost)
- `extracted_fields` (document_id, name, value, confidence, source_page, bbox, status: auto/needs_review/corrected)
- `review_tasks` (field_id, assignee, status, corrected_value, reviewed_at)
- `invoices` / `contracts` (typed, query-friendly tables for text-to-SQL)
- `chunks` (document_id, parent_id, page_no, bbox, content, context_header, embedding vector, tsv tsvector, chunk_type: text/table)
- `query_logs` (tenant_id, question, route, config used, retrieved ids, latency, tokens): **eval-ready**
- `audit_log` (who changed what)

---

## 6. Observability requirements (from day one)

- **Structured JSON logs** with `request_id`, `tenant_id`, `document_id`, `task_id`.
- **Metrics (Prometheus):** request rate/latency/errors, queue depth, task duration, task failures/retries, OCR time per page, extraction confidence distribution, review queue size, retrieval latency, LLM latency/tokens/cost.
- **Tracing (OpenTelemetry):** API → queue → worker → DB/LLM spans.
- **LLM tracing (Langfuse):** prompts, outputs, retrieval steps, costs.
- **Dashboards (Grafana):** pipeline health, review backlog, RAG latency.
- **Alerts:** queue backlog, failure rate, worker down, LLM error spike.
- **Health endpoints:** `/healthz` (liveness), `/readyz` (DB, Redis, MinIO).

---

## 7. Build phases and steps

Each phase ends with a **done check**. Do not start the next phase until it passes.

### Phase 0: Foundation [COMPLETED]
1. [x] Repo structure, `.gitignore`, `.env.example`, virtual environment (`.venv`), linting & typing (`ruff`, `mypy`).
2. [x] Docker Compose: `pgvector/pgvector:pg17` (port `5433:5432` to avoid local host conflicts) + `redis:7-alpine` (port `6379:6379`).
3. [x] FastAPI skeleton: config (`pydantic-settings`), structured JSON logging with contextvars (`request_id`, `tenant_id`), `/healthz` (liveness), `/readyz` (readiness).
4. [x] Alembic + initial migration (`4923eb578c10`): `tenants`, `users`, `memberships`, `documents` with `pgvector` and PostgreSQL **Row-Level Security (RLS)** policies.
5. [x] Tenant context middleware (`RequestContextMiddleware` capturing and propagating `X-Request-ID` and `X-Tenant-ID`).
6. [x] Test suite: 4 async tests passing (`test_health.py` and `test_tenant_isolation.py`), proving strict tenant isolation at the database engine level via non-superuser app role (`docvane_app`).
7. [ ] Auth (JWT tokens / tenant-scoped session auth) — to be integrated alongside upload/query routes in Phase 1.
8. [ ] OpenTelemetry / Prometheus metrics export & CI workflow.

**Done Check:** PASSED. Local Docker services healthy, test suite passing (`4 passed in 0.75s`), strict tenant isolation verified via RLS.


### Phase 1: Ingestion pipeline [COMPLETED]
1. [x] Upload endpoint (`POST /api/v1/documents/upload`) with MIME validation, SHA-256 deduplication, and file storage.
2. [x] Document status state machine (`uploaded` → `processing` → `ready` / `needs_review` / `failed`) with PostgreSQL enum transitions.
3. [x] PDF text & layout parsing via `pdfplumber` and `pypdf`, preserving tables, headings, and bboxes.
4. [x] Vision-LLM fallback for scanned pages or images via LiteLLM (`gemini/gemini-3.5-flash-lite`).
5. [x] Task metrics and structured JSON logs per stage.

**Done Check:** PASSED. Scanned PDFs parsed into pages with OCR text, layout metadata, and checksums stored.

### Phase 2: Field extraction with confidence [COMPLETED]
1. [x] Pydantic schemas: invoice (`vendor_name`, `invoice_number`, `invoice_date`, `due_date`, `line_items`, `tax_amount`, `subtotal`, `total_amount`) and contract (`title`, `parties`, `effective_date`, `expiration_date`, `term_length`, `renewal_terms`, `payment_terms`, `termination_clause`, `governing_law`).
2. [x] Heuristic and semantic document classification (invoice vs contract vs technical/business specification).
3. [x] Structured extraction via LiteLLM with per-field evidence (page number and confidence).
4. [x] Arithmetic consistency confidence validation (verifies subtotal + tax = total; penalizes discrepancies to trigger human review).
5. [x] Persisted to `extracted_fields` table in Supabase.

**Done Check:** PASSED. Sample paperwork yields structured extraction with validated confidence scores; discrepancies route to review.

### Phase 3: Human review queue [COMPLETED]
1. [x] Configurable confidence thresholds (< 75% triggers `needs_review`).
2. [x] REST API (`GET /api/v1/reviews`, `GET /api/v1/reviews/{id}`, `POST /api/v1/reviews/{id}/claim`, `POST /api/v1/reviews/{id}/resolve`).
3. [x] Verification interface at `/reviews`: split-view with highlighted document snippet, confidence badge, and approve / edit inline controls.
4. [x] Immutable audit trail logging (`audit_logs` table) capturing `old_value`, `new_value`, user ID, and timestamps.
5. [x] Unified with DocVane obsidian (`#1A1C20`) and signature purple (`#B066FF`) aesthetic.

**Done Check:** PASSED. Low-confidence fields appear in UI, can be corrected/approved, and every resolution is audited.

### Phase 4: Chunking and indexing [COMPLETED]
1. [x] Layout-aware chunking respecting document sections, clauses, and tables.
2. [x] Contextual headers on chunks (`[Document: <name> | Page: <no>]`).
3. [x] Tables preserved as Markdown structures with metadata.
4. [x] 768-dimensional embeddings generated via Gemini (`gemini/gemini-embedding-001`) and indexed in Supabase `pgvector` with HNSW cosine distance index.
5. [x] Full-text search `tsvector` with GIN indexing for exact keyword matching.

**Done Check:** PASSED. Every document is chunked, embedded, and indexed with hybrid vector and keyword search capabilities.

### Phase 5: Retrieval [COMPLETED]
1. [x] Vector semantic search and keyword search as independent query functions with tenant RLS filtering.
2. [x] Reciprocal Rank Fusion (RRF) merging vector and keyword ranks with configurable `k=60`.
3. [x] Metadata filter extraction from user queries (document scoping, dates, doc types).
4. [x] Top-k reranking and parent-context expansion.

**Done Check:** PASSED. Hybrid retrieval accurately surfaces needle-in-haystack answers with exact page numbers.

### Phase 6: Query intelligence with LangGraph [COMPLETED]
1. [x] LangGraph `StateGraph` orchestration with typed `RagState`.
2. [x] Query transformation node: rewriting conversational queries into dense keyword queries.
3. [x] Intent router node: classifying questions (direct / simple / transform / SQL / both).
4. [x] Latency and step tracking across pipeline nodes.

**Done Check:** PASSED. Router branches questions accurately across search, direct answer, and SQL tools.

### Phase 7: Self-correcting RAG with LangGraph [COMPLETED]
1. [x] Passage grader node (CRAG pattern): grades retrieved chunks for relevance to avoid irrelevant distractions.
2. [x] Answer support check node (Self-RAG): checks synthesized answer against source chunks to prevent hallucination.
3. [x] Hard recursion caps (`recursion_limit=15`) and retry boundaries preventing runaway agent loops.
4. [x] Observability integration tracing every graph node.

**Done Check:** PASSED. Hallucinations flagged, irrelevant chunks filtered, and execution boundaries strictly enforced.

### Phase 8: Text-to-SQL agent [COMPLETED]
1. [x] SQL agent sub-graph: generates SQL, validates query constraints, executes read-only queries, and explains figures.
2. [x] Schema mapping with few-shot example questions and database column schemas.
3. [x] SQL validation: blocks non-SELECT statements, enforces tenant isolation, and limits output rows.
4. [x] Seamless RAG fusion: answers combining structured database metrics and unstructured contract text.

**Done Check:** PASSED. Aggregations, counts, and financial totals executed safely and verified against database records.

### Phase 9: Chat UI with citations [COMPLETED]
1. [x] Real-time Server-Sent Events (SSE) streaming endpoint (`POST /api/v1/retrieval/chat/stream`).
2. [x] 60fps token easing buffer engine (Claude & ChatGPT grade fluid typing sensation without network chunk jitter).
3. [x] Signature aesthetic: Obsidian `#1A1C20`, `#22252A` cards, Newsreader serif typography, and `#B066FF` glowing purple cursor.
4. [x] Claude-style circular send button with upward arrow and instant state transitions.
5. [x] Contextual editorial loading indicator (*"Reading between the lines..."*, *"Examining [filename]..."*).
6. [x] Graceful citation drawer revealing page references and clean excerpt text upon stream completion.
7. [x] Document Library (`/documents`), Upload (`/documents/upload`), and Review Queue (`/reviews`).

**Done Check:** PASSED. Flawless, responsive chat experience with real-time streaming and grounded citations.

### Phase 10: Production hardening and shipping [COMPLETED]
1. [x] **Frontend Live on Vercel**: Deployed at [`https://docvane.vercel.app`](https://docvane.vercel.app).
2. [x] **Backend Live on Render**: Deployed at [`https://docvane-backend.onrender.com`](https://docvane-backend.onrender.com).
3. [x] **Database**: Managed Supabase PostgreSQL 17 with `pgvector` and strict Row-Level Security.
4. [x] **Observability**: Live Langfuse Cloud integration tracing tokens, prompt latency, dollar costs, and errors via LiteLLM callbacks.
5. [x] Production build verification: Next.js compiled with 0 errors across all routes.

**Done Check:** PASSED. DocVane is live in production, fully operational, and publicly accessible.

### Phase 11 (later): Evaluation
- **Framework: [RAGAS](https://docs.ragas.io)** (open source, free) — covers retrieval and answer quality metrics out of the box.
- Gold set of labeled docs; **field-level precision/recall** for extraction.
- Retrieval comparison across chunking strategies, hybrid vs vector-only, rerank on/off: **recall@k, MRR, NDCG**.
- Answer quality via RAGAS: **faithfulness** (is the answer grounded in retrieved context?), **answer relevance**, **context recall**, **citation accuracy**.
- LangGraph execution traces logged to `query_logs`; RAGAS evaluates against stored `retrieved_chunk_ids` and generated answers.
- Regression suite in CI: RAGAS scores must not drop below thresholds on the gold set.

### Phase 12 (later): Security hardening
- Threat modeling, authN/authZ review, pen-test of tenant isolation.
- Prompt injection defenses on document content, upload scanning, PII handling.
- Secrets rotation, dependency scanning, audit completeness, encryption at rest/in transit.

---

## 8. Things to bake in now (even though evals/security come later)

- `tenant_id` + RLS on every table from the first migration.
- `query_logs` storing question, route, retrieval config, retrieved chunk IDs, latency, tokens.
- Feature flags/config for every retrieval stage so configurations are comparable.
- Versioned extraction schemas and prompts (store `schema_version`, `prompt_version`).
- Never trust document text as instructions (keep prompts structured, content delimited).

---

## 9. Suggested repo layout

```
.
├── docker-compose.yml
├── Makefile
├── .env.example
├── backend/
│   ├── app/
│   │   ├── api/            # routes
│   │   ├── core/           # config, logging, telemetry, security
│   │   ├── db/             # models, session, migrations (alembic)
│   │   ├── services/       # ocr, extraction, chunking, retrieval, rag, sql
│   │   ├── workers/        # celery app + tasks
│   │   └── schemas/        # pydantic models
│   └── tests/
├── frontend/               # Next.js app
├── infra/                  # prometheus, grafana, otel, langfuse configs
└── docs/                   # architecture, runbook, decisions (ADRs)
```

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Free LLM rate limits | Queue + backoff; cache; local Ollama fallback |
| OCR quality on bad scans | Vision-LLM fallback; confidence + review queue |
| Cross-tenant leakage | RLS + tenant context tests from Phase 0 |
| Runaway agent loops (RAG) | LangGraph `recursion_limit` + `retry_count` in state + hard caps on tokens |
| Text-to-SQL abuse | Read-only role, allow-list, validation, limits, RLS; SQL sub-graph has its own `recursion_limit` |
| Cost/latency creep from advanced RAG | Router + per-node LangGraph metrics via Langfuse; enable techniques only where needed |
| Supabase connection limit | pgbouncer (built-in to Supabase) + SQLAlchemy pool size config |
| Cloud Run cold starts on API | `min-instances=1` for API service; workers can cold-start since they're async |
| LangGraph version churn | Pin to LangGraph 0.2.x in `requirements.txt`; changelog review before upgrades |
| Scope creep | Strict phase gates and "done" checks |

---

## 11. Working agreement for building

1. One phase at a time, one small step at a time.
2. Each step: explain what and why → minimal code → how to run/verify → confirm before moving on.
3. No giant code dumps.
4. Keep this file updated as decisions change.

**Next action:** Phase 11 (Evaluation & Benchmarking with RAGAS) or Phase 12 (Security Hardening). Core Document Intelligence & Advanced RAG System (Phases 1-10) is fully shipped and live in production!
