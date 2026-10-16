"""Regression checks for the offline documentation validator."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_docs


class DocumentationTests(unittest.TestCase):
    def test_unicode_duplicate_headings_and_fenced_examples(self):
        source = "# Hello, `world`!\n# Hello, `world`!\n## Привет, мышка\n```md\n# Not a heading\n```\n"
        self.assertEqual(check_docs.anchors(source), {"hello-world", "hello-world-1", "привет-мышка"})

    def test_missing_target_and_heading_without_fetching_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            page = root / "README.md"
            page.write_text('# Start\n[yes](#start)\n[no](#absent)\n[no](missing.md)\n[web](https://example.invalid/)\n```\n[example](fake.md)\n```\n', encoding="utf-8")
            errors = check_docs.markdown_errors(page, root)
            self.assertEqual(len(errors), 2)
            self.assertIn("missing heading", errors[0])
            self.assertIn("missing local target", errors[1])

    def test_reference_links_percent_encoding_and_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "Two Words.md").write_text("# A heading\n", encoding="utf-8")
            page = root / "README.md"
            page.write_text('[target]: Two%20Words.md#a-heading\n[bad](../outside.md)\n', encoding="utf-8")
            errors = check_docs.markdown_errors(page, root)
            self.assertEqual(len(errors), 1)
            self.assertIn("escapes repository", errors[0])

    def test_svg_accessibility_and_remote_resource_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "diagram.svg"
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-labelledby="t d"><title id="t">Title</title><desc id="d">Description</desc><path d="M0 0 L1 1"/></svg>', encoding="utf-8")
            self.assertEqual(check_docs.svg_errors(path, root), [])
            path.write_text(path.read_text().replace('<path', '<image href="https://example.invalid/pixel"/><path'), encoding="utf-8")
            self.assertTrue(check_docs.svg_errors(path, root))


if __name__ == "__main__":
    unittest.main()
