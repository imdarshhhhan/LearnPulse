import { authorizedRequest } from "@/services/dashboardApi";
import type { SyncedUser } from "@/services/api";

export type AssessmentType = "quiz" | "homework";
export type FeedbackCategory = "content" | "difficulty" | "experience" | "other";

export interface StudentFeedbackDraft {
  message: string;
  category: FeedbackCategory | "";
  rating: number | "";
}

export interface SavedStudentFeedback {
  message: string;
  category: FeedbackCategory | null;
  rating: number | null;
  submittedAt: string | null;
}

export interface TeacherFeedbackItem {
  id: number;
  studentId: number;
  studentName: string;
  studentUsn: string | null;
  assignmentId: number;
  activityType: AssessmentType;
  activityTitle: string;
  message: string;
  category: FeedbackCategory | null;
  rating: number | null;
  submittedAt: string | null;
}

export interface TeacherFeedbackData {
  profile: SyncedUser;
  feedback: TeacherFeedbackItem[];
  filters: {
    activities: {
      id: number;
      title: string;
      activityType: AssessmentType;
    }[];
  };
}

export function fetchStudentFeedback(
  assignmentId: number,
): Promise<{ feedback: SavedStudentFeedback | null }> {
  return authorizedRequest(
    `/feedback/assignments/${assignmentId}`,
    "Could not load your feedback.",
  );
}

export function saveStudentFeedback(
  assignmentId: number,
  draft: StudentFeedbackDraft,
): Promise<{ id: number; assignmentId: number; submittedAt: string | null }> {
  return authorizedRequest(
    `/feedback/assignments/${assignmentId}`,
    "Could not save your feedback.",
    { method: "POST", body: draft },
  );
}

export function fetchTeacherFeedback(filters: {
  activityType?: AssessmentType;
  assignmentId?: string;
  search?: string;
  sort?: "newest" | "oldest";
}): Promise<TeacherFeedbackData> {
  const params = new URLSearchParams();
  if (filters.activityType) params.set("activityType", filters.activityType);
  if (filters.assignmentId) params.set("assignmentId", filters.assignmentId);
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  if (filters.sort) params.set("sort", filters.sort);
  const query = params.size ? `?${params.toString()}` : "";
  return authorizedRequest(
    `/feedback/teacher${query}`,
    "Could not load student feedback.",
  );
}

export function fetchTeacherFeedbackDetail(
  feedbackId: number,
): Promise<{ profile: SyncedUser } & TeacherFeedbackItem> {
  return authorizedRequest(
    `/feedback/teacher/${feedbackId}`,
    "Could not load this feedback.",
  );
}
