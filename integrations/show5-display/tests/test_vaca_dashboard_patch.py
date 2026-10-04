"""Exercise the generated option flow and safe, reversible source deployment."""

import ast
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "vaca_dashboard_patch.py"
SPEC = importlib.util.spec_from_file_location("vaca_dashboard_patch", SCRIPT)
dashboard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dashboard)

CONFIG = '''import logging
from typing import Any


class VAOptionsFlowHandler(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
''' + dashboard.OLD_SAVE + '''
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HA_URL,
                    description={
                        "suggested_value": self.config_entry.options.get(CONF_HA_URL)
                    },
''' + dashboard.OLD_FIELD
ASSIST = '''def prepare(self):
    if True:
        if True:
            if True:
''' + dashboard.OLD_HOME + '''
                self.device.custom_settings["ha_dashboard"] = home.removeprefix("/")
'''
LABELS = {"options": {"step": {"init": {
    "data": {"ha_url": "Home Assistant URL"},
    "data_description": {"ha_url": "Original description"},
}}}, "unrelated": {"keep": True}}


class Invalid(ValueError):
    pass


class OptionsFlow:
    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}


def generated_namespace():
    # Execute the actual transformed functions, without importing/starting HA.
    code = dashboard.transform("config_flow.py", CONFIG.encode()).decode()
    module = ast.parse(code)
    nodes = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    namespace = {
        "Any": object,
        "OptionsFlow": OptionsFlow,
        "CONF_HA_URL": "ha_url",
        "re": re,
        "vol": SimpleNamespace(Invalid=Invalid, Optional=lambda name, **_: name, Schema=lambda fields: fields),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "generated_config_flow.py", "exec"), namespace)
    return namespace


class OptionFlowTests(unittest.TestCase):
    def setUp(self):
        self.namespace = generated_namespace()
        self.flow = self.namespace["VAOptionsFlowHandler"]()
        self.previous = {"ha_url": "https://ha.example.test", "future_option": {"keep": 1}}
        self.flow.config_entry = SimpleNamespace(options=self.previous)

    def run_flow(self, submitted=None):
        return asyncio.run(self.flow.async_step_init(submitted))

    def test_form_exposes_optional_dashboard_and_existing_url(self):
        result = self.run_flow()
        self.assertEqual(result["type"], "form")
        self.assertEqual(set(result["data_schema"]), {"ha_url", "ha_dashboard"})
        self.assertEqual(result["errors"], {})

    def test_dashboard_only_submission_preserves_url_and_unknown_options(self):
        result = self.run_flow({"ha_dashboard": "/local/show5-display/index.html"})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], {**self.previous, "ha_dashboard": "/local/show5-display/index.html"})
        self.assertNotIn("ha_dashboard", self.previous)

    def test_changing_url_preserves_previous_dashboard(self):
        self.previous["ha_dashboard"] = "/local/existing.html"
        result = self.run_flow({"ha_url": "https://new.example.test"})
        self.assertEqual(result["data"]["ha_dashboard"], "/local/existing.html")
        self.assertEqual(result["data"]["ha_url"], "https://new.example.test")

    def test_explicit_blank_restores_upstream_default_without_losing_options(self):
        self.previous["ha_dashboard"] = "/local/existing.html"
        result = self.run_flow({"ha_dashboard": "  "})
        self.assertEqual(result["data"]["ha_dashboard"], "")
        self.assertEqual(result["data"]["ha_url"], self.previous["ha_url"])

    def test_invalid_paths_return_form_error_and_do_not_save(self):
        for value in ["https://other.test/a", "//other.test/a", "local/a", "/a?token=x", "/a#x", "/../a", "/a/./b", "/a//b", "/%2e%2e/a", "/a\\b", "/a\n/b", "/" + "a" * 512, None, 1, [], {}]:
            with self.subTest(value=value):
                result = self.run_flow({"ha_dashboard": value})
                self.assertEqual(result["type"], "form")
                self.assertEqual(result["errors"], {"ha_dashboard": "invalid_dashboard_path"})
                self.assertNotIn("ha_dashboard", self.previous)

    def test_valid_paths_remain_paths_not_origins(self):
        for value in ["/", "/lovelace/default_view", "/local/show5-display/index.html", " /clock-1/a_b~c.html "]:
            with self.subTest(value=value):
                self.assertEqual(self.run_flow({"ha_dashboard": value})["data"]["ha_dashboard"], value.strip())

    def test_only_configured_entry_overrides_legacy_home(self):
        source = dashboard.transform("assist_satellite.py", ASSIST.encode())
        namespace = {"getVADashboardPath": lambda hass, satellite_id: "/original/" + satellite_id}
        exec(compile(source, "generated_assist.py", "exec"), namespace)
        for options, expected in [({}, "original/unchanged"), ({"ha_dashboard": ""}, "original/unchanged"), ({"ha_dashboard": "/local/show5-display/index.html"}, "local/show5-display/index.html")]:
            instance = SimpleNamespace(config_entry=SimpleNamespace(options=options), hass=object(), device=SimpleNamespace(satellite_id="unchanged", custom_settings={}))
            namespace["prepare"](instance)
            self.assertEqual(instance.device.custom_settings["ha_dashboard"], expected)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "vaca"
        self.root.mkdir()
        self.originals = {
            "config_flow.py": CONFIG.encode(),
            "assist_satellite.py": ASSIST.encode(),
            "strings.json": json.dumps(LABELS).encode(),
            "translations/en.json": json.dumps(LABELS).encode(),
        }
        for name, content in self.originals.items():
            target = self.root / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o640)
        expected = {name: dashboard.digest(content) for name, content in self.originals.items()}
        self.hash_patch = patch.object(dashboard, "EXPECTED", expected)
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)

    def assert_unchanged(self):
        for name, original in self.originals.items():
            self.assertEqual((self.root / name).read_bytes(), original)

    def test_check_is_read_only_and_parses_generated_python(self):
        plan = dashboard.plan_patch(self.root)
        self.assertEqual(set(plan), set(self.originals))
        self.assert_unchanged()
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["vaca"])

    def test_unknown_hash_refuses_entire_patch_before_creating_backup(self):
        (self.root / "assist_satellite.py").write_text("# unexpected update\n")
        with self.assertRaises(dashboard.PatchError):
            dashboard.apply_patch(self.root, self.base / "backup")
        self.assertFalse((self.base / "backup").exists())
        self.assertEqual((self.root / "config_flow.py").read_bytes(), self.originals["config_flow.py"])

    def test_apply_preserves_source_modes_and_saves_private_originals(self):
        backup = self.base / "backup"
        manifest = dashboard.apply_patch(self.root, backup)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o700)
        for name, original in self.originals.items():
            self.assertEqual((backup / name).read_bytes(), original)
            self.assertEqual(stat.S_IMODE((backup / name).stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((self.root / name).stat().st_mode), 0o640)
            self.assertEqual(dashboard.digest((self.root / name).read_bytes()), manifest[name]["after"])
        self.assertEqual(json.loads((backup / "manifest.json").read_text()), manifest)

    def test_backups_and_directory_entries_are_synced_before_source_mutation(self):
        backup = self.base / "backup"
        actual_fsync, actual_write = os.fsync, dashboard.atomic_write
        synced = set()

        def sync(fd):
            inode = os.fstat(fd).st_ino
            paths = [backup.parent, backup, backup / "translations", backup / "manifest.json"]
            paths.extend(backup / name for name in self.originals)
            synced.update(path for path in paths if path.exists() and path.stat().st_ino == inode)
            actual_fsync(fd)

        def write(path, data, mode):
            required = {backup.parent, backup, backup / "translations", backup / "manifest.json"}
            required.update(backup / name for name in self.originals)
            self.assertTrue(required <= synced)
            actual_write(path, data, mode)

        with patch.object(os, "fsync", side_effect=sync), patch.object(dashboard, "atomic_write", side_effect=write):
            dashboard.apply_patch(self.root, backup)

    def test_failed_backup_sync_never_mutates_sources(self):
        for kind in ("file", "directory"):
            with self.subTest(kind=kind):
                backup = self.base / ("backup-" + kind)
                actual_fsync = os.fsync

                def sync(fd):
                    is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                    if is_directory == (kind == "directory"):
                        raise OSError("synthetic backup sync failure")
                    actual_fsync(fd)

                with patch.object(os, "fsync", side_effect=sync), patch.object(dashboard, "atomic_write") as write:
                    with self.assertRaises(OSError):
                        dashboard.apply_patch(self.root, backup)
                    write.assert_not_called()
                self.assert_unchanged()

    def test_rename_sync_failure_rolls_back_the_current_source_on_apply_and_restore(self):
        backup = self.base / "backup"
        actual_sync = dashboard.fsync_directory
        fail = True

        def sync(path):
            nonlocal fail
            if path == self.root and fail:
                fail = False
                raise OSError("synthetic rename sync failure")
            actual_sync(path)

        with patch.object(dashboard, "fsync_directory", side_effect=sync):
            with self.assertRaises(OSError):
                dashboard.apply_patch(self.root, backup)
        self.assert_unchanged()
        backup = self.base / "second-backup"
        receipt = dashboard.apply_patch(self.root, backup)
        fail = True
        with patch.object(dashboard, "fsync_directory", side_effect=sync):
            with self.assertRaises(OSError):
                dashboard.restore_backup(self.root, backup)
        for name in self.originals:
            self.assertEqual(dashboard.digest((self.root / name).read_bytes()), receipt[name]["after"])

    def test_repeat_apply_refuses_without_touching_already_patched_sources(self):
        dashboard.apply_patch(self.root, self.base / "first")
        before = {name: (self.root / name).read_bytes() for name in self.originals}
        with self.assertRaises(dashboard.PatchError):
            dashboard.apply_patch(self.root, self.base / "second")
        self.assertFalse((self.base / "second").exists())
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in self.originals})

    def test_restore_returns_exact_originals_and_preserves_live_modes(self):
        backup = self.base / "backup"
        manifest = dashboard.apply_patch(self.root, backup)
        (self.root / "config_flow.py").chmod(0o600)
        result = dashboard.restore_backup(self.root, backup)
        self.assertEqual(result, manifest)
        self.assert_unchanged()
        self.assertEqual(stat.S_IMODE((self.root / "config_flow.py").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / "assist_satellite.py").stat().st_mode), 0o640)
        self.assertEqual(json.loads((backup / "manifest.json").read_text()), manifest)

    def test_restore_refuses_live_drift_without_changing_any_file(self):
        backup = self.base / "backup"
        dashboard.apply_patch(self.root, backup)
        changed = self.root / "assist_satellite.py"
        changed.write_bytes(changed.read_bytes() + b"\n# later update\n")
        before = {name: (self.root / name).read_bytes() for name in self.originals}
        with self.assertRaisesRegex(dashboard.PatchError, "Live patched hash mismatch"):
            dashboard.restore_backup(self.root, backup)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in self.originals})

    def test_restore_refuses_tampered_backup_original(self):
        backup = self.base / "backup"
        dashboard.apply_patch(self.root, backup)
        (backup / "config_flow.py").write_text("# corrupted backup\n")
        before = {name: (self.root / name).read_bytes() for name in self.originals}
        with self.assertRaisesRegex(dashboard.PatchError, "Original backup hash mismatch"):
            dashboard.restore_backup(self.root, backup)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in self.originals})

    def test_restore_refuses_receipt_rewrite_or_extra_paths(self):
        backup = self.base / "backup"
        receipt = dashboard.apply_patch(self.root, backup)
        target = backup / "manifest.json"
        for variant in [
            {**receipt, "../extra.py": {"before": "x", "after": "y"}},
            {**receipt, "config_flow.py": {**receipt["config_flow.py"], "after": "0" * 64}},
            {**receipt, "config_flow.py": {**receipt["config_flow.py"], "before": "0" * 64}},
            [],
        ]:
            with self.subTest(variant=type(variant).__name__):
                target.write_text(json.dumps(variant))
                with self.assertRaises(dashboard.PatchError):
                    dashboard.restore_backup(self.root, backup)
        for name in self.originals:
            self.assertEqual(dashboard.digest((self.root / name).read_bytes()), receipt[name]["after"])

    def test_restore_failure_rolls_back_to_patched_files(self):
        backup = self.base / "backup"
        receipt = dashboard.apply_patch(self.root, backup)
        original_write = dashboard.atomic_write
        calls = 0

        def fail_second(path, data, mode):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic restore failure")
            original_write(path, data, mode)

        with patch.object(dashboard, "atomic_write", side_effect=fail_second):
            with self.assertRaises(OSError):
                dashboard.restore_backup(self.root, backup)
        for name in self.originals:
            self.assertEqual(dashboard.digest((self.root / name).read_bytes()), receipt[name]["after"])

    def test_restore_refuses_symlinked_backup_file(self):
        backup = self.base / "backup"
        dashboard.apply_patch(self.root, backup)
        saved = backup / "config_flow.py"
        saved.rename(self.base / "moved-original.py")
        saved.symlink_to(self.base / "moved-original.py")
        with self.assertRaisesRegex(dashboard.PatchError, "Symlink"):
            dashboard.restore_backup(self.root, backup)

    def test_existing_or_internal_backup_is_rejected(self):
        existing = self.base / "existing"
        existing.mkdir()
        for backup in [existing, self.root / "backup"]:
            with self.subTest(path=backup):
                with self.assertRaises(dashboard.PatchError):
                    dashboard.apply_patch(self.root, backup)
                self.assert_unchanged()

    def test_symlinked_source_directory_is_rejected(self):
        translations = self.root / "translations"
        translations.rename(self.base / "outside")
        translations.symlink_to(self.base / "outside", target_is_directory=True)
        with self.assertRaises(dashboard.PatchError):
            dashboard.plan_patch(self.root)

    def test_mid_apply_failure_rolls_back_written_sources(self):
        original_write = dashboard.atomic_write
        calls = 0

        def fail_second(path, data, mode):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic write failure")
            original_write(path, data, mode)

        with patch.object(dashboard, "atomic_write", side_effect=fail_second):
            with self.assertRaises(OSError):
                dashboard.apply_patch(self.root, self.base / "backup")
        self.assert_unchanged()
        self.assertTrue((self.base / "backup/manifest.json").exists())

    def test_translations_preserve_unrelated_content(self):
        result = json.loads(dashboard.transform("strings.json", self.originals["strings.json"]))
        self.assertEqual(result["unrelated"], LABELS["unrelated"])
        self.assertEqual(result["options"]["step"]["init"]["data"]["ha_url"], "Home Assistant URL")
        self.assertIn("invalid_dashboard_path", result["options"]["error"])

    def test_missing_or_duplicate_transform_anchors_fail(self):
        for content in [CONFIG.replace("import logging\n", ""), CONFIG.replace("import logging\n", "import logging\nimport logging\n")]:
            with self.assertRaises(dashboard.PatchError):
                dashboard.transform("config_flow.py", content.encode())


if __name__ == "__main__":
    unittest.main()
