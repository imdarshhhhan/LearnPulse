import Link from "next/link";

import type { StudentFolder } from "@/services/foldersApi";

import styles from "../student.module.css";

export function FoldersSection({
  folders,
  error,
}: {
  folders: StudentFolder[] | null;
  error: string;
}) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <h2 className={styles.panelTitle}>My folders</h2>
          <p className={styles.panelDescription}>Your personal study library.</p>
        </div>
        <Link href="/folders" className={styles.panelAction}>View folders</Link>
      </div>
      {error ? (
        <p className={styles.sectionError}>{error}</p>
      ) : folders?.length ? (
        <ul className={styles.resourceList}>
          {folders.slice(0, 3).map((folder) => (
            <li key={folder.id}>
              <Link href="/folders" className={styles.resourceLink}>
                <span className={styles.resourceIcon} aria-hidden="true">▰</span>
                <span className={styles.resourceName}>{folder.name}</span>
                <span className={styles.resourceMeta}>
                  {folder.documentCount} {folder.documentCount === 1 ? "file" : "files"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className={styles.emptyResource}>
          <p>{folders ? "No folders yet. Create one for a subject or exam." : "Your folders could not be loaded."}</p>
          <Link href="/folders" className={styles.inlineAction}>Open my folders</Link>
        </div>
      )}
    </section>
  );
}
