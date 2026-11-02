"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/services/dashboardApi";
import {
  fetchStudentAssignment,
  saveStudentAssignmentProgress,
  submitStudentAssignment,
  type AssignmentResult,
  type StudentAssignment,
} from "@/services/assignmentsApi";

import { AssignmentFeedbackForm } from "./AssignmentFeedbackForm";

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load this assignment.";
}

function formatRemainingTime(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
}

export default function StudentAssignmentPage() {
  const params = useParams<{ assignment_id: string }>();
  const router = useRouter();
  const assignmentId = Number(params.assignment_id);
  const validAssignmentId = Number.isSafeInteger(assignmentId) && assignmentId > 0;

  const [assignment, setAssignment] = useState<StudentAssignment | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<AssignmentResult | null>(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [autosaving, setAutosaving] = useState(false);
  const [error, setError] = useState("");
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  useEffect(() => {
    if (!validAssignmentId) return;

    let active = true;
    fetchStudentAssignment(assignmentId)
      .then((data) => {
        if (active) {
          setAssignment(data);
          setResult(data.submittedResult);
          setAnswers(
            Object.fromEntries(
              Object.entries(data.progressAnswers).map(([id, option]) => [Number(id), option]),
            ),
          );
          if (data.remainingSeconds !== null && data.remainingSeconds !== undefined) {
            setSecondsLeft(data.remainingSeconds);
          }
        }
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        if (loadError instanceof ApiError && loadError.status === 401) {
          router.replace("/auth");
          return;
        }
        if (loadError instanceof ApiError && loadError.status === 403) {
          router.replace("/teacher");
          return;
        }
        setError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [assignmentId, router, validAssignmentId]);

  useEffect(() => {
    if (secondsLeft === null || secondsLeft <= 0 || result !== null) return;
    const interval = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [secondsLeft, result]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assignment || Object.keys(answers).length !== assignment.questions.length) {
      setError("Please answer every question before submitting.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const submission = assignment.questions.map((question) => ({
        questionId: question.id,
        selectedOption: answers[question.id],
      }));
      const currentSubmissionId = submissionId ?? crypto.randomUUID();
      setSubmissionId(currentSubmissionId);
      const submitRes = await submitStudentAssignment(
        assignment.id,
        submission,
        currentSubmissionId,
      );
      setResult(submitRes);
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.status === 401) {
        router.replace("/auth");
        return;
      }
      if (submitError instanceof ApiError && submitError.status === 403) {
        router.replace("/teacher");
        return;
      }
      setError(getErrorMessage(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAnswerChange(questionId: number, selectedOption: string) {
    if (secondsLeft === 0) return;
    const updatedAnswers = { ...answers, [questionId]: selectedOption };
    setAnswers(updatedAnswers);
    setSubmissionId(null);
    setError("");
    setAutosaving(true);
    try {
      await saveStudentAssignmentProgress(
        assignmentId,
        Object.entries(updatedAnswers).map(([id, option]) => ({
          questionId: Number(id),
          selectedOption: option,
        })),
      );
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 401) {
        router.replace("/auth");
        return;
      }
      if (saveError instanceof ApiError && saveError.status === 403) {
        router.replace("/teacher");
        return;
      }
      setError(getErrorMessage(saveError));
    } finally {
      setAutosaving(false);
    }
  }

  if (!validAssignmentId) {
    return (
      <main className="min-h-screen bg-[#fbfbfd] px-4 py-12 text-zinc-900">
        <div className="mx-auto max-w-2xl rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
          <p className="text-sm font-semibold text-rose-600">This assignment link is not valid.</p>
          <Link href="/" className="mt-4 inline-block text-sm font-medium text-zinc-900 underline">
            Back to dashboard
          </Link>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-[#fbfbfd] px-4 py-12 text-zinc-900">
        <div className="mx-auto max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200/80 bg-white px-4 py-2 text-sm text-zinc-600 shadow-sm">
            <span className="h-2 w-2 animate-ping rounded-full bg-zinc-900" />
            Loading assessment details…
          </div>
        </div>
      </main>
    );
  }

  if (error && !assignment) {
    return (
      <main className="min-h-screen bg-[#fbfbfd] px-4 py-12 text-zinc-900">
        <div className="mx-auto max-w-2xl rounded-2xl border border-rose-200 bg-rose-50/50 p-8 text-center shadow-sm">
          <p className="text-sm font-semibold text-rose-700">{error}</p>
          <Link href="/" className="mt-4 inline-block text-sm font-medium text-zinc-900 underline">
            Back to dashboard
          </Link>
        </div>
      </main>
    );
  }

  if (!assignment) return null;

  const isTimeUp = secondsLeft === 0;
  const canAttempt = assignment.canSubmit && !isTimeUp;

  return (
    <main className="min-h-screen bg-[#fbfbfd] px-4 py-8 text-zinc-900 antialiased sm:py-12">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200/80 pb-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-600 transition-colors hover:text-zinc-900"
          >
            ← Back to dashboard
          </Link>

          <div className="flex flex-wrap items-center gap-2">
            {secondsLeft !== null && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                  secondsLeft < 180
                    ? "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
                    : "bg-zinc-100 text-zinc-700"
                }`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {secondsLeft === 0 ? "Time's up" : `${formatRemainingTime(secondsLeft)} remaining`}
              </span>
            )}

            <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
              Attempt {(assignment.attemptsUsed ?? 0) + 1} of {assignment.maxAttempts ?? 1}
            </span>

            {autosaving && (
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                Autosaving…
              </span>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-200/80 bg-white p-6 shadow-sm sm:p-8">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            {assignment.activityType === "quiz" ? "Assessment Quiz" : "Homework Exercise"}
          </span>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-zinc-950 sm:text-3xl">
            {assignment.title}
          </h1>
          <p className="mt-1 text-sm text-zinc-600">
            {assignment.materialTitle} · Assigned by {assignment.teacherName}
            {assignment.dueDate ? ` · Due ${new Date(assignment.dueDate).toLocaleDateString()}` : ""}
          </p>
          {assignment.description && (
            <p className="mt-3 rounded-xl border border-zinc-100 bg-zinc-50/70 p-3.5 text-sm text-zinc-600">
              {assignment.description}
            </p>
          )}
        </div>

        {!assignment.canSubmit && !result && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5 text-sm text-amber-900 shadow-sm">
            {assignment.unavailableReason === "not_yet_available" &&
              "This homework is not available yet."}
            {assignment.unavailableReason === "due_date_passed" &&
              "The due date for this homework has passed. Your saved work can still be reviewed."}
            {assignment.unavailableReason === "max_attempts_reached" &&
              "You have reached the maximum allowed attempts for this assessment."}
          </div>
        )}

        {result ? (
          <div className="space-y-6">
            <div className="rounded-2xl border border-zinc-200/80 bg-white p-6 shadow-sm sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-100 pb-5">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600">
                    Submission Completed
                  </span>
                  <div className="mt-1 flex items-baseline gap-3">
                    <span className="text-4xl font-extrabold tracking-tight text-zinc-950 sm:text-5xl">
                      {result.scorePercent}%
                    </span>
                    <span className="text-sm font-medium text-zinc-500">
                      ({result.correctAnswers} of {result.totalQuestions} questions correct)
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {(assignment.attemptsRemaining ?? 0) > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        setAnswers({});
                        setSubmissionId(null);
                        setResult(null);
                      }}
                      className="rounded-xl border border-zinc-300 bg-white px-4 py-2 text-xs font-semibold text-zinc-800 shadow-sm transition-colors hover:bg-zinc-50"
                    >
                      Try again ({assignment.attemptsRemaining} remaining)
                    </button>
                  )}
                  <Link
                    href="/"
                    className="rounded-xl bg-zinc-900 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-zinc-800"
                  >
                    View dashboard
                  </Link>
                </div>
              </div>

              {result.remediationData && (
                <div className="mt-6 space-y-6">
                  {result.remediationData.summary && (
                    <p className="rounded-xl border border-zinc-100 bg-zinc-50/70 p-4 text-sm text-zinc-700">
                      {result.remediationData.summary}
                    </p>
                  )}

                  {result.remediationData.conceptsNeedingRevision?.length > 0 && (
                    <div className="space-y-3">
                      <h2 className="text-sm font-semibold tracking-wide text-zinc-900">
                        Concepts needing review &amp; study recommendations
                      </h2>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {result.remediationData.conceptsNeedingRevision.map((concept, cIdx) => {
                          const studyRec = result.remediationData?.studyRecommendations?.find(
                            (r) => r.concept === concept.concept,
                          );
                          return (
                            <div
                              key={cIdx}
                              className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-4 text-xs text-amber-950 space-y-2"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-amber-950">{concept.concept}</span>
                                <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">
                                  {concept.accuracyPercent}% accuracy
                                </span>
                              </div>
                              <p className="text-amber-800">
                                {concept.mistakesCount} incorrect response
                                {concept.mistakesCount > 1 ? "s" : ""} out of{" "}
                                {concept.totalConceptQuestions} questions.
                              </p>
                              {studyRec && (
                                <div className="border-t border-amber-200/60 pt-2 text-amber-900">
                                  <div className="font-semibold">
                                    Recommended study: {studyRec.recommendedSection}
                                  </div>
                                  <p className="mt-0.5 text-amber-800">{studyRec.actionGuidance}</p>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {result.remediationData.questionBreakdown?.length > 0 && (
                    <div className="space-y-4">
                      <h2 className="text-sm font-semibold tracking-wide text-zinc-900">
                        Detailed question analysis &amp; source citations
                      </h2>
                      <div className="space-y-3">
                        {result.remediationData.questionBreakdown.map((item, qIdx) => (
                          <div
                            key={qIdx}
                            className={`rounded-xl border p-4 space-y-3 text-sm transition-all ${
                              item.isCorrect
                                ? "border-emerald-200 bg-emerald-50/30"
                                : "border-rose-200 bg-rose-50/30"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200/60 pb-2 text-xs">
                              <span className="font-semibold text-zinc-900">
                                Question {qIdx + 1} · {item.conceptTag}
                                {item.cognitiveLevel ? ` (${item.cognitiveLevel})` : ""}
                              </span>
                              <div className="flex items-center gap-2">
                                {typeof item.sourcePage === "number" && (
                                  <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 font-medium text-zinc-600">
                                    Page {item.sourcePage}
                                  </span>
                                )}
                                <span
                                  className={`rounded-full px-2 py-0.5 font-semibold ${
                                    item.isCorrect
                                      ? "bg-emerald-100 text-emerald-800"
                                      : "bg-rose-100 text-rose-800"
                                  }`}
                                >
                                  {item.isCorrect ? "Correct ✓" : "Incorrect ✗"}
                                </span>
                              </div>
                            </div>

                            <p className="font-medium text-zinc-900">{item.questionText}</p>

                            <div className="grid gap-2 text-xs sm:grid-cols-2">
                              <div className="rounded-lg border border-zinc-200/80 bg-white p-2.5">
                                <span className="font-medium text-zinc-500">Your selection: </span>
                                <span
                                  className={`font-semibold ${
                                    item.isCorrect ? "text-emerald-700" : "text-rose-700"
                                  }`}
                                >
                                  {item.selectedOption || "No answer recorded"}
                                </span>
                              </div>
                              <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-2.5">
                                <span className="font-medium text-emerald-800">Correct key: </span>
                                <span className="font-semibold text-emerald-900">
                                  {item.correctAnswer}
                                </span>
                              </div>
                            </div>

                            {item.explanation && (
                              <div className="rounded-lg border border-zinc-200/70 bg-white/80 p-3 text-xs text-zinc-700">
                                <span className="font-semibold text-zinc-900">Explanation: </span>
                                {item.explanation}
                              </div>
                            )}

                            {item.sourceQuote && (
                              <div className="rounded-lg border border-zinc-200/60 bg-zinc-50 p-3 text-xs text-zinc-600">
                                <span className="font-semibold text-zinc-800">Source passage citation: </span>
                                <span className="italic">“{item.sourceQuote}”</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <AssignmentFeedbackForm assignmentId={assignment.id} />
          </div>
        ) : assignment.questions.length === 0 ? (
          <div className="rounded-2xl border border-zinc-200/80 bg-white p-8 text-center shadow-sm">
            <p className="text-sm text-zinc-500">
              This assignment does not have any approved questions yet. Please check with your teacher.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="rounded-2xl border border-zinc-200/80 bg-white p-4 shadow-sm text-xs text-zinc-600 flex items-center justify-between">
              <span>
                Answer all {assignment.questions.length} questions. Progress is saved automatically.
              </span>
              <span>
                {Object.keys(answers).length} of {assignment.questions.length} completed
              </span>
            </div>

            {assignment.questions.map((question, index) => (
              <div
                key={question.id}
                className="rounded-2xl border border-zinc-200/90 bg-white p-6 shadow-sm transition-all hover:border-zinc-300 sm:p-7 space-y-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 pb-3">
                  <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">
                    Question {index + 1} of {assignment.questions.length}
                  </span>
                  <div className="flex items-center gap-2">
                    {question.cognitiveLevel && (
                      <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-700">
                        {question.cognitiveLevel}
                      </span>
                    )}
                    {question.subtopic && (
                      <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs text-zinc-600">
                        {question.subtopic}
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-base font-semibold leading-relaxed text-zinc-900 sm:text-lg">
                  {question.questionText}
                </p>

                <div className="space-y-2 pt-2">
                  {question.options.map((option, optIdx) => {
                    const isSelected = answers[question.id] === option;
                    return (
                      <label
                        key={optIdx}
                        className={`flex cursor-pointer items-center gap-3.5 rounded-xl border p-3.5 text-sm transition-all ${
                          isSelected
                            ? "border-zinc-900 bg-zinc-900 text-white shadow-sm ring-1 ring-zinc-900"
                            : "border-zinc-200 bg-white text-zinc-800 hover:border-zinc-300 hover:bg-zinc-50/70"
                        } ${!canAttempt ? "cursor-not-allowed opacity-60" : ""}`}
                      >
                        <input
                          type="radio"
                          name={`question-${question.id}`}
                          value={option}
                          checked={isSelected}
                          disabled={submitting || !canAttempt}
                          onChange={() => void handleAnswerChange(question.id, option)}
                          className="h-4 w-4 accent-zinc-900"
                        />
                        <span className="flex-1 font-medium">{option}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}

            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-700">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="submit"
                disabled={
                  submitting ||
                  !canAttempt ||
                  Object.keys(answers).length !== assignment.questions.length
                }
                className="rounded-xl bg-zinc-900 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Submitting assessment…" : "Submit assignment"}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
