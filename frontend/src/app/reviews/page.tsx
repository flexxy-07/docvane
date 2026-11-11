"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Check,
  Edit3,
  CheckCircle2,
  Filter,
} from "lucide-react";
import {
  ReviewTaskItem,
  fetchReviewTasks,
  saveReviewTaskUpdate,
  API_BASE_URL,
  DEFAULT_TENANT_ID,
} from "@/lib/api";

export default function ReviewQueuePage() {
  const [tasks, setTasks] = useState<ReviewTaskItem[]>([]);
  const [selectedTask, setSelectedTask] = useState<ReviewTaskItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<"pending" | "resolved" | "all">("pending");
  const [correctionInput, setCorrectionInput] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchReviewTasks().then((items) => {
      setTasks(items);
      const pendingFirst = items.find((t) => t.status !== "resolved") || items[0] || null;
      if (pendingFirst) {
        setSelectedTask(pendingFirst);
        setCorrectionInput(pendingFirst.field_value || "");
      }
      setLoading(false);
    });
  }, []);

  const handleSelectTask = (task: ReviewTaskItem) => {
    setSelectedTask(task);
    setCorrectionInput(task.corrected_value || task.field_value || "");
    setIsEditing(false);
  };

  const handleResolve = async (action: "approve" | "correct") => {
    if (!selectedTask) return;
    setSubmitting(true);
    const resolvedValue = action === "correct" ? correctionInput : selectedTask.field_value;

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

    // Persist to local storage
    saveReviewTaskUpdate(selectedTask.id, "resolved", resolvedValue);

    // Update local state
    setTasks((prev) =>
      prev.map((t) =>
        t.id === selectedTask.id
          ? {
              ...t,
              status: "resolved",
              corrected_value: resolvedValue,
            }
          : t
      )
    );

    setSelectedTask((prev) =>
      prev
        ? {
            ...prev,
            status: "resolved",
            corrected_value: resolvedValue,
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
  const resolvedCount = tasks.filter((t) => t.status === "resolved").length;

  const visibleTasks = tasks.filter((t) => {
    if (filterTab === "pending") return t.status !== "resolved";
    if (filterTab === "resolved") return t.status === "resolved";
    return true;
  });

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
            <div className="rounded-2xl border border-white/10 bg-[#22252A] px-5 py-2.5 text-right">
              <span className="block text-xs font-mono text-white/50">Needs review</span>
              <span className="font-serif text-2xl font-normal text-[#C48CFF]">
                {pendingCount}
              </span>
            </div>
            <div className="rounded-2xl border border-white/10 bg-[#22252A] px-5 py-2.5 text-right">
              <span className="block text-xs font-mono text-white/50">Verified</span>
              <span className="font-serif text-2xl font-normal text-emerald-400">
                {resolvedCount}
              </span>
            </div>
          </div>
        </div>

        {toastMessage && (
          <div className="mt-6 rounded-xl border border-emerald-500/25 bg-emerald-950/30 p-4 text-xs text-emerald-300">
            ✓ {toastMessage}
          </div>
        )}

        {/* Filter Tabs */}
        <div className="mt-8 flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-white/40 mr-1" />
          <button
            onClick={() => setFilterTab("pending")}
            className={`rounded-full px-4 py-1.5 text-xs transition-colors ${
              filterTab === "pending"
                ? "bg-white text-[#1A1C20] font-medium"
                : "border border-white/10 bg-white/5 text-white/70 hover:bg-white/10"
            }`}
          >
            Needs Review ({pendingCount})
          </button>
          <button
            onClick={() => setFilterTab("resolved")}
            className={`rounded-full px-4 py-1.5 text-xs transition-colors ${
              filterTab === "resolved"
                ? "bg-white text-[#1A1C20] font-medium"
                : "border border-white/10 bg-white/5 text-white/70 hover:bg-white/10"
            }`}
          >
            Verified ({resolvedCount})
          </button>
          <button
            onClick={() => setFilterTab("all")}
            className={`rounded-full px-4 py-1.5 text-xs transition-colors ${
              filterTab === "all"
                ? "bg-white text-[#1A1C20] font-medium"
                : "border border-white/10 bg-white/5 text-white/70 hover:bg-white/10"
            }`}
          >
            All Items ({tasks.length})
          </button>
        </div>

        {/* Main Split Layout: Left List, Right Inspector */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Tasks List (5 cols) */}
          <div className="lg:col-span-5 space-y-3">
            {loading ? (
              <div className="py-12 text-center text-xs text-white/40">
                Loading review items...
              </div>
            ) : visibleTasks.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-xs text-white/50">
                <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-400 mb-2" />
                <p className="font-serif text-sm text-white">
                  {filterTab === "pending"
                    ? "All items have been reviewed!"
                    : "No items in this category."}
                </p>
                {filterTab === "pending" && (
                  <button
                    onClick={() => setFilterTab("all")}
                    className="mt-3 text-xs text-[#C48CFF] hover:text-[#B066FF] hover:underline"
                  >
                    View all verified items →
                  </button>
                )}
              </div>
            ) : (
              visibleTasks.map((task) => {
                const isSelected = selectedTask?.id === task.id;
                const isResolved = task.status === "resolved";
                const matchPct = Math.round((task.confidence || 0.5) * 100);

                return (
                  <div
                    key={task.id}
                    onClick={() => handleSelectTask(task)}
                    className={`cursor-pointer rounded-2xl border p-5 transition-all ${
                      isSelected
                        ? "border-[#B066FF]/70 bg-[#262A32] shadow-[0_0_15px_rgba(176,102,255,0.08)]"
                        : isResolved
                        ? "border-white/5 bg-[#1E2024] opacity-60 hover:opacity-100"
                        : "border-white/10 bg-[#22252A] hover:border-white/20 hover:bg-[#262A30]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-serif text-base font-normal text-white line-clamp-1">
                        {task.field_name || "Document Field"}
                      </span>
                      {isResolved ? (
                        <span className="rounded-full bg-emerald-500/10 border border-emerald-500/25 px-2 py-0.5 text-[10px] font-mono text-emerald-300">
                          Verified ✓
                        </span>
                      ) : (
                        <span className="rounded-full bg-[#B066FF]/15 border border-[#B066FF]/30 px-2 py-0.5 text-[10px] font-mono text-[#C48CFF]">
                          {matchPct}% match
                        </span>
                      )}
                    </div>

                    <p className="mt-2 text-xs text-white/70 line-clamp-2 italic font-serif">
                      &ldquo;{task.corrected_value || task.field_value}&rdquo;
                    </p>

                    <div className="mt-4 flex items-center justify-between text-xs font-mono text-white/40 border-t border-white/5 pt-2">
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
              <div className="rounded-3xl border border-white/10 bg-[#22252A] p-6 sm:p-8">
                <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-6">
                  <div>
                    <span className="text-xs font-mono text-[#C48CFF]">
                      Page {selectedTask.source_page || 1}
                    </span>
                    <h2 className="mt-1 font-serif text-2xl text-white">
                      {selectedTask.field_name}
                    </h2>
                  </div>

                  <div className="text-right">
                    <span className="text-xs font-mono text-white/40 block">Match Score</span>
                    <span className="font-serif text-xl text-[#C48CFF]">
                      {Math.round((selectedTask.confidence || 0.6) * 100)}%
                    </span>
                  </div>
                </div>

                {/* Simulated Document Preview with Highlight */}
                <div className="mt-6 rounded-2xl border border-white/5 bg-black/30 p-6 text-sm">
                  <div className="flex items-center justify-between text-[11px] font-mono text-white/40 mb-3">
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
                    <div className="relative my-2 rounded-lg border border-[#B066FF] bg-[#B066FF]/15 p-3 text-xs text-[#111827] font-semibold">
                      <span className="absolute -top-2.5 right-2 rounded bg-[#1A1C20] border border-[#B066FF]/40 px-1.5 py-0.2 text-[9px] font-mono text-[#C48CFF]">
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
                    <label className="text-xs font-mono text-white/60 uppercase tracking-wider">
                      Confirmed Value
                    </label>
                    {!isEditing && selectedTask.status !== "resolved" && (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="flex items-center gap-1 text-xs text-[#C48CFF] hover:text-[#B066FF] hover:underline"
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
                        className="w-full rounded-xl border border-[#B066FF]/60 bg-black/40 p-3 text-sm text-white outline-none font-serif focus:border-[#B066FF]"
                      />
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => setIsEditing(false)}
                          className="rounded-full border border-white/20 px-4 py-1.5 text-xs text-white/70 hover:bg-white/5"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleResolve("correct")}
                          disabled={submitting}
                          className="rounded-full bg-white px-5 py-1.5 text-xs font-semibold text-[#1A1C20] hover:bg-neutral-200"
                        >
                          Save changes
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm font-serif text-white flex items-center justify-between">
                      <span>{selectedTask.corrected_value || selectedTask.field_value}</span>
                      {selectedTask.status === "resolved" && (
                        <span className="text-xs text-emerald-400 flex items-center gap-1 font-mono">
                          <Check className="h-3.5 w-3.5" />
                          <span>Confirmed</span>
                        </span>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  {selectedTask.status !== "resolved" && !isEditing && (
                    <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
                      <button
                        onClick={() => handleResolve("approve")}
                        disabled={submitting}
                        className="flex items-center gap-2 rounded-full bg-white px-6 py-2.5 text-xs font-semibold text-[#1A1C20] transition-colors hover:bg-neutral-200"
                      >
                        <Check className="h-4 w-4" />
                        <span>Approve value</span>
                      </button>

                      <button
                        onClick={() => setIsEditing(true)}
                        className="flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-5 py-2.5 text-xs font-medium text-white transition-colors hover:bg-white/10"
                      >
                        <Edit3 className="h-4 w-4 text-[#C48CFF]" />
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
