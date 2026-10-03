#!/usr/bin/env python3
"""Download/verify pinned artifacts. Does not open USB or run downloaded code."""
import argparse
import hashlib
import json
import os
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
    name = data['name']
    if Path(name).name != name or len(data['sha256']) != 64:
        raise ValueError('Invalid artifact metadata')
    return data


def verify_file(kind, item, p):
    """Check content at p using the validated artifact's final filename."""
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


def fetch(kind):
    item = metadata(kind)
    p = ROOT / 'downloads' / item['name']
    if p.exists():
        return verify(kind)
    if not item['url'].startswith('https://'):
        raise ValueError('HTTPS artifact URL required')
    p.parent.mkdir(parents=True, exist_ok=True)
    partial = p.with_name(p.name + '.partial')
    try:
        req = urllib.request.Request(item['url'], headers={'User-Agent': 'ha-echo-show-5-preparation'})
        with urllib.request.urlopen(req, timeout=60) as src, partial.open('wb') as dst:
            for block in iter(lambda: src.read(4 * 1024 * 1024), b''):
                dst.write(block)
        verify_file(kind, item, partial)
        os.replace(partial, p)
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
