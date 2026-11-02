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
        <Link href={`/student/${user.userId}`} className="flex items-center gap-3 no-underline" aria-label="LearnPulse dashboard">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span className="text-xl font-bold tracking-tight">
            <span className="text-blue-600">Learn</span>
            <span className="text-slate-900">Pulse</span>
          </span>
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
