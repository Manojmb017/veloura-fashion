from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/auth/register/"
        self.login_url = "/api/auth/login/"
        self.refresh_url = "/api/auth/token/refresh/"
        self.me_url = "/api/auth/me/"

    def test_register_success(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "strongpassword123",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "jane@example.com")
        self.assertEqual(response.data["user"]["name"], "Jane Doe")
        self.assertTrue(User.objects.filter(username="jane@example.com").exists())

    def test_register_duplicate_email(self):
        User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="password123",
            first_name="Existing User",
        )
        payload = {
            "name": "Another User",
            "email": "existing@example.com",
            "password": "password123",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_me_endpoint(self):
        User.objects.create_user(
            username="loginuser@example.com",
            email="loginuser@example.com",
            password="mysecretpassword",
            first_name="Login User",
        )
        response = self.client.post(
            self.login_url,
            {"email": "loginuser@example.com", "password": "mysecretpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]
        self.assertEqual(response.data["user"]["name"], "Login User")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_resp = self.client.get(self.me_url)
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["user"]["email"], "loginuser@example.com")

        self.client.credentials()
        ref_resp = self.client.post(self.refresh_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(ref_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", ref_resp.data)

    def test_login_wrong_password(self):
        User.objects.create_user(
            username="wrongpass@example.com",
            email="wrongpass@example.com",
            password="correctpassword",
        )
        response = self.client.post(
            self.login_url,
            {"email": "wrongpass@example.com", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_unauthenticated(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)



