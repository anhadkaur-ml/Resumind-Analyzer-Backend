"""External AI provider integration for the resumes app."""

import json
import os

from groq import Groq

from .prompt import ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt, build_career_copilot_messages, build_chat_messages, build_job_description_messages, build_professional_summary_messages, build_resume_tailoring_messages


def request_resume_analysis(text, job_title, job_description):
    """Request a structured resume analysis and return its decoded JSON data."""

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_analysis_prompt(text, job_title, job_description),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        # Returning None lets the analysis layer use its deterministic fallback.
        return None


def ask_groq(question, context="", history=None):
    """Send a report-scoped chat question to Groq."""

    # Provider secrets remain on the Django server and never reach the browser.
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return (
            "Groq is not configured yet. Add your GROQ_API_KEY to backend/.env and restart the Django server.",
            "local",
        )

    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=build_chat_messages(question, context, history),
            temperature=0.45,
        )
        return response.choices[0].message.content.strip(), "groq"
    except Exception:
        # Do not expose provider or server details in a client-facing error.
        return "I could not reach Groq right now. Please try again in a moment.", "unavailable"


def generate_professional_summary(context):
    """Generate a candidate summary from the current Resume Builder facts."""

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None, "local"
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=build_professional_summary_messages(context),
            temperature=0.4,
        )
        return response.choices[0].message.content.strip(), "groq"
    except Exception:
        return None, "unavailable"


def generate_job_description(target_role, target_company=""):
    """Generate a reviewable job-description draft for Resume Builder."""

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None, "local"
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=build_job_description_messages(target_role, target_company),
            temperature=0.35,
        )
        return response.choices[0].message.content.strip(), "groq"
    except Exception:
        return None, "unavailable"


def tailor_builder_content(context):
    """Return validated, fact-preserving resume suggestions as structured data."""

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None, "local"
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=build_resume_tailoring_messages(context),
            response_format={"type": "json_object"},
            temperature=0.25,
        )
        result = json.loads(response.choices[0].message.content)
        if not isinstance(result, dict) or not isinstance(result.get("summary"), str):
            return None, "unavailable"
        skills = result.get("skills", [])
        result["skills"] = [str(skill).strip() for skill in skills if str(skill).strip()] if isinstance(skills, list) else []
        result["experience"] = str(result.get("experience", "")).strip()
        return result, "groq"
    except Exception:
        return None, "unavailable"


def ask_career_copilot(question, history=None):
    """Return focused career guidance without exposing the Groq key to the client."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=build_career_copilot_messages(question, history),
            temperature=0.45,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None
