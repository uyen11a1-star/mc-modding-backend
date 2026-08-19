import os
import unittest

if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
    raise RuntimeError("Set DATABASE_URL to the isolated PostgreSQL test database before running this test")

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


class PostgresStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.dialect.name != "postgresql":
            raise RuntimeError("PostgreSQL driver was not selected by SQLAlchemy")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def test_service_starts_with_postgresql_and_protects_backup(self):
        health = self.client.get("/")
        backup = self.client.get("/account/backup")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(backup.status_code, 401)


if __name__ == "__main__":
    unittest.main()
