import Link from "next/link";

import type { StudyGroup } from "@/services/socialApi";

import styles from "../student.module.css";

const groupsHref = "/study-spaces?tab=groups";

export function GroupsSection({ groups, error }: { groups: StudyGroup[] | null; error: string }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <h2 className={styles.panelTitle}>My groups</h2>
          <p className={styles.panelDescription}>Study and share with your peers.</p>
        </div>
        <Link href={groupsHref} className={styles.panelAction}>View groups</Link>
      </div>
      {error ? (
        <p className={styles.sectionError}>{error}</p>
      ) : groups?.length ? (
        <ul className={styles.resourceList}>
          {groups.slice(0, 3).map((group) => (
            <li key={group.id}>
              <Link href={groupsHref} className={styles.resourceLink}>
                <span className={styles.resourceIcon} aria-hidden="true">◎</span>
                <span className={styles.resourceName}>{group.name}</span>
                <span className={styles.resourceMeta}>
                  {group.memberCount} {group.memberCount === 1 ? "member" : "members"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className={styles.emptyResource}>
          <p>{groups ? "No groups yet. Join with an invite code or create a group." : "Your groups could not be loaded."}</p>
          <Link href={groupsHref} className={styles.inlineAction}>Explore study groups</Link>
        </div>
      )}
    </section>
  );
}
