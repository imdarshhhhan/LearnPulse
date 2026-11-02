"use client";

import Link from "next/link";
import { useState } from "react";

import {
  DashboardShell,
  EmptyState,
  ErrorBanner,
  Panel,
} from "@/app/components/DashboardShell";
import { createTest, type GeneratedQuestion } from "@/services/api";
import {
  assignHomework,
  fetchHomeworkRecipients,
  generateTestFromUpload,
  postTest,
  type HomeworkRecipients,
} from "@/services/dashboardApi";
import { QuestionEditor } from "./QuestionEditor";

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500";
const buttonClass =
  "rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50";

function defaultDueDate() {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return date.toLocaleDateString("en-CA");
}

export default function CreateTestPage() {
  const [quizTitle, setQuizTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceText, setSourceText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);
  const [generatedTopic, setGeneratedTopic] = useState("");
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState("");
  const [posted, setPosted] = useState("");
  const [materialId, setMaterialId] = useState<number | null>(null);
  const [recipients, setRecipients] = useState<HomeworkRecipients | null>(null);
  const [recipientsError, setRecipientsError] = useState("");
  const [homeworkTitle, setHomeworkTitle] = useState("");
  const [homeworkDescription, setHomeworkDescription] = useState("");
  const [dueDate, setDueDate] = useState(defaultDueDate);
  const [availableFrom, setAvailableFrom] = useState("");
  const [studentIds, setStudentIds] = useState<number[]>([]);
  const [groupIds, setGroupIds] = useState<number[]>([]);
  const [classIds, setClassIds] = useState<number[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [assignmentError, setAssignmentError] = useState("");
  const [assignmentMessage, setAssignmentMessage] = useState("");
  const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | "">("");
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [randomizeQuestions, setRandomizeQuestions] = useState(true);
  const [randomizeOptions, setRandomizeOptions] = useState(true);

  const resetGeneratedQuiz = () => {
    setQuestions([]);
    setGeneratedTopic("");
    setSourceText("");
    setPostError("");
    setPosted("");
    setMaterialId(null);
    setRecipients(null);
    setRecipientsError("");
    setAssignmentMessage("");
  };

  const handleTopicSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    resetGeneratedQuiz();
    try {
      const result = await createTest(topic.trim());
      setGeneratedTopic(topic.trim());
      setQuizTitle(topic.trim());
      setQuestions(result.questions);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not generate the quiz.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (!selectedFile) {
      setError("Choose a PDF or JSON file first.");
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError("The file must be 10 MB or smaller.");
      return;
    }
    setLoading(true);
    resetGeneratedQuiz();
    try {
      const title = quizTitle.trim() || selectedFile.name.replace(/\.[^.]+$/, "");
      const result = await generateTestFromUpload(selectedFile, title);
      setQuizTitle(result.title);
      setGeneratedTopic(result.title);
      setSourceText(result.sourceText);
      setQuestions(result.questions);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not generate a quiz from this file.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleQuestionChange = (index: number, updated: GeneratedQuestion) => {
    setQuestions((current) => current.map((question, i) => i === index ? updated : question));
  };

  const questionsAreValid =
    questions.length > 0 &&
    questions.every((question) => {
      const options = question.options.map((option) => option.trim().toLocaleLowerCase());
      return (
        question.question.trim().length > 0 &&
        options.length >= 2 &&
        options.every(Boolean) &&
        new Set(options).size === options.length &&
        options.includes(question.answer.trim().toLocaleLowerCase())
      );
    });

  const flaggedCount = questions.filter(
    (q) =>
      q.is_approved_automatically === false ||
      q.isApprovedAutomatically === false ||
      (q.validation_warnings?.length ?? 0) > 0 ||
      (q.validationWarnings?.length ?? 0) > 0,
  ).length;

  const handleApproveAll = () => {
    setQuestions((current) =>
      current.map((q) => ({
        ...q,
        is_approved_automatically: true,
        isApprovedAutomatically: true,
      })),
    );
  };

  const handlePost = async () => {
    setPosting(true);
    setPostError("");
    try {
      const result = await postTest({
        topic: generatedTopic,
        questions,
        ...(sourceText ? { sourceText } : {}),
      });
      setPosted(`"${result.title}" saved with ${result.questionsPosted} questions.`);
      setMaterialId(result.materialId);
      setHomeworkTitle(result.title);
      try {
        setRecipients(await fetchHomeworkRecipients());
      } catch (recipientError) {
        setRecipientsError(
          recipientError instanceof Error
            ? recipientError.message
            : "Could not load homework recipients.",
        );
      }
    } catch (requestError) {
      setPostError(requestError instanceof Error ? requestError.message : "Could not save the quiz.");
    } finally {
      setPosting(false);
    }
  };

  const handlePublish = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!materialId || (!studentIds.length && !groupIds.length && !classIds.length)) return;
    setPublishing(true);
    setAssignmentError("");
    setAssignmentMessage("");
    try {
      const result = await assignHomework({
        title: homeworkTitle.trim(),
        description: homeworkDescription.trim() || undefined,
        activityType: "quiz",
        materialId,
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
      setAssignmentMessage(`"${result.title}" is available to the selected recipients.`);
    } catch (requestError) {
      setAssignmentError(
        requestError instanceof Error ? requestError.message : "Could not publish the quiz.",
      );
    } finally {
      setPublishing(false);
    }
  };

  const toggleId = (ids: number[], id: number, setIds: (next: number[]) => void) => {
    setIds(ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]);
  };

  return (
    <DashboardShell title="Create Quiz and Post" user={null}>
      <Link href="/teacher" className="text-sm text-zinc-600 hover:underline">
        ← Back to dashboard
      </Link>

      <Panel
        title="Create a quiz from your material"
        description="Upload readable PDF or JSON study material. Files are limited to 10 MB."
      >
        <form onSubmit={handleFileSubmit} className="space-y-3">
          <ErrorBanner message={error} />
          <label className="block space-y-1 text-sm font-medium">
            <span>Quiz title (optional)</span>
            <input
              maxLength={200}
              value={quizTitle}
              onChange={(event) => setQuizTitle(event.target.value)}
              placeholder="Defaults to the file name"
              className={inputClass}
            />
          </label>
          <label className="block space-y-1 text-sm font-medium">
            <span>Study material</span>
            <input
              required
              type="file"
              accept=".pdf,.json,application/pdf,application/json"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              className={inputClass}
            />
          </label>
          {selectedFile && (
            <p className="text-sm text-zinc-500">
              {selectedFile.name} · {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
            </p>
          )}
          <button type="submit" disabled={loading || !selectedFile} className={buttonClass}>
            {loading ? "Reading material and generating…" : "Generate from file"}
          </button>
        </form>
      </Panel>

      <Panel title="Generate from a topic" description="Create a quiz without an uploaded source file.">
        <form onSubmit={handleTopicSubmit} className="space-y-3">
          <label className="block space-y-1 text-sm font-medium">
            <span>Topic</span>
            <input
              required
              maxLength={200}
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="e.g. Operating Systems"
              className={inputClass}
            />
          </label>
          <button type="submit" disabled={loading || !topic.trim()} className={buttonClass}>
            {loading ? "Generating…" : "Generate from topic"}
          </button>
        </form>
      </Panel>

      {generatedTopic && (
        <Panel title={`Review quiz · ${questions.length} ${questions.length === 1 ? "question" : "questions"}`}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200/80 bg-zinc-50/60 p-3">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                {questions.length - flaggedCount} Verified
              </span>
              {flaggedCount > 0 ? (
                <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                  {flaggedCount} Flagged for review
                </span>
              ) : (
                <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs text-zinc-600">
                  All questions passed quality checks
                </span>
              )}
            </div>
            {flaggedCount > 0 && (
              <button
                type="button"
                onClick={handleApproveAll}
                className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 shadow-sm transition-colors hover:bg-zinc-50"
              >
                Approve all flagged questions
              </button>
            )}
          </div>

          {questions.length === 0 ? (
            <EmptyState>No questions were generated. Try another source or topic.</EmptyState>
          ) : (
            <ol className="space-y-4">
              {questions.map((question, index) => (
                <QuestionEditor
                  key={index}
                  question={question}
                  index={index}
                  disabled={posting || !!posted}
                  onChange={(updated) => handleQuestionChange(index, updated)}
                  onRemove={() => setQuestions((current) => current.filter((_, i) => i !== index))}
                />
              ))}
            </ol>
          )}

          <div className="mt-6 space-y-3 border-t border-zinc-200 pt-4">
            <ErrorBanner message={postError} />
            {posted && (
              <p role="status" className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                {posted}
              </p>
            )}
            {!questionsAreValid && questions.length > 0 && (
              <p role="alert" className="text-sm text-red-700">
                Each question needs text, four distinct options, and one selected correct answer.
              </p>
            )}
            <button
              type="button"
              onClick={handlePost}
              disabled={posting || !!posted || !questionsAreValid}
              className={buttonClass}
            >
              {posting ? "Saving…" : posted ? "Quiz saved ✓" : "Save quiz"}
            </button>
          </div>
        </Panel>
      )}

      {materialId !== null && (
        <Panel
          title="Publish this quiz"
          description="Choose at least one student, group, or class. The quiz will appear in selected students’ Homework."
        >
          <form onSubmit={handlePublish} className="space-y-4">
            <ErrorBanner message={assignmentError || recipientsError} />
            {assignmentMessage && (
              <p role="status" className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                {assignmentMessage}
              </p>
            )}
            <label className="block space-y-1 text-sm font-medium">
              <span>Assignment title</span>
              <input
                required
                maxLength={200}
                value={homeworkTitle}
                onChange={(event) => setHomeworkTitle(event.target.value)}
                className={inputClass}
              />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              <span>Instructions (optional)</span>
              <textarea
                maxLength={4000}
                value={homeworkDescription}
                onChange={(event) => setHomeworkDescription(event.target.value)}
                className={inputClass}
                rows={3}
              />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              <span>Due date</span>
              <input
                required
                type="date"
                min={new Date().toLocaleDateString("en-CA")}
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                className={inputClass}
              />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              <span>Available from (optional)</span>
              <input
                type="datetime-local"
                value={availableFrom}
                onChange={(event) => setAvailableFrom(event.target.value)}
                className={inputClass}
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1 text-sm font-medium">
                <span>Time limit in minutes (optional)</span>
                <input
                  type="number"
                  min={1}
                  max={360}
                  placeholder="Leave blank for untimed"
                  value={timeLimitMinutes}
                  onChange={(event) =>
                    setTimeLimitMinutes(
                      event.target.value === "" ? "" : Math.max(1, parseInt(event.target.value, 10)),
                    )
                  }
                  className={inputClass}
                />
              </label>
              <label className="block space-y-1 text-sm font-medium">
                <span>Maximum attempts</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={maxAttempts}
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
                  onChange={(e) => setRandomizeQuestions(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                />
                Randomize question order
              </label>
              <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
                <input
                  type="checkbox"
                  checked={randomizeOptions}
                  onChange={(e) => setRandomizeOptions(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                />
                Randomize answer options order
              </label>
            </div>

            {recipients ? (
              <div className="grid gap-4 sm:grid-cols-3">
                <fieldset className="space-y-2">
                  <legend className="mb-2 text-sm font-semibold">Students</legend>
                  {recipients.students.length ? recipients.students.map((student) => (
                    <label key={student.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={studentIds.includes(student.id)}
                        onChange={() => toggleId(studentIds, student.id, setStudentIds)}
                      />
                      {student.usn ?? "USN pending"} · {student.fullName}
                    </label>
                  )) : <p className="text-sm text-zinc-500">No student accounts found.</p>}
                </fieldset>
                <fieldset className="space-y-2">
                  <legend className="mb-2 text-sm font-semibold">Your groups</legend>
                  {recipients.groups.length ? recipients.groups.map((group) => (
                    <label key={group.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={groupIds.includes(group.id)}
                        onChange={() => toggleId(groupIds, group.id, setGroupIds)}
                      />
                      {group.name}
                    </label>
                  )) : <p className="text-sm text-zinc-500">No groups managed by you.</p>}
                </fieldset>
                <fieldset className="space-y-2">
                  <legend className="mb-2 text-sm font-semibold">Your classes</legend>
                  {recipients.classes.length ? recipients.classes.map((teacherClass) => (
                    <label key={teacherClass.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={classIds.includes(teacherClass.id)}
                        onChange={() => toggleId(classIds, teacherClass.id, setClassIds)}
                      />
                      {teacherClass.name}
                    </label>
                  )) : <p className="text-sm text-zinc-500">Create a class to assign to its students.</p>}
                </fieldset>
              </div>
            ) : !recipientsError ? (
              <p role="status" className="text-sm text-zinc-500">Loading recipients…</p>
            ) : null}
            <button
              type="submit"
              disabled={
                !recipients ||
                publishing ||
                !!assignmentMessage ||
                !homeworkTitle.trim() ||
                !dueDate ||
                (!studentIds.length && !groupIds.length && !classIds.length)
              }
              className={buttonClass}
            >
              {publishing ? "Publishing…" : assignmentMessage ? "Published ✓" : "Publish to selected students"}
            </button>
          </form>
        </Panel>
      )}
    </DashboardShell>
  );
}
