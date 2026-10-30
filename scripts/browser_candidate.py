"""Bind the display files to an exact source-release artifact; never deploy."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

import package_source

ROOT = Path(__file__).resolve().parents[1]
FILES = ('index.html', 'display.css', 'i18n.js', 'stream.js', 'auth.js', 'display.js', 'room.js', 'offline-worker.js', 'blank-video.svg')
PREFIX = 'ha-echo-show-5/integrations/show5-display/'
MAX_RECEIPT = 1024 * 1024


def regular(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Candidate input is not a bounded regular file')
    return path


def identity(root=ROOT):
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or sha != os.environ.get('GITHUB_SHA'):
        raise ValueError('Candidate checkout does not match the workflow source SHA')
    result = dict(sourceSha=sha, runId=os.environ.get('GITHUB_RUN_ID', ''), runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', ''))
    if any(not re.fullmatch(r'[1-9][0-9]*', result[key]) for key in ('runId', 'runAttempt')):
        raise ValueError('Candidate requires the current workflow run and attempt')
    return result


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inputs(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Candidate must be a regular directory')
    archives = list(directory.glob('ha-echo-show-5-*.tar.gz'))
    if len(archives) != 1:
        raise ValueError('Expected exactly one source archive')
    archive = regular(archives[0], package_source.MAX_TOTAL)
    receipt = regular(directory / 'release-inputs-package.json', MAX_RECEIPT)
    return archive, receipt, json.loads(receipt.read_text())


def seal(directory, root=ROOT):
    archive, receipt, data = inputs(directory)
    bound = identity(root)
    if data.get('source_sha') != bound['sourceSha']:
        raise ValueError('Release receipt belongs to another source revision')
    data['browser_candidate'] = {**bound, 'archive': archive.name, 'archiveSha256': digest(archive)}
    receipt.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def display_files(archive, root=ROOT):
    """Stream the existing explicit inventory with limits before any member read."""
    expected = ['ha-echo-show-5/' + name for name in package_source.inventory(root)]
    found, total = {}, 0
    with tarfile.open(archive, mode='r|gz') as bundle:
        count = 0
        for count, member in enumerate(bundle, 1):
            if count > len(expected) or member.name != expected[count - 1]:
                raise ValueError('Candidate membership differs from the source inventory')
            if not member.isfile() or member.size < 0 or member.size > package_source.MAX_FILE:
                raise ValueError('Candidate member type or size is invalid')
            total += member.size
            if total > package_source.MAX_TOTAL:
                raise ValueError('Candidate expanded size exceeds the limit')
            if member.name.startswith(PREFIX) and member.name[len(PREFIX):] in FILES:
                name = member.name[len(PREFIX):]
                stream = bundle.extractfile(member)
                if stream is None:
                    raise ValueError('Candidate display member is unreadable')
                content = stream.read(package_source.MAX_FILE + 1)
                source = regular(root / 'integrations/show5-display' / name, package_source.MAX_FILE)
                if content != source.read_bytes():
                    raise ValueError('Candidate display bytes differ from the exact source revision')
                found[name] = content
        if count != len(expected) or set(found) != set(FILES):
            raise ValueError('Candidate is missing reviewed display files')
    return found


def prepare(directory, output, root=ROOT):
    archive, _, data = inputs(directory)
    bound = identity(root)
    candidate = data.get('browser_candidate', {})
    if any(candidate.get(key) != value for key, value in bound.items()) or data.get('source_sha') != bound['sourceSha']:
        raise ValueError('Candidate identity differs from the current source/run/attempt')
    artifact = os.environ.get('CI_BROWSER_CANDIDATE_ARTIFACT_ID', '')
    if not re.fullmatch(r'[1-9][0-9]*', artifact):
        raise ValueError('Candidate requires the exact downloaded artifact ID')
    if candidate.get('archive') != archive.name or candidate.get('archiveSha256') != digest(archive):
        raise ValueError('Candidate archive digest differs from the sealed receipt')
    files = display_files(archive, root)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Display candidate destination must not exist')
    output.mkdir(parents=False)
    for name, content in files.items():
        (output / name).write_bytes(content)
    (output / 'candidate.json').write_text(json.dumps({**candidate, 'candidateArtifactId': artifact}) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['seal', 'prepare'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    if args.command == 'seal':
        seal(args.directory)
    else:
        prepare(args.directory, ROOT / '.browser-display')


if __name__ == '__main__':
    main()
