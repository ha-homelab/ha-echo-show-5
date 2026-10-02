"""Synthetic VACA artifact checks; no network, downloads or device access."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import artifacts


class VacaArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = mock.patch.object(artifacts, 'ROOT', self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def make_artifact(self, name='vaca-fixture.apk'):
        path = self.root / 'downloads' / name
        path.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as package:
            package.writestr('AndroidManifest.xml', b'Synthetic APK fixture, not installable.')
        self.record(path)
        return path

    def record(self, path):
        self.metadata = {'name': path.name, 'size': path.stat().st_size,
                         'sha256': artifacts.digest(path),
                         'url': 'https://example.invalid/vaca-fixture.apk'}
        (self.root / 'vaca-artifact.json').write_text(json.dumps(self.metadata))

    def test_vaca_apk_verifies_and_cli_accepts_kind(self):
        path = self.make_artifact()
        self.assertEqual(artifacts.verify('vaca'), path)
        with mock.patch.object(sys, 'argv', ['artifacts.py', 'verify', 'vaca']), \
                mock.patch('builtins.print') as output:
            artifacts.main()
        output.assert_called_once_with('Verified ' + str(path))

    def test_vaca_rejects_wrong_container_suffix(self):
        self.make_artifact('vaca-fixture.zip')
        with self.assertRaisesRegex(ValueError, 'Unexpected file type'):
            artifacts.verify('vaca')

    def test_vaca_rejects_hash_matching_non_archive(self):
        path = self.make_artifact()
        path.write_bytes(b'Not an APK archive')
        self.record(path)
        with self.assertRaises(zipfile.BadZipFile):
            artifacts.verify('vaca')

    def test_vaca_checks_crc_even_when_manifest_digest_matches(self):
        path = self.make_artifact()
        with zipfile.ZipFile(path) as package:
            member = package.getinfo('AndroidManifest.xml')
            start = member.header_offset + 30 + len(member.filename.encode()) + len(member.extra)
        data = bytearray(path.read_bytes())
        data[start] ^= 1
        path.write_bytes(data)
        self.record(path)
        with self.assertRaisesRegex(ValueError, 'Archive CRC'):
            artifacts.verify('vaca')

    def test_vaca_fetch_uses_manifest_and_verifies_download(self):
        path = self.make_artifact()
        payload = path.read_bytes()
        path.unlink()
        with mock.patch.object(artifacts.urllib.request, 'urlopen', return_value=io.BytesIO(payload)) as get:
            self.assertEqual(artifacts.fetch('vaca'), path)
        request = get.call_args[0][0]
        self.assertEqual(request.full_url, self.metadata['url'])
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse(path.with_name(path.name + '.partial').exists())

    def test_vaca_fetch_rejects_modified_bytes_without_publishing_file(self):
        path = self.make_artifact()
        payload = path.read_bytes() + b'modified'
        path.unlink()
        with mock.patch.object(artifacts.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(ValueError, 'size/SHA256'):
                artifacts.fetch('vaca')
        self.assertFalse(path.exists())
        self.assertFalse(path.with_name(path.name + '.partial').exists())


if __name__ == '__main__':
    unittest.main()
