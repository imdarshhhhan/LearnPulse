import type { SyncedUser } from "@/services/api";
import { authorizedRequest } from "@/services/dashboardApi";

export interface PerformanceClass {
  id: number;
  name: string;
  subject: string | null;
}

export interface PerformanceStudent {
  id: number;
  fullName: string;
  usn: string | null;
  averageScorePercent: number | null;
  submittedAssessments: number;
  participatedAssessments: number;
  eligibleAssessments: number;
  masteryPercent: number | null;
}

export interface ClassPerformance {
  profile: SyncedUser;
  class: { id: number; name: string; subject: string | null; description: string | null };
  totalStudents: number;
  classAveragePercent: number | null;
  topPerformer: PerformanceStudent | null;
  lowestPerformer: PerformanceStudent | null;
  averageMasteryPercent: number | null;
  studentsWithMastery: number;
  participationPercent: number | null;
  completionPercent: number | null;
  participatedOpportunities: number;
  completedOpportunities: number;
  assessmentOpportunities: number;
  assessments: {
    id: number;
    title: string;
    subject: string;
    date: string | null;
    eligibleStudents: number;
    participatedStudents: number;
    completedStudents: number;
    averageScorePercent: number | null;
    distribution: {
      below50: number;
      from50To69: number;
      from70To89: number;
      from90To100: number;
    };
  }[];
  students: PerformanceStudent[];
}

export interface StudentPerformance {
  profile: SyncedUser;
  student: { id: number; fullName: string; usn: string | null; email: string };
  class: { id: number; name: string };
  averageScorePercent: number | null;
  scoreHistory: {
    assessmentId: number;
    assessmentTitle: string;
    date: string | null;
    score: number;
    totalQuestions: number;
    scorePercent: number;
  }[];
  assessments: {
    id: number;
    title: string;
    subject: string;
    date: string | null;
    status: "not_started" | "in_progress" | "submitted";
    score: number | null;
    totalQuestions: number | null;
    scorePercent: number | null;
    attempts: {
      id: number;
      status: "in_progress" | "submitted";
      score: number | null;
      totalQuestions: number | null;
      scorePercent: number | null;
      attemptedAt: string | null;
    }[];
  }[];
  questionStats: { attempted: number; correct: number; incorrect: number };
  topicPerformance: {
    topic: string;
    totalQuestionsAttempted: number;
    correctAnswers: number;
    incorrectAnswers: number;
    errorCounts: { easy: number; medium: number; difficult: number };
    masteryPercent: number;
    sampleSize: number;
    attemptCount: number;
    assessmentDates: string[];
    lastUpdated: string | null;
    recentPerformancePercent: number;
  }[];
  masteryHistory: {
    studentId: number;
    topic: string;
    attemptId: number;
    date: string | null;
    masteryPercent: number;
    sampleSize: number;
  }[];
  practiceTopics: string[];
}

function querySuffix(topic?: string, assessmentId?: string) {
  const query = new URLSearchParams();
  if (topic?.trim()) query.set("topic", topic.trim());
  if (assessmentId) query.set("assessmentId", assessmentId);
  return query.size ? `?${query.toString()}` : "";
}

export function fetchPerformanceClasses(): Promise<{ classes: PerformanceClass[] }> {
  return authorizedRequest("/teacher/performance/classes", "Could not load your classes.");
}

export function fetchClassPerformance(
  classId: number,
  filters: { topic?: string; assessmentId?: string } = {},
): Promise<ClassPerformance> {
  return authorizedRequest(
    `/teacher/performance/classes/${classId}${querySuffix(filters.topic, filters.assessmentId)}`,
    "Could not load class performance.",
  );
}

export function fetchStudentPerformance(
  classId: number,
  studentId: number,
  filters: { topic?: string; assessmentId?: string } = {},
): Promise<StudentPerformance> {
  return authorizedRequest(
    `/teacher/performance/classes/${classId}/students/${studentId}${querySuffix(filters.topic, filters.assessmentId)}`,
    "Could not load student performance.",
  );
}
