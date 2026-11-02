import json
import os
import re
from typing import Literal

try:
    import ollama
except ImportError:
    ollama = None

from services.validator import QuestionValidator


def is_ollama_server_reachable() -> bool:
    if not ollama:
        return False
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.15):
            return True
    except (OSError, socket.timeout):
        return False


class LLMService:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("LLM_MODEL", "qwen2.5:3b")

    def generate_mcq(self, context: str, topic: str) -> dict:
        system_instructions = (
            "You are an objective academic assessment engine. Read the context snippet provided "
            "and generate exactly ONE multiple-choice question. Obey these rules:\n"
            "1. Rely strictly on facts within the context. No outside hallucinated facts.\n"
            "2. 'options' must contain exactly 4 unique and plausible string choices.\n"
            "3. 'correct_answer' must match one of the options word-for-word.\n"
            "4. 'source_quote' must be the exact sentence pulled word-for-word from the context proving the answer.\n"
            "5. 'explanation' must explain why the answer is correct based on the passage.\n"
            "6. 'concept_tag' must be the specific concept or subtopic tested.\n"
            "7. 'cognitive_level' must be one of: Remember, Understand, Apply, Analyse.\n"
            "8. 'difficulty' must be one of: easy, medium, difficult.\n"
            "Return only raw valid JSON without markdown wrapping."
        )

        user_prompt = f"Context Material:\n\"{context}\"\n\nGenerate one MCQ centered around the topic: {topic}"

        if ollama and is_ollama_server_reachable():
            try:
                response = ollama.generate(
                    model=self.model_name,
                    system=system_instructions,
                    prompt=user_prompt,
                    format="json",
                    options={"temperature": 0.2},
                )
                raw_text = response["response"].strip()
                data = json.loads(raw_text)
                data.setdefault("difficulty", "medium")
                data.setdefault("concept_tag", topic)
                data.setdefault("cognitive_level", "Remember")
                data.setdefault("question_type", "mcq")
                return data
            except Exception:
                pass

        # Robust heuristic fallback when Ollama is unavailable
        fallback_questions = self._fallback_extract_questions(topic, context, target_count=1)
        if fallback_questions:
            return fallback_questions[0]

        return {
            "question": f"Which statement regarding {topic} is supported by the study text?",
            "options": [
                f"The text provides direct factual evidence for {topic}.",
                f"The material excludes {topic} completely.",
                f"{topic} is identified as unverified.",
                f"There is no correlation with {topic}.",
            ],
            "correct_answer": f"The text provides direct factual evidence for {topic}.",
            "answer": f"The text provides direct factual evidence for {topic}.",
            "source_quote": context[:120].strip() if context else f"Source content on {topic}.",
            "explanation": f"Supported directly by the study context addressing {topic}.",
            "concept_tag": topic,
            "subtopic": topic,
            "cognitive_level": "Understand",
            "difficulty": "medium",
            "question_type": "mcq",
        }

    def generate_test(
        self,
        topic: str,
        num_questions: int = 10,
        context: str | None = None,
        pages: list[dict] | None = None,
        include_true_false: bool = True,
    ) -> list[dict]:
        cleaned_questions: list[dict] = []

        if ollama and is_ollama_server_reachable():
            system_instructions = (
                "You are an academic assessment engine. Create clear, objective test questions "
                "testing student mastery. Rules:\n"
                "1. Each question must be clear, grammatically sound, and factually accurate.\n"
                "2. Include both multiple-choice (4 options) and True/False (2 options: True, False).\n"
                "3. 'answer' must be the exact text of the one correct option.\n"
                "4. Never use 'All of the above' or 'None of the above'.\n"
                "5. Each item must have: 'question', 'question_type' ('mcq' or 'true_false'), 'options', 'answer', "
                "'explanation', 'source_quote', 'concept_tag', 'cognitive_level' ('Remember','Understand','Apply','Analyse'), "
                "'difficulty' ('easy','medium','difficult').\n"
                "6. Ground everything strictly on the provided context if available.\n"
                "Return raw JSON format: {\"questions\": [...]}"
            )
            if context:
                user_prompt = (
                    f"Topic: {topic}\nSource Context:\n{context[:8000]}\n\n"
                    f"Generate {num_questions} questions grounded only in this text."
                )
            else:
                user_prompt = f"Topic: {topic}\nGenerate {num_questions} assessment questions."

            for _ in range(2):
                try:
                    response = ollama.generate(
                        model=self.model_name,
                        system=system_instructions,
                        prompt=user_prompt,
                        format="json",
                        options={"temperature": 0.25},
                    )
                    data = json.loads(response["response"])
                    cleaned_questions = self._clean_questions(data, context=context, pages=pages)
                    if len(cleaned_questions) >= 3:
                        break
                except Exception:
                    continue

        if len(cleaned_questions) < 5 and context:
            fallback = self._fallback_extract_questions(
                topic,
                context,
                target_count=num_questions,
                pages=pages,
                include_true_false=include_true_false,
            )
            for item in fallback:
                if not any(
                    item["question"].strip().lower() == q["question"].strip().lower()
                    for q in cleaned_questions
                ):
                    cleaned_questions.append(item)

        if len(cleaned_questions) < 3:
            generic_fallback = self._generate_generic_questions(topic)
            cleaned_questions.extend(generic_fallback)

        # Run full QuestionValidator on each question to validate & flag doubtful questions
        final_list: list[dict] = []
        for q in cleaned_questions[:max(num_questions, 5)]:
            validation = QuestionValidator.validate_question(
                q,
                source_context=context,
                existing_questions=final_list,
            )
            q["is_approved_automatically"] = validation["is_approved_automatically"]
            q["quality_score"] = validation["quality_score"]
            q["validation_warnings"] = validation["validation_warnings"]
            q["quality_flags"] = validation["quality_flags"]
            final_list.append(q)

        return final_list

    def _clean_questions(
        self,
        data: object,
        context: str | None = None,
        pages: list[dict] | None = None,
    ) -> list[dict]:
        items = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []

        def strip_label(text: str) -> str:
            return re.sub(r"^\(?[A-Da-d][\).:]\s+", "", text.strip())

        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            raw_options = item.get("options")
            if not question or not isinstance(raw_options, list):
                continue

            q_type = str(item.get("question_type") or ("true_false" if len(raw_options) == 2 else "mcq")).lower()
            options = [strip_label(str(o)) for o in raw_options if str(o).strip()]

            expected_len = 2 if q_type == "true_false" else 4
            if len(options) != expected_len or len({o.lower() for o in options}) != expected_len:
                continue

            raw_answer = str(item.get("answer", item.get("correct_answer", ""))).strip()
            answer = next((o for o in options if o.lower() == strip_label(raw_answer).lower()), None)
            if answer is None:
                letter = re.fullmatch(r"\(?([A-Da-d])[\).:]?", raw_answer)
                if letter:
                    idx = ord(letter.group(1).upper()) - ord("A")
                    if 0 <= idx < len(options):
                        answer = options[idx]
            if answer is None:
                continue

            diff = str(item.get("difficulty", "medium")).lower()
            if diff not in {"easy", "medium", "difficult"}:
                diff = "medium"

            cog = str(item.get("cognitive_level", "Remember")).capitalize()
            if cog not in {"Remember", "Understand", "Apply", "Analyse"}:
                cog = "Remember"

            source_quote = str(item.get("source_quote") or "").strip()
            page_num = self._find_page_number(source_quote, pages)

            cleaned.append({
                "question": question,
                "question_type": q_type,
                "options": options,
                "answer": answer,
                "correct_answer": answer,
                "difficulty": diff,
                "cognitive_level": cog,
                "concept_tag": str(item.get("concept_tag") or "General").strip(),
                "subtopic": str(item.get("subtopic") or item.get("concept_tag") or "Core").strip(),
                "explanation": str(item.get("explanation") or f"Directly grounded in source material.").strip(),
                "source_quote": source_quote,
                "source_page": page_num,
            })
        return cleaned

    def _fallback_extract_questions(
        self,
        topic: str,
        context: str,
        target_count: int = 10,
        pages: list[dict] | None = None,
        include_true_false: bool = True,
    ) -> list[dict]:
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", context)
            if len(s.strip()) > 35 and not s.strip().startswith("#")
        ]

        if not sentences:
            return []

        questions = []
        cognitive_levels = ["Remember", "Understand", "Apply", "Analyse"]
        difficulties = ["easy", "medium", "difficult"]

        entity_candidates = []
        for s in sentences:
            found = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{3,}\b", s)
            entity_candidates.extend(found)
        entity_candidates = list(dict.fromkeys(entity_candidates))

        for idx, sentence in enumerate(sentences):
            if len(questions) >= target_count:
                break

            page_num = self._find_page_number(sentence, pages)
            cog = cognitive_levels[idx % len(cognitive_levels)]
            diff = difficulties[idx % len(difficulties)]

            # Alternate between MCQ and True/False
            if include_true_false and idx % 3 == 2:
                # True/False question
                is_statement_true = (idx % 2 == 0)
                if is_statement_true:
                    q_text = f"True or False: According to the material, {sentence[0].lower() + sentence[1:]}"
                    correct = "True"
                    explanation = f"This statement is directly confirmed in the text: \"{sentence}\""
                else:
                    words = sentence.split()
                    modified = sentence
                    if len(words) > 6:
                        modified = sentence.replace(" is ", " is not ").replace(" are ", " are not ").replace(" was ", " was not ")
                        if modified == sentence:
                            modified = f"It is universally prohibited that {sentence[0].lower() + sentence[1:]}"
                    q_text = f"True or False: According to the material, {modified[0].lower() + modified[1:]}"
                    correct = "False"
                    explanation = f"False. The text confirms the opposite: \"{sentence}\""

                questions.append({
                    "question": q_text,
                    "question_type": "true_false",
                    "options": ["True", "False"],
                    "answer": correct,
                    "correct_answer": correct,
                    "difficulty": diff,
                    "cognitive_level": cog,
                    "concept_tag": topic,
                    "subtopic": self._extract_subtopic(sentence, topic),
                    "explanation": explanation,
                    "source_quote": sentence,
                    "source_page": page_num,
                })
            else:
                # MCQ 4 options
                match = re.search(r"\b([A-Z][a-zA-Z0-9_\s-]{2,20})\b", sentence)
                key_entity = match.group(1).strip() if match else topic

                distractors = [
                    cand for cand in entity_candidates
                    if cand.lower() != key_entity.lower() and len(cand) >= 3
                ]
                while len(distractors) < 3:
                    distractors.append(f"Alternative {len(distractors) + 1}")

                chosen_distractors = distractors[:3]
                options = [key_entity] + chosen_distractors
                # Rotate options based on idx for natural option distribution
                rot = idx % 4
                options = options[rot:] + options[:rot]

                q_text = f"Based on the text, what key element is described in the following statement: \"{sentence}\"?"
                questions.append({
                    "question": q_text,
                    "question_type": "mcq",
                    "options": options,
                    "answer": key_entity,
                    "correct_answer": key_entity,
                    "difficulty": diff,
                    "cognitive_level": cog,
                    "concept_tag": topic,
                    "subtopic": self._extract_subtopic(sentence, topic),
                    "explanation": f"The passage explicitly details: \"{sentence}\"",
                    "source_quote": sentence,
                    "source_page": page_num,
                })

        return questions

    def _generate_generic_questions(self, topic: str) -> list[dict]:
        return [
            {
                "question": f"What is the primary objective of studying {topic}?",
                "question_type": "mcq",
                "options": [
                    f"To comprehend foundational principles of {topic}.",
                    f"To discard all theoretical methods related to {topic}.",
                    f"To replace experimental observation completely.",
                    f"None of these statements.",
                ],
                "answer": f"To comprehend foundational principles of {topic}.",
                "correct_answer": f"To comprehend foundational principles of {topic}.",
                "difficulty": "easy",
                "cognitive_level": "Remember",
                "concept_tag": topic,
                "subtopic": "Fundamentals",
                "explanation": f"Understanding fundamentals is the primary objective of studying {topic}.",
                "source_quote": f"Foundational principles of {topic}.",
                "source_page": 1,
            },
            {
                "question": f"True or False: Systematic analysis of {topic} requires verifiable factual evidence.",
                "question_type": "true_false",
                "options": ["True", "False"],
                "answer": "True",
                "correct_answer": "True",
                "difficulty": "medium",
                "cognitive_level": "Understand",
                "concept_tag": topic,
                "subtopic": "Methodology",
                "explanation": "Academic analysis relies on verifiable evidence.",
                "source_quote": f"Systematic analysis of {topic} requires evidence.",
                "source_page": 1,
            },
        ]

    @staticmethod
    def _find_page_number(quote: str, pages: list[dict] | None) -> int:
        if not pages or not quote:
            return 1
        clean_q = quote.strip().lower()
        for p in pages:
            if clean_q in p.get("text", "").lower() or p.get("text", "").lower() in clean_q:
                return p.get("pageNumber", 1)
        return 1

    @staticmethod
    def _extract_subtopic(sentence: str, fallback_topic: str) -> str:
        words = re.findall(r"\b[A-Za-z]{4,}\b", sentence)
        for w in words:
            if w.lower() not in {"this", "that", "with", "from", "they", "were", "been", "have", "more"}:
                return w.capitalize()
        return fallback_topic
