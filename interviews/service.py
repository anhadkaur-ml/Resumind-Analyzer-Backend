"""Groq integration for interview-question generation and answer evaluation."""

import json
import logging
import os

from groq import Groq

from .prompt import build_evaluation_messages, build_question_messages


logger = logging.getLogger(__name__)


class QuestionGenerationError(Exception):
    """Raised when Groq cannot provide a complete interview question set."""


def _client():
    # Returning None keeps missing local credentials separate from provider
    # errors raised during an actual request.
    key = os.getenv("GROQ_API_KEY", "").strip()
    return Groq(api_key=key) if key else None


def build_resume_context(resume):
    """Convert a user-owned Builder resume into concise prompt context."""
    education = "; ".join(
        " | ".join(str(entry.get(key, "")).strip() for key in ("education_type", "degree", "field", "institution") if str(entry.get(key, "")).strip())
        for entry in resume.education_entries if isinstance(entry, dict)
    ) or resume.education
    skills = ", ".join(resume.skill_items) or resume.skills
    projects = "; ".join(
        " | ".join(str(entry.get(key, "")).strip() for key in ("name", "technologies", "description") if str(entry.get(key, "")).strip())
        for entry in resume.project_entries if isinstance(entry, dict)
    ) or resume.projects
    # Empty sections are removed to keep the prompt focused and token usage low.
    return "\n".join(filter(None, (
        f"Summary: {resume.summary}" if resume.summary else "",
        f"Experience: {resume.job_title} at {resume.company}. {resume.experience}" if resume.job_title or resume.experience else "",
        f"Education: {education}" if education else "",
        f"Skills: {skills}" if skills else "",
        f"Projects: {projects}" if projects else "",
    )))


def generate_questions(interview_type, target_role, experience_level, count=8, resume_context=""):
    """Return a complete Groq-generated question set or fail without fake questions."""
    client = _client()
    if not client:
        raise QuestionGenerationError("AI question generation is temporarily unavailable because Groq is not configured.")
    try:
        response = client.chat.completions.create(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), messages=build_question_messages(interview_type, target_role, experience_level, count, resume_context), response_format={"type": "json_object"}, temperature=0.5)
        content = response.choices[0].message.content or "{}"
        questions = json.loads(content).get("questions", [])
        clean_questions = [str(item).strip() for item in questions if str(item).strip()]
        if len(clean_questions) < count:
            raise ValueError("Groq returned an incomplete question set.")
        return clean_questions[:count], "groq"
    except Exception as error:
        logger.exception("Groq interview-question generation failed.")
        raise QuestionGenerationError("AI questions could not be generated right now. Please try again shortly.") from error


def evaluate_answer(question, answer, interview_type, target_role):
    """Return (score, feedback, source) from Groq or the local evaluator."""
    client = _client()
    if client:
        try:
            response = client.chat.completions.create(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), messages=build_evaluation_messages(question, answer, interview_type, target_role), response_format={"type": "json_object"}, temperature=0.3)
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
            feedback = str(result["feedback"]).strip()
            if not feedback:
                raise ValueError("Groq returned empty feedback.")
            # Clamp model-provided scores to the range accepted by the database.
            return max(0, min(100, int(result["score"]))), feedback, "groq"
        except Exception:
            logger.exception("Groq interview-answer evaluation failed; using local evaluation.")
    else:
        logger.info("GROQ_API_KEY is not configured; using local answer evaluation.")
    # The local evaluator is intentionally simple and is used only when the AI
    # provider cannot evaluate the answer.
    words = len(answer.split())
    score = min(85, 35 + min(words, 100) // 2)
    feedback = "Good start. Add a specific example, your actions, and a measurable result." if words < 60 else "Clear answer. Make the result more measurable and connect it directly to the role."
    return score, feedback, "local"
