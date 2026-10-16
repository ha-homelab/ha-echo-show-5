"""Keep browser execution required and release acceptance bound to its upload."""
from pathlib import Path
import json
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class BrowserWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())['jobs']

    def test_source_browser_job_is_a_required_ci_dependency(self):
        jobs = self.workflow('tests.yml')
        self.assertIn('browser-compatibility', jobs['ci-gate']['needs'])
        browser = jobs['browser-compatibility']
        self.assertEqual(browser['with']['browser-test-command'], 'node scripts/browser-acceptance.cjs')
        self.assertFalse(browser['with']['run-node-ci'])
        self.assertNotIn('continue-on-error', browser)
        self.assertIn("github.event_name == 'workflow_dispatch'", browser['with']['browser-extended'])
        self.assertEqual(jobs['ci-gate']['if'], '${{ !cancelled() }}')

    def test_release_browser_uses_the_same_immutable_upload(self):
        jobs = self.workflow('release-build.yml')
        browser = jobs['browser-release']
        self.assertEqual(browser['needs'], 'package')
        self.assertEqual(browser['with']['browser-artifact-id'], '${{ needs.package.outputs.browser-artifact-id }}')
        self.assertEqual(browser['with']['browser-prepare-command'], 'python3 scripts/browser_candidate.py prepare browser-candidate')
        steps = jobs['package']['steps']
        seal = next(i for i, step in enumerate(steps) if step.get('run') == 'python3 scripts/browser_candidate.py seal release-assets/package')
        upload = next(i for i, step in enumerate(steps) if step.get('id') == 'assets')
        self.assertLess(seal, upload)
        self.assertEqual(steps[upload]['with']['path'], 'release-assets/package/*')
        self.assertEqual(browser['with']['browser-release-channel'], '${{ inputs.channel }}')
        self.assertIn("inputs.channel == 'rc'", browser['with']['browser-extended'])

    def test_reviewed_matrix_covers_three_os_and_historical_browser_lines(self):
        matrix = json.loads((ROOT / '.github/browser-compatibility.json').read_text())
        self.assertEqual(len(matrix), 35)
        self.assertEqual(len([row for row in matrix if row['tier'] == 'required']), 5)
        self.assertEqual({row['engine'] for row in matrix}, {'chromium', 'firefox', 'webkit'})
        self.assertEqual({row['os'] for row in matrix}, {'ubuntu-latest', 'windows-2022', 'macos-15'})
        self.assertEqual(len({row['playwright'] for row in matrix}), 3)


if __name__ == '__main__':
    unittest.main()
