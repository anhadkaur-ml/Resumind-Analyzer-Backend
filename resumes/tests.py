from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from accounts.models import User
from .models import BuilderResume, ChatConversation, ChatMessage, ResumeAnalysis


class ResumeAnalysisApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="employee", email="employee@example.com", password="test-pass-123", role="employee")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_analysis_and_load_dashboard(self):
        resume = SimpleUploadedFile(
            "resume.pdf",
            b"Summary Experience Skills Education Designed and improved a product by 35 percent. Led a team and reduced delivery time by 20%.",
            content_type="application/pdf",
        )
        response = self.client.post(
            "/api/resumes/analyses/",
            {"resume": resume, "job_title": "Product Designer", "job_description": "Product design user research collaboration"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["original_filename"], "resume.pdf")
        self.assertIn("overall_score", response.data)
        self.assertIn("detailed_report", response.data)
        self.assertIn("section_feedback", response.data["detailed_report"])

        dashboard = self.client.get("/api/resumes/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["analysis_count"], 1)
        self.assertEqual(dashboard.data["latest"]["id"], response.data["id"])

    @patch.dict("os.environ", {"GROQ_API_KEY": ""})
    def test_ask_ai_requires_no_browser_side_api_key(self):
        analysis = ResumeAnalysis.objects.create(
            user=self.user,
            resume_file=SimpleUploadedFile("coach.pdf", b"resume content", content_type="application/pdf"),
            original_filename="coach.pdf",
            job_title="Developer",
            overall_score=80,
            impact_score=80,
            clarity_score=80,
            ats_score=80,
            status="Strong",
            recommendations=["Add metrics"],
            detailed_report={"summary": "A detailed report."},
        )
        response = self.client.post("/api/resumes/ask-ai/", {"question": "How can I improve my resume?", "analysis_id": analysis.id}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("answer", response.data)
        self.assertEqual(response.data["provider"], "local")
        self.assertEqual(response.data["analysis_id"], analysis.id)

    @patch("resumes.views.ask_groq", return_value=("Report-specific answer", "test"))
    def test_ask_ai_uses_selected_owned_report_only(self, mocked_ask_groq):
        selected = ResumeAnalysis.objects.create(
            user=self.user,
            resume_file=SimpleUploadedFile("selected.pdf", b"selected", content_type="application/pdf"),
            original_filename="selected.pdf",
            job_title="Backend Developer",
            overall_score=91,
            impact_score=90,
            clarity_score=89,
            ats_score=94,
            status="Excellent",
            recommendations=["Keep the quantified outcomes"],
            detailed_report={"summary": "Selected report summary", "strengths": ["Django"]},
        )
        history = [
            {"role": "user", "content": "Summarize my resume."},
            {"role": "assistant", "content": "Your resume targets backend development."},
        ]
        # Pre-save two messages to confirm Django forwards database history,
        # rather than trusting history submitted by the browser.
        conversation = ChatConversation.objects.create(user=self.user, analysis=selected)
        for message in history:
            ChatMessage.objects.create(conversation=conversation, role=message["role"], content=message["content"])
        response = self.client.post(
            "/api/resumes/ask-ai/",
            {"question": "What are my strengths?", "analysis_id": selected.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        context = mocked_ask_groq.call_args.args[1]
        self.assertIn("selected.pdf", context)
        self.assertIn("Selected report summary", context)
        self.assertEqual(mocked_ask_groq.call_args.args[2], history)
        self.assertEqual(response.data["resume"], "selected.pdf")
        self.assertEqual(response.data["message"]["role"], "assistant")
        self.assertEqual(conversation.messages.count(), 4)

        # Reopening a report must return all messages saved for that report.
        saved_history = self.client.get(f"/api/resumes/ask-ai/history/{selected.id}/")
        self.assertEqual(saved_history.status_code, 200)
        self.assertEqual(len(saved_history.data["results"]), 4)

        # Clearing history removes the conversation and cascades to its messages.
        cleared = self.client.delete(f"/api/resumes/ask-ai/history/{selected.id}/")
        self.assertEqual(cleared.status_code, 204)
        self.assertFalse(ChatConversation.objects.filter(id=conversation.id).exists())

        other_user = User.objects.create_user(username="other", email="other@example.com", password="test-pass-123", role="employee")
        other_report = ResumeAnalysis.objects.create(
            user=other_user,
            resume_file=SimpleUploadedFile("private.pdf", b"private", content_type="application/pdf"),
            original_filename="private.pdf",
            job_title="Private Role",
            overall_score=70,
            impact_score=70,
            clarity_score=70,
            ats_score=70,
            status="Good",
            recommendations=[],
            detailed_report={},
        )
        forbidden = self.client.post("/api/resumes/ask-ai/", {"question": "Show this report", "analysis_id": other_report.id}, format="json")
        self.assertEqual(forbidden.status_code, 404)

    def test_report_detail_download_and_delete(self):
        analysis = ResumeAnalysis.objects.create(
            user=self.user,
            resume_file=SimpleUploadedFile("test.pdf", b"resume content", content_type="application/pdf"),
            original_filename="test.pdf",
            job_title="Developer",
            overall_score=80,
            impact_score=80,
            clarity_score=80,
            ats_score=80,
            status="Strong",
            recommendations=["Add metrics"],
            detailed_report={"summary": "A detailed report."},
        )
        detail = self.client.get(f"/api/resumes/analyses/{analysis.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["detailed_report"]["summary"], "A detailed report.")

        download = self.client.get(f"/api/resumes/analyses/{analysis.id}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])
        download.close()

        deleted = self.client.delete(f"/api/resumes/analyses/{analysis.id}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(ResumeAnalysis.objects.filter(id=analysis.id).exists())

    def test_builder_resume_crud_and_ownership(self):
        # Saving a draft accepts partial content and lets Django calculate its
        # completion percentage instead of trusting a browser-supplied value.
        created = self.client.post(
            "/api/resumes/builder/",
            {
                "title": "Backend Developer Resume",
                "target_role": "Backend Developer",
                "template": "Modern ATS",
                "status": "Draft",
                "full_name": "Test Employee",
                "email": "employee@example.com",
                "education_entries": [{"degree": "B.Tech", "field": "Computer Science", "institution": "Test University", "start_year": "2020", "end_year": "2024"}],
                "skill_items": ["Python", "Django", "python"],
                "project_entries": [{"name": "Resumind", "technologies": "Django, React", "description": "Built a resume platform.", "link": "https://example.com"}],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        resume_id = created.data["id"]
        self.assertGreater(created.data["completion"], 0)
        self.assertLess(created.data["completion"], 100)
        self.assertEqual(created.data["skill_items"], ["Python", "Django"])
        self.assertEqual(created.data["education_entries"][0]["degree"], "B.Tech")
        self.assertEqual(created.data["project_entries"][0]["name"], "Resumind")

        updated = self.client.patch(
            f"/api/resumes/builder/{resume_id}/",
            {"status": "Completed"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["completion"], 100)

        other_user = User.objects.create_user(username="builder-other", email="builder-other@example.com", password="test-pass-123", role="employee")
        private_resume = BuilderResume.objects.create(user=other_user, title="Private Resume")
        self.assertEqual(self.client.get(f"/api/resumes/builder/{private_resume.id}/").status_code, 404)

        deleted = self.client.delete(f"/api/resumes/builder/{resume_id}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(BuilderResume.objects.filter(id=resume_id).exists())

    @patch("resumes.views.generate_professional_summary", return_value=("Backend developer skilled in Python and Django.", "test"))
    def test_builder_generates_professional_summary(self, mocked_generate):
        response = self.client.post(
            "/api/resumes/builder/generate-professional-summary/",
            {"target_role": "Backend Developer", "skills": ["Python", "Django"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Backend developer", response.data["summary"])
        self.assertIn("Target role: Backend Developer", mocked_generate.call_args.args[0])
