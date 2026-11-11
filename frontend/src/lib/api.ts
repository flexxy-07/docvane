export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://docvane-backend.onrender.com/api/v1";

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

// API fetch helpers with local storage persistence and graceful fallback
const DOCS_STORAGE_KEY = "docvane_stored_documents";
const REVIEWS_STORAGE_KEY = "docvane_stored_reviews";

function getLocalDocuments(): DocumentItem[] {
  if (typeof window === "undefined") return MOCK_DOCUMENTS;
  try {
    const raw = localStorage.getItem(DOCS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
    localStorage.setItem(DOCS_STORAGE_KEY, JSON.stringify(MOCK_DOCUMENTS));
    return MOCK_DOCUMENTS;
  } catch {
    return MOCK_DOCUMENTS;
  }
}

export function saveUploadedDocument(doc: DocumentItem): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getLocalDocuments();
    const updated = [doc, ...existing.filter((d) => d.id !== doc.id)];
    localStorage.setItem(DOCS_STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new Event("docvane:documents_updated"));
  } catch (e) {
    console.error("Failed to save document locally:", e);
  }
}

function getLocalReviews(): ReviewTaskItem[] {
  if (typeof window === "undefined") return MOCK_REVIEWS;
  try {
    const raw = localStorage.getItem(REVIEWS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
    localStorage.setItem(REVIEWS_STORAGE_KEY, JSON.stringify(MOCK_REVIEWS));
    return MOCK_REVIEWS;
  } catch {
    return MOCK_REVIEWS;
  }
}

export function saveReviewTaskUpdate(
  taskId: string,
  status: "resolved",
  correctedValue?: string | null
): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getLocalReviews();
    const updated = existing.map((task) =>
      task.id === taskId
        ? {
            ...task,
            status,
            corrected_value: correctedValue !== undefined ? correctedValue : task.field_value,
            reviewed_at: new Date().toISOString(),
          }
        : task
    );
    localStorage.setItem(REVIEWS_STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new Event("docvane:reviews_updated"));
  } catch (e) {
    console.error("Failed to update review task locally:", e);
  }
}

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
    return data.items && data.items.length > 0 ? data.items : getLocalDocuments();
  } catch {
    return getLocalDocuments();
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
    return data.items && data.items.length > 0 ? data.items : getLocalReviews();
  } catch {
    return getLocalReviews();
  }
}

export async function submitChatQuestion(
  question: string,
  tenantId: string = DEFAULT_TENANT_ID
): Promise<ChatResponse> {
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

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const detail = errorData.detail || `Chat request failed (${res.status})`;
    console.error("Chat API error:", detail);
    throw new Error(detail);
  }

  return await res.json();
}

export interface ChatStreamCallbacks {
  onSources?: (citations: CitationItem[]) => void;
  onToken?: (token: string) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

export async function streamChatQuestion(
  question: string,
  callbacks: ChatStreamCallbacks,
  tenantId: string = DEFAULT_TENANT_ID,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE_URL}/retrieval/chat/stream`;

  try {
    const res = await fetch(url, {
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
      signal,
    });

    if (!res.ok) {
      throw new Error(`Streaming failed with status ${res.status}`);
    }

    if (!res.body) {
      throw new Error("No response body available for streaming");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const payload = JSON.parse(jsonStr);
          if (payload.type === "sources" && callbacks.onSources) {
            callbacks.onSources(payload.citations || []);
          } else if (payload.type === "token" && callbacks.onToken) {
            callbacks.onToken(payload.token || "");
          } else if (payload.type === "done" && callbacks.onDone) {
            callbacks.onDone();
          } else if (payload.type === "error" && callbacks.onError) {
            callbacks.onError(new Error(payload.error || "Streaming error"));
          }
        } catch {
          // ignore incomplete JSON fragments
        }
      }
    }

    callbacks.onDone?.();
  } catch (err: unknown) {
    if (signal?.aborted) return;
    console.warn("Live stream error or fallback, switching to standard chat:", err);
    try {
      const fallbackResult = await submitChatQuestion(question, tenantId);
      callbacks.onSources?.(fallbackResult.citations || []);
      const tokens = fallbackResult.answer.match(/\S+|\s+/g) || [fallbackResult.answer];
      for (const tok of tokens) {
        callbacks.onToken?.(tok);
      }
      callbacks.onDone?.();
    } catch (fallbackErr: unknown) {
      callbacks.onError?.(
        fallbackErr instanceof Error ? fallbackErr : new Error("Failed to get response")
      );
    }
  }
}


