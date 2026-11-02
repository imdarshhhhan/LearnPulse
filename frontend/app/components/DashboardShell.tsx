"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";

import type { SyncedUser } from "@/services/api";

function subscribeToStoredRole(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

function getStoredStudentRole() {
  return localStorage.getItem("userRole") === "student";
}

function getStoredTeacherRole() {
  return localStorage.getItem("userRole") === "teacher";
}

export function DashboardShell({
  title,
  user,
  children,
}: {
  title: string;
  user: SyncedUser | null;
  children: ReactNode;
}) {
  const router = useRouter();
  const storedStudentRole = useSyncExternalStore(
    subscribeToStoredRole,
    getStoredStudentRole,
    () => false,
  );
  const storedTeacherRole = useSyncExternalStore(
    subscribeToStoredRole,
    getStoredTeacherRole,
    () => false,
  );
  const isStudent = user?.role === "student" || storedStudentRole;
  const isTeacher = user?.role === "teacher" || storedTeacherRole;

  const handleSignOut = () => {
    localStorage.removeItem("userToken");
    localStorage.removeItem("userRole");
    router.replace("/auth");
  };

  return (
    <div className="flex min-h-screen flex-col bg-[#fbfbfd] text-[#1d1d1f]">
      <header className="sticky top-0 z-30 border-b border-black/[0.06] bg-white/80 backdrop-blur-md">
        <div className="flex w-full items-center justify-between gap-4 px-6 py-3.5 sm:px-10 lg:px-12">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 font-semibold text-white shadow-sm">
              Q
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-zinc-900">{title}</h1>
              {user && (
                <p className="text-xs text-zinc-500">
                  {user.fullName} · {user.email}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isStudent && (
              <>
                <Link
                  href="/folders"
                  className="rounded-full px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
                >
                  Folders
                </Link>
                <Link
                  href="/study-spaces"
                  className="rounded-full px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
                >
                  Study spaces
                </Link>
              </>
            )}
            {isTeacher && (
              <>
                <Link
                  href="/teacher/classes"
                  className="rounded-full px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
                >
                  Classes
                </Link>
                <Link
                  href="/teacher/performance"
                  className="rounded-full px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
                >
                  Analytics & Heatmap
                </Link>
                <Link
                  href="/teacher/submissions"
                  className="rounded-full px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
                >
                  Submissions
                </Link>
              </>
            )}
            <button
              type="button"
              onClick={handleSignOut}
              className="ml-2 rounded-full border border-zinc-200/80 bg-white px-3.5 py-1.5 text-xs font-medium text-zinc-700 shadow-2xs transition-colors hover:bg-zinc-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="flex w-full flex-1 flex-col space-y-8 px-6 py-8 sm:px-10 sm:py-10 lg:px-12 max-w-7xl mx-auto">
        {children}
      </main>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
}) {
  return (
    <div className="apple-card p-5">
      <p className="text-xs font-medium text-zinc-500">{label}</p>
      <p className="mt-1.5 text-3xl font-semibold tracking-tight text-zinc-900">{value}</p>
      {sublabel && <p className="mt-1 text-xs text-zinc-400">{sublabel}</p>}
    </div>
  );
}

export function Panel({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="apple-card p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-900">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-zinc-500">{description}</p>}
        </div>
        {action}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-zinc-200/80 bg-zinc-50/50 px-6 py-10 text-center">
      <p className="text-sm text-zinc-500">{children}</p>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="rounded-2xl border border-rose-200 bg-rose-50/70 px-4 py-3 text-sm text-rose-800 backdrop-blur-xs"
    >
      {message}
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
      <p className="mt-3 text-xs text-zinc-500 font-medium">Loading workspace…</p>
    </div>
  );
}
