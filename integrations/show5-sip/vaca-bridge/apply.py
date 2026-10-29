#!/usr/bin/env python3
"""Apply the additive SIP lease bridge to an already reconstructed, exact VACA .9 tree."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def apply(source: Path) -> None:
    source = source.resolve(strict=True)
    expected = json.loads((HERE / "source-preconditions.json").read_text())
    for relative, digest in expected.items():
        path = source / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Source is not the verified .9 base: {relative}")
    files = list((HERE / "src").rglob("*.kt"))
    for path in files:
        target = source / "app" / path.relative_to(HERE)
        if target.exists() or target.is_symlink():
            raise ValueError(f"Overlay destination already exists: {target.relative_to(source)}")
        if any(parent.is_symlink() for parent in target.parents if parent != source):
            raise ValueError("Overlay destination contains a symbolic link")
    patch = HERE / "vaca-audio-lease.patch"
    subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)], check=True)
    subprocess.run(["git", "-C", str(source), "apply", str(patch)], check=True)
    for path in files:
        target = source / "app" / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    apply(parser.parse_args().source)
