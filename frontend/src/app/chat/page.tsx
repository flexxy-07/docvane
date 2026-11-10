"use client";

export const dynamic = "force-dynamic";

import { useEffect, useRef, useState, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Send,
  RotateCcw,
  Copy,
  Check,
  FileText,
  BookOpen,
  ShieldCheck,
  Users,
  Layers,
  Sparkles,
  FileQuestion,
  ArrowRight,
  Search,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import {
  ChatResponse,
  CitationItem,
  DocumentItem,
  fetchDocuments,
  submitChatQuestion,
} from "@/lib/api";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  responseMeta?: ChatResponse;
}

interface QueryStarter {
  category: string;
  query: string;
  description: string;
  icon: typeof Users;
}

/* ─────────────────────────────────────────────
   cleanCitationExcerpt: Strips raw RAG headers
   like "[Document: xyz | Page: n]" and cleans quotes
───────────────────────────────────────────── */
function cleanCitationExcerpt(rawContent: string): {
  docName?: string;
  pageNum?: number;
  cleanText: string;
} {
  if (!rawContent) return { cleanText: "" };
  let cleanText = rawContent.trim();
  let docName: string | undefined;
  let pageNum: number | undefined;

  // Match "[Document: <name> | Page: <num>]"
  const docMatch = cleanText.match(/^\[Document:\s*([^|]+?)\s*\|\s*Page:\s*(\d+)\]\s*/i);
  if (docMatch) {
    docName = docMatch[1].trim();
    pageNum = parseInt(docMatch[2], 10);
    cleanText = cleanText.slice(docMatch[0].length).trim();
  }

  // Also clean up any leading quotation marks or trailing quotes if doubled
  cleanText = cleanText.replace(/^["“']+|["”']+$/g, "").trim();

  // Normalize excessive spacing caused by OCR linebreaks
  cleanText = cleanText.replace(/\s+/g, " ");

  return { docName, pageNum, cleanText };
}

/* ─────────────────────────────────────────────
   renderFormattedContent: Refined editorial typography
───────────────────────────────────────────── */
function renderFormattedContent(text: string) {
  const lines = text.split("\n");
  return (
    <div className="space-y-2.5 text-sm sm:text-[15px] leading-relaxed text-[#E2E4E9]">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1.5" />;
        }

        const parseLine = (str: string) => {
          // Match bold **...**, inline code `...`, [Source \d+], and [Page \d+]
          const parts = str.split(/(\*\*.*?\*\*|`.*?`|\[Source\s+\d+\]|\[Page\s+\d+\])/g);
          return parts.map((part, pIdx) => {
            if (part.startsWith("**") && part.endsWith("**")) {
              return (
                <strong key={pIdx} className="font-semibold text-white">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            if (part.startsWith("`") && part.endsWith("`")) {
              return (
                <code
                  key={pIdx}
                  className="font-mono text-xs bg-white/10 px-1.5 py-0.5 rounded text-amber-200"
                >
                  {part.slice(1, -1)}
                </code>
              );
            }
            if (part.startsWith("[Source") || part.startsWith("[Page")) {
              return (
                <span
                  key={pIdx}
                  className="inline-flex items-center gap-1 mx-1 rounded px-1.5 py-0.5 text-[11px] font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 align-baseline"
                >
                  {part}
                </span>
              );
            }
            return part;
          });
        };

        // Numbered list: "1." or "1)"
        const numMatch = trimmed.match(/^(\d+[\.\)])\s+(.*)/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2.5 pl-2 py-0.5">
              <span className="text-amber-300/80 font-mono text-xs mt-0.5 select-none">
                {numMatch[1]}
              </span>
              <div className="flex-1">{parseLine(numMatch[2])}</div>
            </div>
          );
        }

        // Bullet point: "•", "-", "*"
        if (trimmed.startsWith("•") || trimmed.startsWith("-") || trimmed.startsWith("*")) {
          const content = trimmed.replace(/^[•\-\*]\s*/, "");
          return (
            <div key={idx} className="flex items-start gap-2.5 pl-2 py-0.5">
              <span className="text-emerald-400 text-sm mt-0.5 select-none leading-none">•</span>
              <div className="flex-1">{parseLine(content)}</div>
            </div>
          );
        }

        // Section header: "### Header" or "## Header"
        if (trimmed.startsWith("###") || trimmed.startsWith("##")) {
          const title = trimmed.replace(/^#+\s*/, "");
          return (
            <h4 key={idx} className="font-serif text-base font-semibold text-white mt-3 mb-1">
              {parseLine(title)}
            </h4>
          );
        }

        return <p key={idx}>{parseLine(trimmed)}</p>;
      })}
    </div>
  );
}

function ChatContent() {
  const searchParams = useSearchParams();
  const initialDocId = searchParams.get("docId");

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(initialDocId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetchDocuments().then((docs) => {
      setDocuments(docs);
      if (initialDocId && !selectedDocId) {
        setSelectedDocId(initialDocId);
      }
    });
  }, [initialDocId]);

  const activeDoc = useMemo(() => {
    if (!selectedDocId) return null;
    return documents.find((d) => d.id === selectedDocId) || null;
  }, [documents, selectedDocId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (questionText?: string) => {
    const q = (questionText || input).trim();
    if (!q || loading) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsgId = "user-" + Date.now();
    const newMessages: Message[] = [
      ...messages,
      { id: userMsgId, sender: "user", text: q, timestamp: timeStr },
    ];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      // If scoped to a specific document, inform retrieval seamlessly
      const effectiveQuestion = activeDoc && !q.toLowerCase().includes(activeDoc.filename.toLowerCase())
        ? `${q} (regarding document ${activeDoc.filename})`
        : q;

      const result = await submitChatQuestion(effectiveQuestion);
      setMessages([
        ...newMessages,
        {
          id: "assistant-" + Date.now(),
          sender: "assistant",
          text: result.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          responseMeta: result,
        },
      ]);
    } catch {
      setMessages([
        ...newMessages,
        {
          id: "assistant-err-" + Date.now(),
          sender: "assistant",
          text: "Could not retrieve an answer at this moment. Please check your connection and try again.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setInput("");
    inputRef.current?.focus();
  };

  const handleCopyCitation = (text: string, id: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Curated, contextual query starters based on active document
  const starters = useMemo<QueryStarter[]>(() => {
    const docName = (activeDoc?.filename || "").toLowerCase();
    const docType = (activeDoc?.doc_type || "").toLowerCase();

    const isTechOrSRS =
      docName.includes("srs") ||
      docName.includes("specification") ||
      docName.includes("architecture") ||
      docName.includes("smart document");

    if (isTechOrSRS) {
      return [
        {
          category: "PERSONNEL & ROLES",
          query: "List the team members, project leads, and their designated roles.",
          description: "Extracts full developer roster, leadership, and assignments",
          icon: Users,
        },
        {
          category: "SYSTEM ARCHITECTURE",
          query: "What is the overall system architecture and proposed tech stack?",
          description: "Outlines frontend, backend, AI modules, and framework choices",
          icon: Layers,
        },
        {
          category: "CORE OBJECTIVES",
          query: "What is the primary purpose and scope of this project?",
          description: "Synthesizes system vision, background, and target goals",
          icon: BookOpen,
        },
        {
          category: "REQUIREMENTS",
          query: "What are the critical functional requirements and design constraints?",
          description: "Surfaces priority capabilities, data flows, and performance criteria",
          icon: ShieldCheck,
        },
      ];
    }

    if (docType === "invoice") {
      return [
        {
          category: "TOTALS & TERMS",
          query: "What is the total amount due, payment terms, and invoice date?",
          description: "Finds vendor, balance due, and payment terms",
          icon: BookOpen,
        },
        {
          category: "LINE ITEMS",
          query: "List all line items, quantities, and unit pricing.",
          description: "Breaks down all itemized charges and services",
          icon: Layers,
        },
        {
          category: "REMITTANCE",
          query: "What are the payment instructions and banking details?",
          description: "Extracts routing, account details, and address",
          icon: ShieldCheck,
        },
        {
          category: "TAXES & ADJUSTMENTS",
          query: "Are there any taxes, discounts, or penalties applied?",
          description: "Verifies tax calculations, credits, and penalties",
          icon: FileQuestion,
        },
      ];
    }

    if (docType === "contract") {
      return [
        {
          category: "GOVERNING JURISDICTION",
          query: "Which state or jurisdiction governs this agreement?",
          description: "Identifies controlling law, venue, and arbitration rules",
          icon: ShieldCheck,
        },
        {
          category: "LIABILITY & INDEMNITY",
          query: "What is the limitation of liability cap and indemnification clause?",
          description: "Surfaces liability limits and indemnification obligations",
          icon: FileQuestion,
        },
        {
          category: "TERMINATION",
          query: "What are the termination provisions, notice periods, and breach terms?",
          description: "Details conditions under which agreement may be ended",
          icon: BookOpen,
        },
        {
          category: "KEY OBLIGATIONS",
          query: "What are the primary performance obligations and deliverables?",
          description: "Summarizes commitments, milestones, and warranties",
          icon: Layers,
        },
      ];
    }

    // Default general starters
    return [
      {
        category: "EXECUTIVE SUMMARY",
        query: activeDoc
          ? `Summarize the primary purpose and scope of ${activeDoc.filename}.`
          : "Summarize the primary obligations and terms across all active paperwork.",
        description: "Synthesizes core objectives, parties, and scope",
        icon: BookOpen,
      },
      {
        category: "PERSONNEL & STAKEHOLDERS",
        query: "List the key team members, leads, and stakeholders identified in the records.",
        description: "Extracts individuals, assigned roles, and organizations",
        icon: Users,
      },
      {
        category: "SPECIFICATIONS & TERMS",
        query: "What are the core technical specifications or legal covenants?",
        description: "Surfaces primary technical requirements or commitments",
        icon: Layers,
      },
      {
        category: "DELIVERABLES & DATES",
        query: "What are the key deadlines, deliverables, or payment milestones?",
        description: "Tracks time-sensitive requirements and obligations",
        icon: ShieldCheck,
      },
    ];
  }, [activeDoc]);

  return (
    <div className="relative flex flex-col h-[calc(100vh-4rem)] w-full bg-[#1A1C20] text-[#E2E4E9]">
      {/* ─── Top Header Bar ─── */}
      <header className="flex-shrink-0 border-b border-white/[0.08] bg-[#1A1C20]/95 px-6 sm:px-8 py-4 backdrop-blur-md z-10">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight text-white">
                Document Inquirer
              </h1>
              {activeDoc && (
                <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-mono text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Scoped: {activeDoc.filename}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-[#A0A5AD]">
              Cryptographically grounded retrieval with page-level citations.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {activeDoc ? (
              <button
                type="button"
                onClick={() => setSelectedDocId(null)}
                title="Search across all documents in library"
                className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:text-white hover:bg-white/10 transition-colors"
              >
                <span>Query entire library</span>
              </button>
            ) : (
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span>
                  {documents.length > 0 ? `${documents.length} records indexed` : "Index active"}
                </span>
              </div>
            )}

            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleReset}
                title="Clear current inquiry session"
                className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/60 hover:text-white hover:bg-white/10 transition-colors"
              >
                <RotateCcw className="h-3 w-3" />
                <span className="hidden sm:inline">New inquiry</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ─── Main Chat / Welcome Scroll Container ─── */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-6">
        <div className="mx-auto max-w-4xl">
          {messages.length === 0 ? (
            /* ══════════════════════════════════════════
               EDITORIAL WELCOME CANVAS (Empty State)
               ══════════════════════════════════════════ */
            <div className="flex flex-col items-center justify-center pt-8 pb-12 text-center animate-in fade-in duration-300">
              {/* Emblem */}
              <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/15 bg-white/[0.04] shadow-inner">
                <BookOpen className="h-7 w-7 text-amber-200/90 stroke-[1.5]" />
              </div>

              {/* Monogram tag */}
              <span className="font-mono text-[11px] uppercase tracking-widest text-[#A0A5AD] mb-2">
                VERIFIED DOCUMENT RETRIEVAL
              </span>

              {/* Heading */}
              <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-normal text-white tracking-tight max-w-xl">
                Read between the lines of your paperwork.
              </h2>

              {/* Subtext */}
              <p className="mt-4 max-w-lg text-sm sm:text-base text-[#A0A5AD] leading-relaxed">
                Inquire across your contracts, specifications, and records. Every answer is
                extracted directly from primary passages with exact page-level citations.
              </p>

              {/* Active Document Badge Card (if scoped) */}
              {activeDoc ? (
                <div className="mt-8 flex items-center gap-3 rounded-2xl border border-emerald-500/25 bg-emerald-950/20 px-5 py-3 text-left">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-300">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white">{activeDoc.filename}</span>
                      <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-mono text-emerald-300">
                        {activeDoc.page_count} pages
                      </span>
                    </div>
                    <span className="text-xs text-white/50">
                      Primary manuscript loaded • Grounded questions scoped to this file
                    </span>
                  </div>
                </div>
              ) : (
                <div className="mt-8 flex items-center gap-2 text-xs text-white/50">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  <span>Cross-searching all verified documents in your workspace</span>
                </div>
              )}

              {/* Curated Inquiries Grid */}
              <div className="mt-10 w-full text-left">
                <div className="mb-3 flex items-center justify-between px-1">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-white/40">
                    Curated Inquiries
                  </span>
                  <span className="text-xs text-white/40">Select a prompt to begin</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {starters.map((starter, idx) => {
                    const Icon = starter.icon;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSend(starter.query)}
                        className="group relative flex flex-col justify-between rounded-xl border border-white/10 bg-[#22252A]/70 p-4 transition-all duration-200 hover:border-white/30 hover:bg-[#2A2E35] text-left"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-mono text-[10px] uppercase tracking-wider text-amber-300/80">
                              {starter.category}
                            </span>
                            <Icon className="h-4 w-4 text-white/30 group-hover:text-white/80 transition-colors" />
                          </div>
                          <p className="font-serif text-sm font-normal text-white group-hover:text-amber-100 transition-colors">
                            &ldquo;{starter.query}&rdquo;
                          </p>
                        </div>
                        <div className="mt-3 flex items-center justify-between pt-2 border-t border-white/[0.06] text-[11px] text-[#A0A5AD]">
                          <span>{starter.description}</span>
                          <ArrowRight className="h-3 w-3 opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all text-white" />
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            /* ══════════════════════════════════════════
               CONVERSATION TIMELINE
               ══════════════════════════════════════════ */
            <div className="space-y-6">
              {messages.map((msg) => {
                const isUser = msg.sender === "user";
                const meta = msg.responseMeta;

                if (isUser) {
                  return (
                    <div key={msg.id} className="flex flex-col items-end animate-in fade-in duration-200">
                      <div className="max-w-2xl rounded-2xl rounded-tr-sm border border-white/10 bg-[#252830] px-5 py-4 text-white shadow-md">
                        <div className="mb-1 flex items-center justify-between gap-4 text-[11px] font-mono text-white/40">
                          <span>You</span>
                          <span>{msg.timestamp}</span>
                        </div>
                        <p className="text-sm sm:text-base leading-relaxed text-[#F3F4F6]">
                          {msg.text}
                        </p>
                      </div>
                    </div>
                  );
                }

                // Assistant Message Card
                return (
                  <div key={msg.id} className="flex flex-col items-start animate-in fade-in duration-200">
                    <div className="w-full max-w-3xl rounded-2xl rounded-tl-sm border border-white/[0.12] bg-[#181A1F] p-6 text-[#E2E4E9] shadow-xl">
                      {/* Assistant Card Header */}
                      <div className="mb-4 flex items-center justify-between border-b border-white/[0.08] pb-3">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                            <Sparkles className="h-3.5 w-3.5" />
                          </div>
                          <span className="font-serif text-sm font-medium text-white tracking-wide">
                            DocVane Inquirer
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-emerald-300">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                            Grounded
                          </span>
                          <span className="text-[11px] font-mono text-white/40">
                            {msg.timestamp}
                          </span>
                        </div>
                      </div>

                      {/* Formatted Answer */}
                      <div className="prose-invert">
                        {renderFormattedContent(msg.text)}
                      </div>

                      {/* Verified Passages / Citations Block */}
                      {meta?.citations && meta.citations.length > 0 && (
                        <div className="mt-6 border-t border-white/[0.08] pt-4">
                          <div className="mb-3 flex items-center justify-between">
                            <span className="font-mono text-[11px] uppercase tracking-wider text-white/50">
                              Verified Passages ({meta.citations.length})
                            </span>
                            <span className="text-[11px] text-white/40">
                              Direct from primary document
                            </span>
                          </div>

                          <div className="space-y-3">
                            {meta.citations.map((cite, i) => {
                              const citeKey = `${msg.id}-${i}`;
                              const isCopied = copiedKey === citeKey;
                              const { docName, pageNum, cleanText } = cleanCitationExcerpt(
                                cite.content || ""
                              );
                              const effectivePage = cite.page_number || pageNum || 1;
                              const effectiveDoc = docName || (activeDoc?.filename ?? "Document");

                              return (
                                <div
                                  key={i}
                                  className="group relative rounded-xl border border-white/[0.08] bg-[#121316] p-4 text-xs transition-colors hover:border-white/20"
                                >
                                  <div className="mb-2 flex items-center justify-between text-[11px] text-white/50">
                                    <div className="flex items-center gap-2">
                                      <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono font-medium text-white">
                                        Source [{i + 1}]
                                      </span>
                                      <span className="text-white/70 font-mono">
                                        Page {effectivePage}
                                      </span>
                                      {effectiveDoc && (
                                        <span className="text-white/40 truncate max-w-[220px]">
                                          • {effectiveDoc}
                                        </span>
                                      )}
                                    </div>

                                    <button
                                      type="button"
                                      onClick={() => handleCopyCitation(cleanText, citeKey)}
                                      className="flex items-center gap-1 text-[11px] text-white/50 hover:text-white transition-colors"
                                    >
                                      {isCopied ? (
                                        <>
                                          <Check className="h-3 w-3 text-emerald-400" />
                                          <span className="text-emerald-400">Copied</span>
                                        </>
                                      ) : (
                                        <>
                                          <Copy className="h-3 w-3" />
                                          <span>Copy excerpt</span>
                                        </>
                                      )}
                                    </button>
                                  </div>

                                  <p className="font-serif italic text-white/80 leading-relaxed border-l-2 border-emerald-500/40 pl-3">
                                    &ldquo;{cleanText}&rdquo;
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Loading Indicator */}
              {loading && (
                <div className="flex items-center gap-3 rounded-2xl border border-white/[0.08] bg-[#181A1F] p-4 text-xs text-white/70 animate-pulse max-w-md">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-400/10 text-amber-300">
                    <Sparkles className="h-4 w-4 animate-spin" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Consulting vector index...</p>
                    <p className="text-[11px] text-white/50">Cross-verifying passages & page citations</p>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* ─── Bottom Docked Input Bar ─── */}
      <footer className="flex-shrink-0 border-t border-white/[0.08] bg-[#1A1C20]/95 px-4 sm:px-8 py-3.5 backdrop-blur-md">
        <div className="mx-auto max-w-4xl">
          {/* Active document pill above input when chatting */}
          {activeDoc && messages.length > 0 && (
            <div className="mb-2 flex items-center justify-between text-xs text-white/50 px-1">
              <span className="truncate">
                Querying: <span className="text-white font-medium">{activeDoc.filename}</span>
              </span>
              <button
                type="button"
                onClick={() => setSelectedDocId(null)}
                className="text-[11px] text-amber-300/80 hover:text-amber-200"
              >
                Switch to entire workspace
              </button>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-center"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                activeDoc
                  ? `Ask anything about ${activeDoc.filename}...`
                  : "Ask anything about your paperwork, agreements, or records..."
              }
              disabled={loading}
              className="w-full rounded-2xl border border-white/15 bg-[#22252A] py-3.5 pl-5 pr-14 text-sm text-white placeholder-white/35 outline-none transition-all focus:border-white/35 focus:bg-[#282C34] disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send inquiry"
              className="absolute right-2 flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#1A1C20] transition-all hover:bg-neutral-200 disabled:opacity-20 disabled:hover:bg-white"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>

          <p className="mt-2 text-center text-[11px] text-white/35 font-mono">
            Answers are grounded directly in your uploaded paperwork • Citations reference verified pages
          </p>
        </div>
      </footer>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-4rem)] w-full items-center justify-center bg-[#1A1C20] text-white/60">
          <div className="flex items-center gap-3">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-mono text-xs">Loading Document Inquirer...</span>
          </div>
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
