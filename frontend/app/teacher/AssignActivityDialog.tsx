"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ErrorBanner } from "@/app/components/DashboardShell";
import {
  assignHomework,
  fetchHomeworkRecipients,
  type HomeworkRecipients,
  type TeacherDashboardData,
} from "@/services/dashboardApi";

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500";
const buttonClass =
  "rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50";

function defaultDueDate() {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return date.toLocaleDateString("en-CA");
}

export function AssignActivityDialog({
  materials,
  onClose,
}: {
  materials: TeacherDashboardData["materials"];
  onClose: () => void;
}) {
  const [recipients, setRecipients] = useState<HomeworkRecipients | null>(null);
  const [recipientsError, setRecipientsError] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [title, setTitle] = useState("");
  const [activityType, setActivityType] = useState<"quiz" | "homework">("quiz");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState(defaultDueDate);
  const [availableFrom, setAvailableFrom] = useState("");
  const [studentIds, setStudentIds] = useState<number[]>([]);
  const [groupIds, setGroupIds] = useState<number[]>([]);
  const [classIds, setClassIds] = useState<number[]>([]);
  const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | "">("");
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [randomizeQuestions, setRandomizeQuestions] = useState(true);
  const [randomizeOptions, setRandomizeOptions] = useState(true);
  const [loadingRecipients, setLoadingRecipients] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [closing, setClosing] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const quizzes = materials.filter((material) => material.questionCount > 0);

  const closeDialog = useCallback(() => {
    if (closing) return;
    setClosing(true);
    closeTimer.current = setTimeout(onClose, 160);
  }, [closing, onClose]);

  useEffect(() => {
    let active = true;
    fetchHomeworkRecipients()
      .then((result) => {
        if (active) setRecipients(result);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setRecipientsError(
            requestError instanceof Error
              ? requestError.message
              : "Could not load students and groups.",
          );
        }
      })
      .finally(() => {
        if (active) setLoadingRecipients(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !assigning) closeDialog();
    };
    document.addEventListener("keydown", handleKeyDown);
    dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [assigning, closeDialog]);

  useEffect(
    () => () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
    },
    [],
  );

  const toggleId = (ids: number[], id: number, setIds: (next: number[]) => void) => {
    setIds(ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    const selectedMaterial = quizzes.find((item) => String(item.id) === materialId);
    if (!selectedMaterial) {
      setError("Choose a quiz to assign.");
      return;
    }
    if (!studentIds.length && !groupIds.length && !classIds.length) {
      setError("Select at least one student, group, or class.");
      return;
    }
    setAssigning(true);
    try {
      const result = await assignHomework({
        title: title.trim(),
        activityType,
        description: description.trim() || undefined,
        materialId: selectedMaterial.id,
        dueDate,
        availableFrom: availableFrom ? new Date(availableFrom).toISOString() : undefined,
        studentIds,
        groupIds,
        classIds,
        timeLimitMinutes: timeLimitMinutes ? Number(timeLimitMinutes) : undefined,
        maxAttempts: maxAttempts ? Number(maxAttempts) : 1,
        randomizeQuestions,
        randomizeOptions,
      });
      setSuccess(`“${result.title}” is now available to the selected students.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not assign this activity.");
    } finally {
      setAssigning(false);
    }
  };

  const isRecipientSelected =
    studentIds.length > 0 || groupIds.length > 0 || classIds.length > 0;

  return (
    <div
      className={`popup-overlay fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/40 p-4 ${
        closing ? "popup-overlay-closing" : ""
      }`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !assigning) closeDialog();
      }}
    >
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-activity-title"
        tabIndex={-1}
        className={`popup-panel max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl sm:p-7 ${
          closing ? "popup-panel-closing" : ""
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="assign-activity-title" className="text-xl font-semibold">Assign Activity</h2>
            <p className="mt-1 text-sm text-zinc-600">
              Assign an existing quiz to selected students, groups, or classes.
            </p>
          </div>
          <button
            type="button"
            onClick={closeDialog}
            disabled={assigning}
            aria-label="Close assignment dialog"
            className="rounded-lg px-2 py-1 text-xl text-zinc-500 hover:bg-zinc-100 disabled:opacity-50"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <ErrorBanner message={error || recipientsError} />
          {success && (
            <p role="status" className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
              {success} Assignment notifications were sent through the existing notification workflow.
            </p>
          )}
          <label className="block space-y-1 text-sm font-medium">
            <span>Existing quiz</span>
            <select
              required
              value={materialId}
              disabled={!!success}
              onChange={(event) => {
                const nextId = event.target.value;
                setMaterialId(nextId);
                const selected = quizzes.find((item) => String(item.id) === nextId);
                if (selected) setTitle(selected.title);
              }}
              className={inputClass}
            >
              <option value="">Choose a quiz</option>
              {quizzes.map((quiz) => (
                <option key={quiz.id} value={quiz.id}>{quiz.title}</option>
              ))}
            </select>
            {!loadingRecipients && quizzes.length === 0 && (
              <span className="block text-sm font-normal text-zinc-500">
                No saved quizzes yet. Create and post a quiz first.
              </span>
            )}
          </label>
          <label className="block space-y-1 text-sm font-medium">
            <span>Activity type</span>
            <select
              value={activityType}
              disabled={!!success}
              onChange={(event) => {
                if (event.target.value === "quiz" || event.target.value === "homework") {
                  setActivityType(event.target.value);
                }
              }}
              className={inputClass}
            >
              <option value="quiz">Quiz</option>
              <option value="homework">Homework</option>
            </select>
          </label>
          <label className="block space-y-1 text-sm font-medium">
            <span>Homework title</span>
            <input
              required
              maxLength={200}
              value={title}
              disabled={!!success}
              onChange={(event) => setTitle(event.target.value)}
              className={inputClass}
            />
          </label>
          <label className="block space-y-1 text-sm font-medium">
            <span>Instructions (optional)</span>
            <textarea
              maxLength={4000}
              value={description}
              disabled={!!success}
              onChange={(event) => setDescription(event.target.value)}
              className={inputClass}
              rows={3}
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1 text-sm font-medium">
              <span>Due date</span>
              <input
                required
                type="date"
                min={new Date().toLocaleDateString("en-CA")}
                value={dueDate}
                disabled={!!success}
                onChange={(event) => setDueDate(event.target.value)}
                className={inputClass}
              />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              <span>Available from (optional)</span>
              <input
                type="datetime-local"
                value={availableFrom}
                disabled={!!success}
                onChange={(event) => setAvailableFrom(event.target.value)}
                className={inputClass}
              />
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1 text-sm font-medium">
              <span>Time limit in minutes (optional)</span>
              <input
                type="number"
                min={1}
                max={360}
                placeholder="e.g. 30 (leave blank for untimed)"
                value={timeLimitMinutes}
                disabled={!!success}
                onChange={(event) =>
                  setTimeLimitMinutes(
                    event.target.value === "" ? "" : Math.max(1, parseInt(event.target.value, 10)),
                  )
                }
                className={inputClass}
              />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              <span>Maximum attempts allowed</span>
              <input
                type="number"
                min={1}
                max={10}
                value={maxAttempts}
                disabled={!!success}
                onChange={(event) =>
                  setMaxAttempts(Math.max(1, parseInt(event.target.value, 10) || 1))
                }
                className={inputClass}
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-4 pt-1">
            <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
              <input
                type="checkbox"
                checked={randomizeQuestions}
                disabled={!!success}
                onChange={(e) => setRandomizeQuestions(e.target.checked)}
                className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
              />
              Randomize question sequence
            </label>
            <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
              <input
                type="checkbox"
                checked={randomizeOptions}
                disabled={!!success}
                onChange={(e) => setRandomizeOptions(e.target.checked)}
                className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
              />
              Randomize answer options
            </label>
          </div>

          {loadingRecipients ? (
            <p role="status" className="text-sm text-zinc-500">Loading students and groups…</p>
          ) : recipients ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <fieldset className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-zinc-200 p-3">
                <legend className="px-1 text-sm font-semibold">Students</legend>
                {recipients.students.length ? recipients.students.map((student) => (
                  <label key={student.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={studentIds.includes(student.id)}
                      disabled={!!success}
                      onChange={() => toggleId(studentIds, student.id, setStudentIds)}
                    />
                    {student.usn ?? "USN pending"} · {student.fullName}
                  </label>
                )) : <p className="text-sm text-zinc-500">No student accounts found.</p>}
              </fieldset>
              <fieldset className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-zinc-200 p-3">
                <legend className="px-1 text-sm font-semibold">Your groups</legend>
                {recipients.groups.length ? recipients.groups.map((group) => (
                  <label key={group.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={groupIds.includes(group.id)}
                      disabled={!!success}
                      onChange={() => toggleId(groupIds, group.id, setGroupIds)}
                    />
                    {group.name}
                  </label>
                )) : <p className="text-sm text-zinc-500">No groups managed by you.</p>}
              </fieldset>
              <fieldset className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-zinc-200 p-3">
                <legend className="px-1 text-sm font-semibold">Your classes</legend>
                {recipients.classes.length ? recipients.classes.map((teacherClass) => (
                  <label key={teacherClass.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={classIds.includes(teacherClass.id)}
                      disabled={!!success}
                      onChange={() => toggleId(classIds, teacherClass.id, setClassIds)}
                    />
                    {teacherClass.name}
                  </label>
                )) : <p className="text-sm text-zinc-500">Create a class to assign to its students.</p>}
              </fieldset>
            </div>
          ) : null}

          <div className="flex flex-wrap justify-end gap-3 border-t border-zinc-200 pt-4">
            <button
              type="button"
              onClick={closeDialog}
              disabled={assigning}
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              {success ? "Close" : "Cancel"}
            </button>
            <button
              type="submit"
              disabled={
                !recipients ||
                loadingRecipients ||
                assigning ||
                !!success ||
                !materialId ||
                !title.trim() ||
                !dueDate ||
                !isRecipientSelected
              }
              className={buttonClass}
            >
              {assigning ? "Assigning…" : success ? "Assigned ✓" : "Assign homework"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
