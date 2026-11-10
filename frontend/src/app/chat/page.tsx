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
  X,
  Loader2,
} from "lucide-react";
import {
  ChatResponse,
  DocumentItem,
  fetchDocuments,
  submitChatQuestion,
} from "@/lib/api";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  responseMeta?: ChatResponse;
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

  const docMatch = cleanText.match(/^\[Document:\s*([^|]+?)\s*\|\s*Page:\s*(\d+)\]\s*/i);
  if (docMatch) {
    docName = docMatch[1].trim();
    pageNum = parseInt(docMatch[2], 10);
    cleanText = cleanText.slice(docMatch[0].length).trim();
  }

  cleanText = cleanText.replace(/^["“']+|["”']+$/g, "").trim();
  cleanText = cleanText.replace(/\s+/g, " ");

  return { docName, pageNum, cleanText };
}

/* ─────────────────────────────────────────────
   renderFormattedContent: Clean, natural typography
───────────────────────────────────────────── */
function renderFormattedContent(text: string) {
  const lines = text.split("\n");
  return (
    <div className="space-y-2 text-sm sm:text-[15px] leading-relaxed text-[#E2E4E9]">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }

        const parseLine = (str: string) => {
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
                  className="inline-flex items-center mx-1 rounded px-1.5 py-0.2 text-[11px] font-mono text-emerald-300 bg-emerald-500/10 border border-emerald-500/20"
                >
                  {part}
                </span>
              );
            }
            return part;
          });
        };

        const numMatch = trimmed.match(/^(\d+[\.\)])\s+(.*)/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-2 py-0.5">
              <span className="text-white/40 font-mono text-xs mt-0.5 select-none">
                {numMatch[1]}
              </span>
              <div className="flex-1">{parseLine(numMatch[2])}</div>
            </div>
          );
        }

        if (trimmed.startsWith("•") || trimmed.startsWith("-") || trimmed.startsWith("*")) {
          const content = trimmed.replace(/^[•\-\*]\s*/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-2 py-0.5">
              <span className="text-emerald-400 text-sm mt-0.5 select-none leading-none">•</span>
              <div className="flex-1">{parseLine(content)}</div>
            </div>
          );
        }

        if (trimmed.startsWith("###") || trimmed.startsWith("##")) {
          const title = trimmed.replace(/^#+\s*/, "");
          return (
            <h4 key={idx} className="font-medium text-white text-base mt-2 mb-1">
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

    const userMsgId = "user-" + Date.now();
    const newMessages: Message[] = [
      ...messages,
      { id: userMsgId, sender: "user", text: q },
    ];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const effectiveQuestion =
        activeDoc && !q.toLowerCase().includes(activeDoc.filename.toLowerCase())
          ? `${q} (regarding document ${activeDoc.filename})`
          : q;

      const result = await submitChatQuestion(effectiveQuestion);
      setMessages([
        ...newMessages,
        {
          id: "assistant-" + Date.now(),
          sender: "assistant",
          text: result.answer,
          responseMeta: result,
        },
      ]);
    } catch {
      setMessages([
        ...newMessages,
        {
          id: "assistant-err-" + Date.now(),
          sender: "assistant",
          text: "Sorry, I could not retrieve an answer right now. Please try again.",
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

  // Simple, clean suggestions
  const suggestedQueries = useMemo<string[]>(() => {
    const name = (activeDoc?.filename || "").toLowerCase();
    if (name.includes("srs") || name.includes("specification") || name.includes("smart document")) {
      return [
        "Summarize this document",
        "Who are the team members and their roles?",
        "What is the system architecture?",
        "What are the main functional requirements?",
      ];
    }
    if (activeDoc?.doc_type === "invoice") {
      return [
        "What is the total amount due?",
        "What are the payment terms?",
        "List all line items and pricing",
      ];
    }
    if (activeDoc?.doc_type === "contract") {
      return [
        "Summarize the main terms of this agreement",
        "Which state or jurisdiction governs this contract?",
        "What is the limitation of liability?",
      ];
    }
    return [
      "Summarize the key points of this document",
      "Who are the people or organizations mentioned?",
      "What are the important dates or deadlines?",
    ];
  }, [activeDoc]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] w-full bg-[#1A1C20] text-[#E2E4E9]">
      {/* ─── Minimal Header Bar ─── */}
      <header className="flex-shrink-0 border-b border-white/[0.08] px-6 sm:px-8 py-3.5 bg-[#1A1C20]">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-xl sm:text-2xl font-normal text-white">
              Document Inquirer
            </h1>
            {activeDoc && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-white/80">
                <FileText className="h-3 w-3 text-white/50" />
                <span className="max-w-[200px] truncate">{activeDoc.filename}</span>
                <button
                  type="button"
                  onClick={() => setSelectedDocId(null)}
                  title="Search all documents"
                  className="text-white/40 hover:text-white ml-0.5"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>

          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-1.5 text-xs text-white/60 hover:text-white transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>New chat</span>
            </button>
          )}
        </div>
      </header>

      {/* ─── Scroll Area ─── */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6 py-6">
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 ? (
            /* ══════════════════════════════════════════
               CLEAN, SIMPLE EMPTY STATE
               ══════════════════════════════════════════ */
            <div className="flex flex-col items-center justify-center pt-16 pb-8 text-center">
              <h2 className="font-serif text-2xl sm:text-3xl font-normal text-white">
                {activeDoc
                  ? `Ask anything about ${activeDoc.filename}`
                  : "Ask anything about your documents"}
              </h2>
              <p className="mt-2 text-sm text-[#A0A5AD]">
                Answers include direct page citations and excerpts.
              </p>

              {/* Simple suggested question pills */}
              <div className="mt-8 flex flex-wrap justify-center gap-2 max-w-xl">
                {suggestedQueries.map((query, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSend(query)}
                    className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-white/80 hover:bg-white/10 hover:border-white/20 hover:text-white transition-colors"
                  >
                    {query}
                  </button>
                ))}
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
                    <div key={msg.id} className="flex justify-end">
                      <div className="max-w-xl rounded-2xl bg-[#262930] px-4 py-3 text-white text-sm sm:text-[15px] leading-relaxed">
                        {msg.text}
                      </div>
                    </div>
                  );
                }

                return (
                  <div key={msg.id} className="flex justify-start">
                    <div className="w-full rounded-2xl border border-white/[0.08] bg-[#1B1D22] p-5 text-[#E2E4E9] shadow-sm">
                      {/* Answer */}
                      <div>{renderFormattedContent(msg.text)}</div>

                      {/* Sources (clean, minimal) */}
                      {meta?.citations && meta.citations.length > 0 && (
                        <div className="mt-4 border-t border-white/[0.08] pt-3">
                          <span className="text-xs font-medium text-white/50 block mb-2">
                            Sources ({meta.citations.length})
                          </span>

                          <div className="space-y-2">
                            {meta.citations.map((cite, i) => {
                              const citeKey = `${msg.id}-${i}`;
                              const isCopied = copiedKey === citeKey;
                              const { docName, pageNum, cleanText } = cleanCitationExcerpt(
                                cite.content || ""
                              );
                              const effectivePage = cite.page_number || pageNum || 1;
                              const effectiveDoc = docName || activeDoc?.filename;

                              return (
                                <div
                                  key={i}
                                  className="rounded-lg border border-white/[0.06] bg-[#14161A] p-3 text-xs"
                                >
                                  <div className="flex items-center justify-between text-[11px] text-white/50 mb-1.5">
                                    <span className="text-white/80 font-mono">
                                      Source [{i + 1}] • Page {effectivePage}
                                      {effectiveDoc ? ` • ${effectiveDoc}` : ""}
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => handleCopyCitation(cleanText, citeKey)}
                                      className="flex items-center gap-1 text-[11px] text-white/40 hover:text-white transition-colors"
                                    >
                                      {isCopied ? (
                                        <>
                                          <Check className="h-3 w-3 text-emerald-400" />
                                          <span className="text-emerald-400">Copied</span>
                                        </>
                                      ) : (
                                        <>
                                          <Copy className="h-3 w-3" />
                                          <span>Copy</span>
                                        </>
                                      )}
                                    </button>
                                  </div>
                                  <p className="font-serif italic text-white/70 leading-relaxed">
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

              {/* Minimal Loading Indicator */}
              {loading && (
                <div className="flex items-center gap-2 text-xs text-white/60 py-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-white/70" />
                  <span>Thinking...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* ─── Minimal Docked Input Bar ─── */}
      <footer className="flex-shrink-0 border-t border-white/[0.08] px-4 sm:px-6 py-3 bg-[#1A1C20]">
        <div className="mx-auto max-w-3xl">
          {activeDoc && messages.length > 0 && (
            <div className="mb-2 flex items-center justify-between text-xs text-white/40 px-1">
              <span className="truncate">
                Searching: <span className="text-white/70">{activeDoc.filename}</span>
              </span>
              <button
                type="button"
                onClick={() => setSelectedDocId(null)}
                className="text-[11px] text-white/50 hover:text-white"
              >
                Search all documents
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
              placeholder="Ask a question..."
              disabled={loading}
              className="w-full rounded-xl border border-white/10 bg-[#22252A] py-3 pl-4 pr-12 text-sm text-white placeholder-white/40 outline-none focus:border-white/25 focus:bg-[#262A30] transition-colors"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send"
              className="absolute right-2 flex h-8 w-8 items-center justify-center rounded-lg bg-white text-[#1A1C20] transition-colors hover:bg-neutral-200 disabled:opacity-20 disabled:hover:bg-white"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>
      </footer>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-4rem)] w-full items-center justify-center bg-[#1A1C20] text-white/50 text-xs">
          Loading...
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
