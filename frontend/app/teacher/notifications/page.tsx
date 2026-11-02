"use client";

import Link from "next/link";
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
  fetchTeacherNotifications,
  markAllTeacherNotificationsRead,
  markTeacherNotificationRead,
  type TeacherActivityType,
  type TeacherCompletionNotification,
  type TeacherNotificationsResponse,
} from "@/services/notificationsApi";

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export default function TeacherNotificationsPage() {
  const router = useRouter();
  const [data, setData] = useState<TeacherNotificationsResponse | null>(null);
  const [activityType, setActivityType] = useState<"" | TeacherActivityType>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    let active = true;
    fetchTeacherNotifications(activityType || undefined)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        if (requestError instanceof ApiError && requestError.status === 403) {
          router.replace("/teacher");
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load teacher notifications.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activityType, reloadCount, router]);

  async function markRead(notification: TeacherCompletionNotification) {
    setPendingId(notification.id);
    setActionError("");
    try {
      await markTeacherNotificationRead(notification.id);
      setData((current) =>
        current
          ? {
              ...current,
              unreadCount: Math.max(0, current.unreadCount - (notification.isRead ? 0 : 1)),
              notifications: current.notifications.map((item) =>
                item.id === notification.id ? { ...item, isRead: true } : item,
              ),
            }
          : current,
      );
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/auth");
        return;
      }
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : "Could not mark this notification as read.",
      );
    } finally {
      setPendingId(null);
    }
  }

  async function markAllRead() {
    setMarkingAll(true);
    setActionError("");
    try {
      await markAllTeacherNotificationsRead();
      setData((current) =>
        current
          ? {
              ...current,
              unreadCount: 0,
              notifications: current.notifications.map((item) => ({ ...item, isRead: true })),
            }
          : current,
      );
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/auth");
        return;
      }
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : "Could not mark notifications as read.",
      );
    } finally {
      setMarkingAll(false);
    }
  }

  function reload() {
    setLoading(true);
    setError("");
    setReloadCount((count) => count + 1);
  }

  return (
    <DashboardShell title="Teacher Notifications" user={data?.profile ?? null}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-indigo-700">Teacher workspace</p>
          <h2 className="mt-1 text-2xl font-semibold">Teacher Notifications</h2>
          <p className="mt-1 text-sm text-zinc-600">
            Completion updates appear when every eligible student has submitted an activity.
          </p>
        </div>
        <Link href="/teacher" className="text-sm font-medium text-indigo-700 hover:underline">
          Back to dashboard
        </Link>
      </div>

      <Panel title="Completion notifications">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <label className="min-w-48 space-y-1 text-sm font-medium">
            <span>Activity type</span>
            <select
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
              onChange={(event) => {
                if (
                  event.target.value === "" ||
                  event.target.value === "quiz" ||
                  event.target.value === "homework"
                ) {
                  setLoading(true);
                  setError("");
                  setActivityType(event.target.value);
                }
              }}
              value={activityType}
            >
              <option value="">All activities</option>
              <option value="quiz">Quizzes</option>
              <option value="homework">Homework</option>
            </select>
          </label>
          <button
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50"
            disabled={!data?.unreadCount || markingAll}
            onClick={() => void markAllRead()}
            type="button"
          >
            {markingAll ? "Updating…" : "Mark all as read"}
          </button>
        </div>

        {actionError && <ErrorBanner message={actionError} />}
        {loading ? (
          <LoadingState />
        ) : error ? (
          <div className="space-y-3">
            <ErrorBanner message={error} />
            <button
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100"
              onClick={reload}
              type="button"
            >
              Try again
            </button>
          </div>
        ) : data?.notifications.length ? (
          <ul className="divide-y divide-zinc-100">
            {data.notifications.map((notification) => (
              <li
                className={`flex flex-wrap items-start justify-between gap-4 py-4 ${
                  notification.isRead ? "" : "rounded-lg bg-indigo-50/60 px-3"
                }`}
                key={notification.id}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold">{notification.title}</h3>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        notification.isRead
                          ? "bg-zinc-100 text-zinc-600"
                          : "bg-indigo-100 text-indigo-800"
                      }`}
                    >
                      {notification.isRead ? "Read" : "Unread"}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-zinc-700">{notification.message}</p>
                  <p className="mt-2 text-xs text-zinc-500">
                    {notification.activityType === "quiz" ? "Quiz" : "Homework"} ·{" "}
                    {notification.audienceName} · {notification.submittedCount} /{" "}
                    {notification.eligibleCount} submitted · {formatDate(notification.createdAt)}
                  </p>
                  <Link
                    className="mt-2 inline-block text-sm font-medium text-indigo-700 hover:underline"
                    href={notification.relatedUrl ?? "/teacher/submissions"}
                  >
                    Open submissions
                  </Link>
                </div>
                {!notification.isRead && (
                  <button
                    className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-white disabled:opacity-50"
                    disabled={pendingId === notification.id}
                    onClick={() => void markRead(notification)}
                    type="button"
                  >
                    {pendingId === notification.id ? "Updating…" : "Mark as read"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState>
            {activityType
              ? "No completion notifications match this activity type."
              : "Completion notifications will appear here after every eligible student submits an activity."}
          </EmptyState>
        )}
      </Panel>
    </DashboardShell>
  );
}
