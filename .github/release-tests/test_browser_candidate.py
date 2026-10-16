"""Reject altered, unbounded and misattributed display release candidates."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import browser_candidate as candidate


class BrowserCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        self.names = sorted(['SOURCE_VERSION', 'release-files.json'] + ['integrations/show5-display/' + name for name in candidate.FILES])
        for name in self.names:
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(name)
        (self.root / 'release-files.json').write_text(json.dumps({'files': self.names}))
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'commit.gpgsign=false', '-c', 'user.name=Fixture', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        self.sha = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()
        self.env = patch.dict(os.environ, {'GITHUB_SHA': self.sha, 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2', 'CI_BROWSER_CANDIDATE_ARTIFACT_ID': '456'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.archive = self.assets / 'ha-echo-show-5-0.1.2.tar.gz'
        self.receipt = self.assets / 'release-inputs-package.json'
        self.write_archive()
        self.receipt.write_text(json.dumps({'source_sha': self.sha}))
        candidate.seal(self.assets, self.root)

    def write_archive(self, replace=None):
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name in self.names:
                data = (self.root / name).read_bytes()
                info = tarfile.TarInfo('ha-echo-show-5/' + name)
                info.size = len(data)
                if replace:
                    info, data = replace(info, data)
                archive.addfile(info, io.BytesIO(data))

    def prepare(self):
        candidate.prepare(self.assets, self.root / 'display', self.root)

    def test_exact_candidate_extracts_only_reviewed_assets_and_retains_identity(self):
        self.prepare()
        self.assertEqual({p.name for p in (self.root / 'display').iterdir()}, set(candidate.FILES) | {'candidate.json'})
        bound = json.loads((self.root / 'display/candidate.json').read_text())
        self.assertEqual(bound['candidateArtifactId'], '456')
        self.assertEqual(bound['sourceSha'], self.sha)
        self.assertEqual(bound['runAttempt'], '2')

    def test_foreign_source_run_attempt_and_missing_artifact_fail_before_output(self):
        for key, value in [('GITHUB_SHA', 'f' * 40), ('GITHUB_RUN_ID', '124'), ('GITHUB_RUN_ATTEMPT', '3'), ('CI_BROWSER_CANDIDATE_ARTIFACT_ID', '')]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse((self.root / 'display').exists())

    def test_changed_archive_or_source_is_rejected(self):
        with self.archive.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'digest'):
            self.prepare()
        candidate.seal(self.assets, self.root)
        (self.root / 'integrations/show5-display/index.html').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'display bytes'):
            self.prepare()
        self.assertFalse((self.root / 'display').exists())

    def test_traversal_and_links_are_rejected_before_extraction(self):
        for kind in ('traversal', 'symlink', 'hardlink'):
            def change(info, data):
                if info.name.endswith('index.html'):
                    if kind == 'traversal':
                        info.name = '../escape'
                    else:
                        info.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
                        info.linkname = '../escape'
                        info.size = 0
                return info, data
            self.write_archive(change)
            candidate.seal(self.assets, self.root)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse((self.root / 'display').exists())

    def test_member_limit_is_enforced_before_reading_the_payload(self):
        class Bundle:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def __iter__(self):
                info = tarfile.TarInfo('ha-echo-show-5/' + self.names[0])
                info.size = candidate.package_source.MAX_FILE + 1
                yield info
                raise AssertionError('Iterator advanced after invalid member')
            def extractfile(self, _):
                raise AssertionError('Oversize payload was read')
        bundle = Bundle()
        bundle.names = self.names
        with patch.object(candidate.tarfile, 'open', return_value=bundle), self.assertRaisesRegex(ValueError, 'size'):
            candidate.display_files(self.archive, self.root)

    def test_input_symlink_and_existing_output_are_rejected(self):
        target = self.assets / 'actual'
        self.archive.rename(target)
        self.archive.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'regular'):
            self.prepare()
        self.archive.unlink()
        target.rename(self.archive)
        (self.root / 'display').mkdir()
        with self.assertRaisesRegex(ValueError, 'must not exist'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
