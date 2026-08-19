import ast
import unittest
from pathlib import Path


AUTH_ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"


class OAuthFrontendUrlTests(unittest.TestCase):
    def test_default_callback_frontend_is_github_pages(self):
        tree = ast.parse(AUTH_ROUTER.read_text())
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "FRONTEND_URL" for target in node.targets)
        )
        self.assertIsInstance(assignment.value, ast.Call)
        self.assertEqual(
            ast.literal_eval(assignment.value.args[1]),
            "https://uyen11a1-star.github.io/minecraft-modding-hub/",
        )


if __name__ == "__main__":
    unittest.main()
