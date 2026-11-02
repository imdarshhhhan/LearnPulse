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

  const [activeTab, setActiveTab] = useState<"homework" | "mastery" | "attempts" | "spaces">("homework");

  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);
  const [remediationData, setRemediationData] = useState<RemediationData | null>(null);
  const [remediationLoading, setRemediationLoading] = useState(false);

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
      <main className="min-h-screen flex items-center justify-center bg-[#f8fafc]">
        <LoadingState />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center bg-[#f8fafc] p-6 space-y-4">
        <ErrorBanner message={error || "Could not load your dashboard."} />
        <button
          type="button"
          className="rounded-xl bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
          onClick={reload}
        >
          Try again
        </button>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      <StudentHeader user={data.dashboard.profile} />

      <main className="max-w-[1520px] mx-auto px-4 sm:px-8 lg:px-12 py-8 space-y-8">
        <section className="saas-card p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3.5 py-1 text-xs font-semibold text-blue-700">
              <span className="h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
              Student Learning Space
            </div>
            <h1 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Welcome back, {data.dashboard.profile.fullName.split(" ")[0]}
            </h1>
            <p className="mt-1 text-base text-slate-500">
              Master concepts through personalized practice and source-grounded feedback.
            </p>
            <div className="mt-3 flex items-center gap-3 text-sm text-slate-500">
              <span className="font-medium text-slate-700">
                USN: {data.dashboard.profile.usn ?? "Not registered"}
              </span>
              {!data.dashboard.profile.usn && (
                <Link href="/settings" className="font-semibold text-blue-600 hover:underline">
                  Add USN in Settings
                </Link>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={startAdaptivePractice}
              className="rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98]"
            >
              🎯 Start Adaptive Practice
            </button>
            <button
              type="button"
              onClick={() => {
                reload();
                router.refresh();
              }}
              className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-xs hover:bg-slate-50 active:scale-[0.98]"
            >
              Refresh
            </button>
          </div>
        </section>

        <OverviewCards stats={data.dashboard.stats} />

        <div className="flex border-b border-slate-200 gap-8 overflow-x-auto">
          <button
            type="button"
            onClick={() => setActiveTab("homework")}
            className={`pb-3.5 text-base font-semibold transition-colors border-b-2 whitespace-nowrap ${
              activeTab === "homework"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            Assigned Coursework ({data.dashboard.assignments.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("mastery")}
            className={`pb-3.5 text-base font-semibold transition-colors border-b-2 whitespace-nowrap ${
              activeTab === "mastery"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            Concept Mastery & Growth ({data.dashboard.mastery.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("attempts")}
            className={`pb-3.5 text-base font-semibold transition-colors border-b-2 whitespace-nowrap ${
              activeTab === "attempts"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            Recent Attempts & Feedback ({data.dashboard.recentAttempts.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("spaces")}
            className={`pb-3.5 text-base font-semibold transition-colors border-b-2 whitespace-nowrap ${
              activeTab === "spaces"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            Study Spaces & Folders
          </button>
        </div>

        {activeTab === "homework" && (
          <AssignedHomework
            studentId={data.dashboard.profile.userId}
            assignments={data.dashboard.assignments}
          />
        )}

        {activeTab === "mastery" && (
          <div className="space-y-4">
            <ConceptMastery mastery={data.dashboard.mastery} />
          </div>
        )}

        {activeTab === "attempts" && (
          <section className="saas-card p-6 sm:p-8 space-y-5">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-slate-900">
                Recent Assessments & Remediation
              </h2>
              <p className="text-sm text-slate-500 mt-1">
                Review question-level evidence citations, study recommendations, and weak concepts.
              </p>
            </div>

            {data.dashboard.recentAttempts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500">
                You have not completed any quizzes yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {data.dashboard.recentAttempts.map((attempt) => (
                  <div key={attempt.id} className="py-4 sm:py-5 flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <h3 className="font-semibold text-slate-900 text-base">{attempt.assignmentTitle}</h3>
                      <p className="text-xs text-slate-500 mt-1">
                        Completed on {formatDate(attempt.attemptedAt)}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-bold text-slate-900 bg-slate-100 px-3.5 py-1.5 rounded-xl">
                        Score: {attempt.scorePercent}%
                      </span>
                      <button
                        type="button"
                        onClick={() => viewRemediation(attempt.id)}
                        className="rounded-xl bg-blue-50 px-4 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100 transition-colors"
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

      {selectedAttemptId && (
        <div className="popup-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="popup-panel w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded-3xl bg-white p-6 sm:p-8 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-xl font-bold text-slate-900">
                  Evidence-Based Feedback & Remediation
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Grounded explanations and recommended study material sections.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedAttemptId(null);
                  setRemediationData(null);
                }}
                className="rounded-full h-8 w-8 flex items-center justify-center text-slate-400 hover:text-slate-700 bg-slate-100"
              >
                ✕
              </button>
            </div>

            {remediationLoading ? (
              <LoadingState />
            ) : remediationData ? (
              <div className="mt-6 space-y-6">
                <div className="saas-card p-5 bg-blue-50/50 border-blue-100">
                  <p className="text-xs font-bold text-blue-700 uppercase tracking-wide">Diagnostic Summary</p>
                  <p className="text-sm font-medium text-slate-800 mt-1.5">{remediationData.summary}</p>
                </div>

                {remediationData.conceptsNeedingRevision.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs font-bold text-rose-700 uppercase tracking-wide">⚠️ Concepts Requiring Revision:</p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {remediationData.conceptsNeedingRevision.map((c, i) => (
                        <div key={i} className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 text-xs">
                          <p className="font-bold text-rose-900 text-sm">{c.concept}</p>
                          <p className="text-rose-700 mt-1">
                            Accuracy: {c.accuracyPercent}% ({c.mistakesCount} mistakes out of {c.totalConceptQuestions})
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {remediationData.studyRecommendations.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs font-bold text-slate-800 uppercase tracking-wide">📚 Recommended Study Material Sections:</p>
                    <div className="space-y-3">
                      {remediationData.studyRecommendations.map((rec, i) => (
                        <div key={i} className="rounded-2xl border border-slate-200 p-4 sm:p-5 bg-slate-50/50 text-xs space-y-2">
                          <p className="font-bold text-blue-900 text-sm">{rec.recommendedSection}</p>
                          <p className="text-slate-700 italic">"{rec.actionGuidance}"</p>
                          {rec.keyExcerptsToReview.map((quote, qIdx) => (
                            <blockquote key={qIdx} className="border-l-2 border-blue-500 pl-3 text-slate-600">
                              "{quote}"
                            </blockquote>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <p className="text-xs font-bold text-slate-800 uppercase tracking-wide">Question-Level Grounded Verification:</p>
                  <div className="space-y-3">
                    {remediationData.questionBreakdown.map((q, idx) => (
                      <div
                        key={idx}
                        className={`rounded-2xl p-4 sm:p-5 text-xs border ${
                          q.isCorrect
                            ? "bg-emerald-50/40 border-emerald-200/70"
                            : "bg-rose-50/40 border-rose-200/70"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">Question {idx + 1} · {q.conceptTag}</span>
                          <span className={`font-bold ${q.isCorrect ? "text-emerald-700" : "text-rose-700"}`}>
                            {q.isCorrect ? "✓ Correct" : "✗ Incorrect"}
                          </span>
                        </div>
                        <p className="text-slate-900 font-semibold text-sm mt-1.5">{q.questionText}</p>
                        <div className="mt-3 space-y-1.5 text-slate-700">
                          <p>Your choice: <span className="font-semibold text-slate-900">{q.selectedOption || "None"}</span></p>
                          {!q.isCorrect && (
                            <p>Correct answer: <span className="font-semibold text-emerald-800">{q.correctAnswer}</span></p>
                          )}
                          <p className="text-blue-900 font-medium mt-1">Grounded Rationale: {q.explanation}</p>
                          {q.sourceQuote && (
                            <p className="text-slate-500 italic">Evidence Citation (Page {q.sourcePage}): "{q.sourceQuote}"</p>
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

      {practiceOpen && (
        <div className="popup-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="popup-panel w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-3xl bg-white p-6 sm:p-8 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-xl font-bold text-slate-900">Adaptive Practice Session</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Targeted questions dynamically adapted to your weak concepts.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPracticeOpen(false)}
                className="rounded-full h-8 w-8 flex items-center justify-center text-slate-400 hover:text-slate-700 bg-slate-100"
              >
                ✕
              </button>
            </div>

            {practiceLoading ? (
              <LoadingState />
            ) : practiceResult ? (
              <div className="mt-6 space-y-6">
                <div className="saas-card p-6 text-center space-y-2 bg-blue-50/50 border-blue-100">
                  <p className="text-xs font-bold text-blue-700 uppercase tracking-wide">Practice Session Completed!</p>
                  <p className="text-4xl sm:text-5xl font-extrabold text-slate-900">{practiceResult.scorePercent}%</p>
                  <p className="text-sm text-slate-500">
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
                    className="rounded-xl bg-blue-600 px-8 py-3 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
                  >
                    Done & Return to Dashboard
                  </button>
                </div>
              </div>
            ) : practiceQuestions.length > 0 ? (
              <div className="mt-6 space-y-6">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="font-medium">Question {currentQIndex + 1} of {practiceQuestions.length}</span>
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700 font-semibold">
                    {practiceQuestions[currentQIndex]?.conceptTag} · {practiceQuestions[currentQIndex]?.difficulty}
                  </span>
                </div>

                <div className="rounded-2xl border border-slate-200 p-5 sm:p-6 bg-slate-50/40">
                  <p className="text-base font-semibold text-slate-900">
                    {practiceQuestions[currentQIndex]?.questionText}
                  </p>

                  <div className="mt-4 space-y-2.5">
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
                          className={`w-full text-left p-4 rounded-xl text-sm font-medium border transition-all ${
                            isSelected
                              ? "bg-blue-50 border-blue-600 text-blue-950 font-semibold shadow-xs"
                              : "bg-white border-slate-200 text-slate-800 hover:bg-slate-50"
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
                    className="rounded-xl border border-slate-200 px-5 py-2.5 text-xs font-semibold text-slate-700 disabled:opacity-40 hover:bg-slate-50"
                  >
                    ← Previous
                  </button>

                  {currentQIndex < practiceQuestions.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => setCurrentQIndex((i) => Math.min(practiceQuestions.length - 1, i + 1))}
                      className="rounded-xl bg-slate-900 px-6 py-2.5 text-xs font-semibold text-white hover:bg-slate-800"
                    >
                      Next →
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={submitPractice}
                      className="rounded-xl bg-blue-600 px-6 py-2.5 text-xs font-semibold text-white hover:bg-blue-700 shadow-sm"
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
