#!/usr/bin/env python3
"""Recreate the pinned release tree as data; never execute it or open USB."""
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from artifacts import ROOT, digest, verify


def reviewed_archive():
    archive = verify('amonet')
    review = json.loads((ROOT / 'amonet-review.json').read_text())
    if (review.get('product') != 'cronos' or review.get('release') != '2.0.1'
            or review.get('archive_sha256') != digest(archive) or not review.get('files')):
        raise RuntimeError('Pinned archive does not match the static cronos review.')
    for name, checksum in review['files'].items():
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name
                or str(path) != name or len(checksum) != 64):
            raise RuntimeError('Invalid reviewed file path/hash.')
    return archive, review


def verify_tree(target, review):
    if target.is_symlink() or not target.is_dir():
        raise RuntimeError('Missing/unsafe extracted release directory.')
    paths = list(target.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise RuntimeError('Symlink in extracted release.')
    actual = {p.relative_to(target).as_posix() for p in paths if p.is_file()}
    if actual != set(review['files']):
        raise RuntimeError('Extracted release contains missing or unreviewed files.')
    for name, checksum in review['files'].items():
        if digest(target / name) != checksum:
            raise RuntimeError('Extracted file hash mismatch: ' + name)
    props = dict(line.split('=', 1) for line in (target / 'device.prop').read_text().splitlines()
                 if '=' in line)
    if props.get('DEVICE') != 'cronos' or props.get('DEVICE_TYPE_ID') != 'A1XWJRHALS1REP':
        raise RuntimeError('Extracted release is not cronos.')
    return target


def verify_package():
    _, review = reviewed_archive()
    if (ROOT / 'vendor').is_symlink():
        raise RuntimeError('Unsafe vendor directory.')
    verify_tree(ROOT / 'vendor' / 'amonet', review)
    return review


def prepare():
    archive, review = reviewed_archive()
    vendor = ROOT / 'vendor'
    if vendor.is_symlink():
        raise RuntimeError('Unsafe vendor directory.')
    vendor.mkdir(mode=0o700, exist_ok=True)
    vendor.chmod(0o700)
    target = vendor / 'amonet'
    if target.exists() or target.is_symlink():
        return verify_tree(target, review)  # Never overwrite an existing release.
    staging = Path(tempfile.mkdtemp(prefix='.amonet-staging-', dir=str(vendor)))
    staging.chmod(0o700)
    try:
        with zipfile.ZipFile(archive) as package:
            selected = {}
            seen = set()
            for member in package.infolist():
                path = PurePosixPath(member.filename)
                kind = stat.S_IFMT(member.external_attr >> 16)
                if (path.is_absolute() or '..' in path.parts or '\\' in member.filename
                        or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or member.filename in seen):
                    raise RuntimeError('Unsafe or duplicate ZIP member.')
                seen.add(member.filename)
                if member.is_dir():
                    continue
                if path.parts[0] == 'amonet':
                    name = PurePosixPath(*path.parts[1:]).as_posix()
                    if name not in review['files'] or name in selected:
                        raise RuntimeError('Unreviewed/duplicate release file.')
                    selected[name] = member
                elif path.parts[0] != 'META-INF':
                    raise RuntimeError('Unexpected release top-level directory.')
            if set(selected) != set(review['files']):
                raise RuntimeError('ZIP is missing reviewed files.')
            for name, member in selected.items():
                output = staging / name
                output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                parent = output.parent
                while parent != vendor:
                    parent.chmod(0o700)
                    parent = parent.parent
                with package.open(member) as src, output.open('xb') as dst:
                    output.chmod(0o700 if member.external_attr >> 16 & 0o111 else 0o600)
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                if digest(output) != review['files'][name]:
                    raise RuntimeError('Extracted file hash mismatch: ' + name)
        verify_tree(staging, review)
        staging.rename(target)
        return target
    finally:
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == '__main__':
    print('Verified release tree:', prepare())
    print('No downloaded code executed. Host runtime validation is a separate step.')
