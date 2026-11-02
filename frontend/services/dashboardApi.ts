import type { GeneratedQuestion, SyncedUser } from "@/services/api";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

/** An error that remembers the HTTP status, so pages can react to 401/403. */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getAuthToken(): string {
  const token = typeof window === "undefined" ? "" : localStorage.getItem("userToken");
  if (!token) {
    throw new ApiError("You are signed out. Please sign in again.", 401);
  }
  return token;
}

/** Turns a FastAPI error response into a readable ApiError. */
async function throwApiError(
  response: Response,
  fallbackMessage: string,
): Promise<never> {
  const body = await response.text();
  if (!body) throw new ApiError(fallbackMessage, response.status);

  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    throw new ApiError(body, response.status);
  }

  if (typeof parsed === "object" && parsed !== null && "detail" in parsed) {
    const { detail } = parsed;
    if (typeof detail === "string") {
      throw new ApiError(detail, response.status);
    }
    // FastAPI validation errors (422) arrive as a list of { msg, loc, ... }.
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String(item.msg)
            : null,
        )
        .filter(Boolean);
      if (messages.length > 0) {
        throw new ApiError(messages.join("; "), response.status);
      }
    }
  }
  throw new ApiError(body, response.status);
}

export async function authorizedRequest<T>(
  path: string,
  fallbackMessage: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const token = getAuthToken();

  let response: Response;
  try {
    const requestBody =
      init.body === undefined
        ? undefined
        : typeof FormData !== "undefined" && init.body instanceof FormData
          ? init.body
          : JSON.stringify(init.body);
    const isFormData =
      typeof FormData !== "undefined" && requestBody instanceof FormData;
    response = await fetch(`${BACKEND_URL}${path}`, {
      method: init.method ?? "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init.body !== undefined && !isFormData
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body: requestBody,
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Could not reach the backend at ${BACKEND_URL}. Check that FastAPI is running and FRONTEND_ORIGINS includes this origin.`,
        { cause: error },
      );
    }
    throw error;
  }

  if (!response.ok) await throwApiError(response, fallbackMessage);
  return response.json();
}

// ─── DASHBOARD TYPES ───

export interface TeacherDashboardData {
  profile: SyncedUser;
  stats: {
    materials: number;
    assignments: number;
    questionsInBank: number;
    submissions: number;
  };
  materials: {
    id: number;
    title: string;
    createdAt: string | null;
    questionCount: number;
  }[];
  assignments: {
    id: number;
    title: string;
    materialTitle: string;
    dueDate: string | null;
    submissions: number;
  }[];
}

export type SubmissionStatus = "submitted" | "in_progress";

export interface TeacherSubmissionsData {
  profile: SyncedUser;
  submissions: {
    id: number;
    studentId: number;
    studentName: string;
    studentUsn: string | null;
    activityId: number;
    activityTitle: string;
    submittedAt: string | null;
    status: SubmissionStatus;
    score: number | null;
    totalQuestions: number | null;
    scorePercent: number | null;
  }[];
  filters: {
    activities: { id: number; title: string }[];
    students: { id: number; fullName: string; usn: string | null }[];
  };
}

export type TeacherSubmissionDetail = TeacherSubmissionsData["submissions"][number] & {
  profile: SyncedUser;
  answers: {
    questionId: number;
    conceptTag: string;
    difficulty: "easy" | "medium" | "difficult";
    questionText: string;
    selectedOption: string | null;
    correctAnswer: string;
    isCorrect: boolean;
  }[];
};

export type AssignmentStatus =
  | "upcoming"
  | "pending"
  | "in_progress"
  | "completed"
  | "overdue";

export interface StudentDashboardData {
  profile: SyncedUser;
  stats: {
    openAssignments: number;
    completedAssignments: number;
    averageScorePercent: number | null;
    conceptsTracked: number;
  };
  assignments: {
    id: number;
    title: string;
    description: string | null;
    materialTitle: string;
    teacherName: string;
    assignedAt: string | null;
    availableFrom: string | null;
    dueDate: string | null;
    status: AssignmentStatus;
    hasQuiz: boolean;
    isSaved: boolean;
    bestScorePercent: number | null;
    submissionCount: number;
    submittedAt: string | null;
  }[];
  mastery: {
    conceptTag: string;
    masteryPercent: number;
    lastUpdated: string | null;
    sampleSize: number;
    correctAnswers: number;
    incorrectAnswers: number;
    difficultyErrors: { easy: number; medium: number; difficult: number };
    recentPerformancePercent: number;
  }[];
  recentAttempts: {
    id: number;
    assignmentTitle: string;
    scorePercent: number;
    attemptedAt: string | null;
  }[];
}

// ─── DASHBOARD CALLS ───

export function fetchTeacherDashboard(): Promise<TeacherDashboardData> {
  return authorizedRequest("/dashboard/teacher", "Could not load the dashboard.");
}

export function fetchStudentDashboard(): Promise<StudentDashboardData> {
  return authorizedRequest("/dashboard/student", "Could not load the dashboard.");
}

export function fetchTeacherSubmissions(filters: {
  activityId?: string;
  studentId?: string;
  status?: string;
} = {}): Promise<TeacherSubmissionsData> {
  const query = new URLSearchParams();
  if (filters.activityId) query.set("activityId", filters.activityId);
  if (filters.studentId) query.set("studentId", filters.studentId);
  if (filters.status) query.set("status", filters.status);
  const suffix = query.size ? `?${query.toString()}` : "";
  return authorizedRequest(
    `/quizzes/teacher/submissions${suffix}`,
    "Could not load student submissions.",
  );
}

export function fetchTeacherSubmission(attemptId: number): Promise<TeacherSubmissionDetail> {
  return authorizedRequest(
    `/quizzes/teacher/submissions/${attemptId}`,
    "Could not load this submission.",
  );
}

// These two reuse your existing /documents/upload and /quizzes/assign routes.
export function uploadMaterial(payload: { title: string; textBody: string }) {
  return authorizedRequest<{
    status: string;
    materialId: number;
    title: string;
    chunksIndexed: number;
  }>("/documents/upload", "Document processing failed.", {
    method: "POST",
    body: payload,
  });
}

export function postTest(payload: {
  topic: string;
  questions: GeneratedQuestion[];
  sourceText?: string;
}) {
  return authorizedRequest<{
    status: string;
    materialId: number;
    title: string;
    questionsPosted: number;
  }>("/documents/post-test", "Could not post the test.", {
    method: "POST",
    body: payload,
  });
}

export function generateTestFromUpload(
  file: File,
  title: string,
  questionCount: number = 5,
  questionType: "mcq" | "true_false" = "mcq",
): Promise<{ title: string; sourceText: string; questions: GeneratedQuestion[] }> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  body.append("questionCount", String(questionCount));
  body.append("questionType", questionType);
  return authorizedRequest(
    "/documents/generate-test",
    "Could not generate a quiz from this file.",
    { method: "POST", body },
  );
}

export function assignHomework(payload: {
  title: string;
  description?: string;
  activityType: "quiz" | "homework";
  materialId: number;
  dueDate: string; // YYYY-MM-DD
  availableFrom?: string;
  studentIds?: number[];
  groupIds?: number[];
  classIds?: number[];
  timeLimitMinutes?: number;
  maxAttempts?: number;
  randomizeQuestions?: boolean;
  randomizeOptions?: boolean;
  poolQuestionCount?: number;
}) {
  return authorizedRequest<{
    status: string;
    assignmentId: number;
    title: string;
    windowClosedAt: string;
  }>("/quizzes/assign", "Could not assign the homework.", {
    method: "POST",
    body: payload,
  });
}

export interface HomeworkRecipients {
  students: { id: number; fullName: string; usn: string | null }[];
  groups: { id: number; name: string }[];
  classes: { id: number; name: string }[];
}

export function fetchHomeworkRecipients(): Promise<HomeworkRecipients> {
  return authorizedRequest(
    "/quizzes/assignment-recipients",
    "Could not load homework recipients.",
  );
}