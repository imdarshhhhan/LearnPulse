import Link from "next/link";

import { formatDate } from "@/lib/format";
import type { StudentDashboardData } from "@/services/dashboardApi";

import { SavedQuizAction } from "../../components/SavedQuizAction";
import styles from "../homework.module.css";

const statusLabels: Record<StudentDashboardData["assignments"][number]["status"], string> = {
  upcoming: "Upcoming",
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  overdue: "Overdue",
};

export function HomeworkCard({
  studentId,
  assignment,
}: {
  studentId: number;
  assignment: StudentDashboardData["assignments"][number];
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardMain}>
        <div className={styles.cardTitleRow}>
          <div>
            <h2 className={styles.title}>{assignment.title}</h2>
            <p className={styles.meta}>
              {assignment.materialTitle} · {assignment.teacherName}
            </p>
          </div>
          <span className={`${styles.status} ${styles[assignment.status]}`}>
            {statusLabels[assignment.status]}
          </span>
        </div>
        {assignment.description && (
          <p className={styles.description}>{assignment.description}</p>
        )}
        <dl className={styles.details}>
          <div>
            <dt>Assigned</dt>
            <dd>{formatDate(assignment.assignedAt)}</dd>
          </div>
          <div>
            <dt>Due</dt>
            <dd>{formatDate(assignment.dueDate)}</dd>
          </div>
          {assignment.submissionCount > 0 && (
            <div>
              <dt>Submissions</dt>
              <dd>{assignment.submissionCount}</dd>
            </div>
          )}
          {assignment.bestScorePercent !== null && (
            <div>
              <dt>Best score</dt>
              <dd>{assignment.bestScorePercent}%</dd>
            </div>
          )}
        </dl>
      </div>
      <Link className={styles.action} href={`/assignments/${assignment.id}`}>
        {assignment.status === "completed" ? "Review homework" : "Open homework"}
      </Link>
      {assignment.hasQuiz && (
        <SavedQuizAction
          studentId={studentId}
          assignmentId={assignment.id}
          isSaved={assignment.isSaved}
        />
      )}
    </article>
  );
}
