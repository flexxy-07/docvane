"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import Link from "next/link";
import { Send, Sparkles } from "lucide-react";
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
      text: "Ask any question across your uploaded documents. Every answer is grounded directly in the text with exact citations.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

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
          text: "Could not retrieve an answer at this moment. Please check your connection and try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sampleQueries = [
    "What are the payment terms on the Acme invoice?",
    "What is the total balance across all invoices?",
    "Which state governs the master services agreement?",
  ];

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] bg-[#1A1C20] text-white">
      <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-4xl flex-col px-6 sm:px-8 py-8">
        {/* Header */}
        <div className="border-b border-white/10 pb-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-serif text-2xl sm:text-3xl font-normal text-white">
                Document Inquirer
              </h1>
              <p className="mt-1 text-xs text-[#A0A5AD]">
                Ask questions across your paperwork with exact citations.
              </p>
            </div>

            <div className="flex items-center gap-2 text-xs text-white/70">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>Citations active</span>
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
                  className={`max-w-2xl rounded-2xl p-5 ${
                    isUser
                      ? "bg-[#282C34] text-white border border-white/10"
                      : "bg-[#0E242B]/90 text-white border border-white/10"
                  }`}
                >
                  {/* Message Body */}
                  <p className="font-serif text-sm sm:text-base leading-relaxed whitespace-pre-wrap">
                    {msg.text}
                  </p>

                  {/* Citations Block */}
                  {meta?.citations && meta.citations.length > 0 && (
                    <div className="mt-5 border-t border-white/10 pt-4">
                      <div className="mb-2 text-[11px] font-medium text-white/60 uppercase tracking-wider">
                        Sources ({meta.citations.length})
                      </div>

                      <div className="space-y-2">
                        {meta.citations.map((cite, i) => (
                          <div
                            key={i}
                            className="rounded-xl border border-white/10 bg-black/30 p-3 text-xs"
                          >
                            <div className="flex items-center justify-between text-[11px] text-white/50 mb-1">
                              <span className="text-white font-medium">
                                Source [{i + 1}] • Page {cite.page_number || 1}
                              </span>
                            </div>
                            <p className="italic text-white/80 font-serif line-clamp-3">
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
            <div className="flex items-center gap-2 text-xs text-white/70">
              <Sparkles className="h-4 w-4 animate-spin text-amber-300" />
              <span>Searching documents and verifying citations...</span>
            </div>
          )}
        </div>

        {/* Sample Query Suggestions */}
        {messages.length <= 2 && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-white/40">Suggested:</span>
            {sampleQueries.map((sq) => (
              <button
                key={sq}
                onClick={() => handleSend(sq)}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 hover:border-white/30 hover:text-white transition-all"
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
            placeholder="Ask anything about your documents, agreements, or records..."
            className="w-full rounded-full border border-white/10 bg-white/5 py-3 pl-5 pr-12 text-sm text-white placeholder-white/40 outline-none transition-all focus:border-white/30 focus:bg-white/10"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="absolute right-2 flex h-8 w-8 items-center justify-center rounded-full bg-white text-[#1A1C20] transition-all hover:bg-neutral-200 disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
