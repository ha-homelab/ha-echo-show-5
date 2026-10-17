#!/usr/bin/env python3
"""Build the pinned dual-wake VACA fork; never access a device or Home Assistant."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

COMMIT = '65906aebffd2f39772773b44729b22fd022a1f3c'
UPSTREAM = 'https://github.com/msp1974/ViewAssistCompanionApp.git'
VERSION_NAME = '0.13.4+myshka.4'
VERSION_CODE = 7004
ROOT = Path(__file__).resolve().parents[2]
PATCH = Path(__file__).with_name('vaca-dual-wake.patch')


class BuildError(RuntimeError):
    """A precondition or validation failed without changing device state."""


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def git(src, *args, env=None, check=True):
    return subprocess.run(['git', '-C', str(src), *map(str, args)], env=env,
                          check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_fingerprint(value):
    result = value.replace(':', '').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', result):
        raise BuildError('Expected a 64-character SHA-256 signing fingerprint')
    return result


def require_private_destination(path):
    """Protect checkout/archive source while permitting explicit external storage."""
    # Check lexical in-tree components before resolving: private/ must not become
    # an external destination merely because an existing component is a symlink.
    lexical = Path(os.path.abspath(path))
    try:
        lexical_relative = lexical.relative_to(ROOT)
    except ValueError:
        lexical_relative = None
    if lexical_relative is not None:
        component = ROOT
        for part in lexical_relative.parts:
            component = component / part
            if component.is_symlink():
                raise BuildError('Build and signing destinations inside the source must not use symlinks')
    resolved = lexical.resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    if not relative.parts:
        raise BuildError('Build and signing destinations must not replace the source root')
    checkout = git(ROOT, 'rev-parse', '--show-toplevel', check=False)
    is_checkout = (checkout.returncode == 0 and
                   Path(os.fsdecode(checkout.stdout).strip()).resolve() == ROOT)
    if is_checkout:
        if git(ROOT, 'check-ignore', '--quiet', relative, check=False).returncode:
            raise BuildError('Build and signing directories inside the repository must be gitignored')
    elif (ROOT / '.git').exists() or (ROOT / '.git').is_symlink():
        raise BuildError('Cannot validate the source checkout; repair Git metadata first')
    elif relative.parts[0] != 'private':
        # Source releases intentionally omit .git and .gitignore. Accept only
        # their dedicated private subtree, not arbitrary archive source paths.
        raise BuildError('Inside a source archive, use private/ for build and signing data')
    return resolved


def validate_ignored_files(src):
    ignored = git(src, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').stdout
    for raw in ignored.split(b'\0'):
        if not raw:
            continue
        path = Path(os.fsdecode(raw))
        absolute = src / path
        if absolute.is_symlink() or any((src / parent).is_symlink() for parent in path.parents):
            raise BuildError('Ignored build paths must not be symbolic links')
        if path.as_posix() == 'local.properties':
            continue  # Replaced with the explicitly selected SDK below.
        output_roots = {('build',), ('.gradle',), ('.kotlin',),
                        ('app', 'build'), ('app', '.cxx'),
                        ('microfeatures', 'build'), ('microfeatures', '.cxx')}
        if any(path.parts[:len(root)] == root and len(path.parts) > len(root)
               for root in output_roots):
            continue
        raise BuildError('Unexpected ignored source file; use a separate clean work directory')


def source_matches(src, env):
    changed = git(src, 'diff', '--no-ext-diff', '--quiet', env=env, check=False)
    if changed.returncode not in (0, 1):
        raise BuildError('Unable to compare the source checkout')
    extras = git(src, 'ls-files', '--others', '--exclude-standard', '-z', env=env).stdout
    return changed.returncode == 0 and not extras


def prepare_source(src, commit=COMMIT, patch=PATCH):
    """Accept only a pristine pinned tree or exactly that tree plus this patch."""
    if git(src, 'rev-parse', 'HEAD').stdout.decode().strip() != commit:
        raise BuildError('Source commit differs from the pinned version')
    if git(src, 'diff', '--cached', '--quiet', 'HEAD', check=False).returncode:
        raise BuildError('Source checkout has staged edits; use a separate clean work directory')
    validate_ignored_files(src)
    with tempfile.TemporaryDirectory(prefix='vaca-source-index-') as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
        git(src, 'read-tree', commit, env=env)
        pristine = source_matches(src, env)
        git(src, 'apply', '--cached', patch, env=env)
        if not source_matches(src, env):
            if not pristine:
                raise BuildError('Source differs from the pinned tree and patch; no files were reset. '
                                 'Choose a new --work-dir for a new patch version')
            git(src, 'apply', '--check', patch)
            git(src, 'apply', patch)
        if not source_matches(src, env):
            raise BuildError('Patched source verification failed')
        return git(src, 'write-tree', env=env).stdout.decode().strip()


def signer_fingerprint(java, key, password):
    result = run(Path(java) / 'bin/keytool', '-exportcert', '-alias', 'vaca',
                 '-keystore', key, '-storepass:file', password,
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return hashlib.sha256(result.stdout).hexdigest()


def ensure_signer(signing, java, create=False, expected=None):
    """A missing key is never silently replaced on an update build."""
    signing.mkdir(parents=True, exist_ok=True, mode=0o700)
    key, password, record = signing / 'vaca.jks', signing / 'password', signing / 'signer.sha256'
    if key.exists() != password.exists():
        raise BuildError('Incomplete signing directory; restore the original key/password pair')
    if not key.exists():
        if record.exists() or expected:
            raise BuildError('Pinned signing identity is missing; restore its original key')
        if not create:
            raise BuildError('No signing key. Only for a first installation, use --create-signing-key')
        password.write_text(secrets.token_urlsafe(40), encoding='utf-8')
        password.chmod(0o600)
        run(Path(java) / 'bin/keytool', '-genkeypair', '-keystore', key,
            '-storepass:file', password, '-keypass:file', password,
            '-alias', 'vaca', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '3650',
            '-dname', 'CN=VACA Local Build', '-storetype', 'JKS')
        key.chmod(0o600)
    elif create:
        raise BuildError('Signing key already exists; omit --create-signing-key for updates')
    actual = signer_fingerprint(java, key, password)
    pinned = normalize_fingerprint(record.read_text()) if record.exists() else None
    requested = normalize_fingerprint(expected) if expected else None
    if (pinned and actual != pinned) or (requested and actual != requested):
        raise BuildError('Signing certificate does not match the expected update identity')
    if not pinned and not requested and not create:
        raise BuildError('Existing key has no fingerprint record; supply --expected-signer-sha256 '
                         'from the previously installed APK before first use of this builder')
    if not record.exists():
        record.write_text(actual + '\n', encoding='ascii')
        record.chmod(0o600)
    return key, password, actual


def sdk_tool(sdk, name):
    choices = [path for path in (Path(sdk) / 'build-tools').glob('*/' + name)
               if re.fullmatch(r'\d+(\.\d+)*', path.parent.name)]
    if not choices:
        raise BuildError(f'Android SDK build-tools with {name} are required')
    return max(choices, key=lambda path: tuple(map(int, path.parent.name.split('.'))))


def validate_apk(apk, sdk, signer):
    signature = run(sdk_tool(sdk, 'apksigner'), 'verify', '--verbose', '--print-certs', apk,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    fingerprints = re.findall(r'^Signer #\d+ certificate SHA-256 digest: (\w+)$', signature, re.M)
    if fingerprints != [signer]:
        raise BuildError('Built APK signature differs from the expected update identity')
    manifest = run(sdk_tool(sdk, 'aapt'), 'dump', 'badging', apk,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", manifest, re.M)
    if not package or package.groups() != ('com.msp1974.vacompanion', str(VERSION_CODE), VERSION_NAME):
        raise BuildError('Built APK package/version differs from the pinned build')
    abi = re.search(r'^native-code: (.+)$', manifest, re.M)
    if not abi or re.findall(r"'([^']+)'", abi[1]) != ['armeabi-v7a']:
        raise BuildError('Built APK is not the expected ARMv7-only artifact')


def test_totals(src):
    """Return JUnit totals after requiring the minimum suite with no failures or skips."""
    totals = dict(tests=0, failures=0, errors=0, skipped=0)
    for report in (src / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
        suite = ET.parse(report).getroot()
        for key in totals:
            totals[key] += int(suite.get(key, '0'))
    if totals['tests'] < 18 or totals['failures'] or totals['errors'] or totals['skipped']:
        raise BuildError('Expected at least eighteen passing JVM tests and no failed/skipped tests')
    return totals


def java_property_value(value):
    # Properties.load(InputStream) reads Latin-1; use UTF-16 escapes for all Unicode.
    escaped = []
    for character in value:
        if character == "\\":
            escaped.append("\\\\")
        elif character == ":":
            escaped.append("\\:")
        elif 32 <= ord(character) < 127:
            escaped.append(character)
        else:
            data = character.encode('utf-16-be')
            escaped.extend('\\u' + data[index:index + 2].hex() for index in range(0, len(data), 2))
    return ''.join(escaped)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'private/vaca-dual-wake-build')
    parser.add_argument('--signing-dir', type=Path, default=ROOT / 'private/vaca-dual-wake-signing')
    parser.add_argument('--create-signing-key', action='store_true',
                        help='Explicitly initialize a NEW installation identity; never for updates')
    parser.add_argument('--expected-signer-sha256', help='Pin the certificate used by the installed APK')
    args = parser.parse_args()
    sdk, java = os.environ.get('ANDROID_HOME'), os.environ.get('JAVA_HOME')
    if not sdk or not java:
        parser.error('Set ANDROID_HOME and JAVA_HOME (JDK 21) first')
    if not (Path(java) / 'bin/keytool').is_file() or not Path(sdk).is_dir():
        parser.error('JAVA_HOME or ANDROID_HOME does not point to the required toolchain')
    work = require_private_destination(args.work_dir)
    signing = require_private_destination(args.signing_dir)
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    src = work / 'source'
    if not src.exists():
        run('git', 'clone', '--filter=blob:none', '--no-checkout', UPSTREAM, src)
        git(src, 'checkout', '--detach', COMMIT)
    source_tree = prepare_source(src)
    # Java properties files need escaped backslashes, colons and non-ASCII characters.
    sdk_path = java_property_value(str(Path(sdk).resolve()))
    sdk_file = src / 'local.properties'
    if sdk_file.is_symlink() or (sdk_file.exists() and not sdk_file.is_file()):
        raise BuildError('local.properties must be a regular file or absent')
    sdk_file.write_text('sdk.dir=' + sdk_path + '\n', encoding='ascii')
    key, password, signer = ensure_signer(signing, java, args.create_signing_key,
                                          args.expected_signer_sha256)
    secret = password.read_text(encoding='utf-8').strip()
    env = dict(os.environ, KEYSTORE_FILE=str(key), KEYSTORE_PASSWORD=secret,
               KEY_ALIAS='vaca', KEY_PASSWORD=secret)
    run(src / 'gradlew', '-p', src, '--no-daemon', '--max-workers=4',
        ':app:testDebugUnitTest', ':app:assembleDebug', env=env)
    totals = test_totals(src)
    if prepare_source(src) != source_tree:
        raise BuildError('Source changed during build')
    apks = list((src / 'app/build/outputs/apk/debug').glob('*.apk'))
    if len(apks) != 1:
        raise BuildError('Expected one debug APK; use a separate clean work directory')
    validate_apk(apks[0], sdk, signer)
    target = work / ('vaca-' + VERSION_NAME.replace('+', '-') + '.apk')
    shutil.copy2(apks[0], target)
    metadata = {
        'schema_version': 1, 'upstream_repository': UPSTREAM[:-4],
        'upstream_commit': COMMIT, 'patched_source_tree': source_tree,
        'patch_sha256': sha256(PATCH), 'application_id': 'com.msp1974.vacompanion',
        'version_name': VERSION_NAME, 'version_code': VERSION_CODE, 'abi': ['armeabi-v7a'],
        'apk_sha256': sha256(target), 'apk_bytes': target.stat().st_size,
        'signing_certificate_sha256': signer, 'unit_tests': totals,
        'deployment_status': 'not_deployed_by_build_tool',
        'note': 'Build evidence only; device installation and acoustic acceptance require separate validation.',
    }
    target.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print('Built and verified:', target)
    print('Build evidence:', target.with_suffix('.json'))


if __name__ == '__main__':
    try:
        main()
    except (BuildError, subprocess.CalledProcessError) as error:
        # Do not dump subprocess environments, which contain signing passwords.
        raise SystemExit(str(error)) from None
