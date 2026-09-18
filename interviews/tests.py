from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User


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
