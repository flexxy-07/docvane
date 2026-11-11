"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText,
  Search,
  Clock,
  ArrowUpRight,
} from "lucide-react";
import { DocumentItem, fetchDocuments } from "@/lib/api";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const loadDocs = () => {
    fetchDocuments().then((items) => {
      setDocuments(items);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadDocs();

    const handleUpdated = () => loadDocs();
    window.addEventListener("docvane:documents_updated", handleUpdated);
    return () => window.removeEventListener("docvane:documents_updated", handleUpdated);
  }, []);

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.filename.toLowerCase().includes(search.toLowerCase()) ||
      (doc.doc_type && doc.doc_type.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = statusFilter === "all" || doc.status === statusFilter;
    const matchesCategory =
      categoryFilter === "all" ||
      (doc.doc_type && doc.doc_type.toLowerCase() === categoryFilter.toLowerCase());
    return matchesSearch && matchesStatus && matchesCategory;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ready":
        return (
          <span className="rounded-full bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-0.5 text-[11px] font-mono text-emerald-300">
            Verified ✓
          </span>
        );
      case "needs_review":
        return (
          <span className="rounded-full bg-amber-500/10 border border-amber-500/25 px-2.5 py-0.5 text-[11px] font-mono text-amber-300">
            Review needed
          </span>
        );
      case "parsing":
      case "extracting":
      case "indexing":
        return (
          <span className="rounded-full bg-blue-500/10 border border-blue-500/25 px-2.5 py-0.5 text-[11px] font-mono text-blue-300 flex items-center gap-1.5">
            <Clock className="h-3 w-3 animate-spin" />
            <span>Processing...</span>
          </span>
        );
      default:
        return (
          <span className="rounded-full bg-white/5 border border-white/10 px-2.5 py-0.5 text-[11px] font-mono text-white/50 capitalize">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] bg-[#1A1C20] text-white">
      <div className="mx-auto max-w-7xl px-6 sm:px-8 py-12">
        {/* Header bar */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 border-b border-white/10 pb-8">
          <div>
            <h1 className="font-serif text-3xl sm:text-4xl font-normal text-white">
              Workspace Library
            </h1>
            <p className="mt-2 text-sm text-[#A0A5AD] max-w-xl">
              All paperwork, invoices, and agreements analyzed with verified citations.
            </p>
          </div>

          <Link
            href="/documents/upload"
            className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-2 text-xs font-semibold text-[#1A1C20] transition-colors hover:bg-neutral-200"
          >
            <span>+ Deposit Document</span>
          </Link>
        </div>

        {/* Search and Filters */}
        <div className="mt-8 space-y-4">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search paperwork by title or type..."
                className="w-full rounded-full border border-white/10 bg-[#22252A] py-2.5 pl-10 pr-4 text-sm text-white placeholder-white/40 outline-none focus:border-white/25 focus:bg-[#262A30] transition-colors"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-white/40 mr-1">Status:</span>
              {[
                { id: "all", label: "All" },
                { id: "ready", label: "Verified" },
                { id: "needs_review", label: "Needs review" },
              ].map((filter) => (
                <button
                  key={filter.id}
                  onClick={() => setStatusFilter(filter.id)}
                  className={`rounded-full px-3.5 py-1.5 text-xs transition-colors ${
                    statusFilter === filter.id
                      ? "bg-white text-[#1A1C20] font-medium"
                      : "border border-white/10 bg-white/5 text-white/70 hover:bg-white/10"
                  }`}
                >
                  {filter.label}
                </button>
              ))}
            </div>
          </div>

          {/* Document Type Chips */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5">
            <span className="text-xs text-white/40 mr-1">Type:</span>
            {[
              { id: "all", label: "All Types" },
              { id: "contract", label: "Contracts & MSAs" },
              { id: "invoice", label: "Invoices" },
              { id: "manifest", label: "Manifests" },
              { id: "general", label: "General" },
            ].map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategoryFilter(cat.id)}
                className={`rounded-full px-3 py-1 text-xs transition-colors ${
                  categoryFilter === cat.id
                    ? "bg-white text-[#1A1C20] font-medium"
                    : "text-white/60 hover:text-white hover:bg-white/5"
                }`}
              >
                {cat.label}
              </button>
            ))}

            <span className="ml-auto text-xs font-mono text-white/40">
              Showing {filteredDocs.length} of {documents.length}
            </span>
          </div>
        </div>

        {/* Documents Grid */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {loading ? (
            <div className="col-span-full py-16 text-center text-xs text-white/40">
              Loading workspace documents...
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="col-span-full rounded-2xl border border-dashed border-white/10 py-16 text-center">
              <FileText className="mx-auto h-8 w-8 text-white/30" />
              <h3 className="mt-3 font-serif text-lg text-white">No documents found</h3>
              <p className="mt-1 text-xs text-white/50">
                Deposit an invoice or contract to begin analysis.
              </p>
            </div>
          ) : (
            filteredDocs.map((doc) => (
              <div
                key={doc.id}
                className="group relative flex flex-col justify-between rounded-2xl border border-white/10 bg-[#22252A] p-6 transition-all hover:border-white/25 hover:bg-[#262A30]"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-white/40">
                      {doc.doc_type || "DOCUMENT"}
                    </span>
                    {getStatusBadge(doc.status)}
                  </div>

                  <h3 className="mt-4 font-serif text-lg font-normal text-white group-hover:text-amber-100 transition-colors line-clamp-2">
                    {doc.filename}
                  </h3>

                  <div className="mt-3 flex items-center gap-2 text-xs font-mono text-white/50">
                    <span>{doc.page_count} pages</span>
                    <span>•</span>
                    <span>{(doc.file_size_bytes / 1024).toFixed(0)} KB</span>
                  </div>
                </div>

                <div className="mt-8 flex items-center justify-between border-t border-white/5 pt-4">
                  <span className="text-xs font-mono text-white/40">
                    {new Date(doc.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>

                  <Link
                    href={
                      doc.status === "needs_review"
                        ? `/reviews?docId=${doc.id}`
                        : `/chat?docId=${doc.id}`
                    }
                    className="flex items-center gap-1 text-xs font-medium text-white/80 group-hover:text-white transition-colors"
                  >
                    <span>{doc.status === "needs_review" ? "Review" : "Inquire"}</span>
                    <ArrowUpRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
