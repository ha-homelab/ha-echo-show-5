#!/usr/bin/env python3
"""NAS-only runtime check with no USB mapping; records private host evidence."""
import datetime
import json
import os
import re
import subprocess

from artifacts import ROOT
from prepare_amonet import verify_package


def validate_host_release(image):
    review = verify_package()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise RuntimeError('An immutable recorded Docker image ID is required.')
    package = ROOT / 'vendor' / 'amonet'
    # This check runs only fixed, hash-reviewed files. No USB device is mapped;
    # networking and privileges are removed and the package mount is read-only.
    script = '''set -euo pipefail
test "$(uname -m)" = x86_64
# rsync deliberately strips host execute bits. Run a private RAM copy, keeping
# the hash-reviewed source mount read-only and unchanged.
cp ./bin/fastboot /tmp/fastboot
chmod 700 /tmp/fastboot
deps="$(ldd /tmp/fastboot)"
printf '%s\\n' "$deps"
if printf '%s\\n' "$deps" | grep -q 'not found'; then exit 1; fi
/tmp/fastboot --version
bash -n ./fastbrick.sh ./profile.sh
timeout --version
command -v clear
'''
    command = ['sudo', '-n', '/usr/local/bin/docker', 'run', '--rm',
               '--network', 'none', '--cap-drop', 'ALL', '--read-only',
               '--security-opt', 'no-new-privileges', '--user', '%d:%d' % (os.getuid(), os.getgid()),
               '--mount', 'type=bind,src=%s,dst=/package,readonly' % package,
               '--tmpfs', '/tmp:rw,nosuid,nodev,exec,size=16m,mode=1777',
               '--workdir', '/package', '--entrypoint', '/bin/bash', image, '-c', script]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=120)
    if (result.returncode or 'fastboot version 28.0.0' not in result.stdout
            or 'timeout (GNU coreutils)' not in result.stdout):
        raise RuntimeError('No-USB host runtime check failed; no validation record written.\n'
                           + result.stdout + result.stderr)
    record = {'schema_version': 1, 'product': 'cronos', 'passed_without_usb': True,
              'archive_sha256': review['archive_sha256'], 'image_id': image,
              'validated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'checks': ['x86_64 host', 'bundled fastboot shared libraries resolved',
                         'bundled fastboot version', 'bash syntax', 'GNU timeout', 'clear'],
              'stdout': result.stdout, 'stderr': result.stderr,
              'isolation': 'No USB mapping; no network; nonroot; no capabilities; read-only rootfs/package; fastboot runs from a private copy in executable RAM tmpfs.'}
    private = ROOT / 'private'
    if private.is_symlink():
        raise RuntimeError('Unsafe private evidence directory.')
    private.mkdir(mode=0o700, exist_ok=True)
    private.chmod(0o700)
    output = private / 'host-release-validation.json'
    partial = private / 'host-release-validation.json.partial'
    if partial.exists() or partial.is_symlink() or output.is_symlink():
        raise RuntimeError('Unsafe or unfinished private validation output.')
    with partial.open('x') as stream:
        partial.chmod(0o600)
        json.dump(record, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    partial.replace(output)
    return output


if __name__ == '__main__':
    from nas import image_id
    print('Validated pinned release for this host:', validate_host_release(image_id()))
