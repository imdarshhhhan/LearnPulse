"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "@/services/dashboardApi";
import {
  fetchSavedQuizzes,
  removeSavedQuiz,
  type SavedQuizzesResponse,
} from "@/services/savedQuizzesApi";

import { StudentHeader } from "../components/StudentHeader";
import { SavedQuizCard } from "./components/SavedQuizCard";
import styles from "./saved-quizzes.module.css";

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load your saved quizzes.";
}

export default function StudentSavedQuizzesPage() {
  const params = useParams<{ student_id: string }>();
  const router = useRouter();
  const [data, setData] = useState<SavedQuizzesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    fetchSavedQuizzes()
      .then((result) => {
        if (!active) return;
        if (String(result.studentId) !== params.student_id) {
          router.replace(`/student/${result.studentId}/saved-quizzes`);
          return;
        }
        setData(result);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        if (requestError instanceof ApiError && requestError.status === 403) {
          router.replace("/teacher");
          return;
        }
        setError(getErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [params.student_id, reloadKey, router]);

  async function handleRemove(assignmentId: number) {
    setBusyId(assignmentId);
    setError("");
    try {
      await removeSavedQuiz(assignmentId);
      setData((current) => current && ({
        ...current,
        quizzes: current.quizzes.filter((quiz) => quiz.assignmentId !== assignmentId),
      }));
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/auth");
        return;
      }
      if (requestError instanceof ApiError && requestError.status === 403) {
        router.replace("/teacher");
        return;
      }
      setError(getErrorMessage(requestError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className={styles.page}>
      {data && <StudentHeader user={data.profile} />}
      <main className={styles.main}>
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>Your learning space</p>
            <h1 className={styles.pageTitle}>Saved Quizzes</h1>
            <p className={styles.pageDescription}>
              Quizzes you bookmarked from your assigned homework.
            </p>
          </div>
          {data && (
            <Link className={styles.backLink} href={`/student/${data.studentId}`}>
              Back to dashboard
            </Link>
          )}
        </div>
        {error && <p className={styles.error} role="alert">{error}</p>}
        {loading ? (
          <p className={styles.state} role="status">Loading your saved quizzes…</p>
        ) : error && !data ? (
          <button
            className={styles.retry}
            type="button"
            onClick={() => {
              setLoading(true);
              setError("");
              setReloadKey((key) => key + 1);
            }}
          >
            Try again
          </button>
        ) : data?.quizzes.length ? (
          <div className={styles.list}>
            {data.quizzes.map((quiz) => (
              <SavedQuizCard
                key={quiz.id}
                quiz={quiz}
                busy={busyId === quiz.assignmentId}
                onRemove={(assignmentId) => void handleRemove(assignmentId)}
              />
            ))}
          </div>
        ) : (
          <p className={styles.state}>
            No saved quizzes yet. Bookmark an eligible quiz from your homework to keep it here.
          </p>
        )}
      </main>
    </div>
  );
}
