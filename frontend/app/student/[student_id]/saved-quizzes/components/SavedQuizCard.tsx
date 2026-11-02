import Link from "next/link";

import { formatDate } from "@/lib/format";
import type { SavedQuiz } from "@/services/savedQuizzesApi";

import styles from "../saved-quizzes.module.css";

export function SavedQuizCard({
  quiz,
  busy,
  onRemove,
}: {
  quiz: SavedQuiz;
  busy: boolean;
  onRemove: (assignmentId: number) => void;
}) {
  return (
    <article className={styles.card}>
      <div className={styles.cardMain}>
        <div className={styles.cardHeading}>
          <div>
            <h2 className={styles.title}>{quiz.title}</h2>
            <p className={styles.meta}>
              {quiz.topic} · {quiz.teacherName}
            </p>
          </div>
          <span className={styles.questionCount}>
            {quiz.questionCount} {quiz.questionCount === 1 ? "question" : "questions"}
          </span>
        </div>
        <dl className={styles.details}>
          <div>
            <dt>Saved</dt>
            <dd>{formatDate(quiz.savedAt)}</dd>
          </div>
          <div>
            <dt>Due date</dt>
            <dd>{formatDate(quiz.dueDate)}</dd>
          </div>
          {quiz.bestScorePercent !== null && (
            <div>
              <dt>Best score</dt>
              <dd>{quiz.bestScorePercent}%</dd>
            </div>
          )}
        </dl>
      </div>
      <div className={styles.actions}>
        <Link className={styles.openLink} href={`/assignments/${quiz.assignmentId}`}>
          Open quiz
        </Link>
        <button
          className={styles.removeButton}
          type="button"
          disabled={busy}
          onClick={() => onRemove(quiz.assignmentId)}
        >
          {busy ? "Removing…" : "Remove"}
        </button>
      </div>
    </article>
  );
}
