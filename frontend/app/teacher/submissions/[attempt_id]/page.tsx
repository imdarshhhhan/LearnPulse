"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  DashboardShell,
  EmptyState,
  ErrorBanner,
  LoadingState,
  Panel,
} from "@/app/components/DashboardShell";
import {
  ApiError,
  fetchTeacherSubmission,
  type TeacherSubmissionDetail,
} from "@/services/dashboardApi";

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export default function TeacherSubmissionDetailPage() {
  const params = useParams<{ attempt_id: string }>();
  const router = useRouter();
  const attemptId = Number(params.attempt_id);
  const validAttemptId = Number.isSafeInteger(attemptId) && attemptId > 0;
  const [submission, setSubmission] = useState<TeacherSubmissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!validAttemptId) return;
    let active = true;
    fetchTeacherSubmission(attemptId)
      .then((result) => {
        if (active) setSubmission(result);
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
            : "Could not load this submission.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [attemptId, router, validAttemptId]);

  if (!validAttemptId) {
    return (
      <main className="mx-auto w-full max-w-3xl px-5 py-8">
        <ErrorBanner message="This submission link is not valid." />
        <Link href="/teacher/submissions" className="mt-4 inline-block text-sm text-indigo-700 hover:underline">
          Back to submissions
        </Link>
      </main>
    );
  }

  if (loading) {
    return (
      <DashboardShell title="Review Submission" user={null}>
        <LoadingState />
      </DashboardShell>
    );
  }

  if (error || !submission) {
    return (
      <DashboardShell title="Review Submission" user={null}>
        <ErrorBanner message={error || "Could not load this submission."} />
        <Link href="/teacher/submissions" className="text-sm text-indigo-700 hover:underline">
          Back to submissions
        </Link>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell title="Review Submission" user={submission.profile}>
      <Link href="/teacher/submissions" className="text-sm text-indigo-700 hover:underline">
        ← Back to submissions
      </Link>

      <Panel title={submission.activityTitle}>
        <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-zinc-500">Student</dt>
            <dd className="mt-1 font-medium">
              {submission.studentUsn ?? "USN pending"} · {submission.studentName}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Date</dt>
            <dd className="mt-1 font-medium">{formatDate(submission.submittedAt)}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Status</dt>
            <dd className="mt-1 font-medium">
              {submission.status === "submitted" ? "Submitted" : "In progress"}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Score</dt>
            <dd className="mt-1 font-medium">
              {submission.scorePercent === null ? "Not available" : `${submission.scorePercent}%`}
            </dd>
          </div>
        </dl>
      </Panel>

      <Panel title="Answers and results">
        {submission.answers.length === 0 ? (
          <EmptyState>No answer details are available for this activity.</EmptyState>
        ) : (
          <ol className="space-y-4">
            {submission.answers.map((answer, index) => (
              <li key={answer.questionId} className="rounded-lg border border-zinc-200 p-4">
                <h3 className="font-medium">
                  {index + 1}. {answer.questionText}
                </h3>
                <p className="mt-2 text-sm text-zinc-700">
                  Student answer: {answer.selectedOption ?? "Not answered"}
                </p>
                <p className="mt-1 text-sm text-zinc-700">
                  Correct answer: {answer.correctAnswer}
                </p>
                {answer.selectedOption !== null && (
                  <p className={`mt-2 text-sm font-medium ${answer.isCorrect ? "text-green-700" : "text-red-700"}`}>
                    {answer.isCorrect ? "Correct" : "Incorrect"}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </DashboardShell>
  );
}
