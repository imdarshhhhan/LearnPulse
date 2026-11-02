"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchUnreadNotificationCount } from "@/services/notificationsApi";

import styles from "../student.module.css";

export function StudentNavigationDrawer({ studentId }: { studentId: number }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [countError, setCountError] = useState("");
  const homeworkHref = `/student/${studentId}/homework`;
  const homeworkActive = pathname === homeworkHref;
  const notificationsHref = `/student/${studentId}/notifications`;
  const notificationsActive = pathname === notificationsHref;
  const savedQuizzesHref = `/student/${studentId}/saved-quizzes`;
  const savedQuizzesActive = pathname === savedQuizzesHref;

  useEffect(() => {
    let active = true;
    const refreshCount = () => {
      fetchUnreadNotificationCount()
        .then((result) => {
          if (!active) return;
          setUnreadCount(result.unreadCount);
          setCountError("");
        })
        .catch((error: unknown) => {
          if (!active) return;
          setCountError(error instanceof Error ? error.message : "Could not load unread count.");
        });
    };
    refreshCount();
    window.addEventListener("quizora:notifications-updated", refreshCount);
    return () => {
      active = false;
      window.removeEventListener("quizora:notifications-updated", refreshCount);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <div className={styles.drawerRoot}>
      <button
        type="button"
        className={styles.drawerToggle}
        aria-label="Open student navigation"
        aria-expanded={open}
        aria-controls="student-navigation-drawer"
        onClick={() => setOpen((current) => !current)}
      >
        <span aria-hidden="true">☰</span>
      </button>
      {open && (
        <>
          <button
            type="button"
            className={styles.drawerBackdrop}
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
          <nav
            id="student-navigation-drawer"
            className={styles.drawerPanel}
            aria-label="Student navigation"
          >
            <p className={styles.drawerHeading}>Learning space</p>
            <Link
              href={homeworkHref}
              aria-current={homeworkActive ? "page" : undefined}
              className={`${styles.drawerLink} ${homeworkActive ? styles.drawerLinkActive : ""}`}
              onClick={() => setOpen(false)}
            >
              <span className={styles.drawerIcon} aria-hidden="true">▤</span>
              Homework
            </Link>
            <Link
              href={notificationsHref}
              aria-current={notificationsActive ? "page" : undefined}
              className={`${styles.drawerLink} ${notificationsActive ? styles.drawerLinkActive : ""}`}
              onClick={() => setOpen(false)}
            >
              <span className={styles.drawerIcon} aria-hidden="true">◉</span>
              <span className={styles.drawerLinkLabel}>Notifications</span>
              {unreadCount > 0 && (
                <span className={styles.unreadBadge} aria-label={`${unreadCount} unread notifications`}>
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
            {countError && (
              <p className={styles.drawerError} role="status">{countError}</p>
            )}
            <Link
              href={savedQuizzesHref}
              aria-current={savedQuizzesActive ? "page" : undefined}
              className={`${styles.drawerLink} ${savedQuizzesActive ? styles.drawerLinkActive : ""}`}
              onClick={() => setOpen(false)}
            >
              <span className={styles.drawerIcon} aria-hidden="true">☆</span>
              Saved Quizzes
            </Link>
          </nav>
        </>
      )}
    </div>
  );
}
