from types import SimpleNamespace

from django.core import mail
from django.test import SimpleTestCase, override_settings

from .email_service import (
    send_analysis_ready_email,
    send_interview_result_email,
    send_workflow_email,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Resumind <no-reply@example.com>",
    FRONTEND_URL="https://resumind.example.com",
)
class WorkflowEmailTests(SimpleTestCase):
    def test_email_goes_to_registered_address_with_private_app_link(self):
        user = SimpleNamespace(pk=1, email="employee@example.com")
        sent = send_workflow_email(user, "Ready", "Completed", "Open the app for details.", "/employee/reports/12")

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["employee@example.com"])
        self.assertIn("https://resumind.example.com/employee/reports/12", mail.outbox[0].body)

    def test_user_without_email_is_safely_skipped(self):
        user = SimpleNamespace(pk=2, email="")
        self.assertFalse(send_workflow_email(user, "Ready", "Completed", "Done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_disabled_analysis_email_is_not_sent(self):
        user = SimpleNamespace(
            pk=3,
            email="employee@example.com",
            email_notifications_enabled=True,
            email_resume_analysis=False,
        )
        analysis = SimpleNamespace(id=12, user=user)

        self.assertFalse(send_analysis_ready_email(analysis))
        self.assertEqual(len(mail.outbox), 0)

    def test_master_switch_disables_interview_email(self):
        user = SimpleNamespace(
            pk=4,
            email="employee@example.com",
            email_notifications_enabled=False,
            email_interview_results=True,
        )
        session = SimpleNamespace(id=8, user=user)

        self.assertFalse(send_interview_result_email(session))
        self.assertEqual(len(mail.outbox), 0)
