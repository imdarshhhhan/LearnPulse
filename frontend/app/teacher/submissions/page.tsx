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
import {
  ApiError,
  fetchTeacherSubmissions,
  type SubmissionStatus,
  type TeacherSubmissionsData,
} from "@/services/dashboardApi";

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export default function TeacherSubmissionsPage() {
  const router = useRouter();
  const [data, setData] = useState<TeacherSubmissionsData | null>(null);
  const [activityId, setActivityId] = useState(() => {
    if (typeof window === "undefined") return "";
    const activityFromUrl = new URLSearchParams(window.location.search).get("activityId");
    return activityFromUrl && /^\d+$/.test(activityFromUrl) ? activityFromUrl : "";
  });
  const [studentId, setStudentId] = useState("");
  const [submissionStatus, setSubmissionStatus] = useState<"" | SubmissionStatus>("");
  const [reloadCount, setReloadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchTeacherSubmissions({ activityId, studentId, status: submissionStatus })
      .then((result) => {
        if (active) setData(result);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load student submissions.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activityId, studentId, submissionStatus, reloadCount, router]);

  const reload = () => {
    setLoading(true);
    setError("");
    setReloadCount((count) => count + 1);
  };

  return (
    <DashboardShell title="Student Submissions" user={data?.profile ?? null}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-indigo-700">Teacher workspace</p>
          <h2 className="mt-1 text-2xl font-semibold">Student Submissions</h2>
          <p className="mt-1 text-sm text-zinc-600">
            Review attempts for activities assigned by you.
          </p>
        </div>
        <Link href="/teacher" className="text-sm font-medium text-indigo-700 hover:underline">
          Back to dashboard
        </Link>
      </div>

      <Panel title="Filters">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="space-y-1 text-sm font-medium">
            <span>Activity</span>
            <select
              value={activityId}
              onChange={(event) => {
                setLoading(true);
                setError("");
                setActivityId(event.target.value);
              }}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
            >
              <option value="">All activities</option>
              {data?.filters.activities.map((activity) => (
                <option key={activity.id} value={activity.id}>{activity.title}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Student</span>
            <select
              value={studentId}
              onChange={(event) => {
                setLoading(true);
                setError("");
                setStudentId(event.target.value);
              }}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
            >
              <option value="">All students</option>
              {data?.filters.students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.usn ?? "USN pending"} · {student.fullName}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Submission status</span>
            <select
              value={submissionStatus}
              onChange={(event) => {
                setLoading(true);
                setError("");
                const value = event.target.value;
                if (value === "" || value === "submitted" || value === "in_progress") {
                  setSubmissionStatus(value);
                }
              }}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
            >
              <option value="">All statuses</option>
              <option value="submitted">Submitted</option>
              <option value="in_progress">In progress</option>
            </select>
          </label>
        </div>
      </Panel>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <div className="space-y-3">
          <ErrorBanner message={error} />
          <button
            type="button"
            onClick={reload}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100"
          >
            Try again
          </button>
        </div>
      ) : data && data.submissions.length === 0 ? (
        <Panel title="Submissions">
          <EmptyState>
            {activityId || studentId || submissionStatus
              ? "No submissions match these filters."
              : "No submissions yet for your assigned activities."}
          </EmptyState>
        </Panel>
      ) : data ? (
        <Panel title={`${data.submissions.length} ${data.submissions.length === 1 ? "submission" : "submissions"}`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                  <th className="px-3 py-3 font-medium">Student</th>
                  <th className="px-3 py-3 font-medium">Activity</th>
                  <th className="px-3 py-3 font-medium">Date</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 font-medium">Score</th>
                  <th className="px-3 py-3"><span className="sr-only">Review</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {data.submissions.map((submission) => (
                  <tr key={submission.id}>
                    <td className="px-3 py-3 font-medium">
                      {submission.studentUsn ?? "USN pending"} · {submission.studentName}
                    </td>
                    <td className="px-3 py-3">{submission.activityTitle}</td>
                    <td className="px-3 py-3 text-zinc-600">{formatDate(submission.submittedAt)}</td>
                    <td className="px-3 py-3">
                      {submission.status === "submitted" ? "Submitted" : "In progress"}
                    </td>
                    <td className="px-3 py-3">
                      {submission.scorePercent === null ? "—" : `${submission.scorePercent}%`}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <Link
                        href={`/teacher/submissions/${submission.id}`}
                        className="font-medium text-indigo-700 hover:underline"
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}
    </DashboardShell>
  );
}
