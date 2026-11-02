import {
  authorizedRequest,
  type StudentDashboardData,
} from "@/services/dashboardApi";
import type { SyncedUser } from "@/services/api";

export interface StudentHomeworkResponse {
  studentId: number;
  profile: SyncedUser;
  assignments: StudentDashboardData["assignments"];
  count: number;
}

export function fetchStudentHomework(): Promise<StudentHomeworkResponse> {
  return authorizedRequest(
    "/homework/assignments",
    "Could not load your homework.",
  );
}
