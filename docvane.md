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


### Phase 1: Ingestion pipeline
1. Upload endpoint (validate type/size, checksum, dedupe) → store in Cloudflare R2 / S3.
2. Document status state machine + DB transitions.
3. Celery task: fetch file, split PDF into pages/images.
4. OCR + layout parsing (Docling/PaddleOCR); store text, layout, bboxes per page.
5. Retry with exponential backoff; idempotent tasks; dead-letter handling.
6. Task metrics and structured logs per stage.

**Done:** upload a scanned PDF → pages with OCR text/layout saved; killing the worker mid-task and restarting completes it.

### Phase 2: Field extraction with confidence
1. Define Pydantic schemas: invoice (vendor, number, date, due date, line items, tax, total, currency) and contract (parties, effective date, term, renewal, payment terms, termination clauses).
2. Document classifier (invoice vs contract vs other).
3. LLM structured extraction (JSON schema output) with per-field evidence (page + bbox).
4. Confidence scoring: combine OCR confidence, LLM self-rating, validation checks (sums match, dates parse, regex formats), cross-field consistency.
5. Vision-LLM fallback for low-quality pages; record that it was used.
6. Persist to `extracted_fields` and typed `invoices` / `contracts` tables.

**Done:** sample docs yield structured fields with confidence; bad scans trigger vision fallback.

### Phase 3: Human review queue
1. Threshold config (per field type) → `needs_review` tasks.
2. API: list/claim/resolve review tasks.
3. UI: side-by-side page image (highlighted bbox) and editable field; approve/correct.
4. Audit log of every correction; corrected values override extracted ones.
5. Document moves to `reviewed` then indexing when all required fields resolved.

**Done:** low-confidence field appears in UI, can be corrected, and the correction is stored and audited.

### Phase 4: Chunking and indexing (Unit 4.10)
1. Layout-aware chunking (respect headings, clauses, tables).
2. Parent-child: small child chunks for search, parent section for context.
3. Contextual header per chunk ("Invoice INV-123 from Acme, section: Payment terms").
4. Tables kept whole; generate natural-language description; index both.
5. Local embeddings → pgvector (HNSW index); `tsvector` + GIN index for keyword.
6. Index only reviewed/approved content; reindex on correction.

**Done:** every ready document has chunks with embeddings, tsvector, headers, parent links.

### Phase 5: Retrieval (Units 4.9, 4.10, 4.11)
1. Vector search and keyword search as separate functions (tenant-filtered).
2. **RRF** to merge into one ranked list.
3. **Filter extraction** from the question (vendor, date range, doc type) → metadata filters.
4. **Reranker** over top-N candidates → top-k; expand to parent sections.
5. Config flags for each stage so setups can be compared later.
6. Log retrieval config + results to `query_logs`.

**Done:** can run the same question through vector-only, keyword-only, hybrid, hybrid+rerank and see different results.

### Phase 6: Query intelligence with LangGraph (Units 4.12, 4.13)
1. **Define the LangGraph `StateGraph`** with typed `State` (TypedDict): `question`, `rewritten_queries`, `filters`, `retrieved_chunks`, `grade`, `answer`, `citations`, `route`, `retry_count`.
2. Query rewrite; multi-query; RAG-Fusion (RRF across queries); HyDE; sub-question decomposition via `Send()`.
3. **Router node** classifying each question: direct / simple / transform / SQL / both → conditional edges in the graph.
4. Adaptive strategy selection with cost/latency tracking per node.
5. Each graph node is unit-tested independently; the full graph is integration-tested with a mock LLM.

**Done:** router decisions are logged and sensible on a hand-made set of ~20 questions; LangGraph studio visualization of the graph is committed to docs.

### Phase 7: Self-correcting RAG with LangGraph (Unit 4.14)
1. **Passage grader node:** grades each retrieved chunk; on weak results adds a rewrite-and-retry loop edge (back to query transform → retrieval).
2. **Answer-support check node:** checks if generated answer is supported by passages; loop edge to retry or terminal edge to "I don't know".
3. **Multi-hop retrieval:** implemented as a loop in the graph — retrieve → check sufficiency → retrieve more if needed.
4. **Hard caps enforced at graph level:** set `recursion_limit` on the LangGraph `CompiledGraph`; also track `retry_count` in state and add a conditional edge that breaks the loop when the cap is hit.
5. Langfuse traces every node execution including token counts and latency.

**Done:** worst-performing questions are retried within limits; LangGraph `recursion_limit` prevents infinite loops; Langfuse shows the full execution trace.

### Phase 8: Text-to-SQL agent (LangGraph sub-graph) (Unit 4.15)
1. **SQL agent sub-graph** (LangGraph `StateGraph`): `generate_sql` → `validate_sql` → `execute_sql` → `explain_result` → (on error/empty) `retry_sql` loop → terminal.
2. Schema map: table/column descriptions, sample values, example question-query pairs — injected into the `generate_sql` node prompt.
3. Read-only DB role; allow-list of tables/views; tenant RLS still enforced at query execution time.
4. SQL validation node (parse, block non-SELECT, limit rows, timeout) — hard-blocks before execution.
5. Execute, explain result, **show the query and figures** in the chat response.
6. Error/empty-result retry within `recursion_limit`; retry node rewrites SQL with error context.
7. Router integration: main graph routes to SQL sub-graph, docs retrieval, or both (e.g. "total invoiced by Acme in Q3 and what do the payment terms say?").

**Done:** counts/totals/filters answered correctly via SQL; SQL sub-graph visualization committed to docs; document questions still go to retrieval graph.

### Phase 9: Chat UI with citations
1. [x] Backend Chat Endpoint (`POST /api/v1/retrieval/chat`): wraps LangGraph RAG pipeline, providing answer synthesis, citation objects, router branch tagging, Text-to-SQL results, and node latencies.
2. [ ] Chat interface with streaming/structured answers.
3. [ ] Citations linking to document + page; highlight the source region on the page image.
4. [ ] Show route taken and SQL when used.
5. [ ] Document list, status, and upload progress views.
6. [ ] Human review queue interface for low-confidence extracted fields.

**Done:** every answer shows verifiable sources; users can query via chat with route tags, SQL inspection, and citations.

### Phase 10: Production hardening and shipping

**Target hosting stack (all free, no self-hosting required):**
- **API + Celery workers → Google Cloud Run** (containerized, scales to zero, free 2M req/month; set `min-instances=1` for API to avoid cold starts)
- **Database → Supabase** (managed Postgres + pgvector + RLS; free tier 500 MB; pgbouncer for pooling)
- **Redis → Upstash Redis** (serverless, pay-per-request, generous free tier)
- **File storage → Cloudflare R2** (10 GB free, zero egress fees, same `boto3` interface)
- **LLM tracing → Langfuse Cloud** (free tier, no infra needed)
- **Metrics/dashboards → Grafana Cloud** (free tier) + Cloud Run built-in metrics
- **Frontend → Vercel** (Next.js native, free tier, CI/CD built in)

1. Grafana Cloud dashboards + alert rules (queue depth, failure rate, LLM latency).
2. Rate limits, request size limits, timeouts, graceful shutdown on Cloud Run.
3. Supabase automated backups + point-in-time recovery; Cloudflare R2 versioning; restore test documented.
4. Secrets in Google Secret Manager; per-environment config via Cloud Run env vars.
5. GitHub Actions CI/CD: lint → test → build image → push to Artifact Registry → deploy to Cloud Run; smoke tests post-deploy.
6. Runbook (common failures: Supabase connection limit, Upstash quota, Cloud Run cold start) and README with architecture and setup.

**Done:** deployed on Cloud Run, reachable on a public URL (custom domain via Cloudflare), monitored in Grafana Cloud, with documented recovery runbook.

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

**Next action:** Phase 1, Step 1 (Document Upload endpoint with MIME validation, SHA-256 deduplication, and S3 / Cloudflare R2 storage client).
