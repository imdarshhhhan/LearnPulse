import type { StudentDashboardData } from "@/services/dashboardApi";

import styles from "../student.module.css";

export function OverviewCards({ stats }: { stats: StudentDashboardData["stats"] }) {
  const cards = [
    { label: "Open assignments", value: stats.openAssignments, detail: "Ready to work on", tone: "indigo" },
    { label: "Completed", value: stats.completedAssignments, detail: "Assignments finished", tone: "green" },
    {
      label: "Average score",
      value: stats.averageScorePercent === null ? "—" : `${stats.averageScorePercent}%`,
      detail: "Across your attempts",
      tone: "blue",
    },
    { label: "Concepts tracked", value: stats.conceptsTracked, detail: "Skills in progress", tone: "violet" },
  ] as const;

  return (
    <section className={styles.overviewGrid} aria-label="Learning overview">
      {cards.map((card) => (
        <article key={card.label} className={`${styles.overviewCard} ${styles[card.tone]}`}>
          <p className={styles.overviewLabel}>{card.label}</p>
          <p className={styles.overviewValue}>{card.value}</p>
          <p className={styles.overviewDetail}>{card.detail}</p>
        </article>
      ))}
    </section>
  );
}
