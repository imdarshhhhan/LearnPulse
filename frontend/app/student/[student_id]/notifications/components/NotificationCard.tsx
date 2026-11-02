import Link from "next/link";

import type { StudentNotification } from "@/services/notificationsApi";

import styles from "../notifications.module.css";

const typeLabels: Record<StudentNotification["type"], string> = {
  assignment: "Homework",
  quiz: "Quiz",
  submission: "Submission",
  group_invite: "Group",
};

export function NotificationCard({
  notification,
  onMarkRead,
  busy,
}: {
  notification: StudentNotification;
  onMarkRead: (id: number) => void;
  busy: boolean;
}) {
  const createdAt = notification.createdAt
    ? new Date(notification.createdAt).toLocaleString()
    : "Time unavailable";

  return (
    <article className={`${styles.card} ${notification.isRead ? "" : styles.unread}`}>
      <div className={styles.cardMain}>
        <div className={styles.cardHeading}>
          <span className={styles.type}>{typeLabels[notification.type]}</span>
          {!notification.isRead && <span className={styles.unreadLabel}>Unread</span>}
        </div>
        <h2 className={styles.title}>{notification.title}</h2>
        <p className={styles.message}>{notification.message}</p>
        <time className={styles.time} dateTime={notification.createdAt ?? undefined}>
          {createdAt}
        </time>
      </div>
      <div className={styles.actions}>
        {notification.relatedUrl && (
          <Link className={styles.openLink} href={notification.relatedUrl}>
            Open
          </Link>
        )}
        {!notification.isRead && (
          <button
            className={styles.readButton}
            type="button"
            disabled={busy}
            onClick={() => onMarkRead(notification.id)}
          >
            Mark as read
          </button>
        )}
      </div>
    </article>
  );
}
