const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type UserRole = "student" | "teacher";

export interface SyncedUser {
  userId: number;
  role: UserRole;
  email: string;
  fullName: string;
  usn: string | null;
  avatarUrl?: string | null;
  achievements?: unknown[];
}

export interface AuthResponse {
  token: string;
  tokenType: "bearer";
  user: SyncedUser;
}

export interface RegisterPayload {
  email: string;
  password: string;
  fullName: string;
  role: UserRole;
  usn?: string;
}

async function fetchBackend(
  url: string,
  init: RequestInit,
): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    if (error instanceof TypeError) {
      const frontendOrigin =
        typeof window === "undefined"
          ? "unknown frontend origin"
          : window.location.origin;
      throw new Error(
        `Could not reach the backend at ${BACKEND_URL} from ${frontendOrigin}. Check that FastAPI is running, the backend URL is reachable from this device, and FRONTEND_ORIGINS includes this frontend origin.`,
        { cause: error },
      );
    }
    throw error;
  }
}

async function throwApiError(
  response: Response,
  fallbackMessage: string,
): Promise<never> {
  const responseBody = await response.text();
  if (!responseBody) {
    throw new Error(fallbackMessage);
  }

  let errorDetails: unknown;
  try {
    errorDetails = JSON.parse(responseBody);
  } catch {
    throw new Error(responseBody);
  }

  if (
    typeof errorDetails === "object" &&
    errorDetails !== null &&
    "detail" in errorDetails &&
    typeof errorDetails.detail === "string"
  ) {
    throw new Error(errorDetails.detail);
  }

  throw new Error(responseBody);
}

export async function registerUser(payload: RegisterPayload): Promise<AuthResponse> {
  const response = await fetchBackend(`${BACKEND_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await throwApiError(response, "User registration failed.");
  }

  return response.json();
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  const response = await fetchBackend(`${BACKEND_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    await throwApiError(response, "Login failed.");
  }

  return response.json();
}

export async function fetchCurrentUser(): Promise<SyncedUser> {
  const token = typeof window === "undefined" ? "" : localStorage.getItem("userToken");
  const response = await fetchBackend(`${BACKEND_URL}/auth/me`, {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    await throwApiError(response, "Could not verify your account.");
  }

  return response.json();
}

export async function updateStudentUSN(usn: string): Promise<SyncedUser> {
    const token = typeof window === "undefined" ? "" : localStorage.getItem("userToken");
    const response = await fetchBackend(`${BACKEND_URL}/auth/usn`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ usn }),
    });
    if (!response.ok) {
      await throwApiError(response, "Could not save your USN.");
    }
    return response.json();
  }
export async function syncFirebaseSignupWithBackend(payload: {
  idToken: string;
  fullName: string;
  roleSelection: UserRole;
}): Promise<SyncedUser> {
  const response = await fetchBackend(`${BACKEND_URL}/auth/verify-sync-signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: payload.fullName.includes("@") ? payload.fullName : undefined,
      password: "legacy-firebase-token",
      fullName: payload.fullName,
      roleSelection: payload.roleSelection,
    }),
  });

  if (!response.ok) {
    await throwApiError(response, "Authentication failed.");
  }

  const body = await response.json();
  return body.user ?? body;
}

export async function syncFirebaseLoginWithBackend(
  idToken: string,
): Promise<SyncedUser> {
  const response = await fetchBackend(`${BACKEND_URL}/auth/verify-sync-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }),
  });

  if (!response.ok) {
    await throwApiError(response, "Authentication failed.");
  }

  const body = await response.json();
  return body.user ?? body;
}

export async function uploadStudyMaterial(textContext: string, token: string) {
  const response = await fetchBackend(`${BACKEND_URL}/documents/upload`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title: "Lesson Context Notes", textBody: textContext }),
  });

  if (!response.ok) {
    await throwApiError(response, "Document processing failed.");
  }
  return response.json();
}

export interface GeneratedQuestion {
  question: string;
  question_type?: "mcq" | "true_false";
  options: string[];
  answer: string;
  difficulty: "easy" | "medium" | "difficult";
  cognitive_level?: "Remember" | "Understand" | "Apply" | "Analyse";
  cognitiveLevel?: "Remember" | "Understand" | "Apply" | "Analyse";
  concept_tag?: string;
  conceptTag?: string;
  subtopic?: string;
  explanation?: string;
  source_quote?: string;
  sourceQuote?: string;
  source_page?: number;
  sourcePage?: number;
  is_approved_automatically?: boolean;
  isApprovedAutomatically?: boolean;
  quality_score?: number;
  qualityScore?: number;
  validation_warnings?: string[];
  validationWarnings?: string[];
}

export async function createTest(
  topic: string,
): Promise<{ questions: GeneratedQuestion[] }> {
  const response = await fetchBackend(`${BACKEND_URL}/create-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });

  if (!response.ok) {
    await throwApiError(response, "Could not generate the test.");
  }
  return response.json();
}
