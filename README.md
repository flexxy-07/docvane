# DocVane

> **Intelligent Document Workspace with Cryptographic Grounding & Advanced RAG**

[![Live Frontend](https://img.shields.io/badge/Frontend-docvane.vercel.app-7928CA?style=for-the-badge&logo=vercel&logoColor=white)](https://docvane.vercel.app)
[![Live Backend API](https://img.shields.io/badge/API-Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://docvane-backend.onrender.com/docs)
[![Next.js 16](https://img.shields.io/badge/Next.js-16%20App%20Router-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Supabase pgvector](https://img.shields.io/badge/Supabase-PostgreSQL%2017%20+%20pgvector-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6F00?style=for-the-badge&logo=python&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Langfuse Tracing](https://img.shields.io/badge/Observability-Langfuse%20Cloud-000000?style=for-the-badge&logo=langfuse&logoColor=white)](https://cloud.langfuse.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

---

## 🚀 Live Deployments

- **Web Application**: [https://docvane.vercel.app](https://docvane.vercel.app)
- **API Swagger Documentation**: [https://docvane-backend.onrender.com/docs](https://docvane-backend.onrender.com/docs)
- **API Health Check**: [https://docvane-backend.onrender.com/health](https://docvane-backend.onrender.com/health)
- **Observability & LLM Traces**: Connected to [Langfuse Cloud](https://cloud.langfuse.com)

---

## 📖 Executive Summary

**DocVane** is a production-grade, multi-tenant document intelligence platform designed to eliminate manual data entry from complex, scanned paperwork (invoices, receipts, legal agreements, and corporate contracts). 

Unlike standard "chat with your PDF" wrappers, DocVane couples **layout-aware OCR** and **structured field extraction** with an **in-the-loop human review queue**, **hybrid Reciprocal Rank Fusion (RRF)**, and **self-correcting LangGraph agents** that rigorously verify answers against source documents before responding.

---

## ⚡ Core Capabilities

### 1. Ingestion & Cryptographic Grounding
- **MIME & Integrity Validation**: Multi-format ingestion (PDF, PNG, JPG, TIFF) with SHA-256 deduplication per tenant.
- **Pluggable Storage Engine**: Seamlessly toggles between local filesystem storage and S3-compatible cloud object storage (**Cloudflare R2 / AWS S3**).
- **Strict Multi-Tenancy**: Built-in Row-Level Security (RLS) enforcement at the database and query levels.

### 2. Layout-Aware OCR & Multimodal Fallback
- **Dual-Engine Processing**: High-speed OCR with Docling / PaddleOCR extracting native layout geometry, bounding boxes, and tables.
- **Vision-LLM Fallback**: Degraded scans, skewed pages, and low-contrast handwriting automatically trigger multimodal vision processing to eliminate transcription errors.

### 3. Structured Field Extraction & Human Review Queue
- **Pydantic Validation**: Extracts structured entities (vendor, invoice number, line items, totals, dates, payment terms) into strictly typed schemas.
- **Confidence Scoring & HITL**: Extracted fields with confidence scores `< 0.75` are routed to `/reviews`.
- **Audited Corrections**: Human operators can review, edit, and approve flagged fields with full versioning in `audit_logs`.

### 4. Hybrid Reciprocal Rank Fusion (RRF) Retrieval
- **Dual Vector + Full-Text Search**: Combines 768-dimensional semantic embeddings (`gemini-embedding-001` with `pgvector` HNSW index) and PostgreSQL Full-Text Search (GIN `tsvector`).
- **Reciprocal Rank Fusion**: Merges semantic and keyword ranks (`k=60`) to surface exact identifiers, clause codes, and thematic answers.
- **Parent Context Expansion**: Searches small, high-density chunks and retrieves the surrounding parent section for generation context.

### 5. Self-Correcting LangGraph Orchestration
- **Stateful Query Intelligence**: Orchestrated via a LangGraph `StateGraph` with typed state transitions.
- **Query Transformation**: Conversational questions are rewritten into dense keyword representations using query expansion and HyDE.
- **Corrective RAG (CRAG)**: Passage grading node assesses chunk relevance, discarding irrelevant noise.
- **Self-RAG Hallucination Detection**: Generated responses are graded against retrieved passages. If ungrounded assertions are detected, the agent self-corrects before finalizing output.
- **Hard Execution Boundaries**: Enforced recursion limits (`recursion_limit=15`) prevent runaway loops.

### 6. Text-to-SQL Analytics Agent
- **Natural Language Aggregations**: Queries like *"What is the total spend across all approved invoices for Acme Corp?"* are routed to a specialized SQL sub-graph.
- **AST Safety & Tenant Sandboxing**: Generates read-only `SELECT` queries, injects mandatory `tenant_id` filters, limits rows, and explains calculations in plain English.

### 7. Editorial Streaming Chat UI
- **60fps Token Easing Buffer**: Real-time Server-Sent Events (SSE) streaming paired with a custom `requestAnimationFrame` easing engine that eliminates network chunk jitter for a fluid typing experience.
- **Grounded Citation Drawer**: Expandable source citations displaying document name, exact page number, and relevant excerpt snippets.
- **Signature Obsidian Aesthetic**: High-contrast dark palette (`#1A1C20`, `#22252A`), Newsreader serif headers, and glowing `#B066FF` purple accents.

### 8. Full-Stack Observability
- **Langfuse Cloud Tracing**: Every agent node, OCR fallback, retrieval call, and streaming token is instrumented with LiteLLM callbacks and hierarchical tags (`docvane`, `rag`, `chat`, `extraction`).
- **Cost & Latency Auditing**: Real-time tracking of token counts, model latency, and cost per query.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([User / Web Browser])

    subgraph Frontend ["Frontend (Vercel)"]
        NextJS["Next.js 16 App Router\n• Real-Time SSE Token Easing\n• Citation Drawer\n• Review Queue Interface"]
    end

    subgraph Backend ["Backend API (Render)"]
        FastAPI["FastAPI App\n• CORS & Tenant Context\n• SSE Streaming Endpoint\n• REST Endpoints"]
        
        subgraph LangGraph ["LangGraph Agent Orchestration"]
            Router{"Intent Router"}
            QueryTransform["Query Transformation (HyDE)"]
            HybridRetriever["Hybrid RRF Search"]
            PassageGrader["CRAG Passage Grader"]
            Synthesizer["RAG Answer Generator"]
            HallucinationCheck["Self-RAG Answer Grader"]
            SQLAgent["Text-to-SQL Engine"]
        end
    end

    subgraph Storage ["Storage & Database"]
        Supabase["Supabase PostgreSQL 17\n• pgvector (HNSW Index)\n• Full-Text Search (GIN)\n• Row-Level Security (RLS)"]
        BlobStore["Object Storage\n• Cloudflare R2 / S3 / Local"]
    end

    subgraph Observability ["Observability"]
        Langfuse["Langfuse Cloud\n• Trace Runs & Costs\n• Latency & Step Spans"]
    end

    User -->|HTTPS / SSE| NextJS
    NextJS -->|REST / SSE| FastAPI
    FastAPI --> Router
    
    Router -->|Document Q&A| QueryTransform
    QueryTransform --> HybridRetriever
    HybridRetriever -->|Vector + Keyword| Supabase
    HybridRetriever --> PassageGrader
    PassageGrader --> Synthesizer
    Synthesizer --> HallucinationCheck
    HallucinationCheck -->|Verified Answer + Citations| FastAPI
    
    Router -->|Financial / Count Analytics| SQLAgent
    SQLAgent -->|Validated Read-Only SQL| Supabase
    SQLAgent -->|Aggregated Metrics| FastAPI
    
    FastAPI -->|Store & Retrieve Files| BlobStore
    FastAPI -.->|Traces & Token Metrics| Langfuse
    FastAPI -->|Streaming SSE Chunks| NextJS
```

---

## 📁 Repository Structure

```
docvane/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints (auth, documents, reviews, retrieval)
│   │   ├── core/            # Config, telemetry, security, database session
│   │   ├── db/              # SQLAlchemy models, migrations (Alembic)
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/
│   │   │   ├── extraction/  # Structured field extraction & Pydantic schemas
│   │   │   ├── ocr/         # Docling / PaddleOCR layout parsing & vision fallback
│   │   │   ├── rag/         # Hybrid RRF, chunking, embeddings, LangGraph nodes
│   │   │   ├── sql/         # Text-to-SQL agent, AST validator, query execution
│   │   │   └── storage/     # S3 / Cloudflare R2 / Local filesystem adapters
│   │   └── main.py          # FastAPI application factory & lifecycle hooks
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Production container build
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── chat/        # 60fps streaming chat with grounded citations
│   │   │   ├── documents/   # Document library & upload interface
│   │   │   ├── reviews/     # Human-in-the-Loop field verification queue
│   │   │   └── layout.tsx   # Root navigation & theme layout
│   │   ├── components/      # UI components (Navigation, CitationDrawer, etc.)
│   │   └── lib/             # API client, tenant context, SSE streaming logic
│   ├── package.json         # Node.js dependencies
│   └── tailwind.config.js   # Tailored theme colors (Obsidian, Purple)
├── .env.example             # Template backend environment variables
├── docvane.md               # Master engineering specification & roadmap
└── README.md                # Project documentation
```

---

## 🛠️ Local Development Quickstart

### Prerequisites
- **Python 3.12+**
- **Node.js 18+** & **pnpm**
- **Docker & Docker Compose** (for local PostgreSQL + pgvector and Redis)

---

### 1. Clone the Repository
```bash
git clone https://github.com/flexxy-07/docvane.git
cd docvane
```

---

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Unix/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp ../.env.example .env
```

Edit `.env` with your API keys:
```env
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/docvane"
GEMINI_API_KEY="your-gemini-api-key"
DEFAULT_LLM_MODEL="gemini/gemini-2.5-flash"
EMBEDDING_MODEL="gemini/gemini-embedding-001"
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="https://cloud.langfuse.com"
```

Start the backend server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### 3. Frontend Setup

```bash
# Navigate to frontend (from repository root)
cd ../frontend

# Install dependencies
pnpm install

# Configure local environment
cat <<EOF > .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_DEFAULT_TENANT_ID=11111111-1111-1111-1111-111111111111
EOF

# Start Next.js development server
pnpm dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## ⚙️ Environment Variables Reference

### Backend (`.env`)
| Variable | Description | Default |
|---|---|---|
| `ENVIRONMENT` | Runtime environment (`development`, `production`, `test`) | `development` |
| `DATABASE_URL` | PostgreSQL connection string (`asyncpg`) | `postgresql+asyncpg://...` |
| `GEMINI_API_KEY` | Google Gemini API key for LLM and embeddings | Required |
| `DEFAULT_LLM_MODEL` | Default LLM identifier for generation | `gemini/gemini-2.5-flash` |
| `EMBEDDING_MODEL` | Embedding model for chunk vectorization | `gemini/gemini-embedding-001` |
| `S3_ENDPOINT_URL` | Object storage endpoint (`local` or Cloudflare R2 URL) | `local` |
| `S3_BUCKET_NAME` | Bucket name for document uploads | `docvane-documents` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse Cloud public key | Optional |
| `LANGFUSE_SECRET_KEY` | Langfuse Cloud secret key | Optional |
| `LANGFUSE_HOST` | Langfuse Cloud endpoint URL | `https://cloud.langfuse.com` |

### Frontend (`frontend/.env.local`)
| Variable | Description | Production Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL for FastAPI backend endpoints | `https://docvane-backend.onrender.com/api/v1` |
| `NEXT_PUBLIC_DEFAULT_TENANT_ID` | Default multi-tenant isolation UUID | `11111111-1111-1111-1111-111111111111` |

---

## 🧪 Testing & Verification

Run backend unit and integration test suites:
```bash
cd backend
pytest -v
```

Run frontend typecheck and build validation:
```bash
cd frontend
pnpm run build
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  <b>DocVane</b> — Built with precision, verifiable citations, and state-of-the-art document AI.
</p>
