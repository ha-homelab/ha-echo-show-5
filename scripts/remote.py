#!/usr/bin/env python3
"""Run one explicit project stage on Synology from the Mac; no shell interpolation."""
import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = os.environ.get('SHOW5_SSH_HOST', 'synology')
DEST = os.environ.get('SHOW5_REMOTE_ROOT', '/volume1/docker/ha-echo-show-5')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', help='sync, or an action accepted by scripts/nas.py')
    ap.add_argument('arguments', nargs=argparse.REMAINDER)
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@:-]*', HOST):
        ap.error('SHOW5_SSH_HOST must be an SSH alias or user@host, without shell syntax.')
    if (not re.fullmatch(r'/[A-Za-z0-9_./-]+', DEST)
            or DEST == '/' or any(p in ('.', '..') for p in DEST.split('/'))):
        ap.error('SHOW5_REMOTE_ROOT must be an absolute directory without spaces or parent traversal.')
    if args.action == 'sync':
        if args.arguments:
            ap.error('sync accepts no additional arguments')
        subprocess.run(['ssh', '-o', 'BatchMode=yes', HOST,
                        'mkdir -p ' + shlex.quote(DEST)], check=True)
        # No --delete: backups/keys/logs on the NAS survive repeated preparation.
        return subprocess.call(['rsync', '-rt', '--chmod=Du=rwx,Dgo=,Fu=rw,Fgo=',
            '--exclude', 'backups/', '--exclude', 'private/', '--exclude', 'logs/',
            '--exclude', '__pycache__/', '--exclude', '*.partial', '--exclude', '.git/',
            str(ROOT) + '/', HOST + ':' + DEST + '/'])
    command = ['python3', DEST + '/scripts/nas.py', args.action] + args.arguments
    tty = ['-t'] if sys.stdin.isatty() else []
    return subprocess.call(['ssh'] + tty + ['-o', 'BatchMode=yes', HOST,
                            'cd ' + shlex.quote(DEST) + ' && ' + ' '.join(shlex.quote(s) for s in command)])


if __name__ == '__main__':
    sys.exit(main())
