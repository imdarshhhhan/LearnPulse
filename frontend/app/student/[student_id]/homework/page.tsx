"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "@/services/dashboardApi";
import { fetchStudentHomework, type StudentHomeworkResponse } from "@/services/homeworkApi";

import { StudentHeader } from "../components/StudentHeader";
import { HomeworkCard } from "./components/HomeworkCard";
import styles from "./homework.module.css";

export default function StudentHomeworkPage() {
  const params = useParams<{ student_id: string }>();
  const router = useRouter();
  const [data, setData] = useState<StudentHomeworkResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    fetchStudentHomework()
      .then((result) => {
        if (!active) return;
        if (String(result.studentId) !== params.student_id) {
          router.replace(`/student/${result.studentId}/homework`);
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
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load your homework.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [params.student_id, reloadKey, router]);

  return (
    <div className={styles.page}>
      {data && <StudentHeader user={data.profile} />}
      <main className={styles.main}>
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>Your learning space</p>
            <h1 className={styles.pageTitle}>Created Homework</h1>
            <p className={styles.pageDescription}>
              Homework assigned to you by your teachers.
            </p>
          </div>
          {data && (
            <Link className={styles.backLink} href={`/student/${data.studentId}`}>
              Back to dashboard
            </Link>
          )}
        </div>
        {loading ? (
          <p className={styles.state} role="status">Loading your homework…</p>
        ) : error ? (
          <div>
            <p className={styles.error} role="alert">{error}</p>
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
          </div>
        ) : data?.assignments.length ? (
          <div className={styles.list}>
            {data.assignments.map((assignment) => (
              <HomeworkCard
                key={assignment.id}
                studentId={data.studentId}
                assignment={assignment}
              />
            ))}
          </div>
        ) : (
          <p className={styles.state}>
            No homework has been assigned to you yet. New work from your teachers will appear here.
          </p>
        )}
      </main>
    </div>
  );
}
