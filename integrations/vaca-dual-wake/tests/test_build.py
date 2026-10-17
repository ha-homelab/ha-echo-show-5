"""Host-side regression tests; no Android device, signing key or network is used."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location('dual_wake_build', Path(__file__).resolve().parents[1] / 'build.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.src = self.root / 'source'
        self.src.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Build test')
        (self.src / '.gitignore').write_text('build/\n.gradle/\nlocal.properties\n*.jks\n')
        (self.src / 'app.txt').write_text('upstream\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        (self.src / 'app.txt').write_text('patched\n')
        (self.src / 'new.txt').write_text('new model helper\n')
        self.git('add', '-N', 'new.txt')
        self.patch = self.root / 'change.patch'
        self.patch.write_text(self.git('diff'))
        self.git('reset', '--hard', '-q', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.src), *args], text=True)

    def prepare(self):
        return build.prepare_source(self.src, self.commit, self.patch)

    def test_clean_checkout_applies_exact_patch_and_is_idempotent(self):
        tree = self.prepare()
        self.assertEqual((self.src / 'app.txt').read_text(), 'patched\n')
        self.assertEqual((self.src / 'new.txt').read_text(), 'new model helper\n')
        self.assertEqual(self.prepare(), tree)

    def test_modified_patch_file_is_rejected_without_reset(self):
        self.prepare()
        (self.src / 'app.txt').write_text('unexpected change\n')
        with self.assertRaises(build.BuildError):
            self.prepare()
        self.assertEqual((self.src / 'app.txt').read_text(), 'unexpected change\n')

    def test_extra_untracked_source_is_rejected(self):
        self.prepare()
        (self.src / 'unreviewed.kt').write_text('unreviewed source\n')
        with self.assertRaises(build.BuildError):
            self.prepare()

    def test_extra_ignored_key_is_rejected(self):
        (self.src / 'unexpected.jks').write_text('not a real key')
        with self.assertRaises(build.BuildError):
            self.prepare()

    def test_build_directory_inside_source_is_not_a_generated_output(self):
        nested = self.src / 'app/src/main/java/build'
        nested.mkdir(parents=True)
        (nested / 'Injected.kt').write_text('class Injected')
        with self.assertRaises(build.BuildError):
            self.prepare()

    def test_sdk_file_symlink_is_rejected_without_modifying_target(self):
        target = self.root / 'preserve.txt'
        target.write_text('preserve')
        (self.src / 'local.properties').symlink_to(target)
        with self.assertRaises(build.BuildError):
            self.prepare()
        self.assertEqual(target.read_text(), 'preserve')

    def test_generated_output_symlink_is_rejected(self):
        (self.src / 'build').mkdir()
        target = self.root / 'outside'
        target.mkdir()
        (self.src / 'build' / 'outside').symlink_to(target, target_is_directory=True)
        with self.assertRaises(build.BuildError):
            self.prepare()

    def test_known_generated_outputs_and_sdk_file_are_allowed(self):
        (self.src / 'build').mkdir()
        (self.src / 'build' / 'output.txt').write_text('generated')
        (self.src / 'local.properties').write_text('sdk.dir=/old-sdk')
        self.prepare()

    def test_staged_edit_is_rejected(self):
        (self.src / 'app.txt').write_text('staged edit\n')
        self.git('add', 'app.txt')
        with self.assertRaises(build.BuildError):
            self.prepare()

    def test_wrong_commit_is_rejected(self):
        with self.assertRaises(build.BuildError):
            build.prepare_source(self.src, '0' * 40, self.patch)


class PrivateDestinationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / 'source-release'
        self.root.mkdir()
        self.mock_root = patch.object(build, 'ROOT', self.root)
        self.mock_root.start()
        self.addCleanup(self.mock_root.stop)

    def test_extracted_archive_accepts_default_private_directories(self):
        for name in ('vaca-dual-wake-build', 'vaca-dual-wake-signing'):
            path = self.root / 'private' / name
            self.assertEqual(build.require_private_destination(path), path)
        self.assertFalse((self.root / 'private').exists())

    def test_extracted_archive_rejects_source_root_and_arbitrary_subdirectories(self):
        for path in (self.root, self.root / 'integrations' / 'build', self.root / 'keys'):
            with self.subTest(path=path), self.assertRaises(build.BuildError):
                build.require_private_destination(path)

    def test_explicit_external_directory_is_supported(self):
        path = self.base / 'external-signing'
        self.assertEqual(build.require_private_destination(path), path)

    def test_archive_private_symlink_cannot_escape_or_overwrite_source(self):
        external = self.base / 'outside'
        external.mkdir()
        (self.root / 'private').symlink_to(external, target_is_directory=True)
        with self.assertRaises(build.BuildError):
            build.require_private_destination(self.root / 'private' / 'signing')
        self.assertEqual(list(external.iterdir()), [])

    def test_git_checkout_still_requires_ignored_paths(self):
        subprocess.check_call(['git', 'init', '-q', str(self.root)])
        (self.root / '.gitignore').write_text('private/\n')
        path = self.root / 'private' / 'signing'
        self.assertEqual(build.require_private_destination(path), path)
        with self.assertRaises(build.BuildError):
            build.require_private_destination(self.root / 'keys')
        (self.root / '.gitignore').write_text('')
        with self.assertRaises(build.BuildError):
            build.require_private_destination(path)

    def test_damaged_git_checkout_does_not_become_archive_mode(self):
        (self.root / '.git').write_text('gitdir: /missing-git-directory-for-test\n')
        with self.assertRaises(build.BuildError):
            build.require_private_destination(self.root / 'private' / 'signing')

    def test_extracted_archive_inside_another_checkout_keeps_archive_rules(self):
        subprocess.check_call(['git', 'init', '-q', str(self.base)])
        (self.base / '.gitignore').write_text('*.tmp\n')
        path = self.root / 'private' / 'signing'
        self.assertEqual(build.require_private_destination(path), path)
        with self.assertRaises(build.BuildError):
            build.require_private_destination(self.root / 'keys.tmp')


class SigningIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.fingerprint = 'a' * 64
        self.mock = patch.object(build, 'signer_fingerprint', return_value=self.fingerprint)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def pair(self):
        (self.directory / 'vaca.jks').write_text('test fixture, not a real key')
        (self.directory / 'password').write_text('test fixture')

    def test_no_key_does_not_implicitly_generate_one(self):
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java')
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_incomplete_pair_never_regenerates_key(self):
        (self.directory / 'password').write_text('existing fixture')
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java', create=True)
        self.assertFalse((self.directory / 'vaca.jks').exists())

    def test_missing_pinned_key_cannot_be_recreated(self):
        (self.directory / 'signer.sha256').write_text(self.fingerprint)
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java', create=True)
        self.assertFalse((self.directory / 'vaca.jks').exists())

    def test_existing_unrecorded_key_requires_explicit_expected_fingerprint(self):
        self.pair()
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java')
        self.assertFalse((self.directory / 'signer.sha256').exists())

    def test_matching_existing_key_is_recorded_and_reused(self):
        self.pair()
        result = build.ensure_signer(self.directory, '/java', expected=self.fingerprint)
        self.assertEqual(result[2], self.fingerprint)
        self.assertEqual(build.ensure_signer(self.directory, '/java')[2], self.fingerprint)

    def test_mismatched_requested_or_recorded_key_is_rejected(self):
        self.pair()
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java', expected='b' * 64)
        self.assertFalse((self.directory / 'signer.sha256').exists())
        (self.directory / 'signer.sha256').write_text('b' * 64)
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java', expected=self.fingerprint)

    def test_create_flag_does_not_replace_existing_key(self):
        self.pair()
        with self.assertRaises(build.BuildError):
            build.ensure_signer(self.directory, '/java', create=True)
        self.assertEqual((self.directory / 'vaca.jks').read_text(), 'test fixture, not a real key')


class MetadataTests(unittest.TestCase):
    def test_java_properties_encode_unicode_and_backslashes(self):
        self.assertEqual(build.java_property_value("/SDK/é/😀"), r"/SDK/\u00e9/\ud83d\ude00")
        self.assertEqual(build.java_property_value(r"C:\SDK"), r"C\:\\SDK")

    def test_fingerprint_normalization(self):
        self.assertEqual(build.normalize_fingerprint(':'.join(['AB'] * 32)), 'ab' * 32)
        with self.assertRaises(build.BuildError):
            build.normalize_fingerprint('not a fingerprint')

    def test_missing_or_failed_jvm_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory)
            with self.assertRaises(build.BuildError):
                build.test_totals(src)
            reports = src / 'app/build/test-results/testDebugUnitTest'
            reports.mkdir(parents=True)
            report = reports / 'TEST-fixture.xml'
            report.write_text('<testsuite tests="9" failures="1" errors="0" skipped="0"/>')
            with self.assertRaises(build.BuildError):
                build.test_totals(src)
            report.write_text('<testsuite tests="9" failures="0" errors="0" skipped="0"/>')
            self.assertEqual(build.test_totals(src)['tests'], 9)


class ApkValidationTests(unittest.TestCase):
    def setUp(self):
        self.fingerprint = 'a' * 64
        self.signature = 'Signer #1 certificate SHA-256 digest: ' + self.fingerprint + '\n'
        self.manifest = (
            "package: name='com.msp1974.vacompanion' versionCode='7002' "
            "versionName='0.13.4+dualwake.2' platformBuildVersionName='16'\n"
            "native-code: 'armeabi-v7a'\n"
        )

    def validate(self):
        with patch.object(build, 'sdk_tool', side_effect=lambda sdk, name: name), \
             patch.object(build, 'run', side_effect=[SimpleNamespace(stdout=self.signature),
                                                    SimpleNamespace(stdout=self.manifest)]):
            build.validate_apk(Path('fixture.apk'), Path('sdk'), self.fingerprint)

    def test_expected_signed_armv7_artifact_is_accepted(self):
        self.validate()

    def test_wrong_signer_is_rejected(self):
        self.signature = self.signature.replace('a' * 64, 'b' * 64)
        with self.assertRaises(build.BuildError):
            self.validate()

    def test_signer_mismatch_reports_only_public_certificate_identity(self):
        self.signature = self.signature.replace('a' * 64, 'b' * 64)
        with self.assertRaises(build.BuildError) as result:
            self.validate()
        self.assertIn('expected ' + self.fingerprint, str(result.exception))
        self.assertIn('b' * 64, str(result.exception))

    def test_stale_version_is_rejected(self):
        self.manifest = self.manifest.replace('7002', '7001')
        with self.assertRaises(build.BuildError):
            self.validate()

    def test_unexpected_abi_is_rejected(self):
        self.manifest = self.manifest.replace("'armeabi-v7a'", "'armeabi-v7a' 'arm64-v8a'")
        with self.assertRaises(build.BuildError):
            self.validate()


if __name__ == '__main__':
    unittest.main()
