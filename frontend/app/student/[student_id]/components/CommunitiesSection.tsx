import Link from "next/link";

import type { Community } from "@/services/socialApi";

import styles from "../student.module.css";

const communitiesHref = "/study-spaces?tab=communities";

export function CommunitiesSection({
  communities,
  error,
}: {
  communities: Community[] | null;
  error: string;
}) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <h2 className={styles.panelTitle}>Joined communities</h2>
          <p className={styles.panelDescription}>Keep up with learning conversations.</p>
        </div>
        <Link href={communitiesHref} className={styles.panelAction}>View communities</Link>
      </div>
      {error ? (
        <p className={styles.sectionError}>{error}</p>
      ) : communities?.length ? (
        <ul className={styles.resourceList}>
          {communities.slice(0, 3).map((community) => (
            <li key={community.id}>
              <Link href={communitiesHref} className={styles.resourceLink}>
                <span className={styles.resourceIcon} aria-hidden="true">◉</span>
                <span className={styles.resourceName}>{community.name}</span>
                <span className={styles.resourceMeta}>
                  {community.memberCount} {community.memberCount === 1 ? "member" : "members"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className={styles.emptyResource}>
          <p>{communities ? "You haven’t joined a community yet." : "Your communities could not be loaded."}</p>
          <Link href={communitiesHref} className={styles.inlineAction}>Explore communities</Link>
        </div>
      )}
    </section>
  );
}
