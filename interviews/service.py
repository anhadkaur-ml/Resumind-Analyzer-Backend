"""Groq integration with deterministic fallbacks for interview practice."""

import json
import logging
import os

from groq import Groq

from .prompt import build_evaluation_messages, build_question_messages


logger = logging.getLogger(__name__)


FALLBACKS = {
    "behavioral": ["Tell me about a challenging project and how you handled it.", "Describe a disagreement with a teammate and how you resolved it.", "Tell me about a time you had to meet a difficult deadline.", "Describe a mistake you made and what you learned from it.", "Give an example of taking ownership beyond your assigned work.", "How have you handled changing priorities?", "Tell me about feedback that improved your work.", "What achievement are you most proud of and why?"],
    "technical": ["Walk me through a difficult technical problem you solved.", "How do you ensure the quality of your work?", "Explain a technical decision and the trade-offs you considered.", "How do you diagnose an issue you cannot reproduce easily?", "Describe how you would improve a slow system.", "How do you review and test a new feature?", "Tell me about a tool or technology you learned recently.", "How would you design a reliable solution for a growing workload?"],
    "role_specific": ["Which skills make you a strong fit for this role?", "How would you approach your first 30 days in this role?", "Describe a project that best demonstrates your fit for this position.", "How do you prioritize competing responsibilities?", "Which result from your past work is most relevant here?", "How do you collaborate with stakeholders in this role?", "What is the biggest challenge you expect in this position?", "How would you measure success in this role?"],
    "hr_screening": ["Tell me about yourself and your career journey.", "Why are you interested in this role?", "Why do you want to join our organization?", "What are your greatest strengths?", "Which area are you currently improving?", "What type of work environment helps you perform best?", "Why are you considering a change?", "Where would you like your career to be in three years?"],
}


def _client():
    key = os.getenv("GROQ_API_KEY", "").strip()
    return Groq(api_key=key) if key else None


def generate_questions(interview_type, target_role, experience_level, count=8):
    """Return (questions, source), using a safe fallback if Groq is unavailable."""
    client = _client()
    if client:
        try:
            response = client.chat.completions.create(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), messages=build_question_messages(interview_type, target_role, experience_level, count), response_format={"type": "json_object"}, temperature=0.5)
            content = response.choices[0].message.content or "{}"
            questions = json.loads(content).get("questions", [])
            clean_questions = [str(item).strip() for item in questions if str(item).strip()]
            if len(clean_questions) >= count:
                return clean_questions[:count], "groq"
            logger.warning("Groq returned too few interview questions; using fallback questions.")
        except Exception:
            logger.exception("Groq interview-question generation failed; using fallback questions.")
    else:
        logger.info("GROQ_API_KEY is not configured; using fallback interview questions.")
    return FALLBACKS.get(interview_type, FALLBACKS["behavioral"])[:count], "fallback"


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
            return max(0, min(100, int(result["score"]))), feedback, "groq"
        except Exception:
            logger.exception("Groq interview-answer evaluation failed; using local evaluation.")
    else:
        logger.info("GROQ_API_KEY is not configured; using local answer evaluation.")
    words = len(answer.split())
    score = min(85, 35 + min(words, 100) // 2)
    feedback = "Good start. Add a specific example, your actions, and a measurable result." if words < 60 else "Clear answer. Make the result more measurable and connect it directly to the role."
    return score, feedback, "local"
