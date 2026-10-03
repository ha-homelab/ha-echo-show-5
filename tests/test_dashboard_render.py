"""Check local mapping validation and private output boundaries without HA."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_dashboard as dashboard


class DashboardRenderTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((dashboard.TEMPLATES / 'mapping.example.json').read_text())
        self.template = json.loads((dashboard.TEMPLATES / 'dashboard.template.json').read_text())
        self.mapping = {key: value.replace('replace_me_', 'fixture_')
                        for key, value in self.example.items()}

    def test_renders_native_camera_and_leaves_call_buttons_inactive(self):
        states = [{'entity_id': value} for key, value in self.mapping.items()
                  if key not in dashboard.PATH_KEYS]
        result = dashboard.render(self.template, self.mapping, self.example, states)
        self.assertNotIn('${', json.dumps(result))
        camera = result['views'][1]['cards'][0]['cards'][0]
        self.assertEqual((camera['aspect_ratio'], camera['fit_mode']), ('16:9', 'contain'))
        calls = result['views'][-1]['cards'][0]['cards'][1]['cards'][0]['cards'][:2]
        self.assertTrue(all(card['tap_action']['action'] == 'none' for card in calls))

    def test_rejects_unmapped_example_and_wrong_domain(self):
        with self.assertRaisesRegex(ValueError, 'Replace every'):
            dashboard.render(self.template, self.example, self.example)
        self.mapping['CAMERA'] = 'script.fixture_camera'
        with self.assertRaisesRegex(ValueError, 'wrong domain'):
            dashboard.render(self.template, self.mapping, self.example)

    def test_rejects_missing_mapping_and_external_navigation(self):
        missing = dict(self.mapping)
        del missing['CAMERA']
        with self.assertRaisesRegex(ValueError, 'exactly'):
            dashboard.render(self.template, missing, self.example)
        self.mapping['DASHBOARD_PATH'] = 'https://example.invalid/dashboard'
        with self.assertRaisesRegex(ValueError, 'local path'):
            dashboard.render(self.template, self.mapping, self.example)

    def test_rejects_missing_entity_in_supplied_inventory(self):
        with self.assertRaisesRegex(ValueError, 'absent'):
            dashboard.render(self.template, self.mapping, self.example, [])

    def test_validates_household_dashboard_paths_without_external_navigation(self):
        self.mapping['MAIN_HOME_PATH'] = '/dashboard-home/main/'
        result = dashboard.render(self.template, self.mapping, self.example)
        self.assertIn('/dashboard-home/main/', json.dumps(result))
        for path in ('https://example.invalid/home', '//example.invalid', '/home/../config',
                     '/home?auth=secret', '/home#fragment', '/%2f%2fexample.invalid'):
            with self.subTest(path=path):
                self.mapping['MAIN_HOME_PATH'] = path
                with self.assertRaisesRegex(ValueError, 'local path'):
                    dashboard.render(self.template, self.mapping, self.example)

    def test_rejects_non_object_mapping_cleanly(self):
        for value in (None, [], 'mapping', 12):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'JSON objects'):
                    dashboard.render(self.template, value, self.example)

    def test_private_write_is_exclusive_and_cannot_target_public_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            output = root / 'private' / 'dashboard.json'
            dashboard.write_private(output, {'views': []}, root)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                dashboard.write_private(output, {'changed': True}, root)
            with self.assertRaisesRegex(ValueError, 'private directory'):
                dashboard.write_private(root / 'README.md', {}, root)

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'private').mkdir()
            (root / 'outside').mkdir()
            (root / 'private' / 'linked').symlink_to(root / 'outside', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'private directory'):
                dashboard.write_private(root / 'private' / 'linked' / 'dashboard.json', {}, root)
            (root / 'private' / 'linked').unlink()
            (root / 'private').rmdir()
            (root / 'private').symlink_to(root / 'outside', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'outside the project'):
                dashboard.write_private(root / 'private' / 'dashboard.json', {}, root)


if __name__ == '__main__':
    unittest.main()
