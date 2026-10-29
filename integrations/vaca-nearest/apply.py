#!/usr/bin/env python3
"""Apply the nearest-device adapter only to the verified composed VACA .10 source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def apply(source: Path) -> None:
    source = source.resolve(strict=True)
    expected = json.loads((HERE / 'source-preconditions.json').read_text())
    for relative, digest in expected.items():
        path = source / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Source is not the verified .10 SIP base: {relative}')
    files = sorted((HERE / 'src').rglob('*.kt'))
    fixture = HERE / 'src/test/golden-vectors.txt'
    fixture_target = source / 'app/src/test/resources/nearest/golden-vectors.txt'
    if not fixture.is_file() or fixture_target.exists() or any(p.is_symlink() for p in fixture_target.parents):
        raise ValueError('Missing fixture or occupied fixture destination')
    if not files:
        raise ValueError('Nearest overlay is empty')
    for path in files:
        target = source / 'app' / path.relative_to(HERE)
        if target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Nearest overlay destination already exists or is linked')
    subprocess.run(['git', '-C', str(source), 'apply', '--check', str(HERE / 'nearest.patch')], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', str(HERE / 'nearest.patch')], check=True)
    for path in files:
        target = source / 'app' / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    fixture_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture, fixture_target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    apply(parser.parse_args().source)
