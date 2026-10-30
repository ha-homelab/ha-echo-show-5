#!/usr/bin/env python3
"""Build the audio-only SIP pilot in private storage. Never contact a device."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PIN = json.loads((HERE / 'linphone-artifact.json').read_text())


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def verify_sdk(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size != PIN['bytes'] or digest(path) != PIN['sha256']:
        raise ValueError('SDK does not match the checked-in size and SHA-256')
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('SDK archive CRC failure')
        if not any(name.startswith('jni/armeabi-v7a/') and name.endswith('.so') for name in archive.namelist()):
            raise ValueError('SDK has no ARMv7 native libraries')


def obtain_sdk(work):
    path = work / ('linphone-' + PIN['version'] + '.aar')
    if path.exists():
        verify_sdk(path)
        return path
    with tempfile.NamedTemporaryFile(dir=work, suffix='.partial', delete=False) as out:
        temporary = Path(out.name)
        try:
            with urllib.request.urlopen(PIN['url'], timeout=60) as response:
                if not response.url.startswith('https://download.linphone.org/'):
                    raise ValueError('SDK download redirected outside the pinned origin')
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > PIN['bytes']:
                        raise ValueError('SDK exceeds pinned size')
                    out.write(block)
            out.flush()
            verify_sdk(temporary)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return path


def inventory(source):
    result = {}
    for path in sorted(source.rglob('*')):
        if any(part in {'build', '.gradle', '.kotlin'} for part in path.relative_to(source).parts):
            continue
        if path.is_symlink():
            raise ValueError('Application source contains a symlink')
        if path.is_file() and path.name != 'local.properties':
            result[path.relative_to(source).as_posix()] = digest(path)
    return result


def unit_results(source):
    totals = dict(tests=0, failures=0, errors=0, skipped=0)
    files = list((source / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
    for path in files:
        suite = ET.parse(path).getroot()
        for key in totals:
            totals[key] += int(suite.get(key, '0'))
    if totals['tests'] < 1 or any(totals[key] for key in ('failures', 'errors', 'skipped')):
        raise ValueError('SIP unit tests must run without failures, errors or skips')
    return totals


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--signing-dir', type=Path, required=True)
    parser.add_argument('--expected-signer-sha256', required=True)
    parser.add_argument('--gradle', type=Path, required=True,
                        help='Gradle 9.4.1 executable or pinned Gradle 9.4.1 wrapper')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('vaca_builder', ROOT / 'integrations/vaca-dual-wake/build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    work = builder.require_private_destination(args.work_dir)
    signing = builder.require_private_destination(args.signing_dir)
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    java, sdk = os.environ.get('JAVA_HOME'), os.environ.get('ANDROID_HOME')
    if not java or not sdk:
        parser.error('Set JAVA_HOME (JDK 21) and ANDROID_HOME first')
    key, password, signer = builder.ensure_signer(signing, java, expected=args.expected_signer_sha256)
    aar = obtain_sdk(work)
    original = HERE / 'android'
    expected = inventory(original)
    if not expected:
        raise ValueError('No application source')
    source = work / 'source'
    if source.exists():
        if inventory(source) != expected:
            raise ValueError('Existing private build source differs; select a new work directory')
    else:
        shutil.copytree(original, source, ignore=shutil.ignore_patterns('build', '.gradle', '.kotlin', 'local.properties'))
    env = dict(os.environ, KEYSTORE_FILE=str(key), KEYSTORE_PASSWORD=password.read_text().strip(),
               KEY_ALIAS='vaca', KEY_PASSWORD=password.read_text().strip())
    version = subprocess.run([str(args.gradle), '--version'], env=env, text=True, capture_output=True, check=True)
    if not re.search(r'^Gradle 9\.4\.1\s*$', version.stdout, re.M):
        raise ValueError('Expected Gradle 9.4.1')
    with (work / 'gradle.private.log').open('w') as log:
        result = subprocess.run([str(args.gradle), '-p', str(source), '--no-daemon', '--max-workers=4',
                                 '-PlinphoneAar=' + str(aar), ':app:testDebugUnitTest', ':app:assembleRelease'],
                                env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError('Gradle failed; inspect the private build log')
    totals = unit_results(source)
    if inventory(source) != expected or inventory(original) != expected:
        raise ValueError('Application source changed during the build')
    apks = list((source / 'app/build/outputs/apk/release').glob('*.apk'))
    if len(apks) != 1:
        raise ValueError('Expected exactly one release APK')
    apk = apks[0]
    result = subprocess.run([str(builder.sdk_tool(Path(sdk), 'apksigner')), 'verify', '--verbose', '--print-certs', str(apk)],
                            check=True, capture_output=True, text=True)
    fingerprints = re.findall(r'certificate SHA-256 digest: ([0-9a-f]{64})', result.stdout)
    if fingerprints != [signer]:
        raise ValueError('SIP APK signer differs from VACA')
    manifest = subprocess.run([str(builder.sdk_tool(Path(sdk), 'aapt')), 'dump', 'badging', str(apk)],
                              check=True, capture_output=True, text=True).stdout
    if "name='org.hahomelab.show5sip'" not in manifest or "'armeabi-v7a'" not in manifest:
        raise ValueError('Wrong application or missing ARMv7 APK support')
    if 'application-debuggable' in manifest:
        raise ValueError('Deploy only a non-debuggable release')
    # Liblinphone's call foreground service uses ApplicationInfo.icon.
    # A missing icon compiles successfully but kills the process at first call.
    icon = re.search(r"^application:.* icon='([^']+)'", manifest, re.M)
    with zipfile.ZipFile(apk) as archive:
        if icon is None or icon.group(1) not in archive.namelist():
            raise ValueError('SIP call foreground service requires a packaged application icon')
    permissions = subprocess.run([str(builder.sdk_tool(Path(sdk), 'aapt')), 'dump', 'permissions', str(apk)],
                                 check=True, capture_output=True, text=True).stdout
    if any("name='" + name + "'" in permissions for name in
           ('android.permission.CAMERA', 'android.permission.FOREGROUND_SERVICE_CAMERA')):
        raise ValueError('Audio-only SIP release must not request camera access')
    target = work / 'show5-sip-0.1.1.apk'
    shutil.copy2(apk, target)
    receipt = {'schema': 1, 'package': 'org.hahomelab.show5sip', 'version': '0.1.1',
               'apk_sha256': digest(target), 'apk_bytes': target.stat().st_size,
               'signer_sha256': signer, 'sdk_sha256': PIN['sha256'], 'source_files': expected,
               'unit_tests': totals, 'deployed': False}
    target.with_suffix('.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Verified release APK:', target)
    print('Unit tests:', totals['tests'], 'Signer:', signer)


if __name__ == '__main__':
    main()
