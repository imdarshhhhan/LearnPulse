import Link from "next/link";

import { DashboardShell } from "@/app/components/DashboardShell";

export default function AboutUsPage() {
  return (
    <DashboardShell title="About LearnPulse" user={null}>
      <section className="max-w-4xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-blue-600">
          Learn with confidence
        </p>
        <h2 className="mt-2 text-2xl font-bold text-slate-900">About LearnPulse</h2>
        <p className="mt-3 text-base leading-7 text-slate-600">
          LearnPulse is an AI-augmented educational assessment platform designed for higher education.
          It provides source-grounded question authoring, psychometric item evaluation, continuous mastery tracking,
          and collaborative study spaces for students and faculty.
        </p>
        <Link href="/" className="mt-5 inline-block text-sm font-semibold text-blue-600 hover:underline">
          ← Return to your dashboard
        </Link>
      </section>
    </DashboardShell>
  );
}
