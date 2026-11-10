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
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-[#1A1C20]/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 sm:px-8">
        {/* Brand / Logo */}
        <div className="flex items-center gap-10">
          <Link href="/" className="font-serif text-2xl font-bold tracking-tight text-white hover:text-white/90 transition-colors">
            docvane
          </Link>

          {/* Navigation Links (Editorial Dark Style) */}
          <nav className="hidden md:flex items-center gap-7 text-[13px] font-normal text-[#A0A5AD]">
            <Link
              href="/documents"
              className={`flex items-center gap-1.5 transition-colors hover:text-white ${
                pathname.startsWith("/documents") ? "text-white font-medium" : "text-[#A0A5AD]"
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
              className={`flex items-center gap-1.5 transition-colors hover:text-white ${
                pathname.startsWith("/reviews") ? "text-white font-medium" : "text-[#A0A5AD]"
              }`}
            >
              <span>Review Queue</span>
              {pendingCount > 0 && (
                <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                  {pendingCount}
                </span>
              )}
            </Link>

            <Link
              href="/chat"
              className={`flex items-center gap-1.5 transition-colors hover:text-white ${
                pathname.startsWith("/chat") ? "text-white font-medium" : "text-[#A0A5AD]"
              }`}
            >
              <span>Inquirer</span>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
            </Link>
          </nav>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <Link
            href="/documents/upload"
            className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-xs font-medium text-white transition-all hover:bg-white/10 hover:border-white/30 hidden sm:inline-block"
          >
            Upload
          </Link>

          <Link
            href="/documents"
            className="rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-[#1A1C20] transition-all hover:bg-neutral-200 hidden sm:inline-block"
          >
            Open Library
          </Link>

          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-white/15 text-white hover:bg-white/10 transition-colors"
            aria-label="Toggle navigation"
          >
            {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-white/10 bg-[#1A1C20] px-6 py-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-150">
          <Link
            href="/documents"
            className={`block py-2 text-sm ${
              pathname.startsWith("/documents") ? "text-white font-semibold" : "text-[#A0A5AD]"
            }`}
          >
            Workspace Library
          </Link>

          <Link
            href="/reviews"
            className={`flex items-center justify-between py-2 text-sm ${
              pathname.startsWith("/reviews") ? "text-white font-semibold" : "text-[#A0A5AD]"
            }`}
          >
            <span>Review Queue</span>
            {pendingCount > 0 && (
              <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-xs font-medium text-amber-300">
                {pendingCount}
              </span>
            )}
          </Link>

          <Link
            href="/chat"
            className={`block py-2 text-sm ${
              pathname.startsWith("/chat") ? "text-white font-semibold" : "text-[#A0A5AD]"
            }`}
          >
            Document Inquirer
          </Link>

          <div className="pt-3 border-t border-white/10 flex items-center gap-3">
            <Link
              href="/documents/upload"
              className="flex-1 text-center rounded-full border border-white/15 py-2 text-xs font-medium text-white hover:bg-white/10"
            >
              Upload
            </Link>
            <Link
              href="/documents"
              className="flex-1 text-center rounded-full bg-white py-2 text-xs font-semibold text-[#1A1C20] hover:bg-neutral-200"
            >
              Open Library
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
