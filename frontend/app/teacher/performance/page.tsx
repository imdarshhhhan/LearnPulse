"use client";

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
  fetchClassPerformance,
  fetchPerformanceClasses,
  fetchStudentPerformance,
  type ClassPerformance,
  type PerformanceClass,
  type StudentPerformance,
} from "@/services/teacherPerformanceApi";

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500";

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
}

function formatPercent(value: number | null) {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

function Stat({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {helper && <p className="mt-1 text-xs text-zinc-500">{helper}</p>}
    </div>
  );
}

export default function TeacherPerformancePage() {
  const router = useRouter();
  const [classes, setClasses] = useState<PerformanceClass[]>([]);
  const [classId, setClassId] = useState("");
  const [studentId, setStudentId] = useState("");
  const [topic, setTopic] = useState("");
  const [assessmentId, setAssessmentId] = useState("");
  const [summary, setSummary] = useState<ClassPerformance | null>(null);
  const [student, setStudent] = useState<StudentPerformance | null>(null);
  const [loadingClasses, setLoadingClasses] = useState(true);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingStudent, setLoadingStudent] = useState(false);
  const [error, setError] = useState("");
  const currentSummary =
    summary?.class.id === Number(classId) ? summary : null;
  const currentStudent =
    student?.class.id === Number(classId) && student.student.id === Number(studentId)
      ? student
      : null;

  useEffect(() => {
    let active = true;
    fetchPerformanceClasses()
      .then(({ classes: result }) => {
        if (!active) return;
        setClasses(result);
        setClassId(result[0] ? String(result[0].id) : "");
        setLoadingSummary(!!result[0]);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Could not load classes.");
      })
      .finally(() => {
        if (active) setLoadingClasses(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    if (!classId) return;
    let active = true;
    fetchClassPerformance(Number(classId), { topic, assessmentId })
      .then((result) => {
        if (!active) return;
        setSummary(result);
        setLoadingStudent(!!result.students.length);
        setStudentId((current) =>
          result.students.some((item) => String(item.id) === current)
            ? current
            : result.students[0] ? String(result.students[0].id) : "",
        );
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Could not load class performance.");
      })
      .finally(() => {
        if (active) setLoadingSummary(false);
      });
    return () => {
      active = false;
    };
  }, [classId, topic, assessmentId, router]);

  useEffect(() => {
    if (!classId || !studentId) return;
    let active = true;
    fetchStudentPerformance(Number(classId), Number(studentId), { topic, assessmentId })
      .then((result) => {
        if (active) setStudent(result);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Could not load student performance.");
      })
      .finally(() => {
        if (active) setLoadingStudent(false);
      });
    return () => {
      active = false;
    };
  }, [classId, studentId, topic, assessmentId, router]);

  const selectedClass = classes.find((item) => String(item.id) === classId);

  return (
    <DashboardShell title="Student Performance" user={currentSummary?.profile ?? null}>
      <section>
        <p className="text-sm font-medium text-indigo-700">Teacher workspace</p>
        <h2 className="mt-1 text-2xl font-semibold">Class and student performance</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Scores and participation use persisted submitted attempts. Missing work is shown separately, not scored as zero.
        </p>
      </section>

      <Panel title="Filters">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="space-y-1 text-sm font-medium">
            <span>Class</span>
            <select
              value={classId}
              onChange={(event) => {
                setError("");
                setLoadingSummary(!!event.target.value);
                setLoadingStudent(!!event.target.value);
                setClassId(event.target.value);
              }}
              className={inputClass}
            >
              <option value="">Choose a class</option>
              {classes.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Student</span>
            <select
              value={studentId}
              onChange={(event) => {
                setLoadingStudent(!!event.target.value);
                setStudentId(event.target.value);
              }}
              disabled={!currentSummary?.students.length}
              className={inputClass}
            >
              <option value="">Choose a student</option>
              {currentSummary?.students.map((item) => (
                <option key={item.id} value={item.id}>{item.usn ?? "USN pending"} · {item.fullName}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Subject or topic</span>
            <input
              value={topic}
              onChange={(event) => {
                setLoadingSummary(!!classId);
                setLoadingStudent(!!classId && !!studentId);
                setTopic(event.target.value);
              }}
              maxLength={120}
              className={inputClass}
              placeholder="Filter by subject or topic"
            />
          </label>
          <label className="space-y-1 text-sm font-medium">
            <span>Assessment</span>
            <select
              value={assessmentId}
              onChange={(event) => {
                setLoadingSummary(!!classId);
                setLoadingStudent(!!classId && !!studentId);
                setAssessmentId(event.target.value);
              }}
              className={inputClass}
            >
              <option value="">All assessments</option>
              {currentSummary?.assessments.map((assessment) => (
                <option key={assessment.id} value={assessment.id}>{assessment.title}</option>
              ))}
            </select>
          </label>
        </div>
      </Panel>

      {loadingClasses || loadingSummary ? (
        <LoadingState />
      ) : error ? (
        <ErrorBanner message={error} />
      ) : !classes.length ? (
        <Panel title="No classes yet">
          <EmptyState>Create a class in Class Management before viewing performance.</EmptyState>
        </Panel>
      ) : currentSummary ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
              <Stat label="Students" value={String(currentSummary.totalStudents)} />
              <Stat label="Class average" value={formatPercent(currentSummary.classAveragePercent)} />
            <Stat
              label="Top performer"
              value={currentSummary.topPerformer ? currentSummary.topPerformer.fullName : "—"}
              helper={currentSummary.topPerformer ? formatPercent(currentSummary.topPerformer.averageScorePercent) : "No submitted scores"}
            />
            <Stat
              label="Lowest performer"
              value={currentSummary.lowestPerformer ? currentSummary.lowestPerformer.fullName : "—"}
              helper={currentSummary.lowestPerformer ? formatPercent(currentSummary.lowestPerformer.averageScorePercent) : "No submitted scores"}
            />
            <Stat
              label="Average mastery"
              value={formatPercent(currentSummary.averageMasteryPercent)}
              helper={`${currentSummary.studentsWithMastery} / ${currentSummary.totalStudents} students with responses · estimate`}
            />
            <Stat
              label="Assessment completion"
              value={formatPercent(currentSummary.completionPercent)}
              helper={`${currentSummary.completedOpportunities} / ${currentSummary.assessmentOpportunities} expected submissions`}
            />
          </section>
          <section className="grid gap-4 sm:grid-cols-2">
            <Stat
              label="Participation"
              value={formatPercent(currentSummary.participationPercent)}
              helper={`${currentSummary.participatedOpportunities} student-assessment starts`}
            />
            <Stat
              label="Assessments"
              value={String(currentSummary.assessments.length)}
              helper={selectedClass?.subject ?? "Quiz and test assignments"}
            />
          </section>

          <Panel title="Assessment comparison" description="Class average is based on the latest submitted attempt per eligible student.">
            {currentSummary.assessments.length === 0 ? (
              <EmptyState>No assessments match this class and filter.</EmptyState>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[780px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                      <th className="px-3 py-3 font-medium">Assessment</th>
                      <th className="px-3 py-3 font-medium">Topic / subject</th>
                      <th className="px-3 py-3 font-medium">Date</th>
                      <th className="px-3 py-3 font-medium">Class average</th>
                      <th className="px-3 py-3 font-medium">Participation</th>
                      <th className="px-3 py-3 font-medium">Completion</th>
                      <th className="px-3 py-3 font-medium">Score distribution</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {currentSummary.assessments.map((assessment) => (
                      <tr key={assessment.id}>
                        <td className="px-3 py-3 font-medium">{assessment.title}</td>
                        <td className="px-3 py-3">{assessment.subject}</td>
                        <td className="px-3 py-3">{formatDate(assessment.date)}</td>
                        <td className="px-3 py-3">{formatPercent(assessment.averageScorePercent)}</td>
                        <td className="px-3 py-3">{assessment.participatedStudents} / {assessment.eligibleStudents}</td>
                        <td className="px-3 py-3">{assessment.completedStudents} / {assessment.eligibleStudents}</td>
                        <td className="px-3 py-3 text-xs text-zinc-600">
                          &lt;50: {assessment.distribution.below50} · 50–69: {assessment.distribution.from50To69}
                          {" · "}70–89: {assessment.distribution.from70To89} · 90+: {assessment.distribution.from90To100}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title={currentStudent ? `${currentStudent.student.fullName} · ${currentStudent.student.usn ?? "USN pending"}` : "Individual performance"}>
            {loadingStudent ? (
              <LoadingState />
            ) : currentStudent ? (
              <div className="space-y-6">
                <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Stat label="Average score" value={formatPercent(currentStudent.averageScorePercent)} />
                  <Stat label="Questions attempted" value={String(currentStudent.questionStats.attempted)} />
                  <Stat label="Correct answers" value={String(currentStudent.questionStats.correct)} />
                  <Stat label="Incorrect answers" value={String(currentStudent.questionStats.incorrect)} />
                </section>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[700px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                        <th className="px-3 py-3 font-medium">Assessment</th>
                        <th className="px-3 py-3 font-medium">Date</th>
                        <th className="px-3 py-3 font-medium">Result</th>
                        <th className="px-3 py-3 font-medium">Attempts</th>
                        <th className="px-3 py-3 font-medium">History</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {currentStudent.assessments.map((assessment) => (
                        <tr key={assessment.id}>
                          <td className="px-3 py-3 font-medium">{assessment.title}</td>
                          <td className="px-3 py-3">{formatDate(assessment.date)}</td>
                          <td className="px-3 py-3">
                            {assessment.status === "not_started"
                              ? "Not attempted"
                              : assessment.status === "in_progress"
                                ? "In progress"
                                : `${assessment.score} / ${assessment.totalQuestions} · ${formatPercent(assessment.scorePercent)}`}
                          </td>
                          <td className="px-3 py-3">{assessment.attempts.length}</td>
                          <td className="px-3 py-3 text-zinc-600">
                            {assessment.attempts.map((attempt) => (
                              <span key={attempt.id} className="mr-2 inline-block whitespace-nowrap">
                                {formatDate(attempt.attemptedAt)}: {attempt.status === "submitted" ? formatPercent(attempt.scorePercent) : "In progress"}
                              </span>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {currentStudent.scoreHistory.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-semibold">Score trend</h3>
                    <div className="flex flex-wrap gap-2">
                      {currentStudent.scoreHistory.map((score, index) => (
                        <div key={`${score.assessmentId}-${index}`} className="rounded-lg bg-zinc-100 px-3 py-2 text-sm">
                          <span className="font-medium">{formatPercent(score.scorePercent)}</span>
                          <span className="ml-2 text-zinc-600">{score.assessmentTitle} · {formatDate(score.date)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <h3 className="mb-1 text-sm font-semibold">Topic mastery estimate</h3>
                  <p className="mb-3 text-xs text-zinc-500">
                    Weighted from persisted question-level answers (easy 1.0, medium 1.5, difficult 2.0); this estimates observed performance, not true ability.
                  </p>
                  {currentStudent.topicPerformance.length === 0 ? (
                    <EmptyState>No submitted question responses are available for the selected topics.</EmptyState>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[720px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                            <th className="px-3 py-3 font-medium">Topic</th>
                            <th className="px-3 py-3 font-medium">Mastery estimate</th>
                            <th className="px-3 py-3 font-medium">Sample</th>
                            <th className="px-3 py-3 font-medium">Correct / incorrect</th>
                            <th className="px-3 py-3 font-medium">Errors easy / medium / difficult</th>
                            <th className="px-3 py-3 font-medium">Recent performance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-100">
                          {currentStudent.topicPerformance.map((item) => (
                            <tr key={item.topic}>
                              <td className="px-3 py-3 font-medium">{item.topic}</td>
                              <td className="px-3 py-3">{formatPercent(item.masteryPercent)}</td>
                              <td className="px-3 py-3">{item.sampleSize} questions · {item.attemptCount} attempts</td>
                              <td className="px-3 py-3">{item.correctAnswers} / {item.incorrectAnswers}</td>
                              <td className="px-3 py-3">{item.errorCounts.easy} / {item.errorCounts.medium} / {item.errorCounts.difficult}</td>
                              <td className="px-3 py-3">{formatPercent(item.recentPerformancePercent)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Historical mastery</h3>
                  {currentStudent.masteryHistory.length === 0 ? (
                    <EmptyState>Mastery history appears after questions have been submitted.</EmptyState>
                  ) : (
                    <ul className="flex flex-wrap gap-2">
                      {currentStudent.masteryHistory.map((point) => (
                        <li key={`${point.topic}-${point.attemptId}`} className="rounded-lg bg-zinc-100 px-3 py-2 text-xs">
                          <span className="font-medium">{point.topic}: {formatPercent(point.masteryPercent)}</span>
                          <span className="ml-2 text-zinc-600">{point.sampleSize} questions · {formatDate(point.date)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {currentStudent.practiceTopics.length > 0 && (
                  <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    Topics to practice next (below 60% estimate): {currentStudent.practiceTopics.join(", ")}
                  </p>
                )}
              </div>
            ) : (
              <EmptyState>Select a student in this class to view their performance.</EmptyState>
            )}
          </Panel>
        </>
      ) : null}
    </DashboardShell>
  );
}
