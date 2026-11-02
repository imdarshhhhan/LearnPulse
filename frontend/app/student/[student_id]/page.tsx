"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorBanner, LoadingState } from "@/app/components/DashboardShell";
import { formatDate } from "@/lib/format";
import {
  fetchAttemptRemediation,
  generateAdaptivePractice,
  submitAdaptivePractice,
  type RemediationData,
} from "@/services/assignmentsApi";

import { AssignedHomework } from "./components/AssignedHomework";
import { CommunitiesSection } from "./components/CommunitiesSection";
import { ConceptMastery } from "./components/ConceptMastery";
import { FoldersSection } from "./components/FoldersSection";
import { GroupsSection } from "./components/GroupsSection";
import { OverviewCards } from "./components/OverviewCards";
import { StudentHeader } from "./components/StudentHeader";
import { useStudentHome } from "./useStudentHome";

export default function StudentDashboardPage() {
  const params = useParams<{ student_id: string }>();
  const router = useRouter();
  const { data, error, loading, reload } = useStudentHome(params.student_id);

  // Clean tabs: 'homework' | 'mastery' | 'attempts' | 'spaces'
  const [activeTab, setActiveTab] = useState<"homework" | "mastery" | "attempts" | "spaces">("homework");

  // Evidence-based Remediation Modal
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);
  const [remediationData, setRemediationData] = useState<RemediationData | null>(null);
  const [remediationLoading, setRemediationLoading] = useState(false);

  // Adaptive Practice Modal
  const [practiceOpen, setPracticeOpen] = useState(false);
  const [practiceQuestions, setPracticeQuestions] = useState<any[]>([]);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [practiceAnswers, setPracticeAnswers] = useState<Record<number, string>>({});
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [practiceResult, setPracticeResult] = useState<any | null>(null);

  const viewRemediation = async (attemptId: number) => {
    setSelectedAttemptId(attemptId);
    setRemediationLoading(true);
    try {
      const res = await fetchAttemptRemediation(attemptId);
      setRemediationData(res.remediationData);
    } catch (err: any) {
      alert(err?.message || "Could not load remediation details.");
      setSelectedAttemptId(null);
    } finally {
      setRemediationLoading(false);
    }
  };

  const startAdaptivePractice = async () => {
    setPracticeOpen(true);
    setPracticeResult(null);
    setPracticeAnswers({});
    setCurrentQIndex(0);
    setPracticeLoading(true);
    try {
      const res = await generateAdaptivePractice(undefined, 5);
      setPracticeQuestions(res.questions || []);
    } catch (err: any) {
      alert(err?.message || "Could not generate adaptive practice.");
      setPracticeOpen(false);
    } finally {
      setPracticeLoading(false);
    }
  };

  const submitPractice = async () => {
    setPracticeLoading(true);
    try {
      const payload = Object.entries(practiceAnswers).map(([qid, sel]) => ({
        questionId: Number(qid),
        selectedOption: sel,
      }));
      const res = await submitAdaptivePractice(payload);
      setPracticeResult(res);
      reload();
    } catch (err: any) {
      alert(err?.message || "Could not submit practice quiz.");
    } finally {
      setPracticeLoading(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-[#fbfbfd]">
        <LoadingState />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center bg-[#fbfbfd] p-6 space-y-4">
        <ErrorBanner message={error || "Could not load your dashboard."} />
        <button
          type="button"
          className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          onClick={reload}
        >
          Try again
        </button>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[#fbfbfd] text-[#1d1d1f]">
      <StudentHeader user={data.dashboard.profile} />

      <main className="max-w-6xl mx-auto px-6 py-8 sm:px-10 sm:py-10 space-y-8">
        {/* ─── Apple Welcome Hero ─── */}
        <section className="apple-card p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 animate-pulse" />
              Student Learning Space
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-900">
              Welcome back, {data.dashboard.profile.fullName.split(" ")[0]}
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              Master concepts through personalized practice and source-grounded feedback.
            </p>
            <div className="mt-3 flex items-center gap-3 text-xs text-zinc-500">
              <span className="font-medium text-zinc-700">
                USN: {data.dashboard.profile.usn ?? "Not registered"}
              </span>
              {!data.dashboard.profile.usn && (
                <Link href="/settings" className="font-medium text-indigo-600 hover:underline">
                  Add USN in Settings
                </Link>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={startAdaptivePractice}
              className="rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white shadow-xs transition-all hover:bg-zinc-800 hover:shadow-md active:scale-[0.98]"
            >
              🎯 Start Adaptive Practice
            </button>
            <button
              type="button"
              onClick={() => {
                reload();
                router.refresh();
              }}
              className="rounded-full border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 shadow-2xs hover:bg-zinc-50 active:scale-[0.98]"
            >
              Refresh
            </button>
          </div>
        </section>

        {/* ─── Metric Overview Cards ─── */}
        <OverviewCards stats={data.dashboard.stats} />

        {/* ─── Segmented Navigation Tabs ─── */}
        <div className="flex border-b border-zinc-200/80 gap-6">
          <button
            type="button"
            onClick={() => setActiveTab("homework")}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "homework"
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-zinc-500 hover:text-zinc-800"
            }`}
          >
            Assigned Coursework ({data.dashboard.assignments.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("mastery")}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "mastery"
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-zinc-500 hover:text-zinc-800"
            }`}
          >
            Concept Mastery & Growth ({data.dashboard.mastery.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("attempts")}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "attempts"
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-zinc-500 hover:text-zinc-800"
            }`}
          >
            Recent Attempts & Feedback ({data.dashboard.recentAttempts.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("spaces")}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "spaces"
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-zinc-500 hover:text-zinc-800"
            }`}
          >
            Study Spaces & Folders
          </button>
        </div>

        {/* ─── Tab 1: Homework ─── */}
        {activeTab === "homework" && (
          <AssignedHomework
            studentId={data.dashboard.profile.userId}
            assignments={data.dashboard.assignments}
          />
        )}

        {/* ─── Tab 2: Concept Mastery ─── */}
        {activeTab === "mastery" && (
          <div className="space-y-4">
            <ConceptMastery mastery={data.dashboard.mastery} />
          </div>
        )}

        {/* ─── Tab 3: Recent Attempts & Evidence Feedback ─── */}
        {activeTab === "attempts" && (
          <section className="apple-card p-6 space-y-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-zinc-900">
                Recent Assessments & Remediation
              </h2>
              <p className="text-xs text-zinc-500 mt-0.5">
                Review question-level evidence citations, study recommendations, and weak concepts.
              </p>
            </div>

            {data.dashboard.recentAttempts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-200 p-8 text-center text-sm text-zinc-500">
                You have not completed any quizzes yet.
              </div>
            ) : (
              <div className="divide-y divide-zinc-100">
                {data.dashboard.recentAttempts.map((attempt) => (
                  <div key={attempt.id} className="py-4 flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <h3 className="font-semibold text-zinc-900 text-sm">{attempt.assignmentTitle}</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        Completed on {formatDate(attempt.attemptedAt)}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-bold text-zinc-900 bg-zinc-100 px-3 py-1 rounded-full">
                        Score: {attempt.scorePercent}%
                      </span>
                      <button
                        type="button"
                        onClick={() => viewRemediation(attempt.id)}
                        className="rounded-full bg-indigo-50 px-4 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors"
                      >
                        Evidence Remediation 📖
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ─── Tab 4: Study Spaces ─── */}
        {activeTab === "spaces" && (
          <div className="grid gap-6 md:grid-cols-3">
            <FoldersSection folders={data.folders} error={data.sectionErrors.folders} />
            <GroupsSection groups={data.groups} error={data.sectionErrors.groups} />
            <CommunitiesSection
              communities={data.communities}
              error={data.sectionErrors.communities}
            />
          </div>
        )}
      </main>

      {/* ─── Evidence-Based Remediation Modal (Feature 6) ─── */}
      {selectedAttemptId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-100">
              <div>
                <h3 className="text-lg font-semibold text-zinc-900">
                  Evidence-Based Feedback & Remediation
                </h3>
                <p className="text-xs text-zinc-500">
                  Grounded explanations and recommended study material sections.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedAttemptId(null);
                  setRemediationData(null);
                }}
                className="rounded-full h-8 w-8 flex items-center justify-center text-zinc-400 hover:text-zinc-700 bg-zinc-100"
              >
                ✕
              </button>
            </div>

            {remediationLoading ? (
              <LoadingState />
            ) : remediationData ? (
              <div className="mt-5 space-y-6">
                <div className="apple-card p-4 bg-indigo-50/40 border-indigo-100">
                  <p className="text-xs font-semibold text-indigo-700">Diagnostic Summary</p>
                  <p className="text-sm font-medium text-zinc-800 mt-1">{remediationData.summary}</p>
                </div>

                {/* Concepts needing revision */}
                {remediationData.conceptsNeedingRevision.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-rose-700">⚠️ Concepts Requiring Revision:</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {remediationData.conceptsNeedingRevision.map((c, i) => (
                        <div key={i} className="rounded-xl border border-rose-200 bg-rose-50/50 p-3 text-xs">
                          <p className="font-semibold text-rose-900">{c.concept}</p>
                          <p className="text-rose-700 mt-0.5">
                            Accuracy: {c.accuracyPercent}% ({c.mistakesCount} mistakes out of {c.totalConceptQuestions})
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Study Recommendations */}
                {remediationData.studyRecommendations.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs font-semibold text-zinc-800">📚 Recommended Study Material Sections:</p>
                    <div className="space-y-2">
                      {remediationData.studyRecommendations.map((rec, i) => (
                        <div key={i} className="rounded-2xl border border-zinc-200/80 p-4 bg-zinc-50/50 text-xs space-y-1.5">
                          <p className="font-semibold text-indigo-900">{rec.recommendedSection}</p>
                          <p className="text-zinc-600 italic">"{rec.actionGuidance}"</p>
                          {rec.keyExcerptsToReview.map((quote, qIdx) => (
                            <blockquote key={qIdx} className="border-l-2 border-indigo-400 pl-2 text-zinc-500">
                              "{quote}"
                            </blockquote>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Question-by-Question Breakdown */}
                <div className="space-y-3">
                  <p className="text-xs font-semibold text-zinc-800">Question-Level Grounded Verification:</p>
                  <div className="space-y-2">
                    {remediationData.questionBreakdown.map((q, idx) => (
                      <div
                        key={idx}
                        className={`rounded-2xl p-4 text-xs border ${
                          q.isCorrect
                            ? "bg-emerald-50/40 border-emerald-200/70"
                            : "bg-rose-50/40 border-rose-200/70"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-zinc-800">Question {idx + 1} · {q.conceptTag}</span>
                          <span className={`font-semibold ${q.isCorrect ? "text-emerald-700" : "text-rose-700"}`}>
                            {q.isCorrect ? "✓ Correct" : "✗ Incorrect"}
                          </span>
                        </div>
                        <p className="text-zinc-900 font-medium mt-1">{q.questionText}</p>
                        <div className="mt-2 space-y-1 text-zinc-600">
                          <p>Your choice: <span className="font-semibold">{q.selectedOption || "None"}</span></p>
                          {!q.isCorrect && (
                            <p>Correct answer: <span className="font-semibold text-emerald-800">{q.correctAnswer}</span></p>
                          )}
                          <p className="text-indigo-900 font-medium mt-1">Grounded Rationale: {q.explanation}</p>
                          {q.sourceQuote && (
                            <p className="text-zinc-400 italic">Evidence Citation (Page {q.sourcePage}): "{q.sourceQuote}"</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* ─── Adaptive Practice Quiz Modal (Feature 4) ─── */}
      {practiceOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-100">
              <div>
                <h3 className="text-lg font-semibold text-zinc-900">Adaptive Practice Session</h3>
                <p className="text-xs text-zinc-500">
                  Targeted questions dynamically adapted to your weak concepts.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPracticeOpen(false)}
                className="rounded-full h-8 w-8 flex items-center justify-center text-zinc-400 hover:text-zinc-700 bg-zinc-100"
              >
                ✕
              </button>
            </div>

            {practiceLoading ? (
              <LoadingState />
            ) : practiceResult ? (
              <div className="mt-5 space-y-5">
                <div className="apple-card p-6 text-center space-y-2 bg-indigo-50/50">
                  <p className="text-xs font-semibold text-indigo-700">Practice Session Completed!</p>
                  <p className="text-4xl font-bold text-zinc-900">{practiceResult.scorePercent}%</p>
                  <p className="text-xs text-zinc-500">
                    You scored {practiceResult.score} of {practiceResult.totalQuestions} questions correctly.
                  </p>
                </div>

                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => {
                      setPracticeOpen(false);
                      setPracticeResult(null);
                      reload();
                    }}
                    className="rounded-full bg-zinc-900 px-6 py-2.5 text-xs font-medium text-white hover:bg-zinc-800"
                  >
                    Done & Return to Dashboard
                  </button>
                </div>
              </div>
            ) : practiceQuestions.length > 0 ? (
              <div className="mt-5 space-y-5">
                <div className="flex items-center justify-between text-xs text-zinc-500">
                  <span>Question {currentQIndex + 1} of {practiceQuestions.length}</span>
                  <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-indigo-700 font-medium">
                    {practiceQuestions[currentQIndex]?.conceptTag} · {practiceQuestions[currentQIndex]?.difficulty}
                  </span>
                </div>

                <div className="rounded-2xl border border-zinc-200/80 p-5 bg-zinc-50/30">
                  <p className="text-sm font-semibold text-zinc-900">
                    {practiceQuestions[currentQIndex]?.questionText}
                  </p>

                  <div className="mt-4 space-y-2">
                    {practiceQuestions[currentQIndex]?.optionsMatrix?.map((opt: string, optIdx: number) => {
                      const qId = practiceQuestions[currentQIndex].questionId;
                      const isSelected = practiceAnswers[qId] === opt;
                      return (
                        <button
                          key={optIdx}
                          type="button"
                          onClick={() => {
                            setPracticeAnswers((prev) => ({ ...prev, [qId]: opt }));
                          }}
                          className={`w-full text-left p-3.5 rounded-xl text-xs font-medium border transition-all ${
                            isSelected
                              ? "bg-indigo-50 border-indigo-600 text-indigo-950 font-semibold"
                              : "bg-white border-zinc-200/80 text-zinc-800 hover:bg-zinc-50"
                          }`}
                        >
                          {opt}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    disabled={currentQIndex === 0}
                    onClick={() => setCurrentQIndex((i) => Math.max(0, i - 1))}
                    className="rounded-full border border-zinc-200 px-4 py-2 text-xs font-medium text-zinc-700 disabled:opacity-40"
                  >
                    ← Previous
                  </button>

                  {currentQIndex < practiceQuestions.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => setCurrentQIndex((i) => Math.min(practiceQuestions.length - 1, i + 1))}
                      className="rounded-full bg-zinc-900 px-5 py-2 text-xs font-medium text-white hover:bg-zinc-800"
                    >
                      Next →
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={submitPractice}
                      className="rounded-full bg-emerald-600 px-6 py-2 text-xs font-medium text-white hover:bg-emerald-500 shadow-sm"
                    >
                      Submit Practice Answers ✓
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
