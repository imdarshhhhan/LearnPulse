import { formatDate } from "@/lib/format";
import type { StudentDashboardData } from "@/services/dashboardApi";

import styles from "../student.module.css";

function masteryTone(percent: number): string {
  if (percent >= 70) return styles.masteryHigh;
  if (percent >= 40) return styles.masteryMedium;
  return styles.masteryLow;
}

export function ConceptMastery({
  mastery,
}: {
  mastery: StudentDashboardData["mastery"];
}) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <h2 className={styles.panelTitle}>Concept mastery</h2>
          <p className={styles.panelDescription}>
            Performance-based estimate from weighted question responses; small samples may be less reliable.
          </p>
        </div>
      </div>
      {mastery.length === 0 ? (
        <p className={styles.emptyState}>
          Your progress will appear here as you practice and answer questions.
        </p>
      ) : (
        <ul className={styles.masteryList}>
          {mastery.slice(0, 6).map((concept) => (
            <li key={concept.conceptTag} className={styles.masteryItem}>
              <div className={styles.masteryHeading}>
                <span className={styles.conceptName}>{concept.conceptTag}</span>
                <span className={styles.conceptMeta}>
                  {concept.masteryPercent}% · {concept.sampleSize} questions · {formatDate(concept.lastUpdated)}
                </span>
              </div>
              <div
                className={styles.progressTrack}
                role="progressbar"
                aria-label={`${concept.conceptTag} mastery`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={concept.masteryPercent}
              >
                <span
                  className={`${styles.progressFill} ${masteryTone(concept.masteryPercent)}`}
                  style={{ width: `${Math.max(0, Math.min(100, concept.masteryPercent))}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
