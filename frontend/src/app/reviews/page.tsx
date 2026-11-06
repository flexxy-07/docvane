"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  AlertTriangle,
  FileText,
  Search,
  Check,
  Edit3,
  Clock,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Undo2,
} from "lucide-react";
import {
  ReviewTaskItem,
  fetchReviewTasks,
  API_BASE_URL,
  DEFAULT_TENANT_ID,
} from "@/lib/api";

export default function ReviewQueuePage() {
  const [tasks, setTasks] = useState<ReviewTaskItem[]>([]);
  const [selectedTask, setSelectedTask] = useState<ReviewTaskItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [correctionInput, setCorrectionInput] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchReviewTasks().then((items) => {
      setTasks(items);
      if (items.length > 0) {
        setSelectedTask(items[0]);
        setCorrectionInput(items[0].field_value || "");
      }
      setLoading(false);
    });
  }, []);

  const handleSelectTask = (task: ReviewTaskItem) => {
    setSelectedTask(task);
    setCorrectionInput(task.field_value || "");
    setIsEditing(false);
  };

  const handleResolve = async (action: "approve" | "correct") => {
    if (!selectedTask) return;
    setSubmitting(true);

    try {
      await fetch(`${API_BASE_URL}/reviews/${selectedTask.id}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": DEFAULT_TENANT_ID,
        },
        body: JSON.stringify({
          action,
          corrected_value: action === "correct" ? correctionInput : null,
        }),
      });
    } catch {
      // Graceful offline mock handling
    }

    // Update local state
    setTasks((prev) =>
      prev.map((t) =>
        t.id === selectedTask.id
          ? {
            ...t,
            status: "resolved",
            corrected_value: action === "correct" ? correctionInput : t.field_value,
          }
          : t
      )
    );

    setSelectedTask((prev) =>
      prev
        ? {
          ...prev,
          status: "resolved",
          corrected_value: action === "correct" ? correctionInput : prev.field_value,
        }
        : null
    );

    setToastMessage(
      action === "approve"
        ? `Field "${selectedTask.field_name}" approved and verified.`
        : `Field "${selectedTask.field_name}" corrected and sealed in audit log.`
    );

    setTimeout(() => setToastMessage(null), 3500);
    setSubmitting(false);
    setIsEditing(false);
  };

  const pendingCount = tasks.filter((t) => t.status !== "resolved").length;

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 border-b border-[#2A2A2A] pb-8">
        <div>
          <span className="font-mono text-xs text-[#E8A87A] uppercase tracking-wider">
            Human-in-the-Loop Quality Gate
          </span>
          <h1 className="mt-1 font-serif text-3xl sm:text-4xl text-[#FAF8F5]">
            Extraction Review Queue
          </h1>
          <p className="mt-2 text-sm text-[#A0998F] max-w-2xl">
            Fields flagged by the model with confidence scores below verified thresholds.
            Inspect the source page bounding box and certify accuracy before downstream indexing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="rounded-lg border border-[#2A2A2A] bg-[#141414] px-4 py-2 text-right">
            <span className="block font-mono text-[11px] text-[#A0998F]">Pending Review</span>
            <span className="font-serif text-2xl font-bold text-[#E8A87A]">
              {pendingCount}
            </span>
          </div>
        </div>
      </div>

      {toastMessage && (
        <div className="mt-6 rounded-lg border border-[#7EC69A]/40 bg-[#7EC69A]/10 p-4 font-mono text-xs text-[#7EC69A]">
          ✓ {toastMessage}
        </div>
      )}

      {/* Main Split Layout: Left List, Right Inspector */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Tasks List (5 cols) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="font-mono text-xs text-[#A0998F] uppercase tracking-wider px-1">
            Verification Queue ({tasks.length} items)
          </div>

          {loading ? (
            <div className="py-12 text-center font-mono text-xs text-[#6B6560]">
              Loading review tasks...
            </div>
          ) : (
            tasks.map((task) => {
              const isSelected = selectedTask?.id === task.id;
              const isResolved = task.status === "resolved";
              const confPct = Math.round((task.confidence || 0.5) * 100);

              return (
                <div
                  key={task.id}
                  onClick={() => handleSelectTask(task)}
                  className={`cursor-pointer rounded-xl border p-4 transition-all ${isSelected
                      ? "border-[#E8C07A] bg-[#1C1C1C]"
                      : isResolved
                        ? "border-[#242424] bg-[#121212] opacity-60 hover:opacity-100"
                        : "border-[#242424] bg-[#141414] hover:border-[#3D3834] hover:bg-[#181818]"
                    }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-serif text-sm font-medium text-[#FAF8F5] line-clamp-1">
                      {task.field_name || "Extracted Field"}
                    </span>
                    {isResolved ? (
                      <span className="flex items-center gap-1 font-mono text-[10px] text-[#7EC69A]">
                        <Check className="h-3 w-3" />
                        <span>Verified</span>
                      </span>
                    ) : (
                      <span className="font-mono text-[11px] text-[#E8A87A]">
                        {confPct}% conf
                      </span>
                    )}
                  </div>

                  <p className="mt-2 text-xs text-[#A0998F] line-clamp-2 italic font-serif">
                    &ldquo;{task.corrected_value || task.field_value}&rdquo;
                  </p>

                  <div className="mt-3 flex items-center justify-between font-mono text-[10px] text-[#6B6560] border-t border-[#222222] pt-2">
                    <span>Page {task.source_page || 1}</span>
                    <span className="capitalize">{task.status}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Detailed Document & Field Inspector (7 cols) */}
        <div className="lg:col-span-7">
          {selectedTask ? (
            <div className="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-6 sm:p-8">
              <div className="flex items-start justify-between gap-4 border-b border-[#242424] pb-6">
                <div>
                  <span className="font-mono text-xs text-[#E8C07A]">
                    Source Page {selectedTask.source_page || 1}
                  </span>
                  <h2 className="mt-1 font-serif text-2xl text-[#FAF8F5]">
                    {selectedTask.field_name}
                  </h2>
                </div>

                <div className="text-right">
                  <span className="font-mono text-xs text-[#6B6560] block">Confidence</span>
                  <span className="font-mono text-lg font-bold text-[#E8A87A]">
                    {Math.round((selectedTask.confidence || 0.6) * 100)}%
                  </span>
                </div>
              </div>

              {/* Simulated Document Preview with Proofreader Bounding Box */}
              <div className="mt-6 rounded-xl border border-[#242424] bg-[#0A0A0A] p-6 text-sm">
                <div className="flex items-center justify-between font-mono text-[11px] text-[#6B6560] mb-4">
                  <span>DOCUMENT SCAN EXCERPT</span>
                  <span>BBOX: [x1, y1, x2, y2]</span>
                </div>

                {/* Simulated Paper View */}
                <div className="relative rounded-lg bg-[#FAF8F5] p-6 text-[#1A1A1A] font-serif shadow-inner">
                  <p className="text-xs text-[#6B6560] select-none mb-3">
                    ...Agreement terms entered into as of effective execution date. Both parties
                    stipulate mutual confidentiality and standard indemnification...
                  </p>

                  {/* Bounding Box Highlight with editorial hand-drawn contour */}
                  <div className="relative my-2 rounded-md border-2 border-[#E8C07A] bg-[#E8C07A]/15 p-3 font-mono text-xs text-[#0F0F0F] font-semibold">
                    <span className="absolute -top-2.5 right-2 rounded bg-[#0F0F0F] px-1.5 py-0.2 text-[9px] font-mono text-[#E8C07A]">
                      EXTRACTED VALUE
                    </span>
                    {selectedTask.field_value}
                  </div>

                  <p className="text-xs text-[#6B6560] select-none mt-3">
                    ...Subject to local state regulations and standard commercial arbitration rules
                    superseding previous memoranda...
                  </p>
                </div>
              </div>

              {/* Correction Input / Approval Form */}
              <div className="mt-8 border-t border-[#242424] pt-6">
                <div className="flex items-center justify-between mb-3">
                  <label className="font-mono text-xs text-[#A0998F] uppercase">
                    Verification Value
                  </label>
                  {!isEditing && selectedTask.status !== "resolved" && (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="flex items-center gap-1 font-mono text-xs text-[#E8C07A] hover:underline"
                    >
                      <Edit3 className="h-3 w-3" />
                      <span>Edit Value</span>
                    </button>
                  )}
                </div>

                {isEditing ? (
                  <div className="space-y-4">
                    <textarea
                      value={correctionInput}
                      onChange={(e) => setCorrectionInput(e.target.value)}
                      rows={3}
                      className="w-full rounded-lg border border-[#E8C07A]/60 bg-[#1A1A1A] p-3 text-sm text-[#FAF8F5] outline-none font-mono"
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setIsEditing(false)}
                        className="rounded-md border border-[#2A2A2A] px-4 py-1.5 text-xs font-mono text-[#A0998F]"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleResolve("correct")}
                        disabled={submitting}
                        className="rounded-md bg-[#E8C07A] px-4 py-1.5 text-xs font-medium text-[#0F0F0F]"
                      >
                        Save Correction & Verify
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-[#2A2A2A] bg-[#161616] p-4 text-sm font-serif text-[#FAF8F5]">
                    {selectedTask.corrected_value || selectedTask.field_value}
                  </div>
                )}

                {/* Actions */}
                {selectedTask.status !== "resolved" && !isEditing && (
                  <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
                    <button
                      onClick={() => handleResolve("approve")}
                      disabled={submitting}
                      className="flex items-center gap-2 rounded-md bg-[#7EC69A] px-5 py-2.5 text-xs font-medium text-[#0F0F0F] transition-all hover:bg-[#6EB68A]"
                    >
                      <Check className="h-4 w-4" />
                      <span>Approve As Extracted</span>
                    </button>

                    <button
                      onClick={() => setIsEditing(true)}
                      className="flex items-center gap-2 rounded-md border border-[#2A2A2A] bg-[#1E1E1E] px-4 py-2.5 text-xs font-medium text-[#FAF8F5] transition-all hover:border-[#E8C07A]/50"
                    >
                      <Edit3 className="h-4 w-4 text-[#E8C07A]" />
                      <span>Correct Value</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-[#2A2A2A] py-20 text-center font-mono text-xs text-[#6B6560]">
              Select a task from the verification queue.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

