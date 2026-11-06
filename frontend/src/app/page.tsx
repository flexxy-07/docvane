import Link from "next/link";

export default function Home() {
  return (
    <div className="w-full bg-[#1A1C20] overflow-hidden">
      {/* =========================================================================
          SECTION 1: DARK MODE HERO (Ellipsus Screenshot 1)
         ========================================================================= */}
      <section className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 py-20 text-center select-none">
        {/* Scattered drifting letters in faint gray (identical to Ellipsus hero) */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden text-[#3A3E47] font-sans text-xs select-none">
          <span className="absolute top-[12%] left-[18%]">u</span>
          <span className="absolute top-[8%] left-[26%]">n</span>
          <span className="absolute top-[15%] left-[45%]">p</span>
          <span className="absolute top-[10%] right-[32%]">d</span>
          <span className="absolute top-[14%] right-[22%]">e</span>
          <span className="absolute top-[8%] right-[15%]">r</span>
          <span className="absolute top-[12%] right-[8%]">y</span>

          <span className="absolute top-[22%] left-[45%]">v</span>
          <span className="absolute top-[25%] left-[52%]">f</span>
          <span className="absolute top-[18%] right-[40%]">k</span>
          <span className="absolute top-[24%] right-[28%]">a</span>
          <span className="absolute top-[20%] right-[18%]">z</span>
          <span className="absolute top-[22%] right-[10%]">g</span>

          <span className="absolute top-[40%] right-[14%]">w</span>
          <span className="absolute top-[48%] right-[12%]">y</span>
          <span className="absolute top-[56%] right-[14%]">r</span>

          <span className="absolute bottom-[28%] left-[28%]">J</span>
          <span className="absolute bottom-[24%] left-[32%]">q</span>
          <span className="absolute bottom-[22%] left-[40%]">ce</span>
          <span className="absolute bottom-[18%] left-[40%]">h</span>
          <span className="absolute bottom-[26%] left-[45%]">s</span>
          <span className="absolute bottom-[20%] left-[45%]">l</span>

          <span className="absolute bottom-[26%] right-[42%]">q</span>
          <span className="absolute bottom-[20%] right-[44%]">b</span>
          <span className="absolute bottom-[30%] right-[34%]">c</span>
          <span className="absolute bottom-[24%] right-[28%]">x</span>
          <span className="absolute bottom-[20%] right-[29%]">n</span>
          <span className="absolute bottom-[22%] right-[24%]">m</span>
          <span className="absolute bottom-[16%] right-[18%]">u</span>
        </div>

        {/* Hand-drawn paper airplane sketch on the left */}
        <div className="pointer-events-none absolute left-[10%] top-[45%] -translate-y-1/2 hidden md:block">
          <svg
            className="w-24 h-24 text-white/90 stroke-current"
            viewBox="0 0 100 100"
            fill="none"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M 15,65 L 85,25 L 35,82 L 42,60 L 68,40" />
            <path d="M 42,60 L 35,82 L 32,68 Z" />
            <path d="M 15,65 L 42,60" />
          </svg>
        </div>

        {/* Hand-drawn purple pointer arrow cursor on the right */}
        <div className="pointer-events-none absolute right-[14%] top-[50%] -translate-y-1/2 hidden md:block">
          <svg
            className="w-10 h-10 text-[#B066FF] fill-current"
            viewBox="0 0 32 32"
          >
            <path d="M 6 4 L 26 18 L 16 19 L 12 28 Z" />
          </svg>
        </div>

        {/* Main Serif Headline */}
        <h1 className="relative font-serif text-5xl sm:text-7xl md:text-[5.5rem] font-normal tracking-tight text-white leading-[1.08]">
          Read between the lines.
        </h1>

        {/* Subtitle */}
        <p className="relative mt-7 max-w-xl text-base sm:text-lg font-light text-[#C5C9D1]">
          DocVane is an intelligent document workspace made for clarity.
        </p>

        {/* Pill CTA button (identical to "Join for free") */}
        <div className="relative mt-9">
          <Link
            href="/documents"
            className="inline-block rounded-full bg-white px-7 py-3 text-sm font-medium text-[#1A1C20] transition-all hover:bg-[#F3F4F6] hover:shadow-lg shadow-sm"
          >
            Explore workspace
          </Link>
        </div>
      </section>

      {/* =========================================================================
          SECTION 2: WARM CREAM PAPER EDITORIAL (Ellipsus Screenshot 2)
         ========================================================================= */}
      <section className="relative w-full bg-[#F7F5F0] px-8 sm:px-16 py-28 text-[#111827]">
        {/* Hand-drawn stack of books sketch (top-left) */}
        <div className="max-w-4xl mx-auto mb-8">
          <svg
            className="w-36 h-28 text-[#111827]"
            viewBox="0 0 160 120"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {/* Top book */}
            <path d="M 25,32 Q 80,18 135,28 L 132,40 Q 78,30 22,44 Z" />
            <path d="M 22,44 L 25,32" />
            <path d="M 22,44 Q 78,32 132,40" />
            <path d="M 35,42 L 35,46" />
            {/* Middle book */}
            <path d="M 20,54 Q 80,40 140,50 L 138,62 Q 78,52 18,66 Z" />
            <path d="M 18,66 L 20,54" />
            {/* Bottom book */}
            <path d="M 25,78 L 138,72 L 136,88 L 22,94 Z" />
            <path d="M 22,94 L 25,78" />
            {/* Spine creases */}
            <path d="M 40,38 L 125,28" strokeWidth="0.8" />
            <path d="M 38,50 L 130,40" strokeWidth="0.8" />
            <path d="M 35,84 L 125,78" strokeWidth="0.8" />
          </svg>
        </div>

        <div className="max-w-4xl mx-auto space-y-12">
          {/* Statement 1 */}
          <h2 className="font-serif text-3xl sm:text-5xl md:text-[3.5rem] font-normal leading-[1.2] tracking-tight">
            Plenty of tools are made for simple text, notes, and chat.{" "}
            <span className="italic hand-wavy-red">That’s not us.</span>
          </h2>

          {/* Statement 2 */}
          <p className="font-serif text-3xl sm:text-5xl md:text-[3.5rem] font-normal leading-[1.2] tracking-tight text-[#1F2124]">
            DocVane is here to decode complex agreements, verify line items,{" "}
            <span className="marker-highlight-purple">catch discrepancies</span>, and certify
            grounded data <span className="hand-circle-green">with citations.</span>
          </p>
        </div>

        {/* Hand-drawn green arrow pointing down */}
        <div className="max-w-4xl mx-auto flex justify-end mt-12 pr-8">
          <svg
            className="w-16 h-12 text-[#2B9A66]"
            viewBox="0 0 80 60"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M 10,15 Q 40,40 60,35" />
            <path d="M 50,30 L 60,35 L 56,45" />
          </svg>
        </div>
      </section>

      {/* =========================================================================
          SECTION 3: WARM BANNER (Ellipsus Screenshot 3)
         ========================================================================= */}
      <section className="relative w-full bg-[#EDE9E0] border-t border-[#E2DDD3] px-8 sm:px-16 py-24 text-center">
        {/* Hanging origami cranes sketch on right */}
        <div className="pointer-events-none absolute right-[10%] top-10 hidden lg:block">
          <svg
            className="w-32 h-44 text-[#111827]"
            viewBox="0 0 100 140"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {/* Hanging thread 1 */}
            <line x1="40" y1="0" x2="40" y2="40" strokeDasharray="3 3" />
            {/* Top Crane */}
            <path d="M 40,40 L 65,48 L 48,60 L 30,52 Z" />
            <path d="M 48,60 L 58,75 L 35,68 Z" />
            <path d="M 30,52 L 20,44" />
            {/* Hanging thread 2 */}
            <line x1="75" y1="0" x2="75" y2="80" strokeDasharray="3 3" />
            {/* Bottom Crane */}
            <path d="M 75,80 L 95,88 L 80,98 L 65,92 Z" />
            <path d="M 80,98 L 88,112 L 68,105 Z" />
          </svg>
        </div>

        <div className="max-w-3xl mx-auto">
          <h2 className="font-serif text-4xl sm:text-6xl font-normal tracking-tight text-[#111827]">
            Made for <span className="italic text-[#E68A36]">critical documents</span>
          </h2>
          <p className="mt-4 text-base text-[#4B5563] font-light max-w-xl mx-auto">
            Where every invoice total, liability cap, and indemnification clause must be verified
            beyond doubt.
          </p>
        </div>
      </section>

      {/* =========================================================================
          SECTION 4: PRODUCT WORKSPACE SHOWCASE (Ellipsus Screenshot 4)
         ========================================================================= */}
      <section className="relative w-full bg-[#1A1C20] px-6 sm:px-12 py-24">
        <div className="max-w-6xl mx-auto">
          {/* Rounded Dark Teal Workspace Canvas (matching Ellipsus Screenshot 4) */}
          <div className="rounded-3xl border border-[#2D3139] bg-gradient-to-b from-[#0E2832] to-[#0A1A20] p-6 sm:p-10 shadow-2xl">
            {/* Inner Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
              <div className="flex items-center gap-4">
                <span className="font-serif text-2xl font-bold text-white tracking-tight">
                  docvane
                </span>
                <span className="text-white/40">|</span>
                <span className="font-serif text-xl text-white">All paperwork (10)</span>
                <Link
                  href="/documents/upload"
                  className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white hover:bg-white/20 transition-colors"
                >
                  + New
                </Link>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="text"
                  placeholder="Search repository..."
                  className="rounded-full bg-white/5 border border-white/10 px-4 py-1.5 text-xs text-white placeholder-white/40 outline-none w-48 sm:w-64"
                />
              </div>
            </div>

            {/* Inner Split: Sidebar + Documents Grid */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
              {/* Left Mini Sidebar */}
              <div className="md:col-span-3 space-y-3 text-sm text-white/70">
                <div className="relative inline-block w-full">
                  <div className="rounded-full border border-white/30 bg-white/10 px-4 py-2 text-white font-medium flex items-center justify-between">
                    <span>Repository</span>
                    <span className="text-xs text-white/50">10</span>
                  </div>
                </div>

                <Link
                  href="/reviews"
                  className="block px-4 py-2 hover:text-white transition-colors flex items-center justify-between"
                >
                  <span>Review Queue</span>
                  <span className="rounded-full bg-[#E68A36]/20 px-2 py-0.5 text-xs text-[#E68A36] font-mono">
                    3
                  </span>
                </Link>

                <Link
                  href="/chat"
                  className="block px-4 py-2 hover:text-white transition-colors"
                >
                  <span>Document Inquirer</span>
                </Link>
              </div>

              {/* Right Documents Cards Grid */}
              <div className="md:col-span-9 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  {
                    title: "The Odyssey Logistics Manifest",
                    time: "6 months",
                    pages: 3,
                    badge: "Verified ✓",
                    badgeColor: "text-emerald-400 bg-emerald-950/60",
                  },
                  {
                    title: "Frankenstein; or, the Modern Prometheus Order",
                    time: "2 months",
                    pages: 8,
                    badge: "Review needed",
                    badgeColor: "text-amber-400 bg-amber-950/60",
                  },
                  {
                    title: "The Iliad Master Services Contract",
                    time: "25 days ago",
                    pages: 10,
                    badge: "Verified ✓",
                    badgeColor: "text-emerald-400 bg-emerald-950/60",
                  },
                  {
                    title: "The Metamorphosis Commercial Lease",
                    time: "10 days ago",
                    pages: 5,
                    badge: "Verified ✓",
                    badgeColor: "text-emerald-400 bg-emerald-950/60",
                  },
                  {
                    title: "The Strange Case of Dr. Jekyll and Mr. Hyde",
                    time: "2 minutes ago",
                    pages: 12,
                    badge: "Review needed",
                    badgeColor: "text-amber-400 bg-amber-950/60",
                    highlight: true,
                  },
                  {
                    title: "The Picture of Dorian Gray Advisory Agreement",
                    time: "Just now",
                    pages: 4,
                    badge: "Verified ✓",
                    badgeColor: "text-emerald-400 bg-emerald-950/60",
                  },
                ].map((item, i) => (
                  <Link
                    key={i}
                    href={item.badge === "Review needed" ? "/reviews" : "/chat"}
                    className={`rounded-2xl border p-5 flex flex-col justify-between transition-all ${
                      item.highlight
                        ? "border-[#E68A36]/60 bg-[#14333D] shadow-lg"
                        : "border-white/10 bg-[#0C2229]/80 hover:border-white/20 hover:bg-[#102B34]"
                    }`}
                  >
                    <div>
                      <h4 className="font-serif text-base font-normal text-white line-clamp-2 leading-snug">
                        {item.title}
                      </h4>
                    </div>

                    <div className="mt-8 flex items-center justify-between text-xs text-white/50 border-t border-white/5 pt-3">
                      <span>{item.time}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.badgeColor}`}>
                        {item.badge}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 5: "GET STARTED—READ AWAY" WITH OPEN DOORWAY SKETCH (New Image)
         ========================================================================= */}
      <section className="relative w-full bg-[#1A1C20] px-8 sm:px-16 pt-20 pb-28 border-t border-white/5 overflow-hidden">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
          {/* Left CTA: "Get started—read away." */}
          <div className="md:col-span-6 space-y-8 z-10">
            <h2 className="font-serif text-4xl sm:text-6xl font-normal text-white tracking-tight leading-[1.12]">
              Get started—read away.
            </h2>

            <div>
              <Link
                href="/documents"
                className="inline-block rounded-full bg-white px-7 py-3 text-sm font-medium text-[#1A1C20] transition-all hover:bg-[#F3F4F6] hover:shadow-lg shadow-sm"
              >
                Sign up—it’s free
              </Link>
            </div>
          </div>

          {/* Right Hand-drawn Sketch: Open Door with Flying Papers (Exact replica of screenshot) */}
          <div className="md:col-span-6 relative flex justify-center md:justify-end">
            <svg
              className="w-full max-w-[460px] h-auto text-white"
              viewBox="0 0 450 400"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {/* Hand-drawn horizon ground line extending to the left */}
              <path d="M 0,360 Q 150,363 320,360" strokeWidth="1.3" strokeOpacity="0.7" />

              {/* Door frame outer */}
              <path d="M 125,55 L 125,360" strokeWidth="1.8" />
              <path d="M 125,55 L 235,25 L 235,360" strokeWidth="1.8" />
              <path d="M 125,55 L 235,25" strokeWidth="1.8" />

              {/* Door leaf swung open into perspective */}
              <path
                d="M 235,25 L 305,75 L 305,372 L 235,360 Z"
                strokeWidth="2"
                fill="#16181C"
              />
              {/* Door side depth/thickness */}
              <path d="M 305,75 L 312,71 L 312,368 L 305,372 Z" strokeWidth="1.5" />
              {/* Door handle */}
              <path d="M 248,198 L 272,204 M 248,198 L 248,206" strokeWidth="2.4" />

              {/* Threshold ground line inside doorway */}
              <path d="M 125,360 L 235,360" strokeWidth="1.8" />

              {/* Flying sheets of paperwork blowing through the open door */}
              {/* Sheet 1 (Top left fluttering) */}
              <g className="animate-float">
                <path
                  d="M 60,115 L 105,98 L 115,150 L 70,167 Z"
                  strokeWidth="1.5"
                  fill="#1A1C20"
                />
                <path d="M 72,118 L 98,108" strokeWidth="1" strokeDasharray="2 3" />
                <path d="M 75,130 L 102,120" strokeWidth="1" strokeDasharray="2 3" />
                <path d="M 78,142 L 105,132" strokeWidth="1" strokeDasharray="2 3" />
                <path d="M 81,154 L 100,147" strokeWidth="1" strokeDasharray="2 3" />
              </g>

              {/* Sheet 2 (Center blowing) */}
              <g className="animate-float-delayed">
                <path
                  d="M 148,95 Q 170,82 192,102 L 180,148 Q 158,132 138,144 Z"
                  strokeWidth="1.5"
                  fill="#1A1C20"
                />
                <path d="M 152,108 Q 168,100 180,112" strokeWidth="1" strokeDasharray="2 2" />
                <path d="M 150,124 Q 165,116 176,128" strokeWidth="1" strokeDasharray="2 2" />
              </g>

              {/* Sheet 3 (Tall manuscript strip) */}
              <g>
                <path
                  d="M 80,185 L 100,181 L 106,260 L 86,264 Z"
                  strokeWidth="1.5"
                  fill="#1A1C20"
                />
                <line x1="85" y1="195" x2="96" y2="193" strokeWidth="1" />
                <line x1="86" y1="205" x2="98" y2="203" strokeWidth="1" />
                <line x1="87" y1="215" x2="99" y2="213" strokeWidth="1" />
                <line x1="88" y1="225" x2="100" y2="223" strokeWidth="1" />
                <line x1="89" y1="235" x2="101" y2="233" strokeWidth="1" />
                <line x1="90" y1="245" x2="102" y2="243" strokeWidth="1" />
              </g>

              {/* Sheet 4 (Near door handle) */}
              <g className="animate-float">
                <path
                  d="M 140,192 L 185,182 L 175,232 L 130,242 Z"
                  strokeWidth="1.5"
                  fill="#1A1C20"
                />
                <line
                  x1="145"
                  y1="200"
                  x2="175"
                  y2="192"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                />
                <line
                  x1="143"
                  y1="212"
                  x2="172"
                  y2="204"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                />
                <line
                  x1="140"
                  y1="224"
                  x2="165"
                  y2="218"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                />
              </g>

              {/* Sheet 5 (Floor drifting paper) */}
              <g>
                <path
                  d="M 125,295 Q 160,290 190,310 L 175,330 Q 145,310 115,320 Z"
                  strokeWidth="1.5"
                  fill="#1A1C20"
                />
                <path
                  d="M 130,305 Q 155,300 175,315"
                  strokeWidth="0.9"
                  strokeDasharray="2 2"
                />
              </g>

              {/* Small scattered paper fragments */}
              <rect
                x="52"
                y="245"
                width="11"
                height="16"
                transform="rotate(22 52 245)"
                strokeWidth="1.3"
              />
              <rect
                x="150"
                y="270"
                width="14"
                height="9"
                transform="rotate(-15 150 270)"
                strokeWidth="1.3"
              />

              {/* Blue spark / crosshair accent on right (from screenshot) */}
              <path
                d="M 335,235 L 335,251 M 327,243 L 343,243"
                stroke="#3B82F6"
                strokeWidth="1.8"
              />

              {/* Red ink accent at the top (from screenshot) */}
              <path d="M 75,18 L 78,30" stroke="#EF4444" strokeWidth="2.4" />
            </svg>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 6: MINIMALIST EDITORIAL FOOTER (Ellipsus Screenshot 5)
         ========================================================================= */}
      <footer className="w-full bg-[#121316] text-[#A0A5AD] px-8 sm:px-16 py-20 border-t border-[#22252A]">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-12 items-start">
          {/* Left Column: Brand & Nav Links */}
          <div className="md:col-span-5 space-y-6">
            <Link href="/" className="font-serif text-3xl font-bold text-white tracking-tight">
              docvane
            </Link>

            <nav className="flex flex-col space-y-2.5 text-xs font-medium tracking-wider text-white/70 uppercase">
              <Link href="/documents" className="hover:text-white transition-colors">
                Workspace Library
              </Link>
              <Link href="/reviews" className="hover:text-white transition-colors">
                Human Review Queue
              </Link>
              <Link href="/chat" className="hover:text-white transition-colors">
                Document Inquirer
              </Link>
              <Link href="/documents/upload" className="hover:text-white transition-colors">
                Intake Deposit
              </Link>
            </nav>
          </div>

          {/* Right Column: Literary Quote (Identical to Walter J. Ong quote in Screenshot 5) */}
          <div className="md:col-span-7 md:pl-8">
            <blockquote className="font-serif text-2xl sm:text-3xl text-white font-normal leading-relaxed">
              &ldquo;More than any other single invention, writing has transformed human
              consciousness.&rdquo;
            </blockquote>
            <p className="mt-4 font-serif text-base text-[#8B919D] italic">— Walter J. Ong</p>
          </div>
        </div>

        {/* Bottom Bar: Copyright & Terms */}
        <div className="max-w-6xl mx-auto mt-16 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between text-xs text-[#6B7280] gap-4">
          <p>© {new Date().getFullYear()} DocVane Intelligence. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <span className="hover:text-white cursor-pointer">TERMS OF SERVICE</span>
            <span className="hover:text-white cursor-pointer">PRIVACY POLICY</span>
            <span className="hover:text-white cursor-pointer">SECURITY & PRIVACY</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
