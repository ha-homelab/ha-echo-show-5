"""The source qualification must execute both patch builds and gate failures."""
import json
import os
from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class AndroidSourceBuilds(unittest.TestCase):
    def test_both_patch_builds_are_required(self):
        tests = yaml.safe_load((ROOT / '.github/workflows/tests.yml').read_text())['jobs']
        self.assertEqual(tests['android-source-builds']['uses'],
                         './.github/workflows/android-source-builds.yml')
        self.assertIn('android-source-builds', tests['ci-gate']['needs'])
        build = yaml.safe_load((ROOT / '.github/workflows/android-source-builds.yml').read_text())['jobs']['build']
        self.assertEqual(set(build['strategy']['matrix']['patch']), {'vaca', 'ottplay'})
        self.assertFalse(build['strategy']['fail-fast'])
        self.assertNotIn('continue-on-error', build)
        self.assertTrue(all('continue-on-error' not in step for step in build['steps']))

    def test_existing_gate_rejects_unsuccessful_android_result(self):
        gate = yaml.safe_load((ROOT / '.github/workflows/tests.yml').read_text())['jobs']['ci-gate']
        command = next(step['run'] for step in gate['steps'] if 'JOB_RESULTS' in step.get('env', {}))
        for status in ('success', 'failure', 'cancelled', 'skipped'):
            with self.subTest(status=status):
                results = {name: {'result': 'success'} for name in gate['needs']}
                results['android-source-builds']['result'] = status
                result = subprocess.run(['bash', '-c', command], cwd=ROOT,
                    env=dict(os.environ, JOB_RESULTS=json.dumps(results)), capture_output=True)
                self.assertEqual(result.returncode == 0, status == 'success')
