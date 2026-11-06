"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";

/* ─────────────────────────────────────────────
   useInView – fires once when element enters viewport
───────────────────────────────────────────── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setInView(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

/* ─────────────────────────────────────────────
   useParallax – returns a y-offset driven by scroll
───────────────────────────────────────────── */
function useParallax(speed = 0.12) {
  const [y, setY] = useState(0);
  useEffect(() => {
    const onScroll = () => setY(window.scrollY * speed);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [speed]);
  return y;
}

/* ─────────────────────────────────────────────
   useMouse – returns normalised cursor position
───────────────────────────────────────────── */
function useMouse() {
  const [pos, setPos] = useState({ x: 0.5, y: 0.5 });
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setPos({ x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight });
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);
  return pos;
}

/* ─────────────────────────────────────────────
   SceneReveal – fade + slight rise on scroll entry
───────────────────────────────────────────── */
function Reveal({
  children,
  delay = 0,
  className = "",
  from = "bottom",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  from?: "bottom" | "left" | "right" | "none";
}) {
  const { ref, inView } = useInView(0.1);
  const translateMap = { bottom: "translateY(40px)", left: "translateX(-40px)", right: "translateX(40px)", none: "none" };
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "none" : translateMap[from],
        transition: `opacity 0.8s cubic-bezier(0.16,1,0.3,1) ${delay}ms, transform 0.8s cubic-bezier(0.16,1,0.3,1) ${delay}ms`,
        willChange: "opacity, transform",
      }}
    >
      {children}
    </div>
  );
}

/* ─────────────────────────────────────────────
   SplitReveal – animates each word sequentially
───────────────────────────────────────────── */
function SplitReveal({ text, className = "", baseDelay = 0 }: { text: string; className?: string; baseDelay?: number }) {
  const { ref, inView } = useInView(0.1);
  const words = text.split(" ");
  return (
    <span ref={ref} className={className} aria-label={text}>
      {words.map((word, i) => (
        <span
          key={i}
          className="inline-block overflow-hidden mr-[0.28em]"
        >
          <span
            style={{
              display: "inline-block",
              transform: inView ? "translateY(0)" : "translateY(110%)",
              opacity: inView ? 1 : 0,
              transition: `transform 0.75s cubic-bezier(0.16,1,0.3,1) ${baseDelay + i * 60}ms, opacity 0.5s ease ${baseDelay + i * 60}ms`,
            }}
          >
            {word}
          </span>
        </span>
      ))}
    </span>
  );
}

/* ─────────────────────────────────────────────
   DrawSVG – animates stroke-dashoffset on entry
───────────────────────────────────────────── */
function DrawSVGPlane({ inView }: { inView: boolean }) {
  return (
    <svg
      className="w-28 h-28 text-white/90"
      viewBox="0 0 100 100"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {[
        { d: "M 15,65 L 85,25 L 35,82 L 42,60 L 68,40", len: 220, delay: 0 },
        { d: "M 42,60 L 35,82 L 32,68 Z", len: 60, delay: 400 },
        { d: "M 15,65 L 42,60", len: 40, delay: 700 },
      ].map((p, i) => (
        <path
          key={i}
          d={p.d}
          stroke="white"
          strokeWidth="1.5"
          strokeDasharray={p.len}
          strokeDashoffset={inView ? 0 : p.len}
          style={{ transition: `stroke-dashoffset 1.1s cubic-bezier(0.16,1,0.3,1) ${p.delay}ms` }}
        />
      ))}
    </svg>
  );
}

/* ─────────────────────────────────────────────
   MAIN PAGE
───────────────────────────────────────────── */
export default function Home() {
  const mouse = useMouse();
  const heroParallaxY = useParallax(0.06);
  const lettersParallaxY = useParallax(0.14);

  /* hero plane / cursor refs */
  const heroRef = useRef<HTMLElement>(null);
  const { ref: planeRef, inView: planeInView } = useInView(0.1);

  /* section reveal hooks */
  const sec2 = useInView(0.08);
  const sec3 = useInView(0.1);
  const sec4 = useInView(0.08);
  const sec5 = useInView(0.1);

  /* scroll-driven smooth behaviour */
  useEffect(() => {
    document.documentElement.style.scrollBehavior = "smooth";
  }, []);

  /* cursor magnetic for CTA buttons */
  const [btnTranslate, setBtnTranslate] = useState({ x: 0, y: 0 });
  const btnRef = useRef<HTMLDivElement>(null);
  const onBtnMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    setBtnTranslate({ x: (e.clientX - cx) * 0.22, y: (e.clientY - cy) * 0.22 });
  }, []);
  const onBtnLeave = useCallback(() => setBtnTranslate({ x: 0, y: 0 }), []);

  const cursorX = (mouse.x - 0.5) * 18;
  const cursorY = (mouse.y - 0.5) * 10;

  return (
    <div className="w-full bg-[#1A1C20] overflow-hidden">

      {/* ══════════════════════════════════════════
          HERO — dark cinematic canvas
         ══════════════════════════════════════════ */}
      <section
        ref={heroRef}
        className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 py-20 text-center select-none overflow-hidden"
      >
        {/* Scattered drifting letters — parallax layer */}
        <div
          className="pointer-events-none absolute inset-0 overflow-hidden text-[#3A3E47] font-sans text-xs select-none"
          style={{ transform: `translateY(${lettersParallaxY}px)` }}
        >
          {[
            { t: "12%", l: "18%", c: "u", d: 0 }, { t: "8%", l: "26%", c: "n", d: 1200 },
            { t: "15%", l: "45%", c: "p", d: 400 }, { t: "10%", r: "32%", c: "d", d: 800 },
            { t: "14%", r: "22%", c: "e", d: 1600 }, { t: "8%", r: "15%", c: "r", d: 300 },
            { t: "12%", r: "8%", c: "y", d: 2000 }, { t: "22%", l: "45%", c: "v", d: 600 },
            { t: "25%", l: "52%", c: "f", d: 1800 }, { t: "18%", r: "40%", c: "k", d: 100 },
            { t: "24%", r: "28%", c: "a", d: 1400 }, { t: "20%", r: "18%", c: "z", d: 900 },
            { t: "22%", r: "10%", c: "g", d: 1100 }, { t: "40%", r: "14%", c: "w", d: 500 },
            { t: "48%", r: "12%", c: "y", d: 2200 }, { t: "56%", r: "14%", c: "r", d: 700 },
            { b: "28%", l: "28%", c: "J", d: 1300 }, { b: "24%", l: "32%", c: "q", d: 200 },
            { b: "22%", l: "40%", c: "ce", d: 1700 }, { b: "18%", l: "40%", c: "h", d: 1500 },
            { b: "26%", l: "45%", c: "s", d: 50 }, { b: "20%", l: "45%", c: "l", d: 1900 },
            { b: "26%", r: "42%", c: "q", d: 350 }, { b: "20%", r: "44%", c: "b", d: 2100 },
            { b: "30%", r: "34%", c: "c", d: 650 }, { b: "24%", r: "28%", c: "x", d: 1050 },
            { b: "20%", r: "29%", c: "n", d: 1750 }, { b: "16%", r: "18%", c: "u", d: 450 },
          ].map((s, i) => (
            <span
              key={i}
              className="absolute"
              style={{
                top: s.t,
                bottom: s.b,
                left: s.l,
                right: s.r,
                animation: `floatLetter ${7 + (i % 5)}s ease-in-out ${s.d}ms infinite`,
              }}
            >
              {s.c}
            </span>
          ))}
        </div>

        {/* Paper airplane — lower-left, well clear of the headline */}
        <div
          ref={planeRef as React.RefObject<HTMLDivElement>}
          className="pointer-events-none absolute left-[7%] bottom-[22%] hidden md:block"
          style={{
            transform: `translateY(${heroParallaxY * 0.4}px) rotate(${cursorX * 0.25}deg)`,
            transition: "transform 0.12s linear",
          }}
        >
          <DrawSVGPlane inView={planeInView} />
        </div>

        {/* Purple cursor — right side, aligned with headline vertically */}
        <div
          className="pointer-events-none absolute right-[11%] top-[46%] hidden md:block"
          style={{
            transform: `translate(${cursorX}px, calc(-50% + ${cursorY}px))`,
            transition: "transform 0.18s cubic-bezier(0.16,1,0.3,1)",
          }}
        >
          <svg className="w-11 h-11 text-[#B066FF] fill-current drop-shadow-[0_0_14px_rgba(176,102,255,0.55)]" viewBox="0 0 32 32">
            <path d="M 6 4 L 26 18 L 16 19 L 12 28 Z" />
          </svg>
        </div>

        {/* Headline — word-by-word reveal */}
        <h1
          className="relative font-serif text-5xl sm:text-7xl md:text-[5.5rem] font-normal tracking-tight text-white leading-[1.08]"
          style={{ transform: `translateY(${heroParallaxY * -0.5}px)` }}
        >
          <SplitReveal text="Read between the lines." baseDelay={200} />
        </h1>

        {/* Subtitle fade */}
        <Reveal delay={700} from="none">
          <p className="relative mt-7 max-w-xl text-base sm:text-lg font-light text-[#C5C9D1]">
            DocVane is an intelligent document workspace made for clarity.
          </p>
        </Reveal>

        {/* CTA — magnetic button */}
        <Reveal delay={950} from="none">
          <div
            ref={btnRef}
            className="relative mt-9"
            onMouseMove={onBtnMove}
            onMouseLeave={onBtnLeave}
          >
            <Link
              href="/documents"
              className="group relative inline-block overflow-hidden rounded-full bg-white px-8 py-3.5 text-sm font-medium text-[#1A1C20] shadow-sm"
              style={{
                transform: `translate(${btnTranslate.x}px, ${btnTranslate.y}px)`,
                transition: "transform 0.3s cubic-bezier(0.16,1,0.3,1), box-shadow 0.3s",
              }}
            >
              <span className="relative z-10 transition-colors duration-300 group-hover:text-[#1A1C20]">
                Explore workspace
              </span>
              {/* ink-spread ripple on hover */}
              <span
                className="absolute inset-0 rounded-full bg-[#F3F4F6] scale-0 group-hover:scale-100 transition-transform duration-500 ease-out origin-center"
              />
            </Link>
          </div>
        </Reveal>

        {/* Scroll indicator */}
        <Reveal delay={1400} from="none">
          <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-white/30">
            <span className="text-[10px] tracking-[0.2em] uppercase">scroll</span>
            <span className="inline-block w-px h-8 bg-white/20" style={{ animation: "scrollPulse 2s ease-in-out infinite" }} />
          </div>
        </Reveal>
      </section>

      {/* ══════════════════════════════════════════
          SECTION 2 — Cream editorial statement
         ══════════════════════════════════════════ */}
      <section
        ref={sec2.ref as React.RefObject<HTMLElement>}
        className="relative w-full bg-[#F7F5F0] px-8 sm:px-16 py-28 text-[#111827] overflow-hidden"
      >
        {/* Background ink-stain circle decoration */}
        <div
          className="pointer-events-none absolute -right-24 -top-24 w-96 h-96 rounded-full bg-[#E68A36]/5"
          style={{
            transform: `scale(${sec2.inView ? 1 : 0.6}) rotate(${sec2.inView ? 0 : 20}deg)`,
            opacity: sec2.inView ? 1 : 0,
            transition: "all 1.4s cubic-bezier(0.16,1,0.3,1) 200ms",
          }}
        />

        {/* Books sketch — draws in from left */}
        <div className="max-w-4xl mx-auto mb-8">
          <div
            style={{
              opacity: sec2.inView ? 1 : 0,
              transform: sec2.inView ? "none" : "translateX(-30px)",
              transition: "all 0.9s cubic-bezier(0.16,1,0.3,1) 100ms",
            }}
          >
            <svg
              className="w-36 h-28 text-[#111827]"
              viewBox="0 0 160 120"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M 25,32 Q 80,18 135,28 L 132,40 Q 78,30 22,44 Z" />
              <path d="M 22,44 L 25,32" />
              <path d="M 22,44 Q 78,32 132,40" />
              <path d="M 35,42 L 35,46" />
              <path d="M 20,54 Q 80,40 140,50 L 138,62 Q 78,52 18,66 Z" />
              <path d="M 18,66 L 20,54" />
              <path d="M 25,78 L 138,72 L 136,88 L 22,94 Z" />
              <path d="M 22,94 L 25,78" />
              <path d="M 40,38 L 125,28" strokeWidth="0.8" />
              <path d="M 38,50 L 130,40" strokeWidth="0.8" />
              <path d="M 35,84 L 125,78" strokeWidth="0.8" />
            </svg>
          </div>
        </div>

        <div className="max-w-4xl mx-auto space-y-12">
          {/* Statement 1 */}
          <h2 className="font-serif text-3xl sm:text-5xl md:text-[3.5rem] font-normal leading-[1.2] tracking-tight">
            <SplitReveal
              text="Plenty of tools are made for simple text, notes, and chat."
              baseDelay={150}
            />{" "}
            <span
              className="italic hand-wavy-red"
              style={{
                opacity: sec2.inView ? 1 : 0,
                transition: "opacity 0.6s ease 900ms",
              }}
            >
              That&apos;s not us.
            </span>
          </h2>

          {/* Statement 2 — staggered words */}
          <p className="font-serif text-3xl sm:text-5xl md:text-[3.5rem] font-normal leading-[1.2] tracking-tight text-[#1F2124]">
            <SplitReveal
              text="DocVane is here to decode complex agreements, verify line items,"
              baseDelay={300}
            />{" "}
            <span
              className="marker-highlight-purple"
              style={{
                opacity: sec2.inView ? 1 : 0,
                transition: "opacity 0.6s ease 1100ms",
              }}
            >
              catch discrepancies
            </span>
            {", and certify grounded data "}
            <span
              className="hand-circle-green"
              style={{
                opacity: sec2.inView ? 1 : 0,
                transition: "opacity 0.6s ease 1300ms",
              }}
            >
              with citations.
            </span>
          </p>
        </div>

        {/* Green arrow — rises in */}
        <div
          className="max-w-4xl mx-auto flex justify-end mt-12 pr-8"
          style={{
            opacity: sec2.inView ? 1 : 0,
            transform: sec2.inView ? "none" : "translateX(20px)",
            transition: "all 0.8s cubic-bezier(0.16,1,0.3,1) 1500ms",
          }}
        >
          <svg className="w-16 h-12 text-[#2B9A66]" viewBox="0 0 80 60" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M 10,15 Q 40,40 60,35" />
            <path d="M 50,30 L 60,35 L 56,45" />
          </svg>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          SECTION 3 — Warm banner with cranes
         ══════════════════════════════════════════ */}
      <section
        ref={sec3.ref as React.RefObject<HTMLElement>}
        className="relative w-full bg-[#EDE9E0] border-t border-[#E2DDD3] px-8 sm:px-16 py-24 text-center overflow-hidden"
      >
        {/* Origami cranes — swing in from top-right, then sway */}
        <div
          className="pointer-events-none absolute right-[10%] top-10 hidden lg:block"
          style={{
            opacity: sec3.inView ? 1 : 0,
            transform: sec3.inView ? "none" : "translateY(-40px) rotate(15deg)",
            transition: "all 1.1s cubic-bezier(0.16,1,0.3,1) 200ms",
          }}
        >
          <svg
            className="w-32 h-44 text-[#111827]"
            viewBox="0 0 100 140"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="40" y1="0" x2="40" y2="40" strokeDasharray="3 3" />
            <g style={{ animation: "craneSway 5s ease-in-out infinite" }}>
              <path d="M 40,40 L 65,48 L 48,60 L 30,52 Z" />
              <path d="M 48,60 L 58,75 L 35,68 Z" />
              <path d="M 30,52 L 20,44" />
            </g>
            <line x1="75" y1="0" x2="75" y2="80" strokeDasharray="3 3" />
            <g style={{ animation: "craneSway 6s ease-in-out 1s infinite" }}>
              <path d="M 75,80 L 95,88 L 80,98 L 65,92 Z" />
              <path d="M 80,98 L 88,112 L 68,105 Z" />
            </g>
          </svg>
        </div>

        {/* Left decorative books */}
        <div
          className="pointer-events-none absolute left-[8%] bottom-8 hidden lg:block"
          style={{
            opacity: sec3.inView ? 0.35 : 0,
            transform: sec3.inView ? "none" : "translateY(30px)",
            transition: "all 1s cubic-bezier(0.16,1,0.3,1) 400ms",
          }}
        >
          <svg className="w-24 h-20 text-[#111827]" viewBox="0 0 160 120" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M 25,32 Q 80,18 135,28 L 132,40 Q 78,30 22,44 Z" />
            <path d="M 25,78 L 138,72 L 136,88 L 22,94 Z" />
          </svg>
        </div>

        <div className="max-w-3xl mx-auto">
          <h2 className="font-serif text-4xl sm:text-6xl font-normal tracking-tight text-[#111827]">
            <SplitReveal text="Made for" baseDelay={100} />{" "}
            <span
              className="italic text-[#E68A36]"
              style={{
                opacity: sec3.inView ? 1 : 0,
                transform: sec3.inView ? "none" : "translateY(20px)",
                display: "inline-block",
                transition: "all 0.7s cubic-bezier(0.16,1,0.3,1) 600ms",
              }}
            >
              critical documents
            </span>
          </h2>
          <Reveal delay={800}>
            <p className="mt-4 text-base text-[#4B5563] font-light max-w-xl mx-auto">
              Where every invoice total, liability cap, and indemnification clause must be verified beyond doubt.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          SECTION 4 — Product workspace showcase
         ══════════════════════════════════════════ */}
      <section
        ref={sec4.ref as React.RefObject<HTMLElement>}
        className="relative w-full bg-[#1A1C20] px-6 sm:px-12 py-24"
      >
        <div className="max-w-6xl mx-auto">
          <div
            className="rounded-3xl border border-[#2D3139] bg-gradient-to-b from-[#0E2832] to-[#0A1A20] p-6 sm:p-10 shadow-2xl"
            style={{
              opacity: sec4.inView ? 1 : 0,
              transform: sec4.inView ? "none" : "translateY(50px) scale(0.97)",
              transition: "all 1s cubic-bezier(0.16,1,0.3,1) 100ms",
            }}
          >
            {/* Inner Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
              <div className="flex items-center gap-4">
                <span className="font-serif text-2xl font-bold text-white tracking-tight">docvane</span>
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
                  className="rounded-full bg-white/5 border border-white/10 px-4 py-1.5 text-xs text-white placeholder-white/40 outline-none w-48 sm:w-64 focus:border-white/30 transition-colors"
                />
              </div>
            </div>

            {/* Inner Split: Sidebar + Grid */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
              {/* Left Mini Sidebar */}
              <div className="md:col-span-3 space-y-3 text-sm text-white/70">
                <div className="relative inline-block w-full">
                  <div className="rounded-full border border-white/30 bg-white/10 px-4 py-2 text-white font-medium flex items-center justify-between">
                    <span>Repository</span>
                    <span className="text-xs text-white/50">10</span>
                  </div>
                </div>
                <Link href="/reviews" className="block px-4 py-2 hover:text-white transition-colors flex items-center justify-between">
                  <span>Review Queue</span>
                  <span className="rounded-full bg-[#E68A36]/20 px-2 py-0.5 text-xs text-[#E68A36] font-mono">3</span>
                </Link>
                <Link href="/chat" className="block px-4 py-2 hover:text-white transition-colors">
                  <span>Document Inquirer</span>
                </Link>
              </div>

              {/* Right Document Cards */}
              <div className="md:col-span-9 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { title: "The Odyssey Logistics Manifest", time: "6 months", badge: "Verified ✓", badgeColor: "text-emerald-400 bg-emerald-950/60" },
                  { title: "Frankenstein; or, the Modern Prometheus Order", time: "2 months", badge: "Review needed", badgeColor: "text-amber-400 bg-amber-950/60" },
                  { title: "The Iliad Master Services Contract", time: "25 days ago", badge: "Verified ✓", badgeColor: "text-emerald-400 bg-emerald-950/60" },
                  { title: "The Metamorphosis Commercial Lease", time: "10 days ago", badge: "Verified ✓", badgeColor: "text-emerald-400 bg-emerald-950/60" },
                  { title: "The Strange Case of Dr. Jekyll and Mr. Hyde", time: "2 minutes ago", badge: "Review needed", badgeColor: "text-amber-400 bg-amber-950/60", highlight: true },
                  { title: "The Picture of Dorian Gray Advisory Agreement", time: "Just now", badge: "Verified ✓", badgeColor: "text-emerald-400 bg-emerald-950/60" },
                ].map((item, i) => (
                  <Link
                    key={i}
                    href={item.badge === "Review needed" ? "/reviews" : "/chat"}
                    className={`group rounded-2xl border p-5 flex flex-col justify-between transition-all duration-300 ${
                      item.highlight
                        ? "border-[#E68A36]/60 bg-[#14333D] shadow-lg shadow-[#E68A36]/5"
                        : "border-white/10 bg-[#0C2229]/80 hover:border-white/25 hover:bg-[#102B34] hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/30"
                    }`}
                    style={{
                      opacity: sec4.inView ? 1 : 0,
                      transform: sec4.inView ? "none" : "translateY(20px)",
                      transition: `opacity 0.6s ease ${300 + i * 90}ms, transform 0.6s cubic-bezier(0.16,1,0.3,1) ${300 + i * 90}ms, border-color 0.3s, background 0.3s, box-shadow 0.3s`,
                    }}
                  >
                    <div>
                      <h4 className="font-serif text-base font-normal text-white line-clamp-2 leading-snug group-hover:text-white/90 transition-colors">
                        {item.title}
                      </h4>
                    </div>
                    <div className="mt-8 flex items-center justify-between text-xs text-white/50 border-t border-white/5 pt-3">
                      <span>{item.time}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.badgeColor}`}>{item.badge}</span>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          SECTION 5 — CTA with open doorway
         ══════════════════════════════════════════ */}
      <section
        ref={sec5.ref as React.RefObject<HTMLElement>}
        className="relative w-full bg-[#1A1C20] px-8 sm:px-16 pt-20 pb-28 border-t border-white/5 overflow-hidden"
      >
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
          {/* Left CTA */}
          <div className="md:col-span-6 space-y-8 z-10">
            <h2
              className="font-serif text-4xl sm:text-6xl font-normal text-white tracking-tight leading-[1.12]"
              style={{
                opacity: sec5.inView ? 1 : 0,
                transform: sec5.inView ? "none" : "translateY(30px)",
                transition: "all 0.9s cubic-bezier(0.16,1,0.3,1) 100ms",
              }}
            >
              Get started—read away.
            </h2>

            <div
              style={{
                opacity: sec5.inView ? 1 : 0,
                transform: sec5.inView ? "none" : "translateY(20px)",
                transition: "all 0.9s cubic-bezier(0.16,1,0.3,1) 400ms",
              }}
            >
              <Link
                href="/documents"
                className="group relative inline-block overflow-hidden rounded-full bg-white px-8 py-3.5 text-sm font-medium text-[#1A1C20] hover:shadow-[0_0_30px_rgba(255,255,255,0.15)] transition-shadow duration-500"
              >
                <span className="relative z-10">Sign up—it&apos;s free</span>
                <span className="absolute inset-0 rounded-full bg-[#F3F4F6] scale-0 group-hover:scale-100 transition-transform duration-500 ease-out origin-center" />
              </Link>
            </div>
          </div>

          {/* Right doorway SVG — papers animate in */}
          <div
            className="md:col-span-6 relative flex justify-center md:justify-end"
            style={{
              opacity: sec5.inView ? 1 : 0,
              transform: sec5.inView ? "none" : "translateX(40px)",
              transition: "all 1s cubic-bezier(0.16,1,0.3,1) 200ms",
            }}
          >
            <svg
              className="w-full max-w-[460px] h-auto text-white"
              viewBox="0 0 450 400"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M 0,360 Q 150,363 320,360" strokeWidth="1.3" strokeOpacity="0.7" />
              <path d="M 125,55 L 125,360" strokeWidth="1.8" />
              <path d="M 125,55 L 235,25 L 235,360" strokeWidth="1.8" />
              <path d="M 125,55 L 235,25" strokeWidth="1.8" />
              <path d="M 235,25 L 305,75 L 305,372 L 235,360 Z" strokeWidth="2" fill="#16181C" />
              <path d="M 305,75 L 312,71 L 312,368 L 305,372 Z" strokeWidth="1.5" />
              <path d="M 248,198 L 272,204 M 248,198 L 248,206" strokeWidth="2.4" />
              <path d="M 125,360 L 235,360" strokeWidth="1.8" />

              <g style={{ animation: "paperDrift 7s ease-in-out infinite" }}>
                <path d="M 60,115 L 105,98 L 115,150 L 70,167 Z" strokeWidth="1.5" fill="#1A1C20" />
                <path d="M 72,118 L 98,108" strokeWidth="1" strokeDasharray="2 3" />
                <path d="M 75,130 L 102,120" strokeWidth="1" strokeDasharray="2 3" />
                <path d="M 78,142 L 105,132" strokeWidth="1" strokeDasharray="2 3" />
              </g>
              <g style={{ animation: "paperDrift 9s ease-in-out 1.5s infinite" }}>
                <path d="M 148,95 Q 170,82 192,102 L 180,148 Q 158,132 138,144 Z" strokeWidth="1.5" fill="#1A1C20" />
                <path d="M 152,108 Q 168,100 180,112" strokeWidth="1" strokeDasharray="2 2" />
              </g>
              <g>
                <path d="M 80,185 L 100,181 L 106,260 L 86,264 Z" strokeWidth="1.5" fill="#1A1C20" />
                <line x1="85" y1="195" x2="96" y2="193" strokeWidth="1" />
                <line x1="86" y1="205" x2="98" y2="203" strokeWidth="1" />
                <line x1="87" y1="215" x2="99" y2="213" strokeWidth="1" />
                <line x1="88" y1="225" x2="100" y2="223" strokeWidth="1" />
              </g>
              <g style={{ animation: "paperDrift 8s ease-in-out 0.7s infinite" }}>
                <path d="M 140,192 L 185,182 L 175,232 L 130,242 Z" strokeWidth="1.5" fill="#1A1C20" />
                <line x1="145" y1="200" x2="175" y2="192" strokeWidth="1" strokeDasharray="2 3" />
                <line x1="143" y1="212" x2="172" y2="204" strokeWidth="1" strokeDasharray="2 3" />
              </g>
              <g>
                <path d="M 125,295 Q 160,290 190,310 L 175,330 Q 145,310 115,320 Z" strokeWidth="1.5" fill="#1A1C20" />
              </g>
              <rect x="52" y="245" width="11" height="16" transform="rotate(22 52 245)" strokeWidth="1.3" style={{ animation: "paperDrift 10s ease-in-out 2s infinite" }} />
              <rect x="150" y="270" width="14" height="9" transform="rotate(-15 150 270)" strokeWidth="1.3" style={{ animation: "paperDrift 8.5s ease-in-out 0.3s infinite" }} />
              <path d="M 335,235 L 335,251 M 327,243 L 343,243" stroke="#3B82F6" strokeWidth="1.8" />
              <path d="M 75,18 L 78,30" stroke="#EF4444" strokeWidth="2.4" />
            </svg>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          FOOTER
         ══════════════════════════════════════════ */}
      <footer className="w-full bg-[#121316] text-[#A0A5AD] px-8 sm:px-16 py-20 border-t border-[#22252A]">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-12 items-start">
          <div className="md:col-span-5 space-y-6">
            <Link href="/" className="font-serif text-3xl font-bold text-white tracking-tight hover:text-white/80 transition-colors">
              docvane
            </Link>
            <nav className="flex flex-col space-y-2.5 text-xs font-medium tracking-wider text-white/70 uppercase">
              {[
                { href: "/documents", label: "Workspace Library" },
                { href: "/reviews", label: "Human Review Queue" },
                { href: "/chat", label: "Document Inquirer" },
                { href: "/documents/upload", label: "Intake Deposit" },
              ].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="group flex items-center gap-2 hover:text-white transition-colors w-fit"
                >
                  <span className="inline-block w-0 h-px bg-white group-hover:w-4 transition-all duration-300" />
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>

          <div className="md:col-span-7 md:pl-8">
            <blockquote className="font-serif text-2xl sm:text-3xl text-white font-normal leading-relaxed">
              &ldquo;More than any other single invention, writing has transformed human consciousness.&rdquo;
            </blockquote>
            <p className="mt-4 font-serif text-base text-[#8B919D] italic">— Walter J. Ong</p>
          </div>
        </div>

        <div className="max-w-6xl mx-auto mt-16 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between text-xs text-[#6B7280] gap-4">
          <p>© {new Date().getFullYear()} DocVane. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <span className="hover:text-white cursor-pointer transition-colors">TERMS OF SERVICE</span>
            <span className="hover:text-white cursor-pointer transition-colors">PRIVACY POLICY</span>
            <span className="hover:text-white cursor-pointer transition-colors">SECURITY &amp; PRIVACY</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
