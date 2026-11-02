"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError } from "@/services/dashboardApi";
import { saveQuiz } from "@/services/savedQuizzesApi";

import styles from "../student.module.css";

export function SavedQuizAction({
  studentId,
  assignmentId,
  isSaved,
}: {
  studentId: number;
  assignmentId: number;
  isSaved: boolean;
}) {
  const router = useRouter();
  const [savedLocally, setSavedLocally] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const saved = isSaved || savedLocally;

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      await saveQuiz(assignmentId);
      setSavedLocally(true);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/auth");
        return;
      }
      if (requestError instanceof ApiError && requestError.status === 403) {
        router.replace("/teacher");
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "Could not save this quiz.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.savedQuizAction}>
      {saved ? (
        <Link
          className={styles.savedQuizLink}
          href={`/student/${studentId}/saved-quizzes`}
        >
          Saved quiz
        </Link>
      ) : (
        <button
          className={styles.savedQuizButton}
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
        >
          {saving ? "Saving…" : "Save quiz"}
        </button>
      )}
      {error && <span className={styles.savedQuizError} role="alert">{error}</span>}
    </div>
  );
}
