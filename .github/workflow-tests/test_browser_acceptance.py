"""Keep browser execution required and release acceptance bound to its upload."""
from pathlib import Path
import base64
import json
import re
import struct
import unittest
import yaml
import zlib

ROOT = Path(__file__).resolve().parents[2]


class BrowserWorkflowTests(unittest.TestCase):
    def test_camera_fixture_has_valid_png_chunk_checksums(self):
        source = (ROOT / 'scripts/browser-acceptance.cjs').read_text()
        encoded = re.search(r"const image = Buffer.from\('([^']+)', 'base64'\)", source).group(1)
        image = base64.b64decode(encoded, validate=True)
        self.assertEqual(image[:8], b'\x89PNG\r\n\x1a\n')
        offset, chunks = 8, []
        while offset < len(image):
            length = struct.unpack('>I', image[offset:offset + 4])[0]
            chunk = image[offset + 4:offset + 8]
            data = image[offset + 8:offset + 8 + length]
            checksum = struct.unpack('>I', image[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(zlib.crc32(chunk + data), checksum, chunk.decode('ascii'))
            chunks.append(chunk)
            if chunk == b'IDAT':
                self.assertEqual(zlib.decompress(data), b'\x01\xff\xff')
            offset += length + 12
        self.assertEqual(offset, len(image))
        self.assertEqual(chunks, [b'IHDR', b'IDAT', b'IEND'])

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
