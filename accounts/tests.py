from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Notification, User


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.signup_url = "/api/auth/signup/"
        self.login_url = "/api/auth/login/"
        self.profile_url = "/api/auth/profile/"

    def test_signup_and_login_return_the_stored_role(self):
        signup_response = self.client.post(
            self.signup_url,
            {
                "full_name": "Test Recruiter",
                "email": "recruiter@example.com",
                "password": "SecurePass482!",
                "password_confirm": "SecurePass482!",
                "role": "hr",
            },
            format="json",
        )
        self.assertEqual(signup_response.status_code, 201)
        self.assertEqual(signup_response.data["user"]["role"], "hr")

        login_response = self.client.post(
            self.login_url,
            {
                "email": "recruiter@example.com",
                "password": "SecurePass482!",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.data["user"]["role"], "hr")
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)

        access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        profile_response = self.client.get(self.profile_url)
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.data["full_name"], "Test Recruiter")
        self.assertEqual(profile_response.data["email"], "recruiter@example.com")
        self.assertEqual(profile_response.data["role"], "hr")

    def test_profile_requires_authentication(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 401)

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(
            self.signup_url,
            {
                "full_name": "Test Employee",
                "email": "employee@example.com",
                "password": "SecurePass482!",
                "password_confirm": "DifferentPass482!",
                "role": "employee",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_notification_list_and_mark_all_read(self):
        user = User.objects.create_user(username="notify", email="notify@example.com", password="SecurePass482!", role="employee")
        Notification.objects.create(user=user, title="Report ready", message="Your report is ready.", link="/employee/reports/1")
        self.client.force_authenticate(user)

        listed = self.client.get("/api/auth/notifications/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data["unread_count"], 1)
        self.assertEqual(len(listed.data["results"]), 1)

        marked = self.client.post("/api/auth/notifications/read-all/")
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(Notification.objects.get(user=user).is_read)
