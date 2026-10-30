#!/usr/bin/env python3
"""Build pinned VACA with SIP, nearest-device and guarded announcement overlays; never access devices."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSION = '0.13.4+myshka.14-announce.3'
CODE = 7014


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--signing-dir', type=Path, required=True)
    parser.add_argument('--expected-signer-sha256', required=True)
    parser.add_argument('--source-cache', type=Path, help='Optional local Git object source; pinned commit still required')
    args = parser.parse_args()
    b = load('vaca_build', ROOT / 'integrations/vaca-dual-wake/build.py')
    sip_dir = ROOT / 'integrations/show5-sip/vaca-bridge'
    overlay = load('vaca_sip_overlay', sip_dir / 'apply.py')
    nearest_dir = ROOT / 'integrations/vaca-nearest'
    nearest = load('vaca_nearest_overlay', nearest_dir / 'apply.py')
    announce = load('vaca_announce_overlay', HERE / 'apply.py')
    work = b.require_private_destination(args.work_dir)
    signing = b.require_private_destination(args.signing_dir)
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    java, sdk = os.environ.get('JAVA_HOME'), os.environ.get('ANDROID_HOME')
    if not java or not sdk:
        parser.error('Set JAVA_HOME and ANDROID_HOME')
    source = work / 'source'
    if not source.exists():
        b.run('git', 'clone', '--no-checkout', str(args.source_cache or b.UPSTREAM), source,
              stdout=subprocess.DEVNULL)
        b.git(source, 'checkout', '--detach', b.COMMIT)
        b.prepare_source(source)
        overlay.apply(source)
        nearest.apply(source)
        announce.apply(source)
    if b.git(source, 'rev-parse', 'HEAD').stdout.decode().strip() != b.COMMIT:
        raise ValueError('Unexpected base commit')
    if b.git(source, 'diff', '--cached', '--quiet', 'HEAD', check=False).returncode:
        raise ValueError('Build source has staged changes')
    bridge = sip_dir
    overlay_files = sorted((bridge / 'src').rglob('*.kt'))
    nearest_files = sorted((nearest_dir / 'src').rglob('*.kt'))
    announce_files = sorted((HERE / 'src').rglob('*.kt'))
    inputs = [Path(__file__), Path(b.__file__), b.PATCH, bridge / 'vaca-audio-lease.patch', bridge / 'apply.py',
              bridge / 'source-preconditions.json', nearest_dir / 'nearest.patch', nearest_dir / 'apply.py',
              nearest_dir / 'source-preconditions.json', HERE / 'announcement.patch', HERE / 'apply.py', HERE / 'source-preconditions.json', nearest_dir / 'src/test/golden-vectors.txt',
              nearest_dir / 'src/test/golden_vectors.go', *overlay_files, *nearest_files, *announce_files]
    if any(path.is_symlink() for path in inputs):
        raise ValueError('Build inputs must be ordinary files')
    frozen_inputs = {path: b.sha256(path) for path in inputs}
    with tempfile.TemporaryDirectory(prefix='sip-vaca-index-') as temporary:
        index_env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
        b.git(source, 'read-tree', b.COMMIT, env=index_env)
        b.git(source, 'apply', '--cached', b.PATCH, env=index_env)
        b.git(source, 'apply', '--cached', bridge / 'vaca-audio-lease.patch', env=index_env)
        for path in overlay_files:
            blob = b.git(source, 'hash-object', '-w', path).stdout.decode().strip()
            relative = 'app/' + path.relative_to(bridge).as_posix()
            b.git(source, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + relative, env=index_env)
        b.git(source, 'apply', '--cached', nearest_dir / 'nearest.patch', env=index_env)
        for path in nearest_files:
            blob = b.git(source, 'hash-object', '-w', path).stdout.decode().strip()
            relative = 'app/' + path.relative_to(nearest_dir).as_posix()
            b.git(source, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + relative, env=index_env)
        b.git(source, 'apply', '--cached', HERE / 'announcement.patch', env=index_env)
        for path in announce_files:
            blob = b.git(source, 'hash-object', '-w', path).stdout.decode().strip()
            relative = 'app/' + path.relative_to(HERE).as_posix()
            b.git(source, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + relative, env=index_env)
        fixture_blob = b.git(source, 'hash-object', '-w', nearest_dir / 'src/test/golden-vectors.txt').stdout.decode().strip()
        b.git(source, 'update-index', '--add', '--cacheinfo',
              '100644,' + fixture_blob + ',app/src/test/resources/nearest/golden-vectors.txt', env=index_env)
        b.validate_ignored_files(source)
        if not b.source_matches(source, index_env):
            raise ValueError('Source does not match the pinned base, .9, SIP and nearest overlays')
        tree = b.git(source, 'write-tree', env=index_env).stdout.decode().strip()
        (source / 'local.properties').write_text('sdk.dir=' + b.java_property_value(str(Path(sdk).resolve())) + '\n', encoding='ascii')
        key, password, signer = b.ensure_signer(signing, java, expected=args.expected_signer_sha256)
        secret = password.read_text().strip()
        env = dict(os.environ, KEYSTORE_FILE=str(key), KEYSTORE_PASSWORD=secret, KEY_ALIAS='vaca', KEY_PASSWORD=secret)
        with (work / 'gradle.private.log').open('w') as log:
            result = subprocess.run([str(source / 'gradlew'), '-p', str(source), '--no-daemon', '--max-workers=4',
                                     ':app:testDebugUnitTest', ':app:assembleDebug'], env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError('VACA build failed; inspect private build log')
        totals = b.test_totals(source)
        cases = set()
        for path in (source / 'app/build/test-results/testDebugUnitTest').glob('TEST-*AudioLeaseCoordinatorTest.xml'):
            cases.update(node.get('name') for node in ET.parse(path).getroot().iter('testcase'))
        if len(cases) < 12:
            raise ValueError('Audio lease coordinator tests did not run')
        nearest_suites = {}
        for path in (source / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
            suite = ET.parse(path).getroot()
            if '.nearest.' in suite.get('name', ''):
                if any(int(suite.get(key, '0')) for key in ('failures', 'errors', 'skipped')):
                    raise ValueError('Nearest-device tests failed or skipped')
                nearest_suites[suite.get('name')] = int(suite.get('tests', '0'))
        if nearest_suites.get('com.msp1974.vacompanion.nearest.NearestCoreJUnitTest', 0) < 36:
            raise ValueError('Nearest protocol, DSP and four-device tests did not run')
        if nearest_suites.get('com.msp1974.vacompanion.nearest.NearestAdapterTest', 0) < 26:
            raise ValueError('Nearest adapter regression tests did not run')
        announce_suite = source / 'app/build/test-results/testDebugUnitTest/TEST-com.msp1974.vacompanion.announce.AnnouncementCoreTest.xml'
        if not announce_suite.exists() or int(ET.parse(announce_suite).getroot().get('tests', '0')) < 46:
            raise ValueError('Guarded announcement core tests did not run')
        admission_suite = source / 'app/build/test-results/testDebugUnitTest/TEST-com.msp1974.vacompanion.announce.AnnouncementAdmissionTest.xml'
        if not admission_suite.exists() or int(ET.parse(admission_suite).getroot().get('tests', '0')) < 18:
            raise ValueError('Announcement preemption and foreground tests did not run')
        duck_suite = source / 'app/build/test-results/testDebugUnitTest/TEST-com.msp1974.vacompanion.announce.AnnouncementDuckingTest.xml'
        if not duck_suite.exists() or int(ET.parse(duck_suite).getroot().get('tests', '0')) < 37:
            raise ValueError('Owned music ducking tests did not run')
        if not b.source_matches(source, index_env):
            raise ValueError('Source changed during VACA build')
        if any(b.sha256(path) != checksum for path, checksum in frozen_inputs.items()):
            raise ValueError('Published bridge inputs changed during the build; use a fresh snapshot')
        if (overlay_files != sorted((bridge / 'src').rglob('*.kt')) or
                nearest_files != sorted((nearest_dir / 'src').rglob('*.kt')) or
                announce_files != sorted((HERE / 'src').rglob('*.kt'))):
            raise ValueError('Overlay source list changed during the build')
    apks = list((source / 'app/build/outputs/apk/debug').glob('*.apk'))
    if len(apks) != 1:
        raise ValueError('Expected one VACA APK')
    b.VERSION_NAME, b.VERSION_CODE = VERSION, CODE
    b.validate_apk(apks[0], sdk, signer)
    target = work / ('vaca-' + VERSION.replace('+', '-') + '.apk')
    shutil.copy2(apks[0], target)
    receipt = {'schema': 1, 'application_id': 'com.msp1974.vacompanion', 'version_name': VERSION,
               'version_code': CODE, 'base_commit': b.COMMIT, 'source_tree': tree,
               'base_patch_sha256': b.sha256(b.PATCH),
               'bridge_patch_sha256': b.sha256(bridge / 'vaca-audio-lease.patch'),
               'inputs': {p.relative_to(ROOT).as_posix(): h for p, h in frozen_inputs.items()},
               'nearest_tests': nearest_suites,
               'apk_sha256': b.sha256(target), 'apk_bytes': target.stat().st_size,
               'signing_certificate_sha256': signer, 'unit_tests': totals, 'deployed': False}
    target.with_suffix('.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('VACA guarded announcement build:', target)
    print('Tests:', totals['tests'], 'source:', tree)


if __name__ == '__main__':
    main()
