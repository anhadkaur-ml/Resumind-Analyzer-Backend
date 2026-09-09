import re
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

from .service import request_resume_analysis

STOP_WORDS = {"and", "the", "with", "for", "from", "that", "this", "will", "you", "your", "are", "our", "their", "have", "has", "into", "using", "role", "work", "team"}
ACTION_VERBS = {"achieved", "built", "created", "delivered", "designed", "developed", "drove", "improved", "increased", "launched", "led", "managed", "optimized", "reduced", "implemented", "collaborated", "analyzed", "owned", "streamlined"}


def _extract_docx(data):
    """Read visible paragraph text directly from a DOCX archive."""

    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def extract_resume_text(upload):
    """Extract text while resetting the upload so Django can save it later."""

    data = upload.read()
    upload.seek(0)
    suffix = Path(upload.name).suffix.lower()
    # PDF and DOCX have structured parsers; older DOC files use a safe text
    # fallback because they are stored in a binary legacy format.
    try:
        if suffix == ".pdf":
            return " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        if suffix == ".docx":
            return _extract_docx(data)
    except Exception:
        return ""
    decoded = data.decode("latin-1", errors="ignore")
    return " ".join(re.findall(r"[A-Za-z][A-Za-z0-9@.,+/#&()' -]{3,}", decoded))


def _keywords(value):
    """Normalize useful ATS keywords and remove common filler words."""

    return [word for word in re.findall(r"[a-z][a-z0-9+#.-]{2,}", value.lower()) if word not in STOP_WORDS]


def _status(score):
    """Convert a numeric score into the label shown in report history."""

    return "Excellent" if score >= 90 else "Strong" if score >= 80 else "Good" if score >= 70 else "Needs work"


def _analyze_locally(text, job_title, job_description):
    """Generate deterministic scores when Groq is unavailable or unconfigured."""

    # Local scoring looks for structure, action verbs, measurable outcomes,
    # and keywords shared with the target job description.
    normalized = re.sub(r"\s+", " ", text).lower()
    word_count = len(normalized.split())
    section_hits = sum(section in normalized for section in ("summary", "experience", "skills", "education", "projects"))
    action_hits = sum(normalized.count(verb) for verb in ACTION_VERBS)
    metric_hits = len(re.findall(r"\b\d+(?:\.\d+)?%|\$\s?\d+|\b\d+\+", normalized))
    clarity = min(96, 48 + min(20, word_count // 35) + section_hits * 5)
    impact = min(97, 48 + min(24, action_hits * 3) + min(24, metric_hits * 5))
    target_keywords = _keywords(f"{job_title} {job_description}")
    if target_keywords:
        counts = Counter(target_keywords)
        matched = sum(weight for word, weight in counts.items() if word in normalized)
        ats = min(96, 50 + round(46 * matched / max(1, sum(counts.values()))))
    else:
        ats = 55
    overall = round(impact * 0.35 + clarity * 0.30 + ats * 0.35)
    recommendations = []
    if metric_hits < 3:
        recommendations.append("Add measurable results to demonstrate the impact of your work.")
    if section_hits < 4:
        recommendations.append("Use clear Summary, Experience, Skills, and Education sections.")
    if ats < 80:
        recommendations.append(f"Add more relevant keywords from the {job_title} job description.")
    if not recommendations:
        recommendations.append("Your resume is well structured; tailor the opening summary for each application.")
    resume_keywords = set(_keywords(text))
    requested_keywords = list(dict.fromkeys(_keywords(job_description)))
    matched = [word for word in requested_keywords if word in resume_keywords][:10]
    missing = [word for word in requested_keywords if word not in resume_keywords][:10]
    detailed_report = {
        "summary": f"This resume shows a { _status(overall).lower() } foundation for the {job_title} role. The strongest opportunity is to make achievements more measurable and align wording more closely with the target description.",
        "strengths": ["Uses recognizable resume sections that help recruiters scan the document.", "Includes experience and skills relevant to professional applications."],
        "weaknesses": recommendations,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "section_feedback": [
            {"section": "Professional summary", "feedback": "State the target role, strongest expertise, and one measurable outcome in 2–3 lines."},
            {"section": "Experience", "feedback": "Lead bullets with action verbs and connect responsibilities to measurable business results."},
            {"section": "Skills", "feedback": "Prioritize skills explicitly requested in the job description and remove unrelated items."},
            {"section": "Education", "feedback": "Keep qualification, institution, and graduation details concise and consistent."},
        ],
        "ats_issues": ["Use standard section headings and simple formatting.", "Mirror important job-description terminology naturally."],
        "bullet_rewrites": ["Replace responsibility-only bullets with: Action + task + measurable result."],
        "improved_summary": f"Results-focused professional targeting {job_title} opportunities, with relevant experience, practical skills, and a track record of contributing to team and business outcomes.",
        "action_plan": recommendations,
    }
    return {"overall_score": overall, "impact_score": impact, "clarity_score": clarity, "ats_score": ats, "status": _status(overall), "recommendations": recommendations, "detailed_report": detailed_report}


def _score(value):
    """Convert AI-provided values to safe integer scores from 0 to 100."""

    return max(0, min(100, int(round(float(value)))))


def analyze_resume(text, job_title, job_description):
    """Create the full analysis with Groq, falling back to local scoring."""

    # Always prepare a local result first so analysis still works during an AI
    # outage or when the server has no Groq API key.
    fallback = _analyze_locally(text, job_title, job_description)
    if not text.strip():
        return fallback
    try:
        result = request_resume_analysis(text, job_title, job_description)
        if result is None:
            return fallback
        # Parse and sanitize every AI field before saving it to the database.
        overall = _score(result["overall_score"])
        recommendations = [str(item).strip() for item in result.get("recommendations", []) if str(item).strip()][:5]
        report = result.get("detailed_report", {})
        if not isinstance(report, dict):
            report = {}
        list_fields = ("strengths", "weaknesses", "matched_keywords", "missing_keywords", "ats_issues", "bullet_rewrites", "action_plan")
        clean_report = {
            "summary": str(report.get("summary", fallback["detailed_report"]["summary"])).strip(),
            "improved_summary": str(report.get("improved_summary", fallback["detailed_report"]["improved_summary"])).strip(),
        }
        for field in list_fields:
            values = report.get(field, fallback["detailed_report"][field])
            clean_report[field] = [str(item).strip() for item in values if str(item).strip()][:10] if isinstance(values, list) else fallback["detailed_report"][field]
        sections = report.get("section_feedback", [])
        clean_report["section_feedback"] = [
            {"section": str(item.get("section", "Section")).strip(), "feedback": str(item.get("feedback", "")).strip()}
            for item in sections if isinstance(item, dict) and str(item.get("feedback", "")).strip()
        ][:8] or fallback["detailed_report"]["section_feedback"]
        return {
            "overall_score": overall,
            "impact_score": _score(result["impact_score"]),
            "clarity_score": _score(result["clarity_score"]),
            "ats_score": _score(result["ats_score"]),
            "status": _status(overall),
            "recommendations": recommendations or fallback["recommendations"],
            "detailed_report": clean_report,
        }
    except (KeyError, TypeError, ValueError):
        # Invalid provider data must not stop resume analysis.
        return fallback
