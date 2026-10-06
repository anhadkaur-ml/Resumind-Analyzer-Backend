"""Reusable, privacy-safe event emails for completed employee workflows."""

import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def _email_preference_is_enabled(user, preference_name):
    """Require the master switch and the workflow-specific switch to be enabled."""
    return getattr(user, "email_notifications_enabled", True) and getattr(
        user, preference_name, True
    )


def send_workflow_email(user, subject, heading, message, action_path=""):
    """Notify the registered user without exposing report data in the email."""
    recipient = (getattr(user, "email", "") or "").strip()
    if not recipient:
        logger.info("Workflow email skipped because user %s has no email address.", user.pk)
        return False

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    action_url = f"{frontend_url}{action_path}" if action_path else frontend_url
    body = f"{heading}\n\n{message}\n\nSign in to view the details: {action_url}\n\n— Resumind"
    try:
        sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        return bool(sent)
    except Exception:
        # Notification delivery must never undo a successfully saved workflow.
        logger.exception("Workflow email could not be sent to user %s.", user.pk)
        return False


def send_analysis_ready_email(analysis):
    if not _email_preference_is_enabled(analysis.user, "email_resume_analysis"):
        return False
    return send_workflow_email(
        analysis.user,
        "Your Resumind analysis is ready",
        "Resume analysis completed",
        "Your resume analysis has finished successfully. Open Resumind to view the private report.",
        f"/employee/reports/{analysis.id}",
    )


def send_builder_completed_email(resume):
    if not _email_preference_is_enabled(resume.user, "email_resume_builder"):
        return False
    return send_workflow_email(
        resume.user,
        "Your Resumind resume is ready",
        "Resume Builder completed",
        "Your resume has been completed and is ready to preview, download, or analyze.",
        f"/employee/resume-builder/{resume.id}/edit?preview=1",
    )


def send_interview_result_email(session):
    if not _email_preference_is_enabled(session.user, "email_interview_results"):
        return False
    return send_workflow_email(
        session.user,
        "Your interview practice result is ready",
        "Interview practice completed",
        "Your practice interview has been completed. Open Resumind to review your private score and feedback.",
        f"/employee/interview-practice/{session.id}",
    )
