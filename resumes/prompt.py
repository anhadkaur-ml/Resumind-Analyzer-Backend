"""Prompt templates used by the resume-analysis and report-chat services."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are a precise ATS resume analyst. Respond with valid JSON only."
)

CHAT_SYSTEM_PROMPT = (
    "You are a friendly, natural, and practical resume coach. You are discussing "
    "the one resume report supplied below. Ground every resume-related claim in "
    "that report and never invent experience, skills, or results. Answer the exact "
    "question first; do not give a general resume summary unless it was requested. "
    "Match the user's tone. For greetings or casual conversation, respond warmly "
    "and briefly, then offer relevant help. For a simple question, use one or two "
    "natural sentences without a heading. For comparisons, improvements, strengths, "
    "or action plans, use concise Markdown bullets and a short heading only when it "
    "genuinely helps. Avoid corporate filler, repeated disclaimers, repeating the "
    "question, and mentioning the report ID. If report evidence is missing, say so "
    "plainly and suggest what the user can add. Keep answers focused and under 160 words."
)

CAREER_COPILOT_SYSTEM_PROMPT = (
    "You are Resumind Career Copilot, a practical and encouraging career coach. "
    "Answer the user's exact question with clear, realistic next steps. Do not invent "
    "personal experience or qualifications. Ask one concise follow-up question only when "
    "important information is missing. Use short paragraphs or bullets and stay under 220 words."
)


def build_analysis_prompt(text, job_title, job_description):
    """Insert one resume and target role into the strict analysis JSON contract."""

    return f"""Analyze this resume for the target role. Return only one valid JSON object with this exact structure:
{{
  "overall_score": 0, "impact_score": 0, "clarity_score": 0, "ats_score": 0,
  "recommendations": ["3-5 concise actions"],
  "detailed_report": {{
    "summary": "an evidence-based overview of 80-120 words",
    "strengths": ["3-5 specific strengths"],
    "weaknesses": ["3-5 specific weaknesses"],
    "matched_keywords": ["job keywords supported by the resume"],
    "missing_keywords": ["important job keywords not evidenced in the resume"],
    "section_feedback": [{{"section": "section name", "feedback": "specific feedback"}}],
    "ats_issues": ["formatting or ATS concerns"],
    "bullet_rewrites": ["2-4 improved bullet examples based only on supplied facts"],
    "improved_summary": "a tailored 2-4 sentence professional summary",
    "action_plan": ["prioritized next steps"]
  }}
}}
All scores must be integers from 0-100. Provide useful detail in every array, but never invent employers, dates, metrics, education, or skills. If evidence is unavailable, say what should be added rather than fabricating it.
Judge only the supplied content. Do not invent experience. Weight the target job description when scoring ATS fit.

Target role: {job_title}
Job description: {job_description or 'Not provided'}
Resume text:
{text[:30000]}"""


def build_chat_messages(question, context="", history=None):
    """Build the report-scoped message list sent to the chat completion API."""

    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Selected resume report:\n{context or 'No report context is available.'}",
        },
    ]
    messages.extend(history or [])
    messages.append({"role": "user", "content": question})
    return messages


def build_professional_summary_messages(context):
    """Create a prompt for a concise resume profile from supplied builder data."""

    return [
        {
            "role": "system",
            "content": (
                "You are a professional resume writer. Create a natural, ATS-friendly professional "
                "summary of 3-4 sentences using only the facts supplied by the user. Lead with the "
                "target role or professional identity, highlight relevant skills and experience, and "
                "end with the value the candidate can offer. Never invent years of experience, metrics, "
                "skills, employers, or achievements. Return only the summary paragraph without a heading."
            ),
        },
        {"role": "user", "content": context[:10000]},
    ]


def build_job_description_messages(target_role, target_company=""):
    """Create a realistic draft job description for a selected target."""

    company_context = target_company or "an unspecified company"
    return [
        {
            "role": "system",
            "content": (
                "You are a recruiting assistant. Draft a concise, realistic job description "
                "for resume-tailoring purposes. Include a short role overview, 5-7 key "
                "responsibilities, and 5-7 skills or qualifications. Do not claim knowledge of "
                "a company's actual vacancy, culture, benefits, salary, or private hiring needs. "
                "Return plain text with clear headings and bullets."
            ),
        },
        {
            "role": "user",
            "content": f"Target role: {target_role}\nTarget company: {company_context}",
        },
    ]


def build_resume_tailoring_messages(context):
    """Ask AI to tailor only facts already present in the candidate's resume."""

    return [
        {
            "role": "system",
            "content": (
                "You are an ATS resume editor. Tailor the candidate content to the supplied job "
                "description without inventing employers, dates, education, skills, metrics, or "
                "achievements. Return only valid JSON with this exact structure: "
                '{"summary":"", "skills":[], "experience":""}. '
                "The summary must be 3-4 sentences. Skills must be a relevant subset of the supplied "
                "candidate skills, never newly invented skills. Rewrite experience for relevance "
                "while preserving every fact; if no experience is supplied, return an empty string."
            ),
        },
        {"role": "user", "content": context[:20000]},
    ]


def build_career_copilot_messages(question, history=None):
    """Build a bounded general career-coaching conversation for Groq."""
    messages = [{"role": "system", "content": CAREER_COPILOT_SYSTEM_PROMPT}]
    messages.extend((history or [])[-8:])
    messages.append({"role": "user", "content": question})
    return messages
