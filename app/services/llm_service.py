import json
import os
import re
import urllib.error
import urllib.request
from typing import Literal

try:
    import ollama
except ImportError:
    ollama = None

from config import settings
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
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-flash-latest")
        self.ollama_model = model_name or os.getenv("LLM_MODEL", "qwen2.5:3b")

    def call_gemini_flash(self, prompt: str, system_instruction: str = "") -> list[dict] | dict | None:
        if not self.gemini_api_key:
            return None

        candidate_models = [self.gemini_model, "gemini-flash-lite-latest", "gemini-flash-latest"]
        seen_models = set()
        models_to_try = []
        for m in candidate_models:
            if m and m not in seen_models:
                models_to_try.append(m)
                seen_models.add(m)

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.25,
                    "responseMimeType": "application/json",
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            body_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body_bytes,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates") or []
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        continue
                    text_content = parts[0].get("text", "").strip()
                    if not text_content:
                        continue
                    return json.loads(text_content)
            except Exception:
                continue

        return None

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
            "Return valid JSON object."
        )

        user_prompt = f"Context Material:\n\"{context}\"\n\nGenerate one MCQ centered around the topic: {topic}"

        gemini_res = self.call_gemini_flash(user_prompt, system_instructions)
        if isinstance(gemini_res, dict):
            gemini_res.setdefault("difficulty", "medium")
            gemini_res.setdefault("concept_tag", topic)
            gemini_res.setdefault("cognitive_level", "Remember")
            gemini_res.setdefault("question_type", "mcq")
            gemini_res.setdefault("answer", gemini_res.get("correct_answer", ""))
            return gemini_res
        elif isinstance(gemini_res, list) and gemini_res:
            item = gemini_res[0]
            item.setdefault("difficulty", "medium")
            item.setdefault("concept_tag", topic)
            item.setdefault("cognitive_level", "Remember")
            item.setdefault("question_type", "mcq")
            item.setdefault("answer", item.get("correct_answer", ""))
            return item

        if ollama and is_ollama_server_reachable():
            try:
                response = ollama.generate(
                    model=self.ollama_model,
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
                data.setdefault("answer", data.get("correct_answer", ""))
                return data
            except Exception:
                pass

        fallback_questions = self._fallback_extract_questions(topic, context, target_count=1, question_type="mcq")
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
        num_questions: int = 5,
        context: str | None = None,
        pages: list[dict] | None = None,
        include_true_false: bool | None = None,
        question_type: str = "mcq",
    ) -> list[dict]:
        target_count = max(1, min(num_questions, 30))
        cleaned_questions: list[dict] = []

        if question_type in {"mcq", "true_false"}:
            selected_type = question_type
        elif include_true_false is False:
            selected_type = "mcq"
        elif include_true_false is True:
            selected_type = "mixed"
        else:
            selected_type = "mcq"

        if selected_type == "true_false":
            system_instructions = (
                "You are an academic assessment engine for higher education. Create rigorous, objective "
                "TRUE/FALSE test questions testing student mastery.\n"
                "MANDATORY REQUIREMENTS:\n"
                "1. ALL QUESTIONS MUST BE STRICTLY TRUE/FALSE QUESTIONS. NEVER GENERATE ANY 4-OPTION MULTIPLE CHOICE QUESTIONS.\n"
                "2. Every question's 'options' array MUST be exactly ['True', 'False'].\n"
                "3. 'question_type' must be 'true_false'.\n"
                "4. NO DUPLICATE OR NEAR-DUPLICATE QUESTIONS. Every single question must focus on a distinct concept, "
                "mechanism, or fact. Never rephrase or repeat a question.\n"
                "5. Ground each question strictly in the provided context material. Avoid external unverified facts.\n"
                "6. 'answer' must be either 'True' or 'False'.\n"
                "7. Distribute cognitive levels: 'Remember', 'Understand', 'Apply', 'Analyse'.\n"
                "8. Distribute difficulty: 'easy', 'medium', 'difficult'.\n"
                "9. Return a JSON array of objects, each containing: 'question', 'question_type': 'true_false', "
                "'options': ['True', 'False'], 'answer', 'explanation', 'source_quote', 'concept_tag', 'subtopic', 'cognitive_level', 'difficulty'."
            )
            type_desc = "True / False (options: ['True', 'False'])"
        elif selected_type == "mcq":
            system_instructions = (
                "You are an academic assessment engine for higher education. Create rigorous, objective "
                "MULTIPLE CHOICE test questions testing student mastery.\n"
                "MANDATORY REQUIREMENTS:\n"
                "1. ALL QUESTIONS MUST BE STRICTLY 4-OPTION MULTIPLE CHOICE QUESTIONS. NEVER GENERATE ANY TRUE/FALSE QUESTIONS.\n"
                "2. Every question's 'options' array MUST contain exactly 4 distinct, plausible choices.\n"
                "3. 'question_type' must be 'mcq'.\n"
                "4. NO DUPLICATE OR NEAR-DUPLICATE QUESTIONS. Every single question must focus on a distinct concept, "
                "mechanism, or fact. Never rephrase or repeat a question.\n"
                "5. Ground each question strictly in the provided context material. Avoid external unverified facts.\n"
                "6. 'answer' must exactly match one of the 4 choices.\n"
                "7. Never use meta-options such as 'All of the above', 'None of the above', or 'Both A and B'.\n"
                "8. Distribute cognitive levels: 'Remember', 'Understand', 'Apply', 'Analyse'.\n"
                "9. Distribute difficulty: 'easy', 'medium', 'difficult'.\n"
                "10. Return a JSON array of objects, each containing: 'question', 'question_type': 'mcq', "
                "'options' (4 items), 'answer', 'explanation', 'source_quote', 'concept_tag', 'subtopic', 'cognitive_level', 'difficulty'."
            )
            type_desc = "Multiple Choice (4 distinct choices per question, no True/False)"
        else:
            system_instructions = (
                "You are an academic assessment engine for higher education. Create rigorous, objective "
                "test questions testing student mastery.\n"
                "MANDATORY REQUIREMENTS:\n"
                "1. NO DUPLICATE OR NEAR-DUPLICATE QUESTIONS. Every single question must focus on a distinct concept, "
                "mechanism, or fact. Never rephrase or repeat a question.\n"
                "2. Ground each question strictly in the provided context material. Avoid external unverified facts.\n"
                "3. Support both Multiple Choice (4 distinct options) and True/False (2 options: ['True', 'False']).\n"
                "4. 'answer' must exactly match one of the choices.\n"
                "5. Never use meta-options such as 'All of the above', 'None of the above', or 'Both A and B'.\n"
                "6. Distribute cognitive levels: 'Remember', 'Understand', 'Apply', 'Analyse'.\n"
                "7. Distribute difficulty: 'easy', 'medium', 'difficult'.\n"
                "8. Return a JSON array of objects, each containing: 'question', 'question_type' ('mcq' or 'true_false'), "
                "'options', 'answer', 'explanation', 'source_quote', 'concept_tag', 'subtopic', 'cognitive_level', 'difficulty'."
            )
            type_desc = "Mixed Multiple Choice and True/False"

        if context:
            truncated_context = context[:14000]
            user_prompt = (
                f"Topic: {topic}\n"
                f"Question Format: {type_desc}\n"
                f"Number of questions to generate: {target_count}\n"
                f"Context Material:\n{truncated_context}\n\n"
                f"Generate exactly {target_count} unique, non-overlapping assessment questions of type '{type_desc}' grounded strictly in this text."
            )
        else:
            user_prompt = (
                f"Topic: {topic}\n"
                f"Question Format: {type_desc}\n"
                f"Generate exactly {target_count} unique, non-overlapping assessment questions of type '{type_desc}' covering diverse subtopics."
            )

        gemini_data = self.call_gemini_flash(user_prompt, system_instructions)
        if gemini_data:
            parsed_items = gemini_data.get("questions") if isinstance(gemini_data, dict) else gemini_data
            cleaned_from_gemini = self._clean_questions(parsed_items, context=context, pages=pages, expected_type=selected_type)
            cleaned_questions = QuestionValidator.deduplicate_questions(cleaned_from_gemini)

        if len(cleaned_questions) < target_count and ollama and is_ollama_server_reachable():
            try:
                response = ollama.generate(
                    model=self.ollama_model,
                    system=system_instructions,
                    prompt=user_prompt,
                    format="json",
                    options={"temperature": 0.25},
                )
                data = json.loads(response["response"])
                ollama_items = self._clean_questions(data, context=context, pages=pages, expected_type=selected_type)
                for item in ollama_items:
                    if not any(QuestionValidator.is_duplicate(item["question"], q["question"]) for q in cleaned_questions):
                        cleaned_questions.append(item)
            except Exception:
                pass

        if len(cleaned_questions) < target_count and context:
            fallback = self._fallback_extract_questions(
                topic,
                context,
                target_count=target_count * 2,
                pages=pages,
                question_type=selected_type,
            )
            for item in fallback:
                if len(cleaned_questions) >= target_count:
                    break
                if not any(QuestionValidator.is_duplicate(item["question"], q["question"]) for q in cleaned_questions):
                    cleaned_questions.append(item)

        if len(cleaned_questions) < target_count:
            generic_fallback = self._generate_generic_questions(topic, question_type=selected_type)
            for item in generic_fallback:
                if len(cleaned_questions) >= target_count:
                    break
                if not any(QuestionValidator.is_duplicate(item["question"], q["question"]) for q in cleaned_questions):
                    cleaned_questions.append(item)

        deduped = QuestionValidator.deduplicate_questions(cleaned_questions)
        final_list: list[dict] = []
        for q in deduped[:target_count]:
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
        expected_type: str | None = None,
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

            if expected_type == "true_false":
                if q_type != "true_false" and len(options) != 2:
                    continue
                q_type = "true_false"
                if set(o.lower() for o in options) != {"true", "false"}:
                    options = ["True", "False"]
            elif expected_type == "mcq":
                if q_type == "true_false" or len(options) != 4:
                    continue
                if set(o.lower() for o in options) == {"true", "false"}:
                    continue
                q_type = "mcq"

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
                if q_type == "true_false" and raw_answer.lower() in ("true", "t"):
                    answer = "True"
                elif q_type == "true_false" and raw_answer.lower() in ("false", "f"):
                    answer = "False"
                else:
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
                "concept_tag": str(item.get("concept_tag") or topic_fallback(question, topic="General")).strip(),
                "subtopic": str(item.get("subtopic") or item.get("concept_tag") or "Core").strip(),
                "explanation": str(item.get("explanation") or "Directly grounded in source material.").strip(),
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
        question_type: str = "mcq",
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

            should_make_tf = (question_type == "true_false") or (question_type == "mixed" and idx % 3 == 2)

            if should_make_tf:
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

                candidate = {
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
                }
                if not any(QuestionValidator.is_duplicate(candidate["question"], q["question"]) for q in questions):
                    questions.append(candidate)
            else:
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
                rot = idx % 4
                options = options[rot:] + options[:rot]

                q_text = f"Based on the text, what key element is described in the following statement: \"{sentence}\"?"
                candidate = {
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
                }
                if not any(QuestionValidator.is_duplicate(candidate["question"], q["question"]) for q in questions):
                    questions.append(candidate)

        return questions

    def _generate_generic_questions(self, topic: str, question_type: str = "mcq") -> list[dict]:
        if question_type == "true_false":
            return [
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
                {
                    "question": f"True or False: Foundational concepts of {topic} can be completely ignored during evaluation.",
                    "question_type": "true_false",
                    "options": ["True", "False"],
                    "answer": "False",
                    "correct_answer": "False",
                    "difficulty": "easy",
                    "cognitive_level": "Remember",
                    "concept_tag": topic,
                    "subtopic": "Core Principles",
                    "explanation": f"Foundational concepts of {topic} are essential for evaluation.",
                    "source_quote": f"Foundational principles of {topic} are core to study.",
                    "source_page": 1,
                },
                {
                    "question": f"True or False: Applying principles of {topic} yields measurable outcomes across diverse scenarios.",
                    "question_type": "true_false",
                    "options": ["True", "False"],
                    "answer": "True",
                    "correct_answer": "True",
                    "difficulty": "difficult",
                    "cognitive_level": "Apply",
                    "concept_tag": topic,
                    "subtopic": "Application",
                    "explanation": f"Applied principles of {topic} generate verified outcomes.",
                    "source_quote": f"Applying {topic} produces measurable outcomes.",
                    "source_page": 1,
                },
            ]
        elif question_type == "mcq":
            return [
                {
                    "question": f"What is the primary objective of studying {topic}?",
                    "question_type": "mcq",
                    "options": [
                        f"To comprehend foundational principles of {topic}.",
                        f"To discard all theoretical methods related to {topic}.",
                        f"To replace experimental observation completely.",
                        f"To disregard empirical validation entirely.",
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
                    "question": f"Which methodology is most effective when analyzing {topic}?",
                    "question_type": "mcq",
                    "options": [
                        "Rigorous empirical verification and conceptual modeling.",
                        "Arbitrary assumption without factual validation.",
                        "Complete avoidance of structured analysis.",
                        "Uncontrolled speculation without documentation.",
                    ],
                    "answer": "Rigorous empirical verification and conceptual modeling.",
                    "correct_answer": "Rigorous empirical verification and conceptual modeling.",
                    "difficulty": "medium",
                    "cognitive_level": "Understand",
                    "concept_tag": topic,
                    "subtopic": "Methodology",
                    "explanation": f"Analyzing {topic} relies on structured empirical validation.",
                    "source_quote": f"Analysis of {topic} requires verifiable modeling.",
                    "source_page": 1,
                },
                {
                    "question": f"How do advanced practitioners typically apply {topic} in practice?",
                    "question_type": "mcq",
                    "options": [
                        "By systematically applying core principles to real-world problems.",
                        "By ignoring all constraints and foundational guidelines.",
                        "By omitting performance measurements entirely.",
                        "By relying strictly on random trials.",
                    ],
                    "answer": "By systematically applying core principles to real-world problems.",
                    "correct_answer": "By systematically applying core principles to real-world problems.",
                    "difficulty": "difficult",
                    "cognitive_level": "Apply",
                    "concept_tag": topic,
                    "subtopic": "Practical Implementation",
                    "explanation": f"Practitioners apply {topic} principles systematically to solve domain problems.",
                    "source_quote": f"Applied {topic} solves domain challenges.",
                    "source_page": 1,
                },
            ]
        else:
            return [
                {
                    "question": f"What is the primary objective of studying {topic}?",
                    "question_type": "mcq",
                    "options": [
                        f"To comprehend foundational principles of {topic}.",
                        f"To discard all theoretical methods related to {topic}.",
                        f"To replace experimental observation completely.",
                        f"To disregard empirical validation entirely.",
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


def topic_fallback(question: str, topic: str = "General") -> str:
    words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", question) if w.lower() not in {"what", "which", "where", "statement", "according"}]
    return words[0].capitalize() if words else topic
