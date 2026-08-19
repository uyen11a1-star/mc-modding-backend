import ast
import unittest
from pathlib import Path


AUTH_ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
MAIN_APP = Path(__file__).resolve().parents[1] / "app" / "main.py"
GITHUB_PAGES_URL = "https://uyen11a1-star.github.io/minecraft-modding-hub/"


def frontend_default(source_file: Path) -> str:
    tree = ast.parse(source_file.read_text())
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id in {"FRONTEND_URL", "_frontend_url"}
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Call)
    return ast.literal_eval(assignment.value.args[1])


class OAuthFrontendUrlTests(unittest.TestCase):
    def test_default_callback_frontend_is_github_pages(self):
        self.assertEqual(frontend_default(AUTH_ROUTER), GITHUB_PAGES_URL)

    def test_default_cors_frontend_is_github_pages(self):
        self.assertEqual(frontend_default(MAIN_APP), GITHUB_PAGES_URL)


if __name__ == "__main__":
    unittest.main()
