import { authorizedRequest } from "@/services/dashboardApi";
import type { SyncedUser } from "@/services/api";

export interface SavedQuiz {
  id: number;
  assignmentId: number;
  title: string;
  topic: string;
  teacherName: string;
  savedAt: string | null;
  dueDate: string | null;
  questionCount: number;
  bestScorePercent: number | null;
}

export interface SavedQuizzesResponse {
  studentId: number;
  profile: SyncedUser;
  quizzes: SavedQuiz[];
}

export function fetchSavedQuizzes(): Promise<SavedQuizzesResponse> {
  return authorizedRequest("/saved-quizzes", "Could not load saved quizzes.");
}

export function saveQuiz(assignmentId: number): Promise<{
  id: number;
  assignmentId: number;
  savedAt: string | null;
  saved: boolean;
}> {
  return authorizedRequest(
    `/saved-quizzes/${assignmentId}`,
    "Could not save this quiz.",
    { method: "POST" },
  );
}

export function removeSavedQuiz(
  assignmentId: number,
): Promise<{ removed: boolean }> {
  return authorizedRequest(
    `/saved-quizzes/${assignmentId}`,
    "Could not remove this saved quiz.",
    { method: "DELETE" },
  );
}
