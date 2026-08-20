import os
import tempfile
import unittest
from unittest.mock import patch

database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
database_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{database_file.name}"
os.environ["SECRET_KEY"] = "resource-moderation-test-secret"
os.environ.pop("MODERATION_API_KEY", None)

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.moderation import moderate_resource


class ResourceModerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        os.unlink(database_file.name)

    def signup(self, email: str) -> dict:
        response = self.client.post(
            "/auth/signup",
            json={"email": email, "password": "strong-password", "name": "Resource Author"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    @staticmethod
    def headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def payload() -> dict:
        return {
            "name": "Lumen Shaders",
            "summary": "A performance-friendly shader preset for Minecraft players.",
            "description": "Includes installation notes, performance tips, and version changes for Minecraft.",
            "kind": "Shader Pack",
            "minecraft_version": "1.21.1",
            "loader": "Không yêu cầu",
            "release_version": "1.0.0",
            "file_name": "lumen-shaders.zip",
            "file_size": 2048,
        }

    def test_missing_ai_key_fails_closed_to_pending(self):
        result = moderate_resource(self.payload())
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["suggested_tags"], [])

    def test_approved_resource_is_public_but_rejected_resource_is_not(self):
        account = self.signup("resource-author@example.com")
        approved = {
            "status": "approved",
            "reason": "Legitimate Minecraft shader metadata.",
            "confidence": 0.92,
            "suggested_tags": ["shader", "1.21"],
        }
        with patch("app.routers.resources.moderate_resource", return_value=approved):
            response = self.client.post(
                "/resources", headers=self.headers(account["access_token"]), json=self.payload()
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "approved")
        self.assertEqual(len(self.client.get("/resources").json()), 1)

        rejected = {
            "status": "rejected",
            "reason": "Suspicious credential-theft claim.",
            "confidence": 0.98,
            "suggested_tags": [],
        }
        rejected_payload = self.payload() | {"name": "Bad resource", "file_name": "bad-resource.jar"}
        with patch("app.routers.resources.moderate_resource", return_value=rejected):
            response = self.client.post(
                "/resources", headers=self.headers(account["access_token"]), json=rejected_payload
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertEqual(len(self.client.get("/resources").json()), 1)
        mine = self.client.get("/resources/mine", headers=self.headers(account["access_token"])).json()
        self.assertEqual({item["status"] for item in mine}, {"approved", "rejected"})
