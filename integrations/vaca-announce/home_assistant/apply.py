#!/usr/bin/env python3
"""Apply a checked additive overlay to a staging copy of the VACA integration."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def apply(source, *, check=False):
    source = source.resolve(strict=True)
    manifest = json.loads((HERE / 'overlay.json').read_text())
    dependencies = json.loads((HERE / 'source-dependencies.json').read_text())
    for name, digest in dependencies.items():
        path = source / name
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError('Unexpected integration dependency: ' + name)
    changes, states = {}, set()
    for name, specification in manifest.items():
        path = source / name
        if path.is_symlink() or (path.exists() and not path.is_file()) or (not path.exists() and specification['before_sha256'] is not None):
            raise ValueError('Missing or linked integration source: ' + name)
        content = path.read_bytes() if path.exists() else b''
        digest = sha(content) if path.exists() else None
        if digest == specification['after_sha256']:
            states.add('after')
            continue
        if digest != specification['before_sha256']:
            raise ValueError('Unexpected integration source: ' + name)
        states.add('before')
        value = content.decode()
        for old, new in specification.get('replacements', []):
            if value.count(old) != 1:
                raise ValueError('Ambiguous source patch: ' + name)
            value = value.replace(old, new, 1)
        value += specification.get('append', '')
        if sha(value.encode()) != specification['after_sha256']:
            raise ValueError('Overlay output mismatch: ' + name)
        if name.endswith('.py'):
            ast.parse(value)
        changes[path] = value.encode()
    if len(states) != 1:
        raise ValueError('Partially applied integration overlay')
    already = states == {'after'}
    for path in sorted((HERE / 'src').glob('*.py')):
        target = source / path.name
        if target.is_symlink():
            raise ValueError('Linked overlay destination')
        if target.exists():
            if not already or target.read_bytes() != path.read_bytes():
                raise ValueError('Occupied or modified overlay destination')
        elif already:
            raise ValueError('Incomplete overlay installation')
        ast.parse(path.read_text())
        changes[target] = path.read_bytes()
    if not check and not already:
        for path, content in changes.items():
            path.write_bytes(content)
    return not already

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    changed = apply(args.source, check=args.check)
    print('Overlay validated' if args.check else ('Overlay applied' if changed else 'Overlay already applied'))
