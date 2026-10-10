"""Offline regression checks for the version-gated VACA timeout patch."""

import ast
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "vaca_timeout_patch.py"
SPEC = importlib.util.spec_from_file_location("vaca_timeout_patch", SCRIPT)
timeout_patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timeout_patch)

# Exercise the source transform without vendoring or importing Home Assistant.
# Only tests substitute the digest; the production CLI accepts its pinned source.
SOURCE = b'''"""Synthetic selector with unrelated settings to preserve."""

class OtherSelect:
    _attr_options = ["off", "on"]

class WyomingSatelliteScreenTimeoutSelect:
    _attr_options = ["15", "30", "60", "120", "300", "600", "1800"]
    sentinel = "keep this setting"
'''


class TimeoutPatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "select.py"
        self.target.write_bytes(SOURCE)
        self.target.chmod(0o640)
        digest_patch = patch.object(
            timeout_patch, "EXPECTED", hashlib.sha256(SOURCE).hexdigest()
        )
        digest_patch.start()
        self.addCleanup(digest_patch.stop)

    def run_cli(self, *args):
        stdout = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), str(self.root), *map(str, args)]):
            with redirect_stdout(stdout):
                timeout_patch.main()
        return stdout.getvalue()

    def test_only_timeout_options_change_and_milliseconds_fit_android_int(self):
        before = ast.parse(SOURCE)
        after = ast.parse(timeout_patch.patched(SOURCE))

        def options(tree):
            selector = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef)
                and node.name == "WyomingSatelliteScreenTimeoutSelect"
            )
            return next(
                node.value for node in selector.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_attr_options"
                        for t in node.targets)
            )

        updated = options(after)
        self.assertEqual(ast.literal_eval(updated)[:-1], ast.literal_eval(options(before)))
        self.assertEqual(ast.literal_eval(updated)[-1], "2147483")
        updated.elts.pop()
        self.assertEqual(ast.dump(before), ast.dump(after))
        self.assertLessEqual(timeout_patch.MAX_SECONDS * 1000, 2**31 - 1)
        self.assertGreater((timeout_patch.MAX_SECONDS + 1) * 1000, 2**31 - 1)

    def test_validation_is_read_only(self):
        self.assertIn("Validated", self.run_cli())
        self.assertEqual(self.target.read_bytes(), SOURCE)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["select.py"])

    def test_unreviewed_source_rejected_before_creating_backup(self):
        changed = SOURCE + b"\n# unreviewed change\n"
        self.target.write_bytes(changed)
        backup = self.root / "original.py"
        with self.assertRaisesRegex(ValueError, "Unreviewed"):
            self.run_cli("--apply", "--writers-stopped", "--backup", backup)
        self.assertEqual(self.target.read_bytes(), changed)
        self.assertFalse(backup.exists())

    def test_patch_requires_exactly_one_option_list_and_valid_syntax(self):
        for source in [
            SOURCE.replace(timeout_patch.OLD.encode(), b"    sentinel = 1"),
            SOURCE + b"\nclass Duplicate:\n" + timeout_patch.OLD.encode() + b"\n",
            SOURCE + b"\ninvalid Python !\n",
        ]:
            with self.subTest(source=source):
                with patch.object(timeout_patch, "EXPECTED", hashlib.sha256(source).hexdigest()):
                    with self.assertRaises((ValueError, SyntaxError)):
                        timeout_patch.patched(source)

    def test_apply_preserves_original_backup_and_source_permissions(self):
        backup = self.root / "original.py"
        self.assertIn("Applied", self.run_cli("--apply", "--writers-stopped", "--backup", backup))
        self.assertEqual(backup.read_bytes(), SOURCE)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o640)
        self.assertEqual(self.target.read_bytes(), timeout_patch.patched(SOURCE))
        self.assertFalse((self.root / "select.py.timeout-patch.tmp").exists())

    def test_repeated_apply_rejects_patched_source_without_second_backup(self):
        self.run_cli("--apply", "--writers-stopped", "--backup", self.root / "original.py")
        updated = self.target.read_bytes()
        second = self.root / "second.py"
        with self.assertRaisesRegex(ValueError, "Unreviewed"):
            self.run_cli("--apply", "--writers-stopped", "--backup", second)
        self.assertEqual(self.target.read_bytes(), updated)
        self.assertFalse(second.exists())

    def test_existing_backup_is_not_clobbered(self):
        backup = self.root / "original.py"
        backup.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.run_cli("--apply", "--writers-stopped", "--backup", backup)
        self.assertEqual(backup.read_bytes(), b"keep")
        self.assertEqual(self.target.read_bytes(), SOURCE)

    def test_apply_requires_stopped_writers_declaration_before_any_write(self):
        backup = self.root / "original.py"
        with self.assertRaises(SystemExit), patch("sys.stderr", io.StringIO()):
            self.run_cli("--apply", "--backup", backup)
        self.assertEqual(self.target.read_bytes(), SOURCE)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["select.py"])

    def test_apply_requires_backup(self):
        with self.assertRaises(SystemExit), patch("sys.stderr", io.StringIO()):
            self.run_cli("--apply", "--writers-stopped")
        self.assertEqual(self.target.read_bytes(), SOURCE)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["select.py"])

    def test_symlink_source_is_rejected_without_mutating_target(self):
        other = self.root / "other.py"
        self.target.rename(other)
        self.target.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "regular"):
            self.run_cli("--apply", "--writers-stopped", "--backup", self.root / "original.py")
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(other.read_bytes(), SOURCE)
        self.assertFalse((self.root / "original.py").exists())

    def test_existing_temporary_file_is_not_clobbered(self):
        temporary = self.root / "select.py.timeout-patch.tmp"
        temporary.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.run_cli("--apply", "--writers-stopped", "--backup", self.root / "original.py")
        self.assertEqual(self.target.read_bytes(), SOURCE)
        self.assertEqual(temporary.read_bytes(), b"keep")

    def test_change_before_final_comparison_is_preserved_and_temporary_removed(self):
        read_bytes = Path.read_bytes
        reads = 0
        changed = SOURCE + b"\n# changed by another writer\n"

        def concurrent_read(path):
            nonlocal reads
            if path == self.target:
                reads += 1
                if reads == 2:
                    path.write_bytes(changed)
            return read_bytes(path)

        backup = self.root / "original.py"
        with patch.object(Path, "read_bytes", concurrent_read):
            with self.assertRaisesRegex(ValueError, "changed during deployment"):
                self.run_cli("--apply", "--writers-stopped", "--backup", backup)
        self.assertEqual(self.target.read_bytes(), changed)
        self.assertEqual(backup.read_bytes(), SOURCE)
        self.assertFalse((self.root / "select.py.timeout-patch.tmp").exists())


if __name__ == "__main__":
    unittest.main()
