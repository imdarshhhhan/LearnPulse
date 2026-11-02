"use client";

import type { GeneratedQuestion } from "@/services/api";

const inputClass =
  "w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-3.5 py-2 text-sm text-zinc-900 transition-all placeholder:text-zinc-400 focus:border-zinc-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-60";

export function QuestionEditor({
  question,
  index,
  disabled,
  onChange,
  onRemove,
}: {
  question: GeneratedQuestion;
  index: number;
  disabled: boolean;
  onChange: (question: GeneratedQuestion) => void;
  onRemove: () => void;
}) {
  const isApproved =
    question.is_approved_automatically ?? question.isApprovedAutomatically ?? true;
  const qualityScore = question.quality_score ?? question.qualityScore ?? 1;
  const warnings = question.validation_warnings ?? question.validationWarnings ?? [];
  const cognitiveLevel = question.cognitive_level ?? question.cognitiveLevel ?? "Understand";
  const sourceQuote = question.source_quote ?? question.sourceQuote ?? "";
  const sourcePage = question.source_page ?? question.sourcePage;
  const qType = question.question_type ?? "mcq";

  const updateOption = (optionIndex: number, value: string) => {
    const previous = question.options[optionIndex];
    const options = question.options.map((option, idx) =>
      idx === optionIndex ? value : option,
    );
    onChange({
      ...question,
      options,
      answer: question.answer === previous ? value : question.answer,
    });
  };

  const handleTypeToggle = (nextType: "mcq" | "true_false") => {
    if (nextType === "true_false") {
      const tfOptions = ["True", "False"];
      onChange({
        ...question,
        question_type: "true_false",
        options: tfOptions,
        answer: tfOptions.includes(question.answer) ? question.answer : "True",
      });
    } else {
      let fourOptions = [...question.options];
      while (fourOptions.length < 4) {
        fourOptions.push(`Option ${fourOptions.length + 1}`);
      }
      onChange({
        ...question,
        question_type: "mcq",
        options: fourOptions.slice(0, 4),
      });
    }
  };

  return (
    <li className="space-y-4 rounded-2xl border border-zinc-200/90 bg-white p-5 shadow-sm transition-all hover:border-zinc-300">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-900 text-xs font-semibold text-white">
            {index + 1}
          </span>
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            {qType === "true_false" ? "True / False" : "Multiple Choice"}
          </span>
          {typeof sourcePage === "number" && (
            <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600">
              Page {sourcePage}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isApproved ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Verified &amp; Grounded ({Math.round(qualityScore * 100)}%)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              Needs Teacher Review
            </span>
          )}

          <button
            type="button"
            onClick={onRemove}
            disabled={disabled}
            aria-label={`Delete question ${index + 1}`}
            className="rounded-lg p-1 text-zinc-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3 text-xs text-amber-900">
          <div className="font-semibold text-amber-950 mb-1">Quality validation flags:</div>
          <ul className="list-inside list-disc space-y-0.5 text-amber-800">
            {warnings.map((warn, wIdx) => (
              <li key={wIdx}>{warn}</li>
            ))}
          </ul>
          {!isApproved && (
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange({
                  ...question,
                  is_approved_automatically: true,
                  isApprovedAutomatically: true,
                })
              }
              className="mt-2 rounded-lg bg-amber-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-amber-700"
            >
              Approve question
            </button>
          )}
        </div>
      )}

      {sourceQuote && (
        <div className="rounded-xl border border-zinc-150 bg-zinc-50 p-3 text-xs text-zinc-600">
          <span className="font-semibold text-zinc-800">Grounding source excerpt: </span>
          <span className="italic">“{sourceQuote}”</span>
        </div>
      )}

      <div className="space-y-1">
        <label className="text-xs font-medium text-zinc-700">Question stem</label>
        <textarea
          required
          maxLength={2000}
          value={question.question}
          disabled={disabled}
          onChange={(event) => onChange({ ...question, question: event.target.value })}
          className={inputClass}
          rows={2}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="space-y-1">
          <label className="text-xs font-medium text-zinc-700">Type</label>
          <select
            value={qType}
            disabled={disabled}
            onChange={(event) => handleTypeToggle(event.target.value as "mcq" | "true_false")}
            className={inputClass}
          >
            <option value="mcq">Multiple Choice</option>
            <option value="true_false">True / False</option>
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-zinc-700">Cognitive level</label>
          <select
            value={cognitiveLevel}
            disabled={disabled}
            onChange={(event) =>
              onChange({
                ...question,
                cognitive_level: event.target.value as any,
                cognitiveLevel: event.target.value as any,
              })
            }
            className={inputClass}
          >
            <option value="Remember">Remember</option>
            <option value="Understand">Understand</option>
            <option value="Apply">Apply</option>
            <option value="Analyse">Analyse</option>
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-zinc-700">Difficulty</label>
          <select
            value={question.difficulty}
            disabled={disabled}
            onChange={(event) =>
              onChange({
                ...question,
                difficulty: event.target.value as GeneratedQuestion["difficulty"],
              })
            }
            className={inputClass}
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="difficult">Difficult</option>
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-zinc-700">Subtopic tag</label>
          <input
            type="text"
            value={question.subtopic ?? ""}
            disabled={disabled}
            placeholder="e.g. Memory Management"
            onChange={(event) =>
              onChange({
                ...question,
                subtopic: event.target.value,
              })
            }
            className={inputClass}
          />
        </div>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium text-zinc-700">Options · select the correct answer key</legend>
        <div className="grid gap-2">
          {question.options.map((option, optionIndex) => (
            <div
              key={optionIndex}
              className={`flex items-center gap-3 rounded-xl border p-2.5 transition-all ${
                question.answer === option
                  ? "border-emerald-300 bg-emerald-50/40 ring-1 ring-emerald-300"
                  : "border-zinc-200 bg-white hover:border-zinc-300"
              }`}
            >
              <input
                type="radio"
                name={`correct-answer-${index}`}
                aria-label={`Mark option ${optionIndex + 1} as correct`}
                checked={question.answer === option}
                disabled={disabled}
                onChange={() => onChange({ ...question, answer: option })}
                className="h-4 w-4 text-emerald-600 accent-emerald-600 focus:ring-emerald-500"
              />
              <input
                required
                maxLength={1000}
                value={option}
                disabled={disabled || qType === "true_false"}
                onChange={(event) => updateOption(optionIndex, event.target.value)}
                className="flex-1 bg-transparent text-sm text-zinc-900 outline-none"
              />
            </div>
          ))}
        </div>
      </fieldset>

      <div className="space-y-1">
        <label className="text-xs font-medium text-zinc-700">Explanation &amp; source grounding</label>
        <textarea
          maxLength={2000}
          value={question.explanation ?? ""}
          disabled={disabled}
          placeholder="Evidence and rationale for why the answer key is correct..."
          onChange={(event) => onChange({ ...question, explanation: event.target.value })}
          className={inputClass}
          rows={2}
        />
      </div>
    </li>
  );
}
