import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LearnPulse — Adaptive Assessment & Learning Platform",
  description: "AI-augmented assessment generation, psychometrics, and continuous mastery tracking",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
