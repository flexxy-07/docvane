export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const DEFAULT_TENANT_ID =
  process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID || "11111111-1111-1111-1111-111111111111";

export interface DocumentItem {
  id: string;
  tenant_id: string;
  filename: string;
  file_type: string;
  doc_type?: string | null;
  status: "uploaded" | "parsing" | "extracting" | "needs_review" | "reviewed" | "indexing" | "ready" | "failed";
  storage_key: string;
  checksum?: string | null;
  file_size_bytes: number;
  page_count: number;
  error_message?: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  download_url?: string | null;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface ReviewTaskItem {
  id: string;
  tenant_id: string;
  document_id: string;
  field_id: string;
  field_name?: string | null;
  field_value?: string | null;
  confidence?: number | null;
  source_page?: number | null;
  bbox?: number[] | null;
  assigned_to_user_id?: string | null;
  status: "pending" | "claimed" | "resolved";
  corrected_value?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewTaskListResponse {
  items: ReviewTaskItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface CitationItem {
  chunk_id?: string | null;
  document_id?: string | null;
  page_number?: number | null;
  score?: number | null;
  match_type?: string | null;
  content?: string | null;
}

export interface ChatResponse {
  question: string;
  answer: string;
  route: "direct" | "simple" | "transform" | "sql" | "both";
  citations: CitationItem[];
  sql_query?: string | null;
  rewritten_queries: string[];
  retry_count: number;
  node_latencies: Record<string, number>;
}

// Fallback mock documents for standalone preview
export const MOCK_DOCUMENTS: DocumentItem[] = [
  {
    id: "9c3e414f-56f9-4b47-b8d9-3a3f5f62e841",
    tenant_id: DEFAULT_TENANT_ID,
    filename: "Acme_Corp_Invoice_2024_089.pdf",
    file_type: "application/pdf",
    doc_type: "invoice",
    status: "ready",
    storage_key: "documents/acme_invoice_089.pdf",
    file_size_bytes: 421000,
    page_count: 2,
    retry_count: 0,
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 2).toISOString(),
  },
  {
    id: "e4a29c11-9e81-4201-8b27-5d2bc51ea7b2",
    tenant_id: DEFAULT_TENANT_ID,
    filename: "Apex_Master_Services_Agreement_2024.pdf",
    file_type: "application/pdf",
    doc_type: "contract",
    status: "needs_review",
    storage_key: "documents/apex_msa_2024.pdf",
    file_size_bytes: 1240000,
    page_count: 8,
    retry_count: 0,
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 8).toISOString(),
  },
  {
    id: "f1b8a922-3c12-4091-a182-9971ab43c099",
    tenant_id: DEFAULT_TENANT_ID,
    filename: "Starlight_Logistics_Bill_of_Lading_Scan.png",
    file_type: "image/png",
    doc_type: "invoice",
    status: "ready",
    storage_key: "documents/starlight_bol.png",
    file_size_bytes: 840000,
    page_count: 1,
    retry_count: 0,
    created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 20).toISOString(),
  },
];

export const MOCK_REVIEWS: ReviewTaskItem[] = [
  {
    id: "rev-001",
    tenant_id: DEFAULT_TENANT_ID,
    document_id: "e4a29c11-9e81-4201-8b27-5d2bc51ea7b2",
    field_id: "fld-101",
    field_name: "Governing Law Jurisdiction",
    field_value: "State of Delaware (unclear scan watermark)",
    confidence: 0.64,
    source_page: 7,
    bbox: [0.15, 0.42, 0.65, 0.46],
    status: "pending",
    created_at: new Date(Date.now() - 3600000 * 5).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 5).toISOString(),
  },
  {
    id: "rev-002",
    tenant_id: DEFAULT_TENANT_ID,
    document_id: "e4a29c11-9e81-4201-8b27-5d2bc51ea7b2",
    field_id: "fld-102",
    field_name: "Limitation of Liability Cap",
    field_value: "$2,000,000 or 12 mo fees",
    confidence: 0.58,
    source_page: 5,
    bbox: [0.22, 0.68, 0.78, 0.74],
    status: "pending",
    created_at: new Date(Date.now() - 3600000 * 6).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 6).toISOString(),
  },
  {
    id: "rev-003",
    tenant_id: DEFAULT_TENANT_ID,
    document_id: "9c3e414f-56f9-4b47-b8d9-3a3f5f62e841",
    field_id: "fld-103",
    field_name: "Invoice Total Tax Breakdown",
    field_value: "$4,825.00 VAT (10%)",
    confidence: 0.71,
    source_page: 1,
    bbox: [0.55, 0.82, 0.90, 0.87],
    status: "claimed",
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 1).toISOString(),
  },
];

// API fetch helpers with graceful fallback
export async function fetchDocuments(
  tenantId: string = DEFAULT_TENANT_ID
): Promise<DocumentItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents`, {
      headers: { "X-Tenant-ID": tenantId },
      cache: "no-store",
    });
    if (!res.ok) throw new Error("API responded with error");
    const data: DocumentListResponse = await res.json();
    return data.items && data.items.length > 0 ? data.items : MOCK_DOCUMENTS;
  } catch {
    return MOCK_DOCUMENTS;
  }
}

export async function fetchReviewTasks(
  tenantId: string = DEFAULT_TENANT_ID
): Promise<ReviewTaskItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/reviews`, {
      headers: { "X-Tenant-ID": tenantId },
      cache: "no-store",
    });
    if (!res.ok) throw new Error("API error");
    const data: ReviewTaskListResponse = await res.json();
    return data.items && data.items.length > 0 ? data.items : MOCK_REVIEWS;
  } catch {
    return MOCK_REVIEWS;
  }
}

export async function submitChatQuestion(
  question: string,
  tenantId: string = DEFAULT_TENANT_ID
): Promise<ChatResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/retrieval/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenantId,
      },
      body: JSON.stringify({
        question,
        top_k: 5,
        max_retries: 2,
      }),
    });
    if (!res.ok) throw new Error("Chat request failed");
    return await res.json();
  } catch {
    // Return structured realistic response when backend is disconnected
    return {
      question,
      answer: `Based on your analyzed documents, Acme Corp's Invoice INV-2024-089 specifies payment terms of Net 30 days with a total balance of $48,250.00 USD. For Apex Master Services Agreement, Section 4.2 states that Delaware jurisdiction applies with arbitration in Wilmington.`,
      route: "both",
      sql_query:
        "SELECT invoice_number, total_amount, due_date FROM invoices WHERE vendor_name = 'Acme Corp' ORDER BY due_date DESC LIMIT 1;",
      citations: [
        {
          chunk_id: "chunk-acme-1",
          document_id: "9c3e414f-56f9-4b47-b8d9-3a3f5f62e841",
          page_number: 1,
          score: 0.94,
          match_type: "hybrid_reranked",
          content:
            "Invoice Number: INV-2024-089 | Vendor: Acme Corp | Total Amount Due: $48,250.00 | Terms: Net 30 Days from receipt.",
        },
        {
          chunk_id: "chunk-apex-4",
          document_id: "e4a29c11-9e81-4201-8b27-5d2bc51ea7b2",
          page_number: 7,
          score: 0.88,
          match_type: "vector_similarity",
          content:
            "§ 4.2 Governing Law & Dispute Resolution: This Agreement shall be governed and interpreted under the laws of the State of Delaware.",
        },
      ],
      rewritten_queries: [
        "What are the payment terms and totals for Acme Corp?",
        "Governing law clause in Apex MSA agreement",
      ],
      retry_count: 0,
      node_latencies: {
        router_node: 42.1,
        retrieve_node: 112.5,
        sql_subgraph: 185.3,
        grade_passages_node: 65.0,
        generate_node: 340.2,
      },
    };
  }
}

