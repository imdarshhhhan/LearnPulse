import Link from "next/link";

import { DashboardShell } from "@/app/components/DashboardShell";

export default function AboutUsPage() {
  return (
    <DashboardShell title="About Quizora" user={null}>
      <section className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">
          Learn with confidence
        </p>
        <h2 className="mt-2 text-2xl font-bold text-slate-900">About Quizora</h2>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          Quizora is a learning platform for study materials, adaptive practice, assignments,
          and collaborative student study spaces.
        </p>
        <Link href="/" className="mt-5 inline-block text-sm font-semibold text-indigo-700 hover:underline">
          Return to your dashboard
        </Link>
      </section>
    </DashboardShell>
  );
}
