"use client";

export const dynamic = "force-dynamic";

import { useEffect, useRef, useState, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowUp,
  RotateCcw,
  Copy,
  Check,
  FileText,
  X,
  Square,
} from "lucide-react";
import {
  ChatResponse,
  CitationItem,
  DocumentItem,
  DEFAULT_TENANT_ID,
  fetchDocuments,
  streamChatQuestion,
} from "@/lib/api";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  isStreaming?: boolean;
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
   renderFormattedContent: Clean typography + streaming cursor
───────────────────────────────────────────── */
function renderFormattedContent(text: string, isStreaming?: boolean) {
  const lines = text.split("\n");
  const lastLineIdx = lines.length - 1;

  return (
    <div className="space-y-2 text-sm sm:text-[15px] leading-relaxed text-[#E2E4E9]">
      {lines.map((line, idx) => {
        const isLastLine = idx === lastLineIdx;
        const trimmed = line.trim();
        if (!trimmed && !isLastLine) {
          return <div key={idx} className="h-1" />;
        }

        const parseLine = (str: string, showCursor: boolean) => {
          const parts = str.split(/(\*\*.*?\*\*|`.*?`|\[Source\s+\d+\]|\[Page\s+\d+\])/g);
          return (
            <>
              {parts.map((part, pIdx) => {
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
              })}
              {showCursor && (
                <span
                  className="inline-block w-1.5 h-3.5 ml-1 bg-[#B066FF] shadow-[0_0_8px_rgba(176,102,255,0.6)] rounded-sm animate-pulse align-middle"
                  aria-hidden="true"
                />
              )}
            </>
          );
        };

        const numMatch = trimmed.match(/^(\d+[\.\)])\s+(.*)/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-2 py-0.5">
              <span className="text-white/40 font-mono text-xs mt-0.5 select-none">
                {numMatch[1]}
              </span>
              <div className="flex-1">{parseLine(numMatch[2], Boolean(isStreaming && isLastLine))}</div>
            </div>
          );
        }

        if (trimmed.startsWith("•") || trimmed.startsWith("-") || trimmed.startsWith("*")) {
          const content = trimmed.replace(/^[•\-\*]\s*/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-2 py-0.5">
              <span className="text-emerald-400 text-sm mt-0.5 select-none leading-none">•</span>
              <div className="flex-1">{parseLine(content, Boolean(isStreaming && isLastLine))}</div>
            </div>
          );
        }

        if (trimmed.startsWith("###") || trimmed.startsWith("##")) {
          const title = trimmed.replace(/^#+\s*/, "");
          return (
            <h4 key={idx} className="font-medium text-white text-base mt-2 mb-1">
              {parseLine(title, Boolean(isStreaming && isLastLine))}
            </h4>
          );
        }

        return <p key={idx}>{parseLine(trimmed, Boolean(isStreaming && isLastLine))}</p>;
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
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastScrollTime = useRef<number>(0);

  // Smooth Token Buffer Engine (Claude / ChatGPT style interpolated stream)
  const streamTargetTextRef = useRef<string>("");
  const streamCurrentTextRef = useRef<string>("");
  const isNetworkDoneRef = useRef<boolean>(false);
  const animFrameIdRef = useRef<number | null>(null);
  const currentMsgIdRef = useRef<string | null>(null);

  useEffect(() => {
    fetchDocuments().then((docs) => {
      setDocuments(docs);
      if (initialDocId && !selectedDocId) {
        setSelectedDocId(initialDocId);
      }
    });
  }, [initialDocId]);

  // Clean up streaming on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
    };
  }, []);

  const activeDoc = useMemo(() => {
    if (!selectedDocId) return null;
    return documents.find((d) => d.id === selectedDocId) || null;
  }, [documents, selectedDocId]);

  useEffect(() => {
    if (!isStreaming) {
      setLoadingPhase(0);
      return;
    }
    const t = setTimeout(() => setLoadingPhase(1), 1200);
    return () => clearTimeout(t);
  }, [isStreaming]);

  const loadingPhrase = useMemo(() => {
    if (loadingPhase === 1) return "Cross-referencing verified passages...";
    if (activeDoc) {
      const shortName =
        activeDoc.filename.length > 28
          ? activeDoc.filename.slice(0, 25) + "..."
          : activeDoc.filename;
      return `Examining ${shortName}...`;
    }
    return "Reading between the lines...";
  }, [loadingPhase, activeDoc]);

  const scrollToBottom = (force = false) => {
    const now = performance.now();
    if (force || now - lastScrollTime.current > 60) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      lastScrollTime.current = now;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Smooth 60fps Token Easing Loop
  const startSmoothLoop = (msgId: string) => {
    if (animFrameIdRef.current) return;

    let lastTick = performance.now();

    const tick = (now: number) => {
      const elapsed = now - lastTick;

      // Update every ~16ms frame
      if (elapsed >= 15) {
        lastTick = now;
        const current = streamCurrentTextRef.current;
        const target = streamTargetTextRef.current;

        if (current.length < target.length) {
          const remaining = target.length - current.length;

          // Adaptive stepping: silky smooth character release with gentle spring catch-up
          let step = 1;
          if (remaining > 140) step = 6;
          else if (remaining > 70) step = 4;
          else if (remaining > 25) step = 2;
          else step = 1;

          const nextText = target.slice(0, current.length + step);
          streamCurrentTextRef.current = nextText;

          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId ? { ...m, text: nextText, isStreaming: true } : m
            )
          );

          scrollToBottom();
        } else if (isNetworkDoneRef.current) {
          // Both network and buffer drain are fully complete!
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId ? { ...m, text: target, isStreaming: false } : m
            )
          );
          setIsStreaming(false);
          currentMsgIdRef.current = null;
          animFrameIdRef.current = null;
          scrollToBottom(true);
          return;
        }
      }

      animFrameIdRef.current = requestAnimationFrame(tick);
    };

    animFrameIdRef.current = requestAnimationFrame(tick);
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (animFrameIdRef.current) {
      cancelAnimationFrame(animFrameIdRef.current);
      animFrameIdRef.current = null;
    }

    const msgId = currentMsgIdRef.current;
    const finalTarget = streamTargetTextRef.current;
    if (msgId) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId ? { ...m, text: finalTarget || m.text, isStreaming: false } : m
        )
      );
    }

    setIsStreaming(false);
    currentMsgIdRef.current = null;
    scrollToBottom(true);
  };

  const handleSend = async (questionText?: string) => {
    const q = (questionText || input).trim();
    if (!q || isStreaming) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (animFrameIdRef.current) {
      cancelAnimationFrame(animFrameIdRef.current);
      animFrameIdRef.current = null;
    }

    abortControllerRef.current = new AbortController();

    const userMsgId = "user-" + Date.now();
    const assistantMsgId = "assistant-" + (Date.now() + 1);

    currentMsgIdRef.current = assistantMsgId;
    streamTargetTextRef.current = "";
    streamCurrentTextRef.current = "";
    isNetworkDoneRef.current = false;

    const initialMeta: ChatResponse = {
      question: q,
      answer: "",
      route: "simple",
      citations: [],
      rewritten_queries: [],
      retry_count: 0,
      node_latencies: {},
    };

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, sender: "user", text: q },
      {
        id: assistantMsgId,
        sender: "assistant",
        text: "",
        isStreaming: true,
        responseMeta: initialMeta,
      },
    ]);
    setInput("");
    setIsStreaming(true);

    try {
      const effectiveQuestion =
        activeDoc && !q.toLowerCase().includes(activeDoc.filename.toLowerCase())
          ? `${q} (regarding document ${activeDoc.filename})`
          : q;

      await streamChatQuestion(
        effectiveQuestion,
        {
          onSources: (citations: CitationItem[]) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      responseMeta: {
                        ...(m.responseMeta || initialMeta),
                        citations,
                      },
                    }
                  : m
              )
            );
          },
          onToken: (token: string) => {
            // Append token to target buffer and start smooth easing loop
            streamTargetTextRef.current += token;
            startSmoothLoop(assistantMsgId);
          },
          onDone: () => {
            isNetworkDoneRef.current = true;
            // Let the RAF loop finish draining the buffer smoothly
            startSmoothLoop(assistantMsgId);
          },
          onError: () => {
            isNetworkDoneRef.current = true;
            if (!streamTargetTextRef.current) {
              streamTargetTextRef.current =
                "Sorry, I could not retrieve an answer right now. Please try again.";
            }
            startSmoothLoop(assistantMsgId);
          },
        },
        DEFAULT_TENANT_ID,
        abortControllerRef.current.signal
      );
    } catch {
      isNetworkDoneRef.current = true;
      if (!streamTargetTextRef.current) {
        streamTargetTextRef.current =
          "Sorry, I could not retrieve an answer right now. Please try again.";
      }
      startSmoothLoop(assistantMsgId);
    }
  };

  const handleReset = () => {
    stopStreaming();
    setMessages([]);
    setInput("");
    inputRef.current?.focus();
  };

  const handleCopyCitation = (text: string, id: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

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

                // If assistant message is still awaiting the very first token (Claude-style subtle breathing dots)
                const isAwaitingFirstToken = msg.isStreaming && !msg.text;

                return (
                  <div key={msg.id} className="flex justify-start">
                    <div className="w-full rounded-2xl border border-white/[0.08] bg-[#1B1D22] p-5 text-[#E2E4E9] shadow-sm">
                      {isAwaitingFirstToken ? (
                        /* Classical DocVane Editorial Loading State */
                        <div className="flex items-center gap-2.5 py-1 text-xs select-none animate-in fade-in duration-200">
                          <div className="flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-[#B066FF]/90 shadow-[0_0_6px_rgba(176,102,255,0.4)] animate-pulse [animation-duration:1.2s]" />
                            <span className="h-1.5 w-1.5 rounded-full bg-[#B066FF]/55 animate-pulse [animation-duration:1.2s] [animation-delay:200ms]" />
                            <span className="h-1.5 w-1.5 rounded-full bg-[#B066FF]/30 animate-pulse [animation-duration:1.2s] [animation-delay:400ms]" />
                          </div>
                          <span className="font-serif italic text-[13px] text-white/60 tracking-wide">
                            {loadingPhrase}
                          </span>
                        </div>
                      ) : (
                        <div>{renderFormattedContent(msg.text, msg.isStreaming)}</div>
                      )}

                      {/* Sources (gracefully reveals once streaming completes) */}
                      {!msg.isStreaming && meta?.citations && meta.citations.length > 0 && (
                        <div className="mt-5 border-t border-white/[0.08] pt-3.5 animate-in fade-in slide-in-from-bottom-2 duration-300">
                          <span className="text-xs font-mono text-white/40 block mb-2.5">
                            SOURCES ({meta.citations.length})
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
                                  <p className="font-serif italic text-white/70 leading-relaxed border-l-2 border-emerald-500/30 pl-2.5">
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
              placeholder={isStreaming ? "Responding..." : "Ask a question..."}
              disabled={isStreaming}
              className="w-full rounded-2xl border border-white/10 bg-[#22252A] py-3 pl-4.5 pr-12 text-sm text-white placeholder-white/40 outline-none focus:border-white/25 focus:bg-[#262A30] transition-colors disabled:opacity-70"
            />
            {isStreaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                title="Stop response"
                className="absolute right-2 flex h-8 w-8 items-center justify-center rounded-full bg-[#B066FF] text-white transition-all hover:bg-[#B877FF] active:scale-95 shadow-[0_0_10px_rgba(176,102,255,0.4)]"
              >
                <Square className="h-3 w-3 fill-current text-white" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                aria-label="Send message"
                className="absolute right-2 flex h-8 w-8 items-center justify-center rounded-full bg-[#B066FF] text-white shadow-[0_0_10px_rgba(176,102,255,0.4)] transition-all duration-200 hover:bg-[#B877FF] hover:scale-105 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:bg-[#B066FF]"
              >
                <ArrowUp className="h-4 w-4 text-white" strokeWidth={2.5} />
              </button>
            )}
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
        <div className="flex min-h-[calc(100vh-4rem)] w-full items-center justify-center bg-[#1A1C20] text-white/50 text-xs font-mono">
          Loading...
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
