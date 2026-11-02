import re
from difflib import SequenceMatcher


class QuestionValidator:

    @staticmethod
    def validate_mcq_structure(quiz_data: dict) -> tuple[bool, list[str]]:
        errors = []

        required_fields = [
            "question",
            "options",
            "correct_answer",
            "source_quote"
        ]

        for field in required_fields:
            if field not in quiz_data or not quiz_data[field]:
                errors.append(f"Missing or empty field: '{field}'")
                return False, errors

        question = quiz_data["question"]
        options = quiz_data["options"]
        correct_answer = quiz_data["correct_answer"]

        if len(options) != 4 and len(options) != 2:
            errors.append(f"Expected 4 options (or 2 for True/False), but got {len(options)}")

        normalized_options = [
            str(option).strip().lower()
            for option in options
            if isinstance(option, str)
        ]

        if len(set(normalized_options)) != len(options):
            errors.append("Duplicate options found")

        matching_correct = [
            opt for opt in options
            if str(opt).strip().lower() == str(correct_answer).strip().lower()
        ]
        if len(matching_correct) == 0:
            errors.append(f"Correct answer '{correct_answer}' is not in the options")

        weak_options = {
            "all of the above",
            "none of the above",
            "both a and b",
            "neither a nor b",
            "all of these",
            "none of these",
        }

        for option in options:
            if str(option).strip().lower() in weak_options:
                errors.append(f"Weak option found: '{option}'")

        return len(errors) == 0, errors

    @classmethod
    def validate_question(
        cls,
        question_data: dict,
        source_context: str | None = None,
        existing_questions: list[dict] | None = None,
    ) -> dict:
        warnings: list[str] = []
        flags: list[str] = []
        score = 100.0

        question = str(question_data.get("question") or "").strip()
        raw_options = question_data.get("options") or []
        options = [str(opt).strip() for opt in raw_options if str(opt).strip()]
        correct_answer = str(
            question_data.get("correct_answer") or question_data.get("answer") or ""
        ).strip()
        source_quote = str(question_data.get("source_quote") or "").strip()
        question_type = str(question_data.get("question_type") or "mcq").strip().lower()

        # 1. Structure and Option Count
        if not question:
            warnings.append("Question text is empty.")
            flags.append("EMPTY_QUESTION")
            score -= 50.0

        expected_count = 2 if question_type == "true_false" else 4
        if len(options) != expected_count:
            warnings.append(
                f"Expected {expected_count} options for {question_type.upper()}, but found {len(options)}."
            )
            flags.append("INVALID_OPTION_COUNT")
            score -= 30.0

        # 2. Duplicate Options Check
        normalized_opts = [opt.casefold() for opt in options]
        if len(set(normalized_opts)) < len(normalized_opts):
            warnings.append("Question contains duplicate or identical options.")
            flags.append("DUPLICATE_OPTIONS")
            score -= 25.0

        # 3. Single Correct Answer Check
        matching_indices = [
            i for i, opt in enumerate(options)
            if opt.casefold() == correct_answer.casefold()
        ]
        if len(matching_indices) == 0:
            warnings.append("Designated correct answer is not among the options.")
            flags.append("MISSING_CORRECT_ANSWER")
            score -= 40.0
        elif len(matching_indices) > 1:
            warnings.append("Multiple options match the correct answer.")
            flags.append("MULTIPLE_CORRECT_ANSWERS")
            score -= 35.0

        # 4. Ambiguity & Quality Checks
        if len(question) < 15 or len(question.split()) < 4:
            warnings.append("Question is too short and may be ambiguous or uninformative.")
            flags.append("AMBIGUOUS_QUESTION_LENGTH")
            score -= 15.0

        # Ambiguous phrasing patterns
        ambiguity_regex = re.compile(
            r"\b(might be|could be|sometimes|often|all of the above|none of the above|not sure)\b",
            re.IGNORECASE,
        )
        if ambiguity_regex.search(question):
            warnings.append("Question uses imprecise or hedge phrasing.")
            flags.append("AMBIGUOUS_PHRASING")
            score -= 10.0

        # Check for overlapping options
        for i in range(len(options)):
            for j in range(i + 1, len(options)):
                sim = SequenceMatcher(None, options[i].casefold(), options[j].casefold()).ratio()
                if sim > 0.85:
                    warnings.append(f"Options '{options[i]}' and '{options[j]}' are nearly identical.")
                    flags.append("NEAR_DUPLICATE_OPTIONS")
                    score -= 15.0

        # 5. Distractor Quality & Length Bias Check
        weak_options = {
            "all of the above", "none of the above", "both a and b",
            "neither a nor b", "all of these", "none of these",
        }
        for opt in options:
            if opt.casefold() in weak_options:
                warnings.append(f"Poor distractor detected: '{opt}'.")
                flags.append("WEAK_DISTRACTOR")
                score -= 15.0

        distractors = [opt for opt in options if opt.casefold() != correct_answer.casefold()]
        if distractors and correct_answer:
            avg_distractor_len = sum(len(d) for d in distractors) / len(distractors)
            correct_len = len(correct_answer)
            if avg_distractor_len > 0:
                length_ratio = correct_len / avg_distractor_len
                if length_ratio > 2.8 or length_ratio < 0.35:
                    warnings.append(
                        "Length cue bias: correct answer length differs significantly from distractors."
                    )
                    flags.append("DISTRACTOR_LENGTH_BIAS")
                    score -= 10.0

        # 6. Grammatical Checks
        if question and not question[0].isupper():
            warnings.append("Question does not start with a capital letter.")
            flags.append("GRAMMAR_CAPITALIZATION")
            score -= 5.0
        if question and not re.search(r"[?.!:]$", question):
            warnings.append("Question lacks terminating punctuation.")
            flags.append("GRAMMAR_PUNCTUATION")
            score -= 5.0

        # 7. Source Material Groundedness
        if source_context:
            context_lower = source_context.casefold()
            if source_quote:
                clean_quote = " ".join(source_quote.split()).casefold()
                if clean_quote not in context_lower:
                    ratio = SequenceMatcher(None, clean_quote[:100], context_lower).quick_ratio()
                    if ratio < 0.3:
                        warnings.append("Source quote could not be confirmed in the provided material.")
                        flags.append("UNVERIFIED_SOURCE_QUOTE")
                        score -= 20.0
            else:
                answer_words = [w for w in re.findall(r"\w+", correct_answer.casefold()) if len(w) > 3]
                if answer_words and not any(w in context_lower for w in answer_words):
                    warnings.append("Correct answer terms were not found in the source text.")
                    flags.append("UNGROUNDED_ANSWER")
                    score -= 25.0

        # 8. Cross-question Duplicate Detection
        if existing_questions:
            q_words = set(re.findall(r"\w+", question.casefold()))
            for past_q in existing_questions:
                past_text = str(past_q.get("question") or "").strip()
                if not past_text or past_text == question:
                    continue
                past_words = set(re.findall(r"\w+", past_text.casefold()))
                if q_words and past_words:
                    jaccard = len(q_words & past_words) / len(q_words | past_words)
                    if jaccard > 0.75:
                        warnings.append("Question is very similar to another question in this quiz.")
                        flags.append("CROSS_QUESTION_DUPLICATE")
                        score -= 25.0
                        break

        final_score = max(0.0, min(100.0, round(score, 1)))
        is_approved = (len(warnings) == 0 and final_score >= 80.0)

        return {
            "is_approved_automatically": is_approved,
            "quality_score": final_score,
            "validation_warnings": warnings,
            "quality_flags": flags,
        }
