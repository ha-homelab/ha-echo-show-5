"""Synthetic optional APK checks; no network, downloads or device access."""
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


class OptionalApkChecks:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = mock.patch.object(artifacts, 'ROOT', self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def make_artifact(self, name='optional-fixture.apk'):
        path = self.root / 'downloads' / name
        path.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as package:
            package.writestr('AndroidManifest.xml', b'Synthetic APK fixture, not installable.')
        self.record(path)
        return path

    def record(self, path):
        self.metadata = {'name': path.name, 'size': path.stat().st_size,
                         'sha256': artifacts.digest(path),
                         'url': 'https://example.invalid/optional-fixture.apk'}
        (self.root / (self.kind + '-artifact.json')).write_text(json.dumps(self.metadata))

    def test_apk_verifies_and_cli_accepts_kind(self):
        path = self.make_artifact()
        self.assertEqual(artifacts.verify(self.kind), path)
        with mock.patch.object(sys, 'argv', ['artifacts.py', 'verify', self.kind]), \
                mock.patch('builtins.print') as output:
            artifacts.main()
        output.assert_called_once_with('Verified ' + str(path))

    def test_rejects_wrong_container_suffix(self):
        self.make_artifact('optional-fixture.zip')
        with self.assertRaisesRegex(ValueError, 'Unexpected file type'):
            artifacts.verify(self.kind)

    def test_rejects_hash_matching_non_archive(self):
        path = self.make_artifact()
        path.write_bytes(b'Not an APK archive')
        self.record(path)
        with self.assertRaises(zipfile.BadZipFile):
            artifacts.verify(self.kind)

    def test_checks_crc_even_when_manifest_digest_matches(self):
        path = self.make_artifact()
        with zipfile.ZipFile(path) as package:
            member = package.getinfo('AndroidManifest.xml')
            start = member.header_offset + 30 + len(member.filename.encode()) + len(member.extra)
        data = bytearray(path.read_bytes())
        data[start] ^= 1
        path.write_bytes(data)
        self.record(path)
        with self.assertRaisesRegex(ValueError, 'Archive CRC'):
            artifacts.verify(self.kind)

    def test_fetch_uses_manifest_and_verifies_download(self):
        path = self.make_artifact()
        payload = path.read_bytes()
        path.unlink()
        with mock.patch.object(artifacts.urllib.request, 'urlopen', return_value=io.BytesIO(payload)) as get:
            self.assertEqual(artifacts.fetch(self.kind), path)
        request = get.call_args[0][0]
        self.assertEqual(request.full_url, self.metadata['url'])
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse(path.with_name(path.name + '.partial').exists())

    def test_fetch_rejects_modified_bytes_without_publishing_file(self):
        path = self.make_artifact()
        payload = path.read_bytes() + b'modified'
        path.unlink()
        with mock.patch.object(artifacts.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(ValueError, 'size/SHA256'):
                artifacts.fetch(self.kind)
        self.assertFalse(path.exists())
        self.assertFalse(path.with_name(path.name + '.partial').exists())

    def test_fetch_rejects_bad_crc_before_publishing_or_replacing_file(self):
        for destination_appears_during_download in (False, True):
            with self.subTest(existing_destination=destination_appears_during_download):
                path = self.make_artifact()
                valid_payload = path.read_bytes()
                corrupted = bytearray(valid_payload)
                corrupted[corrupted.index(b'Synthetic APK fixture')] ^= 1
                path.write_bytes(corrupted)
                self.record(path)  # Size and SHA256 match; only the ZIP CRC is invalid.
                path.unlink()

                def download(*args, **kwargs):
                    if destination_appears_during_download:
                        path.write_bytes(valid_payload)
                    return io.BytesIO(corrupted)

                with mock.patch.object(artifacts.urllib.request, 'urlopen', side_effect=download):
                    with self.assertRaisesRegex(ValueError, 'Archive CRC'):
                        artifacts.fetch(self.kind)
                if destination_appears_during_download:
                    self.assertEqual(path.read_bytes(), valid_payload)
                else:
                    self.assertFalse(path.exists())
                self.assertFalse(path.with_name(path.name + '.partial').exists())

    def test_fetch_keeps_existing_verified_destination(self):
        path = self.make_artifact()
        payload = path.read_bytes()
        with mock.patch.object(artifacts.urllib.request, 'urlopen') as get:
            self.assertEqual(artifacts.fetch(self.kind), path)
        get.assert_not_called()
        self.assertEqual(path.read_bytes(), payload)

    def test_fetch_checks_final_suffix_before_publishing(self):
        path = self.make_artifact('optional-fixture.zip')
        payload = path.read_bytes()
        path.unlink()
        with mock.patch.object(artifacts.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(ValueError, 'Unexpected file type'):
                artifacts.fetch(self.kind)
        self.assertFalse(path.exists())
        self.assertFalse(path.with_name(path.name + '.partial').exists())


class VacaArtifactTests(OptionalApkChecks, unittest.TestCase):
    kind = 'vaca'


class AndroidIpCameraArtifactTests(OptionalApkChecks, unittest.TestCase):
    kind = 'androidipcamera'


class JitsiArtifactTests(OptionalApkChecks, unittest.TestCase):
    kind = 'jitsi'


if __name__ == '__main__':
    unittest.main()
