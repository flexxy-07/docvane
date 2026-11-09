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

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#EBEBEB] bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 sm:px-8">
        {/* Brand / Logo */}
        <div className="flex items-center gap-10">
          <Link href="/" className="font-serif text-2xl font-bold tracking-tight text-[#111827]">
            docvane
          </Link>

          {/* Navigation Links (Ellipsus style) */}
          <nav className="hidden md:flex items-center gap-7 text-[13px] font-normal text-[#1F2124]">
            <Link
              href="/documents"
              className={`flex items-center gap-1 transition-colors hover:text-black ${
                pathname.startsWith("/documents") ? "text-black font-medium" : "text-[#374151]"
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
              className={`flex items-center gap-1 transition-colors hover:text-black ${
                pathname.startsWith("/reviews") ? "text-black font-medium" : "text-[#374151]"
              }`}
            >
              <span>Review Queue</span>
              {pendingCount > 0 && (
                <span className="rounded-full bg-[#FEF3C7] px-1.5 py-0.2 text-[10px] font-medium text-[#D97706]">
                  {pendingCount}
                </span>
              )}
            </Link>

            <Link
              href="/chat"
              className={`flex items-center gap-1 transition-colors hover:text-black ${
                pathname.startsWith("/chat") ? "text-black font-medium" : "text-[#374151]"
              }`}
            >
              <span>Inquirer</span>
            </Link>
          </nav>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <Link
            href="/documents/upload"
            className="rounded-full border border-[#D1D5DB] bg-white px-4 py-1.5 text-xs font-medium text-[#111827] transition-all hover:bg-[#F9FAFB] hover:border-black hidden sm:inline-block"
          >
            Upload
          </Link>

          <Link
            href="/documents"
            className="rounded-full bg-[#111827] px-4 py-1.5 text-xs font-medium text-white transition-all hover:bg-black hidden sm:inline-block"
          >
            Open Library
          </Link>

          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-[#E5E7EB] text-[#111827] hover:bg-neutral-100 transition-colors"
            aria-label="Toggle navigation"
          >
            {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-[#EBEBEB] bg-white px-6 py-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-150">
          <Link
            href="/documents"
            className={`block py-2 text-sm ${
              pathname.startsWith("/documents") ? "text-black font-semibold" : "text-[#374151]"
            }`}
          >
            Workspace Library
          </Link>

          <Link
            href="/reviews"
            className={`flex items-center justify-between py-2 text-sm ${
              pathname.startsWith("/reviews") ? "text-black font-semibold" : "text-[#374151]"
            }`}
          >
            <span>Review Queue</span>
            {pendingCount > 0 && (
              <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-xs font-medium text-[#D97706]">
                {pendingCount}
              </span>
            )}
          </Link>

          <Link
            href="/chat"
            className={`block py-2 text-sm ${
              pathname.startsWith("/chat") ? "text-black font-semibold" : "text-[#374151]"
            }`}
          >
            Document Inquirer
          </Link>

          <div className="pt-3 border-t border-[#EBEBEB] flex items-center gap-3">
            <Link
              href="/documents/upload"
              className="flex-1 text-center rounded-full border border-[#D1D5DB] py-2 text-xs font-medium text-[#111827]"
            >
              Upload
            </Link>
            <Link
              href="/documents"
              className="flex-1 text-center rounded-full bg-[#111827] py-2 text-xs font-medium text-white"
            >
              Open Library
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
