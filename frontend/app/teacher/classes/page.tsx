"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  DashboardShell,
  EmptyState,
  ErrorBanner,
  LoadingState,
  Panel,
} from "@/app/components/DashboardShell";
import { ApiError } from "@/services/dashboardApi";
import {
  addClassStudent,
  createTeacherClass,
  deleteTeacherClass,
  fetchTeacherClasses,
  removeClassStudent,
  searchAvailableStudents,
  type ClassStudent,
  type TeacherClass,
} from "@/services/teacherClassesApi";

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500";

export default function TeacherClassesPage() {
  const router = useRouter();
  const [classes, setClasses] = useState<TeacherClass[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [search, setSearch] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const selectedClass = useMemo(
    () => classes.find((item) => item.id === selectedClassId) ?? null,
    [classes, selectedClassId],
  );

  useEffect(() => {
    let active = true;
    fetchTeacherClasses()
      .then(({ classes: result }) => {
        if (!active) return;
        setClasses(result);
        setSelectedClassId((current) => current ?? result[0]?.id ?? null);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 401) {
          router.replace("/auth");
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Could not load classes.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      searchAvailableStudents(search)
        .then(({ students: result }) => {
          if (active) setStudents(result);
        })
        .catch((requestError: unknown) => {
          if (active) setError(requestError instanceof Error ? requestError.message : "Could not load students.");
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [search]);

  const updateClass = (updated: TeacherClass) => {
    setClasses((current) => current.map((item) => item.id === updated.id ? updated : item));
    setMessage("");
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);
    try {
      const created = await createTeacherClass({
        name: name.trim(),
        subject: subject.trim() || undefined,
        description: description.trim() || undefined,
      });
      setClasses((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedClassId(created.id);
      setName("");
      setSubject("");
      setDescription("");
      setMessage(`Created “${created.name}”.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create the class.");
    } finally {
      setSaving(false);
    }
  };

  const handleAddStudent = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedClass || !selectedStudentId) return;
    setError("");
    setMessage("");
    setSaving(true);
    try {
      updateClass(await addClassStudent(selectedClass.id, Number(selectedStudentId)));
      setSelectedStudentId("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not add this student.");
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveStudent = async (studentId: number) => {
    if (!selectedClass) return;
    setError("");
    setMessage("");
    setSaving(true);
    try {
      updateClass(await removeClassStudent(selectedClass.id, studentId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not remove this student.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClass = async (classId: number) => {
    if (!window.confirm("Are you sure you want to delete this class? This will remove all student enrollments.")) {
      return;
    }
    setError("");
    setMessage("");
    setSaving(true);
    try {
      await deleteTeacherClass(classId);
      const remaining = classes.filter((c) => c.id !== classId);
      setClasses(remaining);
      setSelectedClassId(remaining[0]?.id ?? null);
      setMessage("Class removed successfully.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete class.");
    } finally {
      setSaving(false);
    }
  };

  const availableStudents = students.filter(
    (student) => !selectedClass?.students.some((member) => member.id === student.id),
  );

  return (
    <DashboardShell title="Class Management" user={null}>
      <section>
        <p className="text-sm font-medium text-indigo-700">Teacher workspace</p>
        <h2 className="mt-1 text-2xl font-semibold">Organize students into classes</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Classes are private to you. Students can belong to more than one class.
        </p>
      </section>
      <ErrorBanner message={error} />
      {message && <p role="status" className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">{message}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(15rem,0.75fr)_minmax(0,1.5fr)]">
        <div className="space-y-6">
          <Panel title="Your classes">
            {loading ? (
              <LoadingState />
            ) : classes.length === 0 ? (
              <EmptyState>Create a class to get started.</EmptyState>
            ) : (
              <ul className="space-y-2">
                {classes.map((teacherClass) => (
                  <li key={teacherClass.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedClassId(teacherClass.id)}
                      aria-pressed={selectedClassId === teacherClass.id}
                      className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                        selectedClassId === teacherClass.id
                          ? "border-indigo-300 bg-indigo-50"
                          : "border-zinc-200 hover:bg-zinc-50"
                      }`}
                    >
                      <span className="block font-medium">{teacherClass.name}</span>
                      <span className="mt-1 block text-sm text-zinc-500">
                        {teacherClass.subject ?? "No subject"} · {teacherClass.memberCount} students
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Create a class">
            <form onSubmit={handleCreate} className="space-y-3">
              <label className="block space-y-1 text-sm font-medium">
                <span>Class name</span>
                <input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} />
              </label>
              <label className="block space-y-1 text-sm font-medium">
                <span>Subject (optional)</span>
                <input maxLength={120} value={subject} onChange={(event) => setSubject(event.target.value)} className={inputClass} />
              </label>
              <label className="block space-y-1 text-sm font-medium">
                <span>Description (optional)</span>
                <textarea maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} className={inputClass} rows={3} />
              </label>
              <button type="submit" disabled={saving} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                {saving ? "Creating…" : "Create class"}
              </button>
            </form>
          </Panel>
        </div>

        <Panel
          title={selectedClass ? `${selectedClass.name} · ${selectedClass.memberCount} students` : "Class members"}
          action={
            selectedClass ? (
              <button
                type="button"
                disabled={saving}
                onClick={() => void handleDeleteClass(selectedClass.id)}
                className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs sm:text-sm font-semibold text-rose-700 shadow-xs transition-colors hover:bg-rose-100 disabled:opacity-50"
              >
                Delete Class
              </button>
            ) : undefined
          }
        >
          {!selectedClass ? (
            <EmptyState>Select a class or create one to manage students.</EmptyState>
          ) : (
            <div className="space-y-5">
              {(selectedClass.subject || selectedClass.description) && (
                <p className="text-sm text-zinc-600">
                  {[selectedClass.subject, selectedClass.description].filter(Boolean).join(" · ")}
                </p>
              )}
              <form onSubmit={handleAddStudent} className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <label className="space-y-1 text-sm font-medium">
                  <span>Add a registered student</span>
                  <select
                    required
                    value={selectedStudentId}
                    onChange={(event) => setSelectedStudentId(event.target.value)}
                    className={inputClass}
                  >
                    <option value="">Choose a student</option>
                    {availableStudents.map((student) => (
                      <option key={student.id} value={student.id}>
                        {student.usn ?? "USN pending"} · {student.fullName}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="submit" disabled={saving || !selectedStudentId} className="self-end rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50">
                  Add student
                </button>
              </form>

              <label className="block space-y-1 text-sm font-medium">
                <span>Search students by name or USN</span>
                <input value={search} onChange={(event) => setSearch(event.target.value)} className={inputClass} placeholder="Search registered students" />
              </label>

              {selectedClass.students.length === 0 ? (
                <EmptyState>No students have been added to this class yet.</EmptyState>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[500px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500">
                        <th className="px-3 py-3 font-medium">Student</th>
                        <th className="px-3 py-3 font-medium">USN</th>
                        <th className="px-3 py-3 font-medium">Email</th>
                        <th className="px-3 py-3"><span className="sr-only">Remove</span></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {selectedClass.students.map((student) => (
                        <tr key={student.id}>
                          <td className="px-3 py-3 font-medium">{student.fullName}</td>
                          <td className="px-3 py-3">{student.usn ?? "Not provided"}</td>
                          <td className="px-3 py-3 text-zinc-600">{student.email}</td>
                          <td className="px-3 py-3 text-right">
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() => void handleRemoveStudent(student.id)}
                              className="rounded-lg border border-rose-200 bg-rose-50/70 px-3 py-1 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100 disabled:opacity-50"
                            >
                              Remove from class
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {search.trim() && availableStudents.length === 0 && (
                <p className="text-sm text-zinc-500">No unassigned students match that search.</p>
              )}
            </div>
          )}
        </Panel>
      </div>
    </DashboardShell>
  );
}
