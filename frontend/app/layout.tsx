import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quizora — Adaptive Learning Platform",
  description: "Source-grounded adaptive quiz generation and mastery tracking",
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
