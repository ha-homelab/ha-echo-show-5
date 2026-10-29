"""Fail-closed, idempotent source overlay tests using isolated fixture files."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('apply_guarded', HERE / 'apply.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

def sha(text): return hashlib.sha256(text.encode()).hexdigest()

class OverlayTests(unittest.TestCase):
    def test_public_metadata_is_valid_and_syntax_checked(self):
        manifest = json.loads((HERE / 'overlay.json').read_text())
        self.assertEqual(set(manifest), {'__init__.py', 'assist_satellite.py', 'services.yaml'})
        for name, row in manifest.items():
            self.assertEqual(len(row['after_sha256']), 64)
            if row['before_sha256'] is not None:
                self.assertEqual(len(row['before_sha256']), 64)
        for path in (HERE / 'src').glob('*.py'):
            ast.parse(path.read_text())

    def fixture(self, parent):
        overlay = parent / 'overlay'; overlay.mkdir()
        (overlay / 'src').mkdir()
        (overlay / 'source-dependencies.json').write_text('{}')
        (overlay / 'src/extra.py').write_text('VALUE = 1\n')
        source = parent / 'source'; source.mkdir()
        (source / 'base.py').write_text('VALUE = 1\n')
        manifest = {'base.py': {'before_sha256': sha('VALUE = 1\n'), 'after_sha256': sha('VALUE = 2\n'), 'replacements': [['VALUE = 1', 'VALUE = 2']]},
                    'services.yaml': {'before_sha256': None, 'after_sha256': sha('service: {}\n'), 'append': 'service: {}\n'}}
        (overlay / 'overlay.json').write_text(json.dumps(manifest))
        return overlay, source

    def test_check_does_not_mutate_and_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, source = self.fixture(Path(directory))
            with patch.object(module, 'HERE', overlay):
                self.assertTrue(module.apply(source, check=True))
                self.assertEqual((source / 'base.py').read_text(), 'VALUE = 1\n')
                self.assertFalse((source / 'extra.py').exists())
                self.assertTrue(module.apply(source))
                self.assertFalse(module.apply(source))
                self.assertEqual((source / 'base.py').read_text(), 'VALUE = 2\n')
                self.assertTrue((source / 'services.yaml').exists())

    def test_unknown_source_or_occupied_destination_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, source = self.fixture(Path(directory))
            with patch.object(module, 'HERE', overlay):
                (source / 'extra.py').write_text('occupied\n')
                with self.assertRaises(ValueError): module.apply(source)
                self.assertEqual((source / 'base.py').read_text(), 'VALUE = 1\n')
                (source / 'extra.py').unlink()
                (source / 'base.py').write_text('unknown\n')
                with self.assertRaises(ValueError): module.apply(source)
                self.assertFalse((source / 'services.yaml').exists())

    def test_partial_overlay_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, source = self.fixture(Path(directory))
            with patch.object(module, 'HERE', overlay):
                (source / 'base.py').write_text('VALUE = 2\n')
                with self.assertRaisesRegex(ValueError, 'Partially'):
                    module.apply(source)

if __name__ == '__main__': unittest.main()
