DocVane Frontend — Design & Build Plan

Ellipsus-inspired, editorial-grade design adapted for a document intelligence platform. Not generic AI slop. Every design choice is intentional and tied to the product's purpose.

1. Design Philosophy — Ellipsus → DocVane Translation

The Ellipsus site works because every visual element reinforces its product's core idea: writing as a craft. We do the same for DocVane, where the craft is extracting intelligence from messy documents.

Ellipsus Element	DocVane Adaptation
Dark hero with serif "Write like a human."	Dark hero with serif "Read between the lines." — floating document fragments (invoice numbers, clause snippets) drift in the background instead of scattered letters
Handwritten annotation effects (underlines, circles)	Extraction annotation effects — hand-drawn circles around bounding boxes, wavy underlines on extracted field values, confidence score badges that look like editor's marks
Paper crane illustrations	Folded document / magnifying glass illustrations — soft hand-drawn SVGs of documents being unfolded, scanned, decoded
Serif + sans-serif contrast	Playfair Display (serif) for headings / hero text + Inter (sans) for body / UI — same editorial premium feel
Dark mode as default	Dark mode primary (#0F0F0F near-black) with warm paper-white (#FAF8F5) accent panels — documents feel like they're being examined on a dark desk
Whitespace-driven hierarchy	Generous spacing, large type scale, intentional breathing room between sections
2. Color System
Background (dark):     #0F0F0F  — near-black, not pure black
Surface (cards):       #1A1A1A  — elevated dark surface
Surface hover:         #242424  — subtle lift on interaction
Border subtle:         #2A2A2A  — barely visible structure lines
Text primary:          #FAF8F5  — warm white (not blue-white)
Text secondary:        #A0998F  — warm gray for supporting text
Text muted:            #6B6560  — de-emphasized labels
Accent (brand):        #E8C07A  — warm gold (confidence, highlights)
Accent hover:          #D4A85A  — deeper gold on interaction
Success:               #7EC69A  — soft sage green (approved, ready)
Warning:               #E8A87A  — warm amber (needs review)
Error:                 #D47272  — soft red (failed, rejected)
Info:                  #7AA8E8  — calm blue (processing, info)
Paper white (panels):  #FAF8F5  — for light-mode document previews
Paper cream:           #F5F0E8  — slightly warmer variant
3. Typography
Headings / Hero:     Playfair Display (serif), 700 weight
                     Hero: 64px / 72px line-height
                     H1:   40px / 48px
                     H2:   28px / 36px
                     H3:   20px / 28px
Body / UI:           Inter (sans-serif), 400/500/600
                     Body: 16px / 26px (generous line-height)
                     Small: 14px / 22px
                     Caption: 12px / 18px
                     Code/mono: JetBrains Mono, 14px
4. Pages & Views
4.1 Landing / Dashboard (/)

The entry point. Dark, cinematic, editorial.

Hero Section:

Large serif heading: "Read between the lines."
Subtext: "Upload messy invoices and contracts. Get structured intelligence, verified by humans, answered with citations."
Floating background: semi-transparent document fragments (invoice numbers, dates, clause text) drift slowly using CSS keyframe animations — same concept as Ellipsus's scattered floating letters
Two CTAs: [Upload a Document] (primary, gold border) and [Ask a Question] (secondary, ghost)

Below the fold — 3 feature cards (horizontal scroll on mobile):

Extract — hand-drawn magnifying glass icon — "OCR + LLM extraction with confidence scores. Tables, clauses, line items — structured automatically."
Verify — hand-drawn checkmark/circle icon — "Low-confidence fields surface in a human review queue. Side-by-side: document + editable field."
Ask — hand-drawn chat bubble icon — "Hybrid RAG + Text-to-SQL. Ask questions across documents with cited, grounded answers."

Stats / Pipeline Overview (after the fold): A horizontal pipeline visualization showing the document state machine: uploaded → parsing → extracting → needs_review → reviewed → indexing → ready Each node is a small circle with a count badge (e.g., "3 documents extracting").

4.2 Documents Library (/documents)

A list/grid of all uploaded documents for the tenant.

Top bar: Search input (serif placeholder: "Search your documents…"), filter pills (status, type, date), upload button
Document cards (grid layout):
Thumbnail preview (first page miniature or file-type icon)
Filename (truncated), doc type badge (invoice / contract)
Status chip with annotation-style treatment:
ready → green chip with hand-drawn checkmark
needs_review → amber chip with hand-drawn circle
extracting → blue chip with animated dots
failed → red chip with hand-drawn X
Date, page count, file size
Click → document detail view
4.3 Upload Flow (/documents/upload)

Drag-and-drop zone with editorial flair.

Large dashed-border drop zone with a hand-drawn "unfold document" illustration
Serif text: "Drop your invoices and contracts here"
Supported formats shown below: PDF, PNG, JPG, TIFF
On drop: file appears with a progress bar styled as a "pen stroke" filling left-to-right
After upload: card shows document status transitioning through the pipeline in real-time (polling or SSE)
4.4 Document Detail (/documents/[id])

Split-pane view: document preview on the left, extracted data on the right.

Left pane (60%):

Page-by-page document viewer (rendered PDF page images)
Page navigation (prev/next + page number input)
Bounding box overlays on extracted fields (hand-drawn style: slightly imperfect rectangles with warm gold stroke)
Hover a field on the right → the corresponding bbox highlights and pulses on the left

Right pane (40%):

Accordion sections for each extraction category (General Info, Line Items, Payment Terms, Parties, etc.)
Each field row:
Field name (label, small caps)
Extracted value (editable if in review)
Confidence bar: a thin horizontal bar with warm gold fill, percentage label
Source indicator: "p.2, line 14" — clickable, scrolls the left pane to that location
Status icon: ✓ approved / ⊙ needs review / ✕ rejected
"Send to Review" button on low-confidence fields
4.5 Human Review Queue (/reviews)

The core differentiator view. Editorial, focused, task-driven.

Queue list:

Table with columns: Document, Field Name, Extracted Value, Confidence, Status, Assigned To
Filterable by status (pending / claimed / resolved), document, confidence range
Click a row → opens the review detail

Review Detail (full-screen modal or dedicated page):

Left (55%): Document page with the relevant bounding box highlighted in warm gold, zoomed to the region of interest. Hand-drawn annotation circle around the bbox.
Right (45%):
Field label (serif, large)
Current extracted value (in a warm-paper input box)
Confidence score with a visual bar
OCR raw text snippet (monospace, muted)
Action buttons: [Approve as-is] (green) / [Correct & Save] (gold) / [Reject] (red)
Correction input field (appears on "Correct")
Keyboard shortcuts: A = approve, E = edit/correct, → = next task (power-user flow)
Bottom bar: task counter ("3 of 17 remaining") with a serif progress label
4.6 Chat / Ask (/chat)

The RAG + SQL conversational interface.

Layout: Full-height, centered column (max-width 720px), dark background.

Message bubbles:

User messages: right-aligned, warm dark surface card
Assistant messages: left-aligned, slightly lighter surface, serif heading for the answer summary
Citations rendered inline as small "footnote chips" [1] [2] — hover shows chunk preview tooltip, click expands citation panel

Citation Panel (expandable below the answer):

Each citation card:
Document name + page number
Chunk excerpt (first 200 chars, monospace-ish styling)
Relevance score badge
"View in Document" link → opens /documents/[id] at that page

Route Indicator (subtle):

Below each answer, a muted label: routed via: hybrid search + rerank or routed via: Text-to-SQL
If SQL was used, a collapsible [Show SQL Query] panel with syntax-highlighted SQL in JetBrains Mono

Input bar (bottom, sticky):

Full-width input with serif placeholder: "Ask about your documents…"
Send button (gold accent)
Small toggle: [Include SQL] on/off
5. Components & Micro-interactions
Hand-drawn Annotation Effects (CSS/SVG)
Bounding box overlays: slightly wobbly rectangles (SVG path with small random offsets)
Underline effects on extracted values: wavy SVG underline (like a proofreader's mark)
Circle highlights on review items: hand-drawn circle SVG around the confidence score
These are NOT heavy — they're lightweight SVG paths or CSS border-image tricks
Transitions & Motion
Page transitions: subtle fade + slight upward slide (200ms ease-out)
Card hovers: gentle scale(1.01) + subtle shadow increase
Status changes: the status chip morphs with a brief color-fade animation
Floating background elements: very slow CSS translate + opacity keyframes (60s+ cycle)
No bouncy/spring animations — everything is calm, editorial, deliberate
Responsive Strategy
Desktop (>1024px): full split-pane layouts, grid document cards
Tablet (768–1024px): stacked panes, 2-column document grid
Mobile (<768px): single column, bottom-sheet for citation panels, swipe for review tasks
6. Tech Stack
Layer	Choice	Reason
Framework	Next.js 15 (App Router)	SSR for SEO on landing, client components for interactive views
Language	TypeScript (strict)	Type safety end-to-end with backend Pydantic schemas
Styling	Tailwind CSS v4 + custom design tokens	Utility-first with the dark editorial palette baked in
Components	shadcn/ui (customized heavily)	Accessible primitives, then we override everything to match the editorial design
Icons	Lucide React + custom hand-drawn SVGs	Lucide for standard UI, custom SVGs for the editorial illustration elements
Fonts	Playfair Display + Inter + JetBrains Mono	Google Fonts, self-hosted via next/font for performance
State	TanStack Query v5	Server state management, caching, optimistic updates for the API
Forms	React Hook Form + Zod	Review task corrections, upload validation
PDF Viewer	react-pdf (pdfjs-dist)	Render document pages for the split-pane viewer
Charts	Recharts (minimal)	Confidence distribution, pipeline stats
Animations	Framer Motion (light usage)	Page transitions, floating elements, citation panel expand
7. Build Order (Step by Step)
Step 1: Scaffold & Design System Foundation
pnpm create next-app frontend with TypeScript + Tailwind + App Router
Install shadcn/ui, configure with dark theme
Set up next/font for Playfair Display + Inter + JetBrains Mono
Create the Tailwind config with the full color system from Section 2
Build the <Layout> shell: dark nav bar with serif "Docvane" logo, nav links, content area
Step 2: Landing / Dashboard Hero
Build the hero section with floating background fragments
Feature cards section
Pipeline status overview (static mockup first, then wire to API)
Step 3: Documents Library
Document grid with status chips
Search + filter bar
Wire to GET /api/v1/documents via TanStack Query
Step 4: Upload Flow
Drag-and-drop zone component
Upload progress with "pen stroke" progress bar
Wire to POST /api/v1/documents/upload
Step 5: Document Detail (Split Pane)
PDF page renderer (left pane)
Extracted fields accordion (right pane)
Bounding box overlays with hand-drawn styling
Wire to GET /api/v1/documents/{id}
Step 6: Review Queue
Review task list table
Review detail view (split pane with zoom + correction)
Keyboard shortcuts
Wire to review API endpoints
Step 7: Chat / Ask Interface
Message list with user/assistant bubbles
Citation chips + expandable panel
Route indicator + SQL viewer
Wire to POST /api/v1/retrieval/chat
Step 8: Polish & Responsive
Mobile layouts
Loading skeletons (editorial-style shimmer)
Error states (hand-drawn sad document illustration)
404 page (serif "Lost in the paperwork.")

IMPORTANT

We build step by step, one view at a time, verified before moving on. Next action: Step 1 — Scaffold the Next.js app with the full design system.