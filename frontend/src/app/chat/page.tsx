"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Send,
  Sparkles,
  Database,
  FileText,
  Clock,
  Layers,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { ChatResponse, CitationItem, submitChatQuestion } from "@/lib/api";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  responseMeta?: ChatResponse;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "initial-assistant-msg",
      sender: "assistant",
      text: "Greetings. I am DocVane's inquiry engine, backed by a self-correcting LangGraph pipeline over your invoices and contracts. Ask questions across your documents or request cross-vendor metrics.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedSql, setExpandedSql] = useState<Record<string, boolean>>({});

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
      const result = await submitChatQuestion(q);
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
          text: "An error occurred executing the retrieval pipeline. Please check backend connectivity.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSql = (msgId: string) => {
    setExpandedSql((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const sampleQueries = [
    "What are the payment terms on the Acme Corp invoice?",
    "What is the total amount invoiced across all documents?",
    "Which state governs the Apex Master Services Agreement?",
  ];

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-5xl flex-col px-6 py-8">
      {/* Header */}
      <div className="border-b border-[#2A2A2A] pb-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="font-mono text-xs text-[#E8C07A] uppercase tracking-wider">
              Self-Correcting RAG + SQL
            </span>
            <h1 className="mt-0.5 font-serif text-2xl sm:text-3xl font-normal text-[#FAF8F5]">
              Document Inquirer
            </h1>
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px] text-[#A0998F]">
            <span className="h-2 w-2 rounded-full bg-[#7EC69A]" />
            <span>CRAG + Self-RAG Active</span>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto py-6 space-y-6">
        {messages.map((msg) => {
          const isUser = msg.sender === "user";
          const meta = msg.responseMeta;

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-2xl rounded-2xl p-5 ${isUser
                    ? "bg-[#1E1E1E] text-[#FAF8F5] border border-[#2A2A2A]"
                    : "bg-[#141414] text-[#FAF8F5] border border-[#242424]"
                  }`}
              >
                {/* Router Badge for Assistant */}
                {!isUser && meta && (
                  <div className="mb-3 flex flex-wrap items-center gap-2 font-mono text-[10px] text-[#A0998F] border-b border-[#222222] pb-2">
                    <span className="rounded bg-[#E8C07A]/15 px-2 py-0.5 text-[#E8C07A] uppercase">
                      Route: {meta.route}
                    </span>
                    {meta.node_latencies && (
                      <span>
                        Latency:{" "}
                        {Object.values(meta.node_latencies)
                          .reduce((a, b) => a + b, 0)
                          .toFixed(0)}
                        ms
                      </span>
                    )}
                  </div>
                )}

                {/* Message Body */}
                <p className="font-serif text-sm sm:text-base leading-relaxed whitespace-pre-wrap">
                  {msg.text}
                </p>

                {/* SQL Query Collapsible */}
                {meta?.sql_query && (
                  <div className="mt-4 pt-3 border-t border-[#222222]">
                    <button
                      onClick={() => toggleSql(msg.id)}
                      className="flex items-center gap-1.5 font-mono text-xs text-[#7AA8E8] hover:underline"
                    >
                      <Database className="h-3.5 w-3.5" />
                      <span>Executed SQL Query</span>
                      {expandedSql[msg.id] ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                    </button>

                    {expandedSql[msg.id] && (
                      <div className="mt-2 rounded-lg bg-[#0A0A0A] p-3 font-mono text-xs text-[#7EC69A] overflow-x-auto border border-[#222222]">
                        <code>{meta.sql_query}</code>
                      </div>
                    )}
                  </div>
                )}

                {/* Citations Block */}
                {meta?.citations && meta.citations.length > 0 && (
                  <div className="mt-5 border-t border-[#242424] pt-4">
                    <div className="mb-2 font-mono text-[10px] text-[#E8C07A] uppercase tracking-wider">
                      Grounding Citations ({meta.citations.length})
                    </div>

                    <div className="space-y-2">
                      {meta.citations.map((cite, i) => (
                        <div
                          key={i}
                          className="rounded-lg border border-[#222222] bg-[#0F0F0F] p-3 text-xs"
                        >
                          <div className="flex items-center justify-between font-mono text-[10px] text-[#A0998F] mb-1">
                            <span className="text-[#E8C07A]">
                              Citation [{i + 1}] • Page {cite.page_number || 1}
                            </span>
                            {cite.score && (
                              <span>{(cite.score * 100).toFixed(0)}% match</span>
                            )}
                          </div>
                          <p className="italic text-[#FAF8F5]/80 font-serif line-clamp-3">
                            &ldquo;{cite.content}&rdquo;
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex items-center gap-2 font-mono text-xs text-[#E8C07A]">
            <Sparkles className="h-4 w-4 animate-spin" />
            <span>Evaluating question, routing, and grading passages...</span>
          </div>
        )}
      </div>

      {/* Sample Query Suggestions */}
      {messages.length <= 2 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-[#6B6560]">Sample queries:</span>
          {sampleQueries.map((sq) => (
            <button
              key={sq}
              onClick={() => handleSend(sq)}
              className="rounded-full border border-[#2A2A2A] bg-[#141414] px-3 py-1 text-xs text-[#A0998F] hover:border-[#E8C07A]/40 hover:text-[#FAF8F5] transition-all"
            >
              {sq}
            </button>
          ))}
        </div>
      )}

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="relative flex items-center"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about your uploaded contracts, invoices, or metrics..."
          className="w-full rounded-xl border border-[#2A2A2A] bg-[#141414] py-3.5 pl-4 pr-12 text-sm text-[#FAF8F5] placeholder-[#6B6560] outline-none transition-all focus:border-[#E8C07A]/60 focus:bg-[#1A1A1A]"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="absolute right-2.5 flex h-8 w-8 items-center justify-center rounded-lg bg-[#E8C07A] text-[#0F0F0F] transition-all hover:bg-[#D4A85A] disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}

