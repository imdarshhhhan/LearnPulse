"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  DashboardShell,
  EmptyState,
  ErrorBanner,
  LoadingState,
  Panel,
} from "@/app/components/DashboardShell";
import { ApiError } from "@/services/dashboardApi";
import {
  fetchTeacherFeedback,
  fetchTeacherFeedbackDetail,
  type AssessmentType,
  type TeacherFeedbackData,
  type TeacherFeedbackItem,
} from "@/services/feedbackApi";

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500";

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function categoryLabel(category: TeacherFeedbackItem["category"]) {
  if (!category) return "Not specified";
  return {
    content: "Content",
    difficulty: "Difficulty",
    experience: "Learning experience",
    other: "Other",
  }[category];
}

export default function TeacherFeedbackPage() {
  const router = useRouter();
  const [data, setData] = useState<TeacherFeedbackData | null>(null);
  const [activityType, setActivityType] = useState<"" | AssessmentType>("");
  const [assignmentId, setAssignmentId] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<TeacherFeedbackItem | null>(null);
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    let active = true;
    fetchTeacherFeedback({
      activityType: activityType || undefined,
      assignmentId,
      search,
      sort,
    })
      .then((result) => {
        if (!active) return;
        setData(result);
        setSelectedId((currentId) =>
          currentId && !result.feedback.some((item) => item.id === currentId)
            ? null
            : currentId,
        );
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        if (requestError instanceof ApiError && requestError.status === 403) {
          router.replace("/teacher");
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load student feedback.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activityType, assignmentId, reloadCount, router, search, sort]);

  useEffect(() => {
    if (selectedId === null) return;
    let active = true;
    fetchTeacherFeedbackDetail(selectedId)
      .then((result) => {
        if (active) setDetail(result);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        if (requestError instanceof ApiError && requestError.status === 403) {
          router.replace("/teacher");
          return;
        }
        setDetailError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load this feedback.",
        );
      })
    return () => {
      active = false;
    };
  }, [router, selectedId]);

  const activities = (data?.filters.activities ?? []).filter(
    (item) => !activityType || item.activityType === activityType,
  );
  const detailLoading = selectedId !== null && detail === null && !detailError;

  const reload = () => {
    setLoading(true);
    setError("");
    setReloadCount((count) => count + 1);
  };

  return (
    <DashboardShell title="Student Feedback" user={data?.profile ?? null}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-indigo-700">Teacher workspace</p>
          <h2 className="mt-1 text-2xl font-semibold">Student Feedback</h2>
          <p className="mt-1 text-sm text-zinc-600">
            Review feedback saved by students for your quizzes and homework.
          </p>
        </div>
        <Link href="/teacher" className="text-sm font-medium text-indigo-700 hover:underline">
          Back to dashboard
        </Link>
      </div>

      <Panel title="Filters">
        <form
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            setLoading(true);
            setError("");
            setSearch(searchInput.trim());
          }}
        >
          <label className="space-y-1 text-sm font-medium">
            <span>Activity type</span>
            <select
              className={inputClass}
              onChange={(event) => {
                setLoading(true);
                setError("");
                setActivityType(event.target.value as "" | AssessmentType);
                setAssignmentId("");
              }}
              value={activityType}
            >
              <option value="">All feedback</option>
              <option value="quiz">Quiz feedback</option>
              <option value="homework">Homework feedback</option>
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Assessment</span>
            <select
              className={inputClass}
              onChange={(event) => {
                setLoading(true);
                setError("");
                setAssignmentId(event.target.value);
              }}
              value={assignmentId}
            >
              <option value="">All assessments</option>
              {activities.map((activity) => (
                <option key={activity.id} value={activity.id}>
                  {activity.title}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Search students or feedback</span>
            <input
              className={inputClass}
              maxLength={100}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Name, USN, activity or message"
              value={searchInput}
            />
          </label>
          <div className="flex items-end gap-2">
            <label className="flex-1 space-y-1 text-sm font-medium">
              <span>Sort</span>
              <select
                className={inputClass}
                onChange={(event) =>
                  {
                    setLoading(true);
                    setError("");
                    setSort(event.target.value === "oldest" ? "oldest" : "newest");
                  }
                }
                value={sort}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </label>
            <button
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700"
              type="submit"
            >
              Search
            </button>
          </div>
        </form>
      </Panel>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <div className="space-y-3">
          <ErrorBanner message={error} />
          <button
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100"
            onClick={reload}
            type="button"
          >
            Try again
          </button>
        </div>
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
          <Panel title={`Feedback (${data?.feedback.length ?? 0})`}>
            {data?.feedback.length ? (
              <ul className="divide-y divide-zinc-100">
                {data.feedback.map((item) => (
                  <li key={item.id} className="py-3">
                    <button
                      aria-pressed={selectedId === item.id}
                      className="w-full rounded-lg p-2 text-left transition-colors hover:bg-zinc-50 aria-pressed:bg-indigo-50"
                      onClick={() => {
                        setSelectedId(item.id);
                        setDetail(null);
                        setDetailError("");
                      }}
                      type="button"
                    >
                      <span className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold">
                          {item.studentUsn ?? "USN pending"} · {item.studentName}
                        </span>
                        <span className="text-xs text-zinc-500">{formatDate(item.submittedAt)}</span>
                      </span>
                      <span className="mt-1 block text-sm text-zinc-600">
                        {item.activityType === "quiz" ? "Quiz" : "Homework"} · {item.activityTitle}
                      </span>
                      <span className="mt-1 block line-clamp-2 text-sm text-zinc-700">
                        {item.message}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState>
                {search || assignmentId || activityType
                  ? "No feedback matches these filters."
                  : "Student feedback will appear here after students submit it."}
              </EmptyState>
            )}
          </Panel>

          <Panel title="Feedback details">
            {detailLoading ? (
              <p className="text-sm text-zinc-500" role="status">Loading feedback…</p>
            ) : detailError ? (
              <ErrorBanner message={detailError} />
            ) : selectedId !== null && detail ? (
              <div className="space-y-3 text-sm">
                <div>
                  <p className="font-semibold">{detail.studentName}</p>
                  <p className="text-zinc-500">{detail.studentUsn ?? "USN not provided"}</p>
                </div>
                <p>
                  <span className="font-medium">Assessment:</span>{" "}
                  {detail.activityType === "quiz" ? "Quiz" : "Homework"} · {detail.activityTitle}
                </p>
                <p><span className="font-medium">Category:</span> {categoryLabel(detail.category)}</p>
                <p>
                  <span className="font-medium">Rating:</span>{" "}
                  {detail.rating === null ? "Not rated" : `${detail.rating} / 5`}
                </p>
                <p><span className="font-medium">Submitted:</span> {formatDate(detail.submittedAt)}</p>
                <p className="whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 text-zinc-700">
                  {detail.message}
                </p>
              </div>
            ) : (
              <EmptyState>Select a feedback item to read its details.</EmptyState>
            )}
          </Panel>
        </div>
      )}
    </DashboardShell>
  );
}
