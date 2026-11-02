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
  StatCard,
} from "@/app/components/DashboardShell";
import {
  ApiError,
  fetchTeacherDashboard,
  type TeacherDashboardData,
} from "@/services/dashboardApi";
import {
  fetchMaterialItemAnalysis,
  fetchTeacherAuditLogs,
} from "@/services/assignmentsApi";
import { AssignActivityDialog } from "./AssignActivityDialog";

export default function TeacherDashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<TeacherDashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [assignActivityOpen, setAssignActivityOpen] = useState(false);

  // Tabs: 'materials' | 'assignments' | 'audit'
  const [activeTab, setActiveTab] = useState<"materials" | "assignments" | "audit">("materials");

  // Item Psychometrics Modal state
  const [analysisMaterialId, setAnalysisMaterialId] = useState<number | null>(null);
  const [itemAnalysis, setItemAnalysis] = useState<any | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const loadDashboard = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await fetchTeacherDashboard());
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/auth");
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "Could not load the dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    fetchTeacherDashboard()
      .then((dashboard) => {
        if (active) setData(dashboard);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Could not load the dashboard.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  const openItemAnalysis = async (materialId: number) => {
    setAnalysisMaterialId(materialId);
    setAnalysisLoading(true);
    try {
      const res = await fetchMaterialItemAnalysis(materialId);
      setItemAnalysis(res);
    } catch (err: any) {
      alert(err?.message || "Could not load item analysis.");
      setAnalysisMaterialId(null);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const loadAuditLogs = async () => {
    setActiveTab("audit");
    setLogsLoading(true);
    try {
      const res = await fetchTeacherAuditLogs(40);
      setAuditLogs(res.logs || []);
    } catch {
      // Handled silently
    } finally {
      setLogsLoading(false);
    }
  };

  return (
    <DashboardShell title="Faculty Workspace" user={data?.profile ?? null}>
      {/* ─── Apple Header Section ─── */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-2">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50/80 px-3 py-1 text-xs font-semibold text-indigo-700">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 animate-pulse" />
            Teacher Operations Hub
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-900">
            Create and manage adaptive assessments
          </h1>
          <p className="mt-1 text-sm text-zinc-500 max-w-2xl">
            Upload study materials, generate source-grounded questions, examine distractor psychometrics, and assign work to classes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setAssignActivityOpen(true)}
            className="rounded-full border border-zinc-200/90 bg-white px-5 py-2.5 text-sm font-medium text-zinc-800 shadow-2xs transition-all hover:bg-zinc-50 hover:shadow-xs active:scale-[0.98]"
          >
            Assign Activity
          </button>
          <Link
            href="/teacher/create-test"
            className="rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white shadow-xs transition-all hover:bg-zinc-800 hover:shadow-md active:scale-[0.98]"
          >
            + Create Quiz and Post
          </Link>
        </div>
      </section>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <div className="space-y-4">
          <ErrorBanner message={error} />
          <button
            type="button"
            onClick={() => void loadDashboard()}
            className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Try again
          </button>
        </div>
      ) : data ? (
        <>
          {/* ─── Metric Cards ─── */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Study Materials" value={data.stats.materials} sublabel="Uploaded guides & texts" />
            <StatCard label="Active Assignments" value={data.stats.assignments} sublabel="Assigned across classes" />
            <StatCard label="Questions Bank" value={data.stats.questionsInBank} sublabel="Source-vetted items" />
            <StatCard label="Student Submissions" value={data.stats.submissions} sublabel="Total graded attempts" />
          </section>

          {/* ─── Clean Action Hub (Uncluttered replacement of buttons) ─── */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Link
              href="/teacher/classes"
              className="apple-card p-5 group flex flex-col justify-between hover:border-indigo-300 transition-colors"
            >
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 font-semibold mb-3">
                  👥
                </div>
                <h3 className="font-semibold text-zinc-900 text-sm group-hover:text-indigo-600 transition-colors">
                  Class Management
                </h3>
                <p className="mt-1 text-xs text-zinc-500">
                  Organize rosters, enroll students, and manage USNs.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-indigo-600">Open classes →</span>
            </Link>

            <Link
              href="/teacher/performance"
              className="apple-card p-5 group flex flex-col justify-between hover:border-indigo-300 transition-colors"
            >
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 font-semibold mb-3">
                  📊
                </div>
                <h3 className="font-semibold text-zinc-900 text-sm group-hover:text-emerald-600 transition-colors">
                  Class Performance & Heatmap
                </h3>
                <p className="mt-1 text-xs text-zinc-500">
                  Concept mastery heatmaps and student learning trends.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-emerald-600">View analytics →</span>
            </Link>

            <Link
              href="/teacher/submissions"
              className="apple-card p-5 group flex flex-col justify-between hover:border-indigo-300 transition-colors"
            >
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-700 font-semibold mb-3">
                  📝
                </div>
                <h3 className="font-semibold text-zinc-900 text-sm group-hover:text-violet-600 transition-colors">
                  Student Submissions
                </h3>
                <p className="mt-1 text-xs text-zinc-500">
                  Answer reviews, score distribution, and audit trails.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-violet-600">Review submissions →</span>
            </Link>

            <Link
              href="/teacher/feedback"
              className="apple-card p-5 group flex flex-col justify-between hover:border-indigo-300 transition-colors"
            >
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700 font-semibold mb-3">
                  💬
                </div>
                <h3 className="font-semibold text-zinc-900 text-sm group-hover:text-amber-600 transition-colors">
                  Student Feedback
                </h3>
                <p className="mt-1 text-xs text-zinc-500">
                  Student clarity ratings and qualitative question notes.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-amber-600">View feedback →</span>
            </Link>
          </section>

          {/* ─── Segmented Navigation Controls ─── */}
          <div className="flex border-b border-zinc-200/80 gap-6">
            <button
              type="button"
              onClick={() => setActiveTab("materials")}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === "materials"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Study Materials & Question Banks ({data.materials.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("assignments")}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === "assignments"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Recent Assignments ({data.assignments.length})
            </button>
            <button
              type="button"
              onClick={loadAuditLogs}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === "audit"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Teacher Action Audit Log
            </button>
          </div>

          {/* ─── Tab Content 1: Materials ─── */}
          {activeTab === "materials" && (
            <Panel
              title="Published Study Materials & Banks"
              description="Each material contains source-grounded questions with empirical difficulty and distractor psychometrics."
            >
              {data.materials.length === 0 ? (
                <EmptyState>You have not published any quiz materials yet. Click 'Create Quiz and Post' to start.</EmptyState>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {data.materials.map((material) => (
                    <div
                      key={material.id}
                      className="rounded-2xl border border-zinc-200/80 bg-white p-5 flex flex-col justify-between hover:shadow-xs transition-shadow"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-zinc-900 text-sm">{material.title}</span>
                          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-700">
                            {material.questionCount} {material.questionCount === 1 ? "question" : "questions"}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-zinc-500">
                          Indexed for source citation and adaptive assessment.
                        </p>
                      </div>
                      <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3">
                        <button
                          type="button"
                          onClick={() => openItemAnalysis(material.id)}
                          className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors"
                        >
                          Item & Distractor Analysis 📊
                        </button>
                        <span className="text-xs text-zinc-400">ID #{material.id}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {/* ─── Tab Content 2: Assignments ─── */}
          {activeTab === "assignments" && (
            <Panel
              title="Assigned Learning Activities"
              description="Monitor student submissions, completion rates, and due dates."
            >
              {data.assignments.length === 0 ? (
                <EmptyState>Published quizzes and assignments will appear here once assigned.</EmptyState>
              ) : (
                <div className="divide-y divide-zinc-100">
                  {data.assignments.map((assignment) => (
                    <div key={assignment.id} className="py-4 flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="font-medium text-zinc-900 text-sm">{assignment.title}</p>
                        <p className="text-xs text-zinc-500">Material: {assignment.materialTitle}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-700">
                          {assignment.submissions} {assignment.submissions === 1 ? "submission" : "submissions"}
                        </span>
                        <Link
                          href={`/teacher/submissions?activityId=${assignment.id}`}
                          className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
                        >
                          View attempts
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {/* ─── Tab Content 3: Audit Trail ─── */}
          {activeTab === "audit" && (
            <Panel
              title="Teacher Action Audit Trail"
              description="Verifiable audit trail of important teacher modifications, quiz creations, and assignments."
            >
              {logsLoading ? (
                <LoadingState />
              ) : auditLogs.length === 0 ? (
                <EmptyState>No teacher audit logs recorded yet.</EmptyState>
              ) : (
                <div className="divide-y divide-zinc-100">
                  {auditLogs.map((log) => (
                    <div key={log.id} className="py-3 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-semibold text-zinc-800">{log.action}</span>
                        <span className="text-zinc-500 ml-2">
                          Target: {log.targetType} #{log.targetId}
                        </span>
                        {log.details && (
                          <span className="text-zinc-400 ml-2">
                            ({JSON.stringify(log.details)})
                          </span>
                        )}
                      </div>
                      <span className="text-zinc-400">
                        {new Date(log.createdAt).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}
        </>
      ) : null}

      {/* ─── Item & Distractor Analysis Modal (Feature 5) ─── */}
      {analysisMaterialId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-4xl max-h-[85vh] overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-100">
              <div>
                <h3 className="text-lg font-semibold text-zinc-900">
                  Question & Distractor Psychometric Analysis
                </h3>
                <p className="text-xs text-zinc-500">
                  Empirical difficulty (P-value), discrimination index (D), and distractor efficiency.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setAnalysisMaterialId(null);
                  setItemAnalysis(null);
                }}
                className="rounded-full h-8 w-8 flex items-center justify-center text-zinc-400 hover:text-zinc-700 bg-zinc-100"
              >
                ✕
              </button>
            </div>

            {analysisLoading ? (
              <LoadingState />
            ) : itemAnalysis ? (
              <div className="mt-6 space-y-6">
                <div className="grid grid-cols-3 gap-4">
                  <div className="apple-card p-4">
                    <p className="text-xs text-zinc-500">Total Questions</p>
                    <p className="text-2xl font-bold text-zinc-900">{itemAnalysis.totalQuestions}</p>
                  </div>
                  <div className="apple-card p-4">
                    <p className="text-xs text-zinc-500">Student Attempts Logged</p>
                    <p className="text-2xl font-bold text-zinc-900">{itemAnalysis.totalAttemptsLogged}</p>
                  </div>
                  <div className="apple-card p-4">
                    <p className="text-xs text-zinc-500">Average Item Health</p>
                    <p className="text-2xl font-bold text-emerald-600">
                      {itemAnalysis.averageItemHealth !== null ? `${itemAnalysis.averageItemHealth}%` : "Pending Data"}
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  {itemAnalysis.questions.map((q: any, idx: number) => (
                    <div key={q.id} className="rounded-2xl border border-zinc-200/80 p-5 bg-white space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full">
                          Question {idx + 1} · {q.conceptTag}
                        </span>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                              q.healthStatus === "EXCELLENT"
                                ? "bg-emerald-50 text-emerald-700"
                                : q.healthStatus === "NEEDS_REVISION"
                                ? "bg-amber-50 text-amber-700"
                                : q.healthStatus === "DEFECTIVE"
                                ? "bg-rose-50 text-rose-700"
                                : "bg-zinc-100 text-zinc-700"
                            }`}
                          >
                            {q.healthStatus}
                          </span>
                        </div>
                      </div>

                      <p className="text-sm font-medium text-zinc-900">{q.questionText}</p>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-zinc-600 pt-2 border-t border-zinc-100">
                        <div>
                          <span className="text-zinc-400">Difficulty (P):</span>{" "}
                          <span className="font-semibold">{q.difficultyIndexP} ({q.difficultyRating})</span>
                        </div>
                        <div>
                          <span className="text-zinc-400">Discrimination (D):</span>{" "}
                          <span className="font-semibold">
                            {q.discriminationIndex !== null ? q.discriminationIndex : "N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-zinc-400">Cognitive Level:</span>{" "}
                          <span className="font-semibold">{q.cognitiveLevel}</span>
                        </div>
                        <div>
                          <span className="text-zinc-400">Total Attempts:</span>{" "}
                          <span className="font-semibold">{q.totalAttempts}</span>
                        </div>
                      </div>

                      {/* Distractor Breakdown */}
                      <div className="space-y-1.5 pt-2">
                        <p className="text-xs font-semibold text-zinc-700">Distractor Performance Matrix:</p>
                        <div className="space-y-1">
                          {q.distractorAnalysis.map((d: any, dIdx: number) => (
                            <div
                              key={dIdx}
                              className={`flex items-center justify-between px-3 py-1.5 rounded-xl text-xs ${
                                d.isCorrect
                                  ? "bg-emerald-50/70 border border-emerald-200 text-emerald-900 font-medium"
                                  : d.status === "AMBIGUOUS_DISTRACTOR"
                                  ? "bg-amber-50/70 border border-amber-200 text-amber-900"
                                  : "bg-zinc-50 border border-zinc-200/60 text-zinc-700"
                              }`}
                            >
                              <span>{d.option}</span>
                              <div className="flex items-center gap-3">
                                <span>{d.selectionCount} picks ({d.selectionPercent}%)</span>
                                <span className="font-semibold">[{d.status}]</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <p className="text-xs text-zinc-500 italic bg-zinc-50 p-2.5 rounded-xl">
                        💡 Recommendation: {q.recommendation}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {assignActivityOpen && (
        <AssignActivityDialog
          materials={data?.materials ?? []}
          onClose={() => setAssignActivityOpen(false)}
        />
      )}
    </DashboardShell>
  );
}
