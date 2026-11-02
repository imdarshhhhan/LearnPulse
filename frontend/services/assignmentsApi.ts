import { authorizedRequest } from "@/services/dashboardApi";

export interface StudentAssignment {
  id: number;
  title: string;
  activityType: "quiz" | "homework";
  materialTitle: string;
  teacherName: string;
  description: string | null;
  dueDate: string | null;
  availableFrom: string | null;
  canSubmit: boolean;
  unavailableReason: "not_yet_available" | "due_date_passed" | "max_attempts_reached" | null;
  timeLimitMinutes: number | null;
  remainingSeconds: number | null;
  isExpired: boolean;
  maxAttempts: number;
  attemptsUsed: number;
  attemptsRemaining: number;
  progressAnswers: Record<string, string>;
  submittedResult: AssignmentResult | null;
  questions: {
    id: number;
    conceptTag: string;
    subtopic?: string;
    cognitiveLevel: string;
    difficulty?: string;
    questionType?: string;
    questionText: string;
    options: string[];
  }[];
}

export interface QuestionBreakdown {
  questionId: number;
  questionText: string;
  selectedOption: string;
  correctAnswer: string;
  isCorrect: boolean;
  explanation: string;
  sourceQuote: string;
  sourcePage: number;
  conceptTag: string;
  subtopic: string;
  difficulty: string;
  cognitiveLevel: string;
}

export interface RemediationData {
  attemptId: number;
  score: number;
  totalQuestions: number;
  scorePercent: number;
  summary: string;
  questionBreakdown: QuestionBreakdown[];
  conceptsNeedingRevision: {
    concept: string;
    accuracyPercent: number;
    mistakesCount: number;
    totalConceptQuestions: number;
  }[];
  strongConcepts: {
    concept: string;
    accuracyPercent: number;
  }[];
  studyRecommendations: {
    concept: string;
    recommendedSection: string;
    keyExcerptsToReview: string[];
    actionGuidance: string;
  }[];
  nextSteps?: {
    canGeneratePracticeQuiz: boolean;
    targetConcepts: string[];
    message: string;
  };
}

export interface AssignmentResult {
  attemptId: number;
  correctAnswers: number;
  totalQuestions: number;
  scorePercent: number;
  attemptedAt: string | null;
  studentFeedbackNotes?: string | null;
  remediationData?: RemediationData | null;
}

export function fetchStudentAssignment(assignmentId: number): Promise<StudentAssignment> {
  return authorizedRequest(
    `/quizzes/assignments/${assignmentId}`,
    "Could not load this assignment.",
  );
}

export function submitStudentAssignment(
  assignmentId: number,
  answers: { questionId: number; selectedOption: string }[],
  submissionId: string,
): Promise<AssignmentResult> {
  return authorizedRequest(
    `/quizzes/assignments/${assignmentId}/submit`,
    "Could not submit this assignment.",
    { method: "POST", body: { answers, submissionId } },
  );
}

export function saveStudentAssignmentProgress(
  assignmentId: number,
  answers: { questionId: number; selectedOption: string }[],
): Promise<{ status: string; answeredQuestions: number }> {
  return authorizedRequest(
    `/quizzes/assignments/${assignmentId}/progress`,
    "Could not save your progress.",
    { method: "PUT", body: { answers } },
  );
}

export function fetchAttemptRemediation(attemptId: number): Promise<{
  attemptId: number;
  score: number;
  totalQuestions: number;
  scorePercent: number;
  studentFeedbackNotes: string | null;
  remediationData: RemediationData | null;
}> {
  return authorizedRequest(
    `/quizzes/attempts/${attemptId}/remediation`,
    "Could not load remediation details.",
  );
}

export function generateAdaptivePractice(
  materialId?: number,
  numQuestions: number = 5,
): Promise<{
  status: string;
  totalQuestions: number;
  questions: {
    questionId: number;
    questionText: string;
    questionType: string;
    optionsMatrix: string[];
    conceptTag: string;
    subtopic: string;
    difficulty: string;
    cognitiveLevel: string;
  }[];
}> {
  return authorizedRequest(
    `/quizzes/practice/generate`,
    "Could not generate an adaptive practice quiz.",
    {
      method: "POST",
      body: { materialId: materialId || null, numQuestions },
    },
  );
}

export function submitAdaptivePractice(
  answers: { questionId: number; selectedOption: string }[],
): Promise<{
  attemptId: number;
  score: number;
  totalQuestions: number;
  scorePercent: number;
  remediation: RemediationData;
}> {
  return authorizedRequest(
    `/quizzes/practice/submit`,
    "Could not submit adaptive practice quiz.",
    {
      method: "POST",
      body: { answers },
    },
  );
}

export function fetchMaterialItemAnalysis(materialId: number): Promise<{
  materialId: number;
  totalQuestions: number;
  totalAttemptsLogged: number;
  averageItemHealth: number | null;
  questions: {
    id: number;
    questionText: string;
    questionType: string;
    conceptTag: string;
    subtopic: string;
    difficulty: string;
    cognitiveLevel: string;
    correctAnswer: string;
    options: string[];
    totalAttempts: number;
    correctAttempts: number;
    difficultyIndexP: number;
    difficultyRating: string;
    discriminationIndex: number | null;
    discriminationRating: string;
    distractorAnalysis: {
      option: string;
      selectionCount: number;
      selectionPercent: number;
      upperGroupCount?: number;
      lowerGroupCount?: number;
      isCorrect: boolean;
      status: string;
    }[];
    healthStatus: string;
    recommendation: string;
  }[];
}> {
  return authorizedRequest(
    `/quizzes/materials/${materialId}/item-analysis`,
    "Could not load item analysis for this material.",
  );
}

export function fetchTeacherAuditLogs(limit: number = 50): Promise<{
  logs: {
    id: number;
    action: string;
    targetType: string;
    targetId: number;
    details: any;
    createdAt: string;
  }[];
}> {
  return authorizedRequest(
    `/quizzes/teacher/audit-logs?limit=${limit}`,
    "Could not load teacher audit logs.",
  );
}

export function fetchStudentMasteryTrends(): Promise<{
  studentId: number;
  trends: {
    conceptTag: string;
    masteryScore: number;
    attemptsCount: number;
    lastUpdated: string | null;
    history: {
      timestamp: string;
      score: number;
      outcome: string;
    }[];
  }[];
}> {
  return authorizedRequest(
    `/quizzes/student/mastery-trends`,
    "Could not load student mastery trends.",
  );
}

export function fetchTeacherClassHeatmap(classId: number): Promise<{
  classId: number;
  className: string;
  concepts: string[];
  studentHeatmap: {
    studentId: number;
    studentName: string;
    usn: string | null;
    concepts: Record<
      string,
      {
        score: number | null;
        status: string;
        attempts: number;
      }
    >;
  }[];
}> {
  return authorizedRequest(
    `/quizzes/teacher/heatmap/${classId}`,
    "Could not load class heatmap.",
  );
}

export function updateQuestionTags(
  questionId: number,
  payload: {
    conceptTag?: string;
    subtopic?: string;
    difficulty?: "easy" | "medium" | "difficult";
    cognitiveLevel?: "Remember" | "Understand" | "Apply" | "Analyse";
    questionText?: string;
    correctAnswer?: string;
    optionsMatrix?: string[];
  },
): Promise<any> {
  return authorizedRequest(
    `/documents/questions/${questionId}`,
    "Could not update question tags.",
    { method: "PATCH", body: payload },
  );
}

export function archiveQuestion(questionId: number): Promise<any> {
  return authorizedRequest(
    `/documents/questions/${questionId}`,
    "Could not archive question.",
    { method: "DELETE" },
  );
}
