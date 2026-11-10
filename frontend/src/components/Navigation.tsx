"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { fetchReviewTasks } from "@/lib/api";

export function Navigation() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState<number>(3);

  const updateCount = () => {
    fetchReviewTasks().then((items) => {
      const pending = items.filter((t) => t.status !== "resolved").length;
      setPendingCount(pending);
    });
  };

  useEffect(() => {
    updateCount();
    const handleUpdate = () => updateCount();
    window.addEventListener("docvane:reviews_updated", handleUpdate);
    return () => window.removeEventListener("docvane:reviews_updated", handleUpdate);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  const isChat = pathname.startsWith("/chat");

  return (
    <header
      className={`sticky top-0 z-50 w-full transition-colors ${
        isChat
          ? "border-b border-white/10 bg-[#1A1C20]/90 backdrop-blur-md"
          : "border-b border-[#EBEBEB] bg-white"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 sm:px-8">
        {/* Brand / Logo */}
        <div className="flex items-center gap-10">
          <Link
            href="/"
            className={`font-serif text-2xl font-bold tracking-tight transition-colors ${
              isChat ? "text-white hover:text-white/90" : "text-[#111827]"
            }`}
          >
            docvane
          </Link>

          {/* Navigation Links */}
          <nav
            className={`hidden md:flex items-center gap-7 text-[13px] font-normal ${
              isChat ? "text-[#A0A5AD]" : "text-[#1F2124]"
            }`}
          >
            <Link
              href="/documents"
              className={`flex items-center gap-1.5 transition-colors ${
                isChat
                  ? pathname.startsWith("/documents")
                    ? "text-white font-medium"
                    : "text-[#A0A5AD] hover:text-white"
                  : pathname.startsWith("/documents")
                  ? "text-black font-medium"
                  : "text-[#374151] hover:text-black"
              }`}
            >
              <span>Library</span>
              <svg
                className="h-3 w-3 opacity-60"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m6 9 6 6 6-6" />
              </svg>
            </Link>

            <Link
              href="/reviews"
              className={`flex items-center gap-1.5 transition-colors ${
                isChat
                  ? pathname.startsWith("/reviews")
                    ? "text-white font-medium"
                    : "text-[#A0A5AD] hover:text-white"
                  : pathname.startsWith("/reviews")
                  ? "text-black font-medium"
                  : "text-[#374151] hover:text-black"
              }`}
            >
              <span>Review Queue</span>
              {pendingCount > 0 && (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                    isChat
                      ? "bg-amber-500/15 border border-amber-500/30 text-amber-300"
                      : "bg-[#FEF3C7] text-[#D97706]"
                  }`}
                >
                  {pendingCount}
                </span>
              )}
            </Link>

            <Link
              href="/chat"
              className={`flex items-center gap-1.5 transition-colors ${
                isChat
                  ? "text-white font-medium"
                  : pathname.startsWith("/chat")
                  ? "text-black font-medium"
                  : "text-[#374151] hover:text-black"
              }`}
            >
              <span>Inquirer</span>
              {isChat && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>}
            </Link>
          </nav>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <Link
            href="/documents/upload"
            className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all hidden sm:inline-block ${
              isChat
                ? "border border-white/15 bg-white/5 text-white hover:bg-white/10 hover:border-white/30"
                : "border border-[#D1D5DB] bg-white text-[#111827] hover:bg-[#F9FAFB] hover:border-black"
            }`}
          >
            Upload
          </Link>

          <Link
            href="/documents"
            className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-all hidden sm:inline-block ${
              isChat
                ? "bg-white text-[#1A1C20] hover:bg-neutral-200"
                : "bg-[#111827] text-white hover:bg-black"
            }`}
          >
            Open Library
          </Link>

          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className={`md:hidden flex h-9 w-9 items-center justify-center rounded-lg border transition-colors ${
              isChat
                ? "border-white/15 text-white hover:bg-white/10"
                : "border-[#E5E7EB] text-[#111827] hover:bg-neutral-100"
            }`}
            aria-label="Toggle navigation"
          >
            {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div
          className={`md:hidden border-t px-6 py-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-150 ${
            isChat ? "border-white/10 bg-[#1A1C20]" : "border-[#EBEBEB] bg-white"
          }`}
        >
          <Link
            href="/documents"
            className={`block py-2 text-sm ${
              isChat
                ? pathname.startsWith("/documents")
                  ? "text-white font-semibold"
                  : "text-[#A0A5AD]"
                : pathname.startsWith("/documents")
                ? "text-black font-semibold"
                : "text-[#374151]"
            }`}
          >
            Workspace Library
          </Link>

          <Link
            href="/reviews"
            className={`flex items-center justify-between py-2 text-sm ${
              isChat
                ? pathname.startsWith("/reviews")
                  ? "text-white font-semibold"
                  : "text-[#A0A5AD]"
                : pathname.startsWith("/reviews")
                ? "text-black font-semibold"
                : "text-[#374151]"
            }`}
          >
            <span>Review Queue</span>
            {pendingCount > 0 && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  isChat
                    ? "bg-amber-500/15 border border-amber-500/30 text-amber-300"
                    : "bg-[#FEF3C7] text-[#D97706]"
                }`}
              >
                {pendingCount}
              </span>
            )}
          </Link>

          <Link
            href="/chat"
            className={`block py-2 text-sm ${
              isChat
                ? "text-white font-semibold"
                : pathname.startsWith("/chat")
                ? "text-black font-semibold"
                : "text-[#374151]"
            }`}
          >
            Document Inquirer
          </Link>

          <div
            className={`pt-3 border-t flex items-center gap-3 ${
              isChat ? "border-white/10" : "border-[#EBEBEB]"
            }`}
          >
            <Link
              href="/documents/upload"
              className={`flex-1 text-center rounded-full border py-2 text-xs font-medium ${
                isChat
                  ? "border-white/15 text-white hover:bg-white/10"
                  : "border-[#D1D5DB] text-[#111827]"
              }`}
            >
              Upload
            </Link>
            <Link
              href="/documents"
              className={`flex-1 text-center rounded-full py-2 text-xs font-semibold ${
                isChat
                  ? "bg-white text-[#1A1C20] hover:bg-neutral-200"
                  : "bg-[#111827] text-white"
              }`}
            >
              Open Library
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
