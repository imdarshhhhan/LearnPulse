import { authorizedRequest } from "@/services/dashboardApi";

export interface ClassStudent {
  id: number;
  fullName: string;
  usn: string | null;
  email: string;
}

export interface TeacherClass {
  id: number;
  name: string;
  subject: string | null;
  description: string | null;
  createdAt: string | null;
  memberCount: number;
  students: ClassStudent[];
}

export function fetchTeacherClasses(): Promise<{ classes: TeacherClass[] }> {
  return authorizedRequest("/teacher/classes", "Could not load your classes.");
}

export function searchAvailableStudents(
  search: string,
): Promise<{ students: ClassStudent[] }> {
  const query = new URLSearchParams();
  if (search.trim()) query.set("search", search.trim());
  return authorizedRequest(
    `/teacher/classes/students${query.size ? `?${query.toString()}` : ""}`,
    "Could not search students.",
  );
}

export function createTeacherClass(payload: {
  name: string;
  subject?: string;
  description?: string;
}): Promise<TeacherClass> {
  return authorizedRequest("/teacher/classes", "Could not create the class.", {
    method: "POST",
    body: payload,
  });
}

export function addClassStudent(classId: number, studentId: number): Promise<TeacherClass> {
  return authorizedRequest(
    `/teacher/classes/${classId}/students`,
    "Could not add this student.",
    { method: "POST", body: { studentId } },
  );
}

export function removeClassStudent(
  classId: number,
  studentId: number,
): Promise<TeacherClass> {
  return authorizedRequest(
    `/teacher/classes/${classId}/students/${studentId}`,
    "Could not remove this student.",
    { method: "DELETE" },
  );
}

export function deleteTeacherClass(
  classId: number,
): Promise<{ status: string; message: string }> {
  return authorizedRequest(
    `/teacher/classes/${classId}`,
    "Could not delete this class.",
    { method: "DELETE" },
  );
}
