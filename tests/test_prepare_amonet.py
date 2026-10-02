"""Synthetic artifact/bootstrap tests; never invoke Docker, NAS or USB."""
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import artifacts
import prepare_amonet as prepare
import validate_host_release as runtime


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(module, 'ROOT', self.root)
                        for module in (artifacts, prepare, runtime)]
        for item in self.patches:
            item.start()
        self.files = {
            'device.prop': b'DEVICE=cronos\nDEVICE_TYPE_ID=A1XWJRHALS1REP\n',
            'fastbrick.sh': b'#!/bin/bash\n# Synthetic fixture only\n',
            'profile.sh': b'# Synthetic fixture only\n',
            'bin/fastboot': b'Synthetic bytes, not executable code\n'}
        self.make_archive()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def make_archive(self, additional=(), omitted=()):
        downloads = self.root / 'downloads'
        downloads.mkdir(exist_ok=True)
        self.archive = downloads / 'amonet-cronos-v2.0.1.zip'
        with zipfile.ZipFile(self.archive, 'w') as package:
            for name, data in self.files.items():
                if name not in omitted:
                    package.writestr('amonet/' + name, data)
            package.writestr('META-INF/com/google/android/updater-script', b'Fixture only')
            for name, data in additional:
                package.writestr(name, data)
        checksum = artifacts.digest(self.archive)
        self.review = {'release': '2.0.1', 'product': 'cronos', 'archive_sha256': checksum,
                       'files': {name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()}}
        (self.root / 'amonet-review.json').write_text(json.dumps(self.review))
        metadata = {'name': self.archive.name, 'size': self.archive.stat().st_size, 'sha256': checksum}
        (self.root / 'amonet-artifact.json').write_text(json.dumps(metadata))

    def test_extract_exact_reviewed_files_and_idempotently_verify(self):
        target = prepare.prepare()
        self.assertEqual(prepare.prepare(), target)
        self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()},
                         set(self.files))
        for name, data in self.files.items():
            self.assertEqual((target / name).read_bytes(), data)
        self.assertEqual(prepare.verify_package()['archive_sha256'], self.review['archive_sha256'])
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_modified_archive_rejected_before_extraction(self):
        with self.archive.open('ab') as stream:
            stream.write(b'modified')
        with self.assertRaisesRegex(ValueError, 'size/SHA256'):
            prepare.prepare()
        self.assertFalse((self.root / 'vendor' / 'amonet').exists())

    def test_unsafe_zip_paths_rejected(self):
        for path in ('amonet/../../outside', '/outside', 'amonet\\outside'):
            with self.subTest(path=path):
                self.make_archive(additional=[(path, b'unsafe')])
                with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                    prepare.prepare()
                self.assertFalse((self.root / 'vendor' / 'amonet').exists())
                self.assertFalse(list((self.root / 'vendor').glob('.amonet-staging-*')))

    def test_zip_symlink_rejected(self):
        info = zipfile.ZipInfo('amonet/linked')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.make_archive(additional=[(info, b'../../outside')])
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            prepare.prepare()

    def test_archive_unreviewed_and_missing_files_rejected(self):
        self.make_archive(additional=[('amonet/unreviewed', b'extra')])
        with self.assertRaisesRegex(RuntimeError, 'Unreviewed'):
            prepare.prepare()
        self.make_archive(omitted=['profile.sh'])
        with self.assertRaisesRegex(RuntimeError, 'missing reviewed'):
            prepare.prepare()

    def test_existing_modified_tree_is_not_overwritten(self):
        target = prepare.prepare()
        (target / 'profile.sh').write_bytes(b'modified')
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            prepare.prepare()
        self.assertEqual((target / 'profile.sh').read_bytes(), b'modified')

    def test_existing_extra_file_and_symlink_rejected(self):
        target = prepare.prepare()
        extra = target / 'unreviewed'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(RuntimeError, 'unreviewed'):
            prepare.prepare()
        extra.unlink()
        (target / 'profile.sh').unlink()
        (target / 'profile.sh').symlink_to(target / 'fastbrick.sh')
        with self.assertRaisesRegex(RuntimeError, 'Symlink'):
            prepare.prepare()

    def test_wrong_model_rejected_despite_consistent_hashes(self):
        self.files['device.prop'] = b'DEVICE=checkers\nDEVICE_TYPE_ID=OTHER\n'
        self.make_archive()
        with self.assertRaisesRegex(RuntimeError, 'not cronos'):
            prepare.prepare()

    def test_mocked_host_validation_has_no_usb_and_writes_private_evidence(self):
        prepare.prepare()
        result = SimpleNamespace(returncode=0,
                                 stdout='fastboot version 28.0.0 rc1\ntimeout (GNU coreutils) 9.1\n',
                                 stderr='')
        image = 'sha256:' + 'a' * 64
        with patch.object(runtime.subprocess, 'run', return_value=result) as run:
            output = runtime.validate_host_release(image)
        command = run.call_args[0][0]
        self.assertNotIn('--device', command)
        self.assertNotIn('--privileged', command)
        self.assertEqual(command[command.index('--network') + 1], 'none')
        self.assertIn('--read-only', command)
        self.assertIn('--cap-drop', command)
        self.assertTrue(command[command.index('--mount') + 1].endswith(',readonly'))
        self.assertIn('exec', command[command.index('--tmpfs') + 1].split(','))
        self.assertNotIn('noexec', command[command.index('--tmpfs') + 1].split(','))
        self.assertIn('cp ./bin/fastboot /tmp/fastboot', command[-1])
        self.assertIn('chmod 700 /tmp/fastboot', command[-1])
        self.assertIn('/tmp/fastboot --version', command[-1])
        record = json.loads(output.read_text())
        self.assertEqual(record['image_id'], image)
        self.assertEqual(record['archive_sha256'], self.review['archive_sha256'])
        self.assertEqual(record['product'], 'cronos')
        self.assertIs(record['passed_without_usb'], True)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(output.parent.stat().st_mode & 0o777, 0o700)

    def test_failed_or_incomplete_runtime_check_writes_no_record(self):
        prepare.prepare()
        for result in (SimpleNamespace(returncode=1, stdout='', stderr='failure'),
                       SimpleNamespace(returncode=0, stdout='missing required checks', stderr='')):
            with patch.object(runtime.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'runtime check failed'):
                    runtime.validate_host_release('sha256:' + 'a' * 64)
            self.assertFalse((self.root / 'private' / 'host-release-validation.json').exists())

    def test_mutable_image_reference_never_starts_container(self):
        prepare.prepare()
        with patch.object(runtime.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'immutable'):
                runtime.validate_host_release('host-tools:latest')
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
