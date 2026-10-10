#!/usr/bin/env python3
"""Add the Android-safe maximum timeout to reviewed VACA 0.13.4.

Default: validate only. Before applying, stop HA and every integration/source
updater, and keep them stopped until the patch completes. --writers-stopped is
your declaration of that prerequisite, not a live-state check or a lock. Keep a
private backup, then restart HA and select 2147483 seconds on the intended
satellites. This prevents VACA from restoring a short Android timeout when its
settings reconnect. It is a bounded
24.8-day timeout, not an infinite wake lock. Ordinary VACA always-on behavior
and deliberate screen-off controls remain unchanged.
"""

import argparse
import ast
import hashlib
import os
from pathlib import Path


EXPECTED = "fa05133394828d16fa92cab8f5db4cb3b3b0218a06b364a75129d1058ac71517"
MAX_SECONDS = 2_147_483
OLD = '    _attr_options = ["15", "30", "60", "120", "300", "600", "1800"]'
NEW = OLD[:-1] + f', "{MAX_SECONDS}"]'


def patched(source: bytes) -> bytes:
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise ValueError("Unreviewed select.py; inspect the installed version first")
    text = source.decode()
    if text.count(OLD) != 1:
        raise ValueError("Expected exactly one screen-timeout option list")
    assert MAX_SECONDS * 1000 <= 2**31 - 1
    updated = text.replace(OLD, NEW, 1)
    ast.parse(updated)
    return updated.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("integration", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument(
        "--writers-stopped", action="store_true",
        help="declare HA and all source updaters stopped until completion; not a lock",
    )
    args = parser.parse_args()
    if args.apply:
        if not args.writers_stopped:
            parser.error("--apply requires --writers-stopped; stop HA and all source updaters first")
        if args.backup is None:
            parser.error("--apply requires a new private --backup path")
    target = args.integration / "select.py"
    if target.is_symlink() or not target.is_file():
        raise ValueError("Expected a regular select.py")
    original = target.read_bytes()
    updated = patched(original)
    if args.apply:
        # Existing backups must never be overwritten.
        with args.backup.open("xb") as handle:
            os.chmod(args.backup, 0o600)
            handle.write(original)
        temporary = target.with_name("select.py.timeout-patch.tmp")
        created = False
        try:
            with temporary.open("xb") as handle:
                created = True
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, target.stat().st_mode & 0o777)
            os.chown(temporary, target.stat().st_uid, target.stat().st_gid)
            # This detects some prior changes, not writes after the comparison.
            # All source writers must remain stopped through the replacement.
            if target.read_bytes() != original:
                raise ValueError("select.py changed during deployment")
            os.replace(temporary, target)
        finally:
            if created:
                temporary.unlink(missing_ok=True)
    print("Applied" if args.apply else "Validated", "maximum timeout:", MAX_SECONDS)


if __name__ == "__main__":
    main()
