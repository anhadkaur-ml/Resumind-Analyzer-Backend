"""Prompts used by the interview practice AI service."""

import json


def build_question_messages(interview_type, target_role, experience_level, count, resume_context=""):
    # Resume context is optional, allowing the same endpoint to support both
    # personalized and general interview sessions.
    resume_instruction = (
        f"Use the candidate resume below to personalize relevant questions. Do not invent facts.\nCandidate resume:\n{resume_context}"
        if resume_context else ""
    )
    return [
        # The system instruction constrains the response to machine-readable
        # JSON so the service can validate it before saving questions.
        {"role": "system", "content": "You are a practical interview coach. Return valid JSON only."},
        {"role": "user", "content": (
            f"Create {count} distinct {interview_type} interview questions for a {experience_level} "
            f"candidate applying as {target_role}. Keep each question concise and realistic. "
            f"{resume_instruction} "
            'Return exactly: {"questions":["question 1","question 2"]}'
        )},
    ]


def build_evaluation_messages(question, answer, interview_type, target_role):
    # Serializing user content as data helps keep it separate from the scoring
    # instructions surrounding it.
    payload = json.dumps({"question": question, "answer": answer})
    return [
        {"role": "system", "content": "You are a supportive interview coach. Evaluate only the supplied answer and return valid JSON."},
        {"role": "user", "content": (
            f"Interview: {interview_type}; role: {target_role}. Data: {payload}. "
            "Give a fair score from 0 to 100 and one short, actionable feedback sentence. "
            'Return exactly: {"score":75,"feedback":"..."}'
        )},
    ]
