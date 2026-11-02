"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/services/dashboardApi";
import {
  fetchStudentFeedback,
  saveStudentFeedback,
  type FeedbackCategory,
  type StudentFeedbackDraft,
} from "@/services/feedbackApi";

import styles from "./assignment.module.css";

const categories: { value: FeedbackCategory; label: string }[] = [
  { value: "content", label: "Content" },
  { value: "difficulty", label: "Difficulty" },
  { value: "experience", label: "Learning experience" },
  { value: "other", label: "Other" },
];

export function AssignmentFeedbackForm({ assignmentId }: { assignmentId: number }) {
  const router = useRouter();
  const [draft, setDraft] = useState<StudentFeedbackDraft>({
    message: "",
    category: "",
    rating: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasSavedFeedback, setHasSavedFeedback] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    fetchStudentFeedback(assignmentId)
      .then(({ feedback }) => {
        if (!active || !feedback) return;
        setDraft({
          message: feedback.message,
          category: feedback.category ?? "",
          rating: feedback.rating ?? "",
        });
        setHasSavedFeedback(true);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load your feedback.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [assignmentId, router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await saveStudentFeedback(assignmentId, draft);
      setHasSavedFeedback(true);
      setNotice("Your feedback has been saved.");
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        router.replace("/auth");
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save your feedback.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={styles.feedback}>
      <p className={styles.eyebrow}>Student feedback</p>
      <h2 className={styles.feedbackTitle}>Share your thoughts</h2>
      <p className={styles.description}>
        Your feedback is shared with the teacher who assigned this activity.
      </p>
      {loading ? (
        <p className={styles.instructions} role="status">Loading your saved feedback…</p>
      ) : (
        <form className={styles.feedbackForm} onSubmit={handleSubmit}>
          <label className={styles.feedbackLabel}>
            Feedback
            <textarea
              className={styles.feedbackInput}
              maxLength={2000}
              minLength={1}
              onChange={(event) => setDraft({ ...draft, message: event.target.value })}
              required
              rows={4}
              value={draft.message}
            />
          </label>
          <div className={styles.feedbackOptions}>
            <label className={styles.feedbackLabel}>
              Category (optional)
              <select
                className={styles.feedbackInput}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    category: event.target.value as FeedbackCategory | "",
                  })
                }
                value={draft.category}
              >
                <option value="">Choose a category</option>
                {categories.map((category) => (
                  <option key={category.value} value={category.value}>{category.label}</option>
                ))}
              </select>
            </label>
            <label className={styles.feedbackLabel}>
              Rating (optional)
              <select
                className={styles.feedbackInput}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    rating: event.target.value ? Number(event.target.value) : "",
                  })
                }
                value={draft.rating}
              >
                <option value="">No rating</option>
                {[5, 4, 3, 2, 1].map((rating) => (
                  <option key={rating} value={rating}>{rating} / 5</option>
                ))}
              </select>
            </label>
          </div>
          {error && <p className={styles.error} role="alert">{error}</p>}
          {notice && <p className={styles.feedbackNotice} role="status">{notice}</p>}
          <button className={styles.submitButton} disabled={saving} type="submit">
            {saving ? "Saving…" : hasSavedFeedback ? "Update feedback" : "Send feedback"}
          </button>
        </form>
      )}
    </section>
  );
}
