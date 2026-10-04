#!/usr/bin/env python3
"""Guarded, opt-in VACA 0.13.4 per-entry dashboard patch.

Run against a copied integration first. Without --apply this only validates and
reports hashes. --apply requires a new backup directory outside the integration.
It changes source files, never HA options, services, or running Python modules.
After deployment, restart HA Core normally once, then use the selected VACA
entry's Configure form. Keep ha_url origin-only; ha_dashboard is a URL path.
Blank dashboard retains upstream View Assist/default-home behavior. Later option
changes reload only that config entry through upstream's existing listener.
--restore-backup restores only the four known originals after checking both the
backup and currently installed patched hashes. Restart Core afterward to load
restored Python. It does not remove an already saved config-entry option.

Supported source: ViewAssist_Companion_App 0.13.4, reviewed installed snapshot.
An upstream/HACS update requires another review; unknown files fail closed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile


EXPECTED = {
    "config_flow.py": "ff87ab95ac22017fbf572cf37f3e96470b10574290e9c2f2dfbe03b27829e11a",
    "assist_satellite.py": "34cee0120b9c9d44371ac270c6f53f189a1d459ad41577900308f936c499285e",
    "strings.json": "5bb7fc29ce1b5d7a60e67050fab6b1b8b0291bd1ec044cd03acafa51f6759574",
    "translations/en.json": "7fcc769fbc33ec034187fdeb7c8a221bb535913ec10cdbeaee296bf76b981cd6",
}

VALIDATOR = '''

def _dashboard_path(value: Any) -> str:
    """Allow only an origin-relative path; blank selects upstream default."""
    if not isinstance(value, str):
        raise vol.Invalid("invalid_dashboard_path")
    value = value.strip()
    if not value:
        return ""
    if (
        len(value) > 512
        or not re.fullmatch(r"/[A-Za-z0-9._~/-]*", value)
        or "//" in value
        or any(part in (".", "..") for part in value.split("/"))
    ):
        raise vol.Invalid("invalid_dashboard_path")
    return value
'''

OLD_SAVE = '''        if user_input is not None:
            return self.async_create_entry(data=user_input)
'''
NEW_SAVE = '''        errors = {}
        values = {**self.config_entry.options, **(user_input or {})}
        if user_input is not None:
            try:
                values["ha_dashboard"] = _dashboard_path(values.get("ha_dashboard", ""))
            except vol.Invalid:
                errors["ha_dashboard"] = "invalid_dashboard_path"
            else:
                return self.async_create_entry(data=values)
'''
OLD_FIELD = '''                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
'''
NEW_FIELD = '''                ): str,
                vol.Optional(
                    "ha_dashboard",
                    description={"suggested_value": values.get("ha_dashboard", "")},
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
'''
OLD_HOME = '                home = getVADashboardPath(self.hass, self.device.satellite_id)'
NEW_HOME = '''                home = self.config_entry.options.get("ha_dashboard") or getVADashboardPath(
                    self.hass, self.device.satellite_id
                )'''


class PatchError(ValueError):
    """Source or filesystem differs from the reviewed deployment."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise PatchError("Expected source anchor is not unique")
    return text.replace(old, new, 1)


def transform(name: str, data: bytes) -> bytes:
    text = data.decode("utf-8")
    if name == "config_flow.py":
        text = replace_once(text, "import logging\n", "import logging\nimport re\n")
        text = replace_once(text, "\n\nclass VAOptionsFlowHandler(OptionsFlow):", VALIDATOR + "\n\nclass VAOptionsFlowHandler(OptionsFlow):")
        text = replace_once(text, OLD_SAVE, NEW_SAVE)
        text = replace_once(text, "self.config_entry.options.get(CONF_HA_URL)", "values.get(CONF_HA_URL)")
        text = replace_once(text, OLD_FIELD, NEW_FIELD)
    elif name == "assist_satellite.py":
        text = replace_once(text, OLD_HOME, NEW_HOME)
    elif name in ("strings.json", "translations/en.json"):
        content = json.loads(text)
        options = content["options"]
        form = options["step"]["init"]
        if "ha_dashboard" in form["data"]:
            raise PatchError("Dashboard translation already exists")
        form["data"]["ha_dashboard"] = "Home dashboard path"
        form["data_description"]["ha_dashboard"] = (
            "Optional path on this Home Assistant, for example /local/show5-display/index.html. "
            "Leave blank to keep View Assist or the default dashboard. Keep Home Assistant URL unchanged."
        )
        options.setdefault("error", {})["invalid_dashboard_path"] = (
            "Use a path starting with one slash, without a host, query, fragment, or dot segments; "
            "leave blank for the default dashboard."
        )
        text = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
    else:
        raise PatchError("Unsupported file")
    if name.endswith(".py"):
        ast.parse(text, filename=name)
    return text.encode("utf-8")


def safe_file(root: Path, name: str) -> Path:
    path = root / name
    current = path
    while current != root:
        if current.is_symlink():
            raise PatchError("Symlink in target path")
        current = current.parent
    if root.is_symlink() or not path.is_file():
        raise PatchError("Expected a regular source file")
    return path


def plan_patch(root: Path) -> dict[str, tuple[bytes, bytes]]:
    """Read-only full preflight: no partial patch or unknown revision allowed."""
    result = {}
    for name, expected in EXPECTED.items():
        data = safe_file(root, name).read_bytes()
        if digest(data) != expected:
            raise PatchError(f"Source hash mismatch: {name}; restore/review before applying")
        result[name] = (data, transform(name, data))
    return result


def fsync_directory(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".show5-dashboard-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fchmod(output.fileno(), mode)
            os.fsync(output.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_patch(root: Path, backup: Path) -> dict[str, dict[str, str]]:
    """Back up all four originals, recheck, then replace with rollback on error."""
    changes = plan_patch(root)
    root_real, backup_real = root.resolve(), backup.resolve()
    if backup_real == root_real or root_real in backup_real.parents:
        raise PatchError("Backup must be outside the integration directory")
    if backup.exists() or backup.is_symlink():
        raise PatchError("Backup directory must be new")
    backup.mkdir(mode=0o700, parents=False)
    manifest = {name: {"before": digest(old), "after": digest(new)} for name, (old, new) in changes.items()}
    modes = {}
    for name, (old, _) in changes.items():
        source = safe_file(root, name)
        modes[name] = stat.S_IMODE(source.stat().st_mode)
        target = backup / name
        target.parent.mkdir(mode=0o700, exist_ok=True)
        with target.open("xb") as output:
            os.chmod(target, 0o600)
            output.write(old)
            output.flush()
            os.fsync(output.fileno())
    manifest_path = backup / "manifest.json"
    with manifest_path.open("x") as output:
        os.chmod(manifest_path, 0o600)
        json.dump(manifest, output, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    directories = {backup.parent, backup, *((backup / name).parent for name in changes)}
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        fsync_directory(directory)
    # Detect edits between initial read and the first write.
    for name, (old, _) in changes.items():
        if safe_file(root, name).read_bytes() != old:
            raise PatchError("Source changed during backup; nothing applied")
    written = []
    try:
        for name, (_, new) in changes.items():
            written.append(name)
            atomic_write(root / name, new, modes[name])
        for name, (_, new) in changes.items():
            if safe_file(root, name).read_bytes() != new:
                raise PatchError("Post-write verification failed")
    except BaseException:
        for name in reversed(written):
            atomic_write(root / name, changes[name][0], modes[name])
        raise
    return manifest


def restore_backup(root: Path, backup: Path) -> dict[str, dict[str, str]]:
    """Restore reviewed originals only when all live patched hashes still match."""
    root_real, backup_real = root.resolve(), backup.resolve()
    if backup_real == root_real or root_real in backup_real.parents:
        raise PatchError("Backup must be outside the integration directory")
    manifest = json.loads(safe_file(backup, "manifest.json").read_text())
    if not isinstance(manifest, dict) or set(manifest) != set(EXPECTED):
        raise PatchError("Backup manifest must name exactly the four known files")
    changes = {}
    modes = {}
    for name, expected in EXPECTED.items():
        receipt = manifest[name]
        if not isinstance(receipt, dict) or set(receipt) != {"before", "after"}:
            raise PatchError("Invalid backup receipt")
        original = safe_file(backup, name).read_bytes()
        before = digest(original)
        if before != expected or receipt["before"] != before:
            raise PatchError(f"Original backup hash mismatch: {name}")
        # Recompute the reviewed result; a rewritten receipt cannot authorize
        # replacing arbitrary current source, even with a self-consistent hash.
        patched = transform(name, original)
        after = digest(patched)
        if receipt["after"] != after:
            raise PatchError(f"Patched receipt hash mismatch: {name}")
        target = safe_file(root, name)
        current = target.read_bytes()
        if digest(current) != after:
            raise PatchError(f"Live patched hash mismatch: {name}; nothing restored")
        changes[name] = (current, original)
        modes[name] = stat.S_IMODE(target.stat().st_mode)
    # All four files are verified before any write; repeat the live-byte guard
    # immediately before starting to catch an update during preflight.
    for name, (current, _) in changes.items():
        if safe_file(root, name).read_bytes() != current:
            raise PatchError("Live source changed during restore preflight")
    written = []
    try:
        for name, (_, original) in changes.items():
            written.append(name)
            atomic_write(root / name, original, modes[name])
        for name, (_, original) in changes.items():
            if safe_file(root, name).read_bytes() != original:
                raise PatchError("Restored source verification failed")
    except BaseException:
        for name in reversed(written):
            atomic_write(root / name, changes[name][0], modes[name])
        raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("integration", type=Path, help="Path to custom_components/vaca")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write after complete preflight")
    mode.add_argument("--restore-backup", type=Path, help="Restore the exact saved originals after hash checks")
    parser.add_argument("--backup-dir", type=Path, help="New private directory outside the integration")
    args = parser.parse_args()
    if args.apply and args.backup_dir is None:
        parser.error("--apply requires --backup-dir")
    if args.backup_dir is not None and not args.apply:
        parser.error("--backup-dir is only valid with --apply")
    try:
        if args.restore_backup is not None:
            result = restore_backup(args.integration, args.restore_backup)
        elif args.apply:
            result = apply_patch(args.integration, args.backup_dir)
        else:
            result = {name: {"before": digest(old), "after": digest(new)} for name, (old, new) in plan_patch(args.integration).items()}
    except (PatchError, OSError, UnicodeError, KeyError, SyntaxError, json.JSONDecodeError) as error:
        parser.exit(1, f"Patch refused: {error}\n")
    print(json.dumps({"applied": args.apply, "restored": args.restore_backup is not None, "files": result}, indent=2))


if __name__ == "__main__":
    main()
