import os
import tempfile
import unittest

database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
database_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{database_file.name}"
os.environ["SECRET_KEY"] = "backup-test-secret"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.models import User
from app.models_post import Post


class AccountBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        os.unlink(database_file.name)

    def signup(self, email: str, name: str) -> dict:
        response = self.client.post(
            "/auth/signup",
            json={"email": email, "password": "strong-password", "name": name},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    @staticmethod
    def auth_headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_export_contains_only_owned_profile_and_posts(self):
        first = self.signup("backup-owner@example.com", "Backup Owner")
        second = self.signup("backup-other@example.com", "Backup Other")
        self.client.post(
            "/posts",
            headers=self.auth_headers(first["access_token"]),
            json={"title": "My guide", "content": "Owned content", "category": "Guide"},
        )
        self.client.post(
            "/posts",
            headers=self.auth_headers(second["access_token"]),
            json={"title": "Other guide", "content": "Other content", "category": "Guide"},
        )

        response = self.client.get("/account/backup", headers=self.auth_headers(first["access_token"]))

        self.assertEqual(response.status_code, 200)
        backup = response.json()
        self.assertEqual(backup["schema_version"], "modden-backup-v1")
        self.assertEqual(backup["profile"]["name"], "Backup Owner")
        self.assertNotIn("email", backup["profile"])
        self.assertEqual([post["title"] for post in backup["posts"]], ["My guide"])
        self.assertNotIn("author_id", backup["posts"][0])

    def test_restore_ignores_foreign_identifiers_and_adds_posts_to_current_user(self):
        account = self.signup("restore-owner@example.com", "Before restore")
        payload = {
            "backup": {
                "schema_version": "modden-backup-v1",
                "exported_at": "2026-08-19T00:00:00",
                "profile": {"name": "After restore", "avatar_url": "https://example.com/avatar.png", "email": "ignored@example.com"},
                "posts": [{"title": "Restored note", "content": "Recovered safely", "category": "Dev log", "created_at": "2026-08-18T00:00:00", "author_id": 9999}],
            }
        }

        response = self.client.post(
            "/account/restore",
            headers=self.auth_headers(account["access_token"]),
            json=payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"restored_posts": 1, "profile_updated": True})
        backup = self.client.get("/account/backup", headers=self.auth_headers(account["access_token"])).json()
        self.assertEqual(backup["profile"]["name"], "After restore")
        self.assertEqual(backup["posts"][0]["title"], "Restored note")

    def test_backup_requires_a_valid_session(self):
        response = self.client.get("/account/backup")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
