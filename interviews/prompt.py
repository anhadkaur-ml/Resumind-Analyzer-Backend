"""Prompts used by the interview practice AI service."""

import json


def build_question_messages(interview_type, target_role, experience_level, count):
    return [
        {"role": "system", "content": "You are a practical interview coach. Return valid JSON only."},
        {"role": "user", "content": (
            f"Create {count} distinct {interview_type} interview questions for a {experience_level} "
            f"candidate applying as {target_role}. Keep each question concise and realistic. "
            'Return exactly: {"questions":["question 1","question 2"]}'
        )},
    ]


def build_evaluation_messages(question, answer, interview_type, target_role):
    payload = json.dumps({"question": question, "answer": answer})
    return [
        {"role": "system", "content": "You are a supportive interview coach. Evaluate only the supplied answer and return valid JSON."},
        {"role": "user", "content": (
            f"Interview: {interview_type}; role: {target_role}. Data: {payload}. "
            "Give a fair score from 0 to 100 and one short, actionable feedback sentence. "
            'Return exactly: {"score":75,"feedback":"..."}'
        )},
    ]
