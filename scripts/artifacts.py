#!/usr/bin/env python3
"""Download/verify pinned artifacts. Does not open USB or run downloaded code."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from urllib.parse import urlsplit
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def metadata(kind):
    data = json.loads((ROOT / (kind + '-artifact.json')).read_text())
    if not isinstance(data, dict):
        raise ValueError('Invalid artifact metadata')
    name, size, checksum = (data.get(key) for key in ('name', 'size', 'sha256'))
    if (not isinstance(name, str) or not name or name in ('.', '..')
            or Path(name).name != name or '\\' in name
            or type(size) is not int or size <= 0
            or not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum)):
        raise ValueError('Invalid artifact metadata')
    return data


def verify_file(kind, item, p):
    """Check content at p using the validated artifact's final filename."""
    if p.is_symlink() or not p.is_file():
        raise ValueError('Artifact must be a regular file')
    if p.stat().st_size != item['size'] or digest(p) != item['sha256']:
        raise ValueError('Artifact size/SHA256 mismatch: ' + str(p))
    expected_suffix = '.apk' if kind in ('companion', 'vaca', 'androidipcamera', 'jitsi') else '.zip'
    if Path(item['name']).suffix != expected_suffix:
        raise ValueError('Unexpected file type for ' + kind)
    if kind in ('lineage', 'companion', 'amonet', 'vaca', 'androidipcamera', 'jitsi'):
        with zipfile.ZipFile(p) as z:
            if z.testzip():
                raise ValueError('Archive CRC failed: ' + str(p))
            if kind == 'lineage':
                text = z.read('META-INF/com/android/metadata').decode()
                fields = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
                if fields.get('pre-device') != 'cronos':
                    raise ValueError('ROM is not for cronos')
    return p


def verify(kind):
    item = metadata(kind)
    return verify_file(kind, item, ROOT / 'downloads' / item['name'])


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('Artifact redirect must remain HTTPS')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def open_source(request):
    return urllib.request.build_opener(HTTPSRedirect()).open(request, timeout=60)


def fetch(kind):
    item = metadata(kind)
    p = ROOT / 'downloads' / item['name']
    if p.exists():
        return verify(kind)
    url = item.get('url')
    if not isinstance(url, str):
        raise ValueError('HTTPS artifact URL without credentials required')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('HTTPS artifact URL without credentials required')
    p.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=p.name + '.', suffix='.partial', dir=p.parent)
    partial = Path(temporary)
    try:
        req = urllib.request.Request(item['url'], headers={'User-Agent': 'ha-echo-show-5-preparation'})
        # Own the descriptor before opening the network stream, including on failure.
        with os.fdopen(descriptor, 'wb') as dst, open_source(req) as src:
            received = 0
            while True:
                block = src.read(min(4 * 1024 * 1024, item['size'] - received + 1))
                if not block:
                    break
                received += len(block)
                if received > item['size']:
                    raise ValueError('Artifact size/SHA256 mismatch: response exceeds pinned size')
                dst.write(block)
        verify_file(kind, item, partial)
        try:
            os.link(partial, p)
        except FileExistsError:
            # Another completed download may win; never overwrite its bytes.
            verify_file(kind, item, p)
        return p
    finally:
        partial.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['fetch', 'verify'])
    ap.add_argument('kinds', nargs='+', choices=['lineage', 'companion', 'amonet', 'vaca', 'androidipcamera', 'jitsi'])
    args = ap.parse_args()
    for kind in args.kinds:
        p = fetch(kind) if args.action == 'fetch' else verify(kind)
        print('Verified ' + str(p))


if __name__ == '__main__':
    main()
