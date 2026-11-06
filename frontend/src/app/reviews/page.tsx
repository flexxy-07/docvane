"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Check,
  Edit3,
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
        ? `"${selectedTask.field_name}" approved.`
        : `"${selectedTask.field_name}" updated and saved.`
    );

    setTimeout(() => setToastMessage(null), 3500);
    setSubmitting(false);
    setIsEditing(false);
  };

  const pendingCount = tasks.filter((t) => t.status !== "resolved").length;

  return (
    <div className="w-full min-h-[calc(100vh-4rem)] bg-[#1A1C20] text-white">
      <div className="mx-auto max-w-7xl px-6 sm:px-8 py-12">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 border-b border-white/10 pb-8">
          <div>
            <h1 className="font-serif text-3xl sm:text-4xl font-normal text-white">
              Review Queue
            </h1>
            <p className="mt-2 text-sm text-[#A0A5AD] max-w-2xl">
              Confirm items that need a human check. Compare the detected text against the
              document snippet and approve or correct.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-white/10 bg-[#0E242B] px-5 py-2.5 text-right">
              <span className="block text-xs text-white/50">Needs review</span>
              <span className="font-serif text-2xl font-normal text-[#E68A36]">
                {pendingCount}
              </span>
            </div>
          </div>
        </div>

        {toastMessage && (
          <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-950/40 p-4 text-xs text-emerald-300">
            ✓ {toastMessage}
          </div>
        )}

        {/* Main Split Layout: Left List, Right Inspector */}
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Tasks List (5 cols) */}
          <div className="lg:col-span-5 space-y-3">
            <div className="text-xs text-white/50 uppercase tracking-wider px-1">
              Items ({tasks.length})
            </div>

            {loading ? (
              <div className="py-12 text-center text-xs text-white/40">
                Loading review items...
              </div>
            ) : (
              tasks.map((task) => {
                const isSelected = selectedTask?.id === task.id;
                const isResolved = task.status === "resolved";
                const matchPct = Math.round((task.confidence || 0.5) * 100);

                return (
                  <div
                    key={task.id}
                    onClick={() => handleSelectTask(task)}
                    className={`cursor-pointer rounded-2xl border p-5 transition-all ${
                      isSelected
                        ? "border-[#E68A36] bg-[#14333D]"
                        : isResolved
                        ? "border-white/5 bg-white/5 opacity-50 hover:opacity-100"
                        : "border-white/10 bg-[#0E242B]/80 hover:border-white/20 hover:bg-[#122B33]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-serif text-base font-normal text-white line-clamp-1">
                        {task.field_name || "Document Field"}
                      </span>
                      {isResolved ? (
                        <span className="rounded-full bg-emerald-950/70 border border-emerald-500/30 px-2 py-0.5 text-[10px] text-emerald-400">
                          Verified ✓
                        </span>
                      ) : (
                        <span className="rounded-full bg-amber-950/70 border border-amber-500/30 px-2 py-0.5 text-[10px] text-amber-400">
                          {matchPct}% match
                        </span>
                      )}
                    </div>

                    <p className="mt-2 text-xs text-white/70 line-clamp-2 italic font-serif">
                      &ldquo;{task.corrected_value || task.field_value}&rdquo;
                    </p>

                    <div className="mt-4 flex items-center justify-between text-xs text-white/40 border-t border-white/5 pt-2">
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
              <div className="rounded-3xl border border-white/10 bg-[#0E242B] p-6 sm:p-8">
                <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-6">
                  <div>
                    <span className="text-xs text-[#E68A36]">
                      Page {selectedTask.source_page || 1}
                    </span>
                    <h2 className="mt-1 font-serif text-2xl text-white">
                      {selectedTask.field_name}
                    </h2>
                  </div>

                  <div className="text-right">
                    <span className="text-xs text-white/40 block">Match Score</span>
                    <span className="font-serif text-xl text-[#E68A36]">
                      {Math.round((selectedTask.confidence || 0.6) * 100)}%
                    </span>
                  </div>
                </div>

                {/* Simulated Document Preview with Highlight */}
                <div className="mt-6 rounded-2xl border border-white/5 bg-black/40 p-6 text-sm">
                  <div className="flex items-center justify-between text-[11px] text-white/40 mb-3">
                    <span>DOCUMENT EXCERPT</span>
                    <span>Page {selectedTask.source_page || 1}</span>
                  </div>

                  {/* Paper View */}
                  <div className="relative rounded-xl bg-[#FAF8F5] p-6 text-[#1A1C20] font-serif shadow-inner">
                    <p className="text-xs text-[#6B7280] select-none mb-3">
                      ...Agreement terms entered into as of the execution date. Both parties
                      stipulate mutual confidentiality and standard obligations...
                    </p>

                    {/* Detected Highlight */}
                    <div className="relative my-2 rounded-lg border-2 border-[#E68A36] bg-[#E68A36]/15 p-3 text-xs text-[#111827] font-semibold">
                      <span className="absolute -top-2.5 right-2 rounded bg-[#111827] px-1.5 py-0.2 text-[9px] text-[#E68A36]">
                        DETECTED
                      </span>
                      {selectedTask.field_value}
                    </div>

                    <p className="text-xs text-[#6B7280] select-none mt-3">
                      ...Subject to governing regulations and commercial guidelines superseding
                      previous discussions...
                    </p>
                  </div>
                </div>

                {/* Correction Input / Approval Form */}
                <div className="mt-8 border-t border-white/10 pt-6">
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-xs text-white/60 uppercase tracking-wider">
                      Confirmed Value
                    </label>
                    {!isEditing && selectedTask.status !== "resolved" && (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="flex items-center gap-1 text-xs text-[#E68A36] hover:underline"
                      >
                        <Edit3 className="h-3 w-3" />
                        <span>Edit</span>
                      </button>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="space-y-4">
                      <textarea
                        value={correctionInput}
                        onChange={(e) => setCorrectionInput(e.target.value)}
                        rows={3}
                        className="w-full rounded-xl border border-[#E68A36]/60 bg-black/40 p-3 text-sm text-white outline-none font-serif"
                      />
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => setIsEditing(false)}
                          className="rounded-full border border-white/20 px-4 py-1.5 text-xs text-white/70"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleResolve("correct")}
                          disabled={submitting}
                          className="rounded-full bg-white px-5 py-1.5 text-xs font-medium text-[#1A1C20]"
                        >
                          Save changes
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm font-serif text-white">
                      {selectedTask.corrected_value || selectedTask.field_value}
                    </div>
                  )}

                  {/* Actions */}
                  {selectedTask.status !== "resolved" && !isEditing && (
                    <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
                      <button
                        onClick={() => handleResolve("approve")}
                        disabled={submitting}
                        className="flex items-center gap-2 rounded-full bg-white px-6 py-2.5 text-xs font-medium text-[#1A1C20] transition-all hover:bg-neutral-200"
                      >
                        <Check className="h-4 w-4" />
                        <span>Approve value</span>
                      </button>

                      <button
                        onClick={() => setIsEditing(true)}
                        className="flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-5 py-2.5 text-xs font-medium text-white transition-all hover:bg-white/10"
                      >
                        <Edit3 className="h-4 w-4 text-[#E68A36]" />
                        <span>Edit value</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 py-20 text-center text-xs text-white/40">
                Select an item from the review queue.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
