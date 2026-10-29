#!/usr/bin/env python3
"""Apply guarded announcements and optional owned-player music ducking to the verified nearest base."""
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
            raise ValueError(f'Source is not the verified .11 nearest base: {relative}')
    files = sorted((HERE / 'src').rglob('*.kt'))
    if not files:
        raise ValueError('Announcement overlay is empty')
    for path in files:
        target = source / 'app' / path.relative_to(HERE)
        if target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Announcement overlay destination exists or is linked')
    subprocess.run(['git', '-C', str(source), 'apply', '--check', str(HERE / 'announcement.patch')], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', str(HERE / 'announcement.patch')], check=True)
    for path in files:
        target = source / 'app' / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    apply(parser.parse_args().source)
