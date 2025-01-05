from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

class FirebaseAuthTests(TestCase):
    @patch("accounts.firebase_auth.auth.verify_id_token")
    def test_valid_token(self, mock_verify):
        mock_verify.return_value = {
            "uid": "test-uid",
            "email": "testuser@example.com",
        }

        client = APIClient()
        response = client.post("/api/accounts/login/", {"firebase_token": "valid-token"})
        self.assertEqual(response.status_code, 200)

    @patch("accounts.firebase_auth.auth.verify_id_token")
    def test_invalid_token(self, mock_verify):
        mock_verify.side_effect = Exception("Invalid token")

        client = APIClient()
        response = client.post("/api/accounts/login/", {"firebase_token": "invalid-token"})
        self.assertEqual(response.status_code, 401)
