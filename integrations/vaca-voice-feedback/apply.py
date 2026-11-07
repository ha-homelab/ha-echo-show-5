#!/usr/bin/env python3
"""Apply owned native voice feedback to the exact 7016 composition."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def apply(source: Path) -> None:
    source = source.resolve(strict=True)
    for name, digest in json.loads((HERE / 'source-preconditions.json').read_text()).items():
        path = source / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Source is not the verified 7016 feedback base: {name}')
    files = sorted((HERE / 'src').rglob('*.kt'))
    if not files:
        raise ValueError('Voice feedback sources are missing')
    for path in files:
        target = source / 'app' / path.relative_to(HERE)
        if path.is_symlink() or target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Voice feedback destination exists or is linked')
    subprocess.run(['git', '-C', str(source), 'apply', '--check', str(HERE / 'feedback.patch')], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', str(HERE / 'feedback.patch')], check=True)
    for path in files:
        target = source / 'app' / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
