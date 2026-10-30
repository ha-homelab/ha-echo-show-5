#!/usr/bin/env python3
"""Run offline Go/Kotlin compatibility tests without Gradle, Android, or network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    test_dir = Path(__file__).resolve().parent
    module = test_dir.parent.parent
    package = Path("com/msp1974/vacompanion/nearest")
    sources = [module / "src/main/java" / package / name for name in (
        "NearestProtocol.kt", "NearestElection.kt", "StandoutScore.kt"
    )] + [test_dir / "java" / package / "NearestCoreTests.kt"]
    fixture = test_dir / "golden-vectors.txt"
    oracle = subprocess.run(["go", "run", str(test_dir / "golden_vectors.go")],
                            capture_output=True, check=True, timeout=60).stdout
    if oracle != fixture.read_bytes():
        raise RuntimeError("Checked-in golden vectors differ from the independent Go oracle")
    with tempfile.TemporaryDirectory(prefix="nearest-core-tests-") as temp:
        jar = str(Path(temp) / "tests.jar")
        subprocess.run(["kotlinc", *map(str, sources), "-include-runtime", "-d", jar],
                       check=True, timeout=90)
        result = subprocess.run(["java", "-jar", jar, str(fixture)],
                                check=True, capture_output=True, text=True, timeout=60)
    print(result.stdout, end="")
    print("Independent Go protocol, DSP, and four-peer election vectors match.")
    if args.receipt:
        receipt = {"result": result.stdout.strip(), "go_vectors_match": True,
                   "network_access": False, "real_device_election_test": False,
                   "source_sha256": {str(path.relative_to(module)): hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in sources + [fixture, test_dir / "golden_vectors.go"]}}
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
