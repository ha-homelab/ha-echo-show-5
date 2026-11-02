"""Guard the old-Python template tests' complete hashed install."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TemplateLockTests(unittest.TestCase):
    def test_ci_uses_the_hashed_template_lock(self):
        workflow = (ROOT / ".github/workflows/tests.yml").read_text()
        self.assertIn("python -m pip install --require-hashes --only-binary=:all: -r tests/requirements-template.txt", workflow)
        self.assertNotIn("pip install 'Jinja2==", workflow)

    def test_all_template_dependencies_have_hashes(self):
        lock = (ROOT / "tests/requirements-template.txt").read_text()
        packages = set()
        for line in lock.replace("\\\n", " ").splitlines():
            if not line or line.lstrip().startswith("#"):
                continue
            match = re.match(r"([a-z0-9_-]+)==", line)
            self.assertIsNotNone(match, line)
            packages.add(match[1])
            self.assertRegex(line, r"--hash=sha256:[0-9a-f]{64}")
        self.assertEqual(packages, {"jinja2", "markupsafe"})
        for line in (ROOT / "tests/requirements-template.in").read_text().splitlines():
            if line and not line.startswith("#"):
                self.assertIn(line.lower() + " ", lock)


if __name__ == "__main__":
    unittest.main()
