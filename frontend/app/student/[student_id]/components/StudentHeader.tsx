import Link from "next/link";

import type { SyncedUser } from "@/services/api";

import { ProfileMenu } from "./ProfileMenu";
import { StudentNavigationDrawer } from "./StudentNavigationDrawer";
import styles from "../student.module.css";

export function StudentHeader({ user }: { user: SyncedUser }) {
  return (
    <header className={styles.header}>
      <div className={styles.headerStart}>
        <StudentNavigationDrawer studentId={user.userId} />
        <Link href={`/student/${user.userId}`} className={styles.brand} aria-label="Quizora dashboard">
          {user.avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.brandAvatar} src={user.avatarUrl} alt="" />
          ) : (
            <span className={styles.brandMark}>Q</span>
          )}
          <span>Quizora</span>
        </Link>
      </div>
      <nav className={styles.headerNav} aria-label="Student navigation">
        <Link href="/folders" className={styles.navLink}>My folders</Link>
        <Link href="/study-spaces?tab=groups" className={styles.navLink}>Groups</Link>
        <Link href="/study-spaces?tab=communities" className={styles.navLink}>Communities</Link>
      </nav>
      <ProfileMenu user={user} />
    </header>
  );
}
