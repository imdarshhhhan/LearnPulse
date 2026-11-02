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
    <div className="flex min-h-screen flex-col bg-[#f8fafc] text-[#0f172a]">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur-md">
        <div className="flex w-full items-center justify-between gap-4 px-4 py-3.5 sm:px-8 lg:px-12 max-w-[1520px] mx-auto">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white font-bold shadow-sm shadow-blue-500/25 transition-transform group-hover:scale-105">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
              </div>
              <span className="text-xl sm:text-2xl font-black tracking-tight">
                <span className="text-blue-600">Learn</span>
                <span className="text-slate-900">Pulse</span>
              </span>
            </Link>

            <span className="hidden sm:inline-block text-slate-300">|</span>

            <div className="hidden sm:block">
              <h1 className="text-sm sm:text-base font-semibold tracking-tight text-slate-800">{title}</h1>
              {user && (
                <p className="text-xs text-slate-500">
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
                  className="rounded-xl px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  Folders
                </Link>
                <Link
                  href="/study-spaces"
                  className="rounded-xl px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  Study Spaces
                </Link>
              </>
            )}
            {isTeacher && (
              <>
                <Link
                  href="/teacher/classes"
                  className="rounded-xl px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  Classes
                </Link>
                <Link
                  href="/teacher/performance"
                  className="rounded-xl px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  Analytics &amp; Heatmap
                </Link>
                <Link
                  href="/teacher/submissions"
                  className="rounded-xl px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
                >
                  Submissions
                </Link>
              </>
            )}
            <button
              type="button"
              onClick={handleSignOut}
              className="ml-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 shadow-xs transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="flex w-full flex-1 flex-col space-y-8 px-4 py-8 sm:px-8 sm:py-10 lg:px-12 max-w-[1520px] mx-auto">
        {children}
      </main>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sublabel,
  icon,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="saas-card rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm transition-all hover:border-slate-300 hover:shadow-md">
      <div className="flex items-center justify-between">
        <p className="text-xs sm:text-sm font-semibold uppercase tracking-wider text-slate-500">{label}</p>
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
            {icon}
          </div>
        )}
      </div>
      <p className="mt-3 text-3xl sm:text-4xl font-black tracking-tight text-slate-900">{value}</p>
      {sublabel && <p className="mt-1.5 text-xs sm:text-sm font-medium text-slate-400">{sublabel}</p>}
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
    <section className="saas-card rounded-2xl border border-slate-200/80 bg-white p-6 sm:p-8 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
          {description && <p className="mt-1 text-sm text-slate-500 leading-relaxed">{description}</p>}
        </div>
        {action}
      </div>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 px-6 py-12 text-center">
      <p className="text-sm sm:text-base font-medium text-slate-500">{children}</p>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="rounded-2xl border border-rose-200 bg-rose-50/80 px-5 py-3.5 text-sm font-medium text-rose-800"
    >
      {message}
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="h-8 w-8 animate-spin rounded-full border-3 border-blue-600 border-t-transparent" />
      <p className="mt-3.5 text-sm font-medium text-slate-500">Loading workspace…</p>
    </div>
  );
}
