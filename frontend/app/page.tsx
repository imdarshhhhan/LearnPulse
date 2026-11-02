"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { LoadingState } from "@/app/components/DashboardShell";
import { fetchCurrentUser } from "@/services/api";

export default function HomePage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("userToken")) {
      router.replace("/auth");
      return;
    }

    let active = true;
    fetchCurrentUser()
      .then((user) => {
        if (!active) return;
        router.replace(user.role === "teacher" ? "/teacher" : `/student/${user.userId}`);
      })
      .catch((authError: unknown) => {
        if (!active) return;
        localStorage.removeItem("userToken");
        localStorage.removeItem("userRole");
        router.replace("/auth");
        setError(authError instanceof Error ? authError.message : "Could not verify your account.");
      });
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 bg-zinc-50 px-6">
      <LoadingState />
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </main>
  );
}
