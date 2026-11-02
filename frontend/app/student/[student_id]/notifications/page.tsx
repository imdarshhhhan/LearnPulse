"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/services/dashboardApi";
import {
  fetchStudentNotifications,
  markAllStudentNotificationsRead,
  markStudentNotificationRead,
  type StudentNotificationsResponse,
} from "@/services/notificationsApi";

import { StudentHeader } from "../components/StudentHeader";
import { NotificationCard } from "./components/NotificationCard";
import styles from "./notifications.module.css";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Could not update your notifications.";
}

export default function StudentNotificationsPage() {
  const params = useParams<{ student_id: string }>();
  const router = useRouter();
  const [data, setData] = useState<StudentNotificationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const handleError = useCallback((requestError: unknown) => {
    if (requestError instanceof ApiError && requestError.status === 401) {
      router.replace("/auth");
      return;
    }
    if (requestError instanceof ApiError && requestError.status === 403) {
      router.replace("/teacher");
      return;
    }
    setError(errorMessage(requestError));
  }, [router]);

  useEffect(() => {
    let active = true;
    fetchStudentNotifications()
      .then((result) => {
        if (!active) return;
        if (String(result.studentId) !== params.student_id) {
          router.replace(`/student/${result.studentId}/notifications`);
          return;
        }
        setData(result);
      })
      .catch((requestError: unknown) => {
        if (active) handleError(requestError);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [handleError, params.student_id, reloadKey, router]);

  async function handleMarkRead(notificationId: number) {
    setBusyId(notificationId);
    setError("");
    try {
      await markStudentNotificationRead(notificationId);
      setData((current) => current && ({
        ...current,
        unreadCount: Math.max(0, current.unreadCount - 1),
        notifications: current.notifications.map((notification) =>
          notification.id === notificationId
            ? { ...notification, isRead: true }
            : notification,
        ),
      }));
      window.dispatchEvent(new Event("quizora:notifications-updated"));
    } catch (requestError) {
      handleError(requestError);
    } finally {
      setBusyId(null);
    }
  }

  async function handleMarkAllRead() {
    setMarkingAll(true);
    setError("");
    try {
      await markAllStudentNotificationsRead();
      setData((current) => current && ({
        ...current,
        unreadCount: 0,
        notifications: current.notifications.map((notification) => ({
          ...notification,
          isRead: true,
        })),
      }));
      window.dispatchEvent(new Event("quizora:notifications-updated"));
    } catch (requestError) {
      handleError(requestError);
    } finally {
      setMarkingAll(false);
    }
  }

  return (
    <div className={styles.page}>
      {data && <StudentHeader user={data.profile} />}
      <main className={styles.main}>
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>Your learning space</p>
            <h1 className={styles.pageTitle}>Notifications</h1>
            <p className={styles.pageDescription}>
              Updates about your homework and scheduled quizzes.
            </p>
          </div>
          <div className={styles.actions}>
            {data && (
              <>
                <button
                  className={styles.markAllButton}
                  type="button"
                  disabled={!data.unreadCount || markingAll}
                  onClick={() => void handleMarkAllRead()}
                >
                  {markingAll ? "Marking…" : "Mark all as read"}
                </button>
                <Link className={styles.backLink} href={`/student/${data.studentId}`}>
                  Back to dashboard
                </Link>
              </>
            )}
          </div>
        </div>
        {error && <p className={styles.error} role="alert">{error}</p>}
        {loading ? (
          <p className={styles.state} role="status">Loading your notifications…</p>
        ) : error && !data ? (
          <div>
            <button
              className={styles.retry}
              type="button"
              onClick={() => {
                setLoading(true);
                setError("");
                setReloadKey((key) => key + 1);
              }}
            >
              Try again
            </button>
          </div>
        ) : data?.notifications.length ? (
          <div className={styles.list}>
            {data.notifications.map((notification) => (
              <NotificationCard
                key={notification.id}
                notification={notification}
                busy={busyId === notification.id}
                onMarkRead={(id) => void handleMarkRead(id)}
              />
            ))}
          </div>
        ) : (
          <p className={styles.state}>
            You’re all caught up. New homework and quiz updates will appear here.
          </p>
        )}
      </main>
    </div>
  );
}
