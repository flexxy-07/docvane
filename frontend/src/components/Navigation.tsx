"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navigation() {
  const pathname = usePathname();

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
              <span className="rounded-full bg-[#FEF3C7] px-1.5 py-0.2 text-[10px] font-medium text-[#D97706]">
                3
              </span>
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

        {/* Right Actions: Log In + Sign Up style */}
        <div className="flex items-center gap-3">
          <Link
            href="/documents/upload"
            className="rounded-full border border-[#D1D5DB] bg-white px-4 py-1.5 text-xs font-medium text-[#111827] transition-all hover:bg-[#F9FAFB] hover:border-black"
          >
            Upload
          </Link>

          <Link
            href="/documents"
            className="rounded-full bg-[#111827] px-4 py-1.5 text-xs font-medium text-white transition-all hover:bg-black"
          >
            Open Library
          </Link>
        </div>
      </div>
    </header>
  );
}
