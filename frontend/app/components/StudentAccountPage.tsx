"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { DashboardShell, ErrorBanner, LoadingState } from "@/app/components/DashboardShell";
import {
  fetchCurrentUser,
  updateStudentUSN,
  type SyncedUser,
} from "@/services/api";

export function StudentAccountPage({
  title,
  description,
  kind,
}: {
  title: string;
  description: string;
  kind: "achievements" | "settings";
}) {
  const router = useRouter();
  const [user, setUser] = useState<SyncedUser | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [usn, setUsn] = useState("");
  const [savingUsn, setSavingUsn] = useState(false);
  const [usnMessage, setUsnMessage] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("userToken")) {
      router.replace("/auth");
      return;
    }
    let active = true;
    fetchCurrentUser()
      .then((currentUser) => {
        if (!active) return;
        if (currentUser.role !== "student") {
          router.replace(currentUser.role === "teacher" ? "/teacher" : "/");
          return;
        }
        setUser(currentUser);
      })
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "Could not load your account.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  if (loading) return <LoadingState />;

  return (
    <DashboardShell title={title} user={user}>
      <ErrorBanner message={error} />
      {user && (
        <section className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">
            Student account
          </p>
          <h2 className="mt-2 text-2xl font-bold text-slate-900">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
          <div className="mt-6">
            {kind === "achievements" ? (
              user.achievements?.length ? (
                <ul className="space-y-3">
                  {user.achievements.map((achievement, index) => (
                    <li
                      key={`${String(achievement)}-${index}`}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700"
                    >
                      {typeof achievement === "string"
                        ? achievement
                        : JSON.stringify(achievement)}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-300 px-5 py-8 text-center">
                  <p className="font-medium text-slate-800">No achievements recorded yet</p>
                  <p className="mt-2 text-sm text-slate-500">
                    Keep learning—your account achievements will appear here when they are awarded.
                  </p>
                  <Link
                    href={`/student/${user.userId}`}
                    className="mt-4 inline-block text-sm font-semibold text-indigo-700 hover:underline"
                  >
                    Back to dashboard
                  </Link>
                </div>
              )
            ) : (
              <dl className="divide-y divide-slate-100">
                <div className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr]">
                  <dt className="text-sm font-medium text-slate-500">Full name</dt>
                  <dd className="m-0 text-sm text-slate-900">{user.fullName}</dd>
                </div>
                <div className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr]">
                  <dt className="text-sm font-medium text-slate-500">Email</dt>
                  <dd className="m-0 text-sm text-slate-900">{user.email}</dd>
                </div>
                <div className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr]">
                  <dt className="text-sm font-medium text-slate-500">Account type</dt>
                  <dd className="m-0 text-sm capitalize text-slate-900">{user.role}</dd>
                </div>
                <div className="grid gap-1 py-4 sm:grid-cols-[10rem_1fr]">
                  <dt className="text-sm font-medium text-slate-500">Student USN</dt>
                  <dd className="m-0 text-sm text-slate-900">{user.usn ?? "Not provided"}</dd>
                </div>
                {!user.usn && (
                  <form
                    className="mt-3 space-y-3"
                    onSubmit={async (event) => {
                      event.preventDefault();
                      setSavingUsn(true);
                      setUsnMessage("");
                      try {
                        const updatedUser = await updateStudentUSN(usn);
                        setUser(updatedUser);
                        setUsnMessage("Your USN has been saved.");
                      } catch (saveError: unknown) {
                        setUsnMessage(
                          saveError instanceof Error ? saveError.message : "Could not save your USN.",
                        );
                      } finally {
                        setSavingUsn(false);
                      }
                    }}
                  >
                    <label className="block space-y-1 text-sm font-medium">
                      <span>Add your Student USN</span>
                      <input
                        required
                        minLength={4}
                        maxLength={32}
                        value={usn}
                        onChange={(event) => setUsn(event.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      />
                    </label>
                    {usnMessage && <p role="status" className="text-sm text-slate-600">{usnMessage}</p>}
                    <button
                      type="submit"
                      disabled={savingUsn}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                    >
                      {savingUsn ? "Saving…" : "Save USN"}
                    </button>
                  </form>
                )}
                <p className="pt-3 text-sm leading-6 text-slate-500">
                  Profile editing and preference controls are not currently available.
                </p>
              </dl>
            )}
          </div>
        </section>
      )}
    </DashboardShell>
  );
}
