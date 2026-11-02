import Link from "next/link";

import { formatDate } from "@/lib/format";
import type { StudentDashboardData } from "@/services/dashboardApi";

import { SavedQuizAction } from "./SavedQuizAction";
import styles from "../student.module.css";

const statusLabel = {
  upcoming: "Upcoming",
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  overdue: "Overdue",
} as const;

interface AssignedHomeworkProps {
  studentId: number;
  assignments: StudentDashboardData["assignments"];
}

export function AssignedHomework({ studentId, assignments }: AssignedHomeworkProps) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <h2 className={styles.panelTitle}>Assigned homework</h2>
          <p className={styles.panelDescription}>Your assignments, ordered by due date.</p>
        </div>
        <Link className={styles.panelAction} href={`/student/${studentId}/homework`}>
          View all
        </Link>
      </div>
      {assignments.length === 0 ? (
        <p className={styles.emptyState}>
          Nothing assigned yet. New homework from your teachers will appear here.
        </p>
      ) : (
        <ul className={styles.assignmentList}>
          {assignments.map((assignment) => (
            <li key={assignment.id} className={styles.assignment}>
              <div className={styles.assignmentMain}>
                <h3 className={styles.assignmentTitle}>{assignment.title}</h3>
                <p className={styles.assignmentMeta}>
                  {assignment.materialTitle} · {assignment.teacherName}
                </p>
              </div>
              <div className={styles.assignmentProgress}>
                <span className={`${styles.status} ${styles[assignment.status]}`}>
                  {statusLabel[assignment.status]}
                </span>
                <span className={styles.dueDate}>Due {formatDate(assignment.dueDate)}</span>
                <div
                  className={styles.assignmentProgressTrack}
                  role="progressbar"
                  aria-label={`${assignment.title} progress`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={assignment.status === "completed" ? 100 : 0}
                >
                  <span
                    className={styles.assignmentProgressFill}
                    style={{ width: assignment.status === "completed" ? "100%" : "0%" }}
                  />
                </div>
              </div>
              {assignment.bestScorePercent !== null && (
                <span className={styles.assignmentScore}>
                  Best {assignment.bestScorePercent}%
                </span>
              )}
              <Link
                className={styles.assignmentAction}
                href={`/assignments/${assignment.id}`}
              >
                {assignment.status === "completed" ? "Review" : "Start"}
              </Link>
              {assignment.hasQuiz && (
                <SavedQuizAction
                  studentId={studentId}
                  assignmentId={assignment.id}
                  isSaved={assignment.isSaved}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
