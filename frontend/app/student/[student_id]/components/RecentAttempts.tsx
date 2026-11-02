import { formatDate } from "@/lib/format";
import type { StudentDashboardData } from "@/services/dashboardApi";

import styles from "../student.module.css";

export function RecentAttempts({
  attempts,
}: {
  attempts: StudentDashboardData["recentAttempts"];
}) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <h2 className={styles.panelTitle}>Recent attempts</h2>
          <p className={styles.panelDescription}>A snapshot of your recent quiz work.</p>
        </div>
      </div>
      {attempts.length === 0 ? (
        <p className={styles.emptyState}>Your quiz attempts and scores will show up here.</p>
      ) : (
        <ul className={styles.attemptList}>
          {attempts.map((attempt) => (
            <li key={attempt.id} className={styles.attempt}>
              <div>
                <h3 className={styles.assignmentTitle}>{attempt.assignmentTitle}</h3>
                <p className={styles.assignmentMeta}>{formatDate(attempt.attemptedAt)}</p>
              </div>
              <span className={styles.attemptScore}>{attempt.scorePercent}%</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
