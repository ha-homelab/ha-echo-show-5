"""Regenerate the pinned Riva bindings offline; --check never modifies files."""

import argparse
import ast
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
NAMES = ("riva_asr", "riva_tts", "riva_audio", "riva_common")
MODULES = tuple(name + "_pb2.py" for name in NAMES) + (
    "riva_asr_pb2_grpc.py", "riva_tts_pb2_grpc.py",
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def generate(check):
    package = ROOT / "riva_proto"
    manifest = json.loads((package / "UPSTREAM.json").read_text())
    for dependency, expected in manifest["generator"].items():
        if version(dependency) != expected:
            raise ValueError(f"Install proto-requirements.txt: {dependency} must be {expected}")
    if sha256((package / "LICENSE").read_bytes()) != manifest["license_sha256"]:
        raise ValueError("Upstream license differs from the pinned manifest")
    sources = []
    for name in NAMES:
        path = ROOT / "proto/riva/proto" / (name + ".proto")
        if sha256(path.read_bytes()) != manifest["sources"][path.name]["source_sha256"]:
            raise ValueError(f"Upstream source changed: {path.name}")
        sources.append(str(path))
    with tempfile.TemporaryDirectory(prefix="riva-proto-") as temporary:
        subprocess.run(
            [sys.executable, "-m", "grpc_tools.protoc", "-I" + str(ROOT / "proto"),
             "--python_out=" + temporary, "--grpc_python_out=" + temporary, *sources],
            check=True, timeout=30,
        )
        outputs = {}
        for module in MODULES:
            text = (Path(temporary) / "riva/proto" / module).read_text()
            # Relocate only Python imports and class metadata, never wire descriptors.
            text = text.replace("from riva.proto import ", "from . import ")
            if module.endswith("_pb2.py"):
                old = "'riva.proto." + module[:-3] + "'"
                if text.count(old) != 1:
                    raise ValueError(f"Unexpected generated module metadata: {module}")
                text = text.replace(old, "'riva_proto." + module[:-3] + "'")
                descriptors = [ast.literal_eval(node.args[0]) for node in ast.walk(ast.parse(text))
                               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                               and node.func.attr == "AddSerializedFile"]
                expected = manifest["sources"][module.replace("_pb2.py", ".proto")]["descriptor_sha256"]
                if len(descriptors) != 1 or sha256(descriptors[0]) != expected:
                    raise ValueError(f"Wire descriptor changed: {module}")
            outputs[module] = text.encode()
        for module, data in outputs.items():
            target = package / module
            if check:
                if not target.is_file() or target.read_bytes() != data:
                    raise ValueError(f"Generated binding is stale: {module}")
            else:
                target.write_bytes(data)
    print(f"{'Verified' if check else 'Generated'} {len(MODULES)} pinned Riva binding modules")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)
