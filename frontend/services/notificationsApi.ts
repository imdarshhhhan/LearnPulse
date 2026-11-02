import { authorizedRequest } from "@/services/dashboardApi";
import type { SyncedUser } from "@/services/api";

export type NotificationType = "assignment" | "quiz" | "submission" | "group_invite";
export type TeacherActivityType = "quiz" | "homework";

export interface StudentNotification {
  id: number;
  title: string;
  message: string;
  type: NotificationType;
  createdAt: string | null;
  isRead: boolean;
  relatedUrl: string | null;
}

export interface StudentNotificationsResponse {
  studentId: number;
  profile: SyncedUser;
  notifications: StudentNotification[];
  unreadCount: number;
}

export interface TeacherCompletionNotification {
  id: number;
  title: string;
  message: string;
  type: "assignment" | "quiz";
  activityType: TeacherActivityType;
  audienceName: string;
  eligibleCount: number;
  submittedCount: number;
  createdAt: string | null;
  isRead: boolean;
  relatedUrl: string | null;
}

export interface TeacherNotificationsResponse {
  profile: SyncedUser;
  notifications: TeacherCompletionNotification[];
  unreadCount: number;
}

export function fetchStudentNotifications(): Promise<StudentNotificationsResponse> {
  return authorizedRequest(
    "/notifications",
    "Could not load your notifications.",
  );
}

export function fetchUnreadNotificationCount(): Promise<{ unreadCount: number }> {
  return authorizedRequest(
    "/notifications/unread-count",
    "Could not load your unread notification count.",
  );
}

export function markStudentNotificationRead(
  notificationId: number,
): Promise<{ id: number; isRead: boolean }> {
  return authorizedRequest(
    `/notifications/${notificationId}/read`,
    "Could not mark this notification as read.",
    { method: "POST" },
  );
}

export function markAllStudentNotificationsRead(): Promise<{
  updatedCount: number;
  unreadCount: number;
}> {
  return authorizedRequest(
    "/notifications/read-all",
    "Could not mark notifications as read.",
    { method: "POST" },
  );
}

export function fetchTeacherNotifications(
  activityType?: TeacherActivityType,
): Promise<TeacherNotificationsResponse> {
  const query = activityType
    ? `?activityType=${encodeURIComponent(activityType)}`
    : "";
  return authorizedRequest(
    `/notifications/teacher${query}`,
    "Could not load teacher notifications.",
  );
}

export function markTeacherNotificationRead(
  notificationId: number,
): Promise<{ id: number; isRead: boolean }> {
  return authorizedRequest(
    `/notifications/${notificationId}/read`,
    "Could not mark this notification as read.",
    { method: "POST" },
  );
}

export function markAllTeacherNotificationsRead(): Promise<{
  updatedCount: number;
  unreadCount: number;
}> {
  return authorizedRequest(
    "/notifications/read-all",
    "Could not mark notifications as read.",
    { method: "POST" },
  );
}
