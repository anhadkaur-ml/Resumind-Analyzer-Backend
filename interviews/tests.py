from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from resumes.models import BuilderResume
from .service import QuestionGenerationError


class InterviewSessionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="employee", email="employee@example.com", password="pass1234", role="employee")
        self.client.force_authenticate(self.user)

    @patch("interviews.views.generate_questions", return_value=(["Question one?", "Question two?"], "fallback"))
    def test_session_answers_are_saved_and_session_completes(self, _generate):
        created = self.client.post("/api/interviews/sessions/", {"interview_type":"technical", "target_role":"Software Engineer", "experience_level":"Entry level"}, format="json")
        self.assertEqual(created.status_code, 201)
        session_id = created.data["id"]
        self.assertEqual(created.data["question_source"], "fallback")
        with patch("interviews.views.evaluate_answer", return_value=(80, "Good answer.", "local")):
            first = self.client.post(f"/api/interviews/sessions/{session_id}/answer/", {"answer":"I solved the problem with a tested approach."}, format="json")
            second = self.client.post(f"/api/interviews/sessions/{session_id}/answer/", {"answer":"I measured the result and shared it."}, format="json")
        self.assertEqual(first.data["status"], "in_progress")
        self.assertEqual(second.data["status"], "completed")
        self.assertEqual(second.data["overall_score"], 80)
        self.assertEqual(len(second.data["answers"]), 2)
        self.assertEqual(second.data["answers"][0]["evaluation_source"], "local")

    def test_anonymous_user_cannot_list_sessions(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/interviews/sessions/").status_code, 401)

    @patch("interviews.views.generate_questions")
    def test_supported_interview_types_can_create_sessions(self, generate):
        generate.return_value = (["Question one?"], "groq")
        for interview_type in ("behavioral", "technical", "role_specific", "hr_screening"):
            response = self.client.post("/api/interviews/sessions/", {"interview_type": interview_type, "target_role": "Software Engineer", "experience_level": "Entry level"}, format="json")
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["question_source"], "groq")

    @patch("interviews.views.generate_questions", return_value=(["One?", "Two?"], "fallback"))
    def test_question_can_be_skipped_and_session_can_end_early(self, _generate):
        created = self.client.post("/api/interviews/sessions/", {"interview_type":"behavioral", "target_role":"Designer", "experience_level":"Entry level"}, format="json")
        session_id = created.data["id"]
        skipped = self.client.post(f"/api/interviews/sessions/{session_id}/skip/", format="json")
        self.assertEqual(skipped.status_code, 200)
        self.assertEqual(skipped.data["current_index"], 1)
        self.assertEqual(skipped.data["answers"][0]["feedback"], "This question was skipped.")
        ended = self.client.post(f"/api/interviews/sessions/{session_id}/end/", format="json")
        self.assertEqual(ended.data["status"], "completed")
        self.assertEqual(ended.data["overall_score"], 0)

    @patch("interviews.views.generate_questions")
    def test_selected_question_count_is_used_for_generation(self, generate):
        generate.return_value = ([f"Question {index}?" for index in range(15)], "groq")
        response = self.client.post("/api/interviews/sessions/", {"interview_type":"technical", "target_role":"Software Engineer", "experience_level":"Mid-level", "question_count":15}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["questions"]), 15)
        generate.assert_called_once_with("technical", "Software Engineer", "Mid-level", count=15, resume_context="")

    def test_unsupported_question_count_is_rejected(self):
        response = self.client.post("/api/interviews/sessions/", {"interview_type":"technical", "target_role":"Software Engineer", "experience_level":"Mid-level", "question_count":12}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("interviews.views.generate_questions", side_effect=QuestionGenerationError("AI questions could not be generated right now. Please try again shortly."))
    def test_provider_failure_returns_retryable_error_without_creating_session(self, _generate):
        response = self.client.post(
            "/api/interviews/sessions/",
            {"interview_type":"technical", "target_role":"Software Engineer", "experience_level":"Mid-level", "question_count":5},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("try again", str(response.data["detail"]).lower())
        self.assertEqual(self.user.interview_sessions.count(), 0)

    @patch("interviews.views.generate_questions")
    def test_completed_owned_resume_personalizes_questions(self, generate):
        resume = BuilderResume.objects.create(
            user=self.user, title="Backend CV", status=BuilderResume.Status.COMPLETED,
            full_name="Employee", email="employee@example.com", target_role="Backend Developer",
            summary="Django developer", skill_items=["Python", "Django"],
            project_entries=[{"name": "Resumind", "technologies": "Django", "description": "Resume platform"}],
        )
        generate.return_value = (["How did you use Django in Resumind?"], "groq")
        response = self.client.post("/api/interviews/sessions/", {"interview_type":"technical", "target_role":"Backend Developer", "experience_level":"Entry level", "question_count":5, "resume_id":resume.id}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["resume_id"], resume.id)
        self.assertEqual(response.data["resume_title"], "Backend CV")
        context = generate.call_args.kwargs["resume_context"]
        self.assertIn("Python, Django", context)
        self.assertIn("Resumind", context)

    def test_another_users_resume_cannot_be_selected(self):
        other = User.objects.create_user(username="other", email="other@example.com", password="pass1234", role="employee")
        resume = BuilderResume.objects.create(user=other, title="Private", status=BuilderResume.Status.COMPLETED)
        response = self.client.post("/api/interviews/sessions/", {"interview_type":"technical", "target_role":"Developer", "experience_level":"Entry level", "question_count":5, "resume_id":resume.id}, format="json")
        self.assertEqual(response.status_code, 404)
