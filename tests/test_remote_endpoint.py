"""Offline identity-guard, target isolation and session-lifecycle checks."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_remote_endpoint as endpoint


def fixture():
    return {
        "prefix": "show5_fixture", "serial": "G1234567890ABCDE",
        "adb_entity": "media_player.fixture_android",
        "vaca_mute_entity": "switch.fixture_mute",
        "vaca_media_entity": "media_player.fixture_vaca",
        "vaca_refresh_entity": "button.fixture_refresh",
        "jitsi_room_url": "https://meet.example.invalid/fixture",
        "ottplay_url": "https://tv.example.invalid/player",
        "app_ids": {"vlc": "org.videolan.vlc", "jitsi": "org.jitsi.meet",
                    "browser": "org.example.browser", "ottplayer": "org.example.ottplayer",
                    "ottplay_native": "org.example.ottplay"},
        "tv_presets": {"news": {"label": "News", "url": "https://tv.example.invalid/news.m3u8"}},
        "clock_path": "/local/show5-display/index.html",
    }


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def actions(value, service):
    return [row for row in walk(value) if isinstance(row, dict) and row.get("service") == service]


class RemoteEndpointTests(unittest.TestCase):
    def setUp(self):
        self.config = fixture()
        self.package = endpoint.render_package(self.config)
        self.scripts = self.package["script"]
        self.main = self.scripts["show5_fixture_command"]

    def test_json_roundtrip_and_input_not_mutated(self):
        original = copy.deepcopy(self.config)
        self.assertEqual(json.loads(json.dumps(self.package)), self.package)
        self.assertEqual(self.config, original)

    def test_ha_package_and_sandbox_compatibility(self):
        # Package merging drops empty selector mappings; HA's Jinja sandbox
        # rejects ranges containing more than 100000 items.
        text_selector = self.main['fields']['audio_media_id']['selector']['text']
        self.assertEqual(text_selector, {'multiline': False})
        for low, high in re.findall(r'range\((\d+), (\d+)\)', endpoint.MARKER):
            self.assertLessEqual(int(high) - int(low), 100000)

    def test_rejects_unrecognized_or_missing_bindings(self):
        for change in ({"navigation": {}}, {"adb_command": "arbitrary"}):
            bad = dict(self.config, **change)
            with self.assertRaises(ValueError):
                endpoint.render_package(bad)
        for key in self.config:
            if key == "clock_path":
                continue
            bad = dict(self.config)
            del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                endpoint.render_package(bad)

    def test_rejects_identity_and_entity_injection(self):
        for key, value in (("prefix", "a;reboot"), ("serial", "G123; echo unsafe"),
                           ("adb_entity", "remote.wrong_domain"),
                           ("vaca_mute_entity", "switch.x {{ states }}"),
                           ("vaca_refresh_entity", "script.other_device")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                endpoint.render_package(dict(self.config, **{key: value}))
        with self.assertRaises(ValueError):
            endpoint.render_package(dict(self.config, adb_entity=self.config["vaca_media_entity"]))

    def test_rejects_owned_vaca_duplicate_or_invalid_package(self):
        for package in (endpoint.VACA_PACKAGE, "x; reboot", "notapackage", "org.jitsi.meet"):
            bad = copy.deepcopy(self.config)
            bad["app_ids"]["vlc"] = package
            with self.subTest(package=package), self.assertRaises(ValueError):
                endpoint.render_package(bad)

    def test_rejects_unsafe_url_and_jitsi_configuration_overrides(self):
        for url in ("https://user:secret@example.invalid/r", "https://example.invalid/r#config.prejoinConfig.enabled=false",
                    "https://example.invalid/r?jwt=secret", "http://example.invalid/r", "https://example.invalid/a/b"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                endpoint.render_package(dict(self.config, jitsi_room_url=url))
        for url in ("file:///sdcard/movie", "javascript:alert(1)", "https://example.invalid/{{ token }}", "https://example.invalid/\nreboot"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                endpoint.render_package(dict(self.config, ottplay_url=url))

    def test_tv_presets_are_named_fixed_urls_only(self):
        for presets in ({"bad key": {"label": "X", "url": "https://example.invalid/v"}},
                        {"x": {"label": "X", "url": "file:///video"}},
                        {"x": {"label": "X", "url": "https://example.invalid/v", "command": "reboot"}}):
            with self.assertRaises(ValueError):
                endpoint.render_package(dict(self.config, tv_presets=presets))
        commands = endpoint.fixed_operations(self.config)
        self.assertIn("tv_news", commands)
        self.assertIn("https://tv.example.invalid/news.m3u8", commands["tv_news"])
        self.assertNotIn("url", self.main["fields"])
        self.assertNotIn("command", self.main["fields"])

    def test_every_adb_operation_has_all_identity_guards(self):
        commands = endpoint.fixed_operations(self.config)
        for name, command in commands.items():
            with self.subTest(operation=name):
                self.assertIn('"$(getprop ro.serialno)" = G1234567890ABCDE', command)
                self.assertIn('"$(getprop ro.product.device)" = cronos', command)
                self.assertIn('"$(id -u)" = 2000', command)
                self.assertNotIn("{{", command)
        direct_adb = actions(self.package, "androidtv.adb_command")
        self.assertEqual(len(direct_adb), 1)
        self.assertEqual(direct_adb[0]["target"]["entity_id"], self.config["adb_entity"])

    def run_guard(self, serial, product, uid):
        # Execute only a synthetic operation with shell builtins, never ADB.
        stubs = ('getprop() { case "$1" in ro.serialno) echo ' + serial +
                 ';; ro.product.device) echo ' + product + ';; esac; }; '
                 'id() { echo ' + str(uid) + '; }; ')
        result = subprocess.run(["/bin/sh", "-c", stubs + endpoint.guarded_command(self.config["serial"], "echo EXECUTED")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        return result

    def test_wrong_serial_product_or_root_cannot_execute_operation(self):
        good = self.run_guard(self.config["serial"], "cronos", 2000)
        self.assertEqual((good.returncode, good.stdout.strip()), (0, "EXECUTED"))
        for serial, product, uid in (("GOTHER1234567890", "cronos", 2000),
                                     (self.config["serial"], "thebes", 2000),
                                     (self.config["serial"], "cronos", 0)):
            bad = self.run_guard(serial, product, uid)
            self.assertNotEqual(bad.returncode, 0)
            self.assertNotIn("EXECUTED", bad.stdout)

    def test_fixed_url_shell_metacharacters_cannot_escape_argument(self):
        bad = copy.deepcopy(self.config)
        bad["tv_presets"]["news"]["url"] = "https://example.invalid/v?x=';echo_PWNED;$(touch_x)&y=1"
        command = endpoint.fixed_operations(endpoint.validate_config(bad))["tv_news"]
        self.assertIn("'\"'\"'", command)
        # The shell parser accepts the generated quoting. Nothing is executed.
        result = subprocess.run(["/bin/sh", "-n", "-c", command], capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)

    def test_adb_requires_fresh_response_marker_after_service(self):
        sequence = self.scripts["show5_fixture_adb_fixed"]["sequence"]
        self.assertIn("response_marker", sequence[2]["variables"])
        self.assertEqual(sequence[3]["service"], "androidtv.adb_command")
        self.assertIn("endswith(response_marker)", sequence[4]["if"][0]["value_template"])
        self.assertTrue(sequence[4]["then"][0]["error"])

    def test_preflight_precedes_any_mode_cleanup_or_mute(self):
        sequence = self.main["sequence"]
        probe_index = next(i for i, row in enumerate(sequence) if any(a.get("data", {}).get("operation") == "probe_jitsi" for a in actions(row, "script.show5_fixture_adb_fixed")))
        first_effect = next(i for i, row in enumerate(sequence) if actions(row, "input_number.set_value"))
        self.assertLess(probe_index, first_effect)
        self.assertIn("Unknown remote mode", json.dumps(sequence[0]))

    def test_persistent_state_has_no_initial_values_and_timer_restores(self):
        for domain in ("input_select", "input_boolean", "input_text", "input_number", "timer"):
            for value in self.package[domain].values():
                self.assertNotIn("initial", value)
        self.assertTrue(self.package["timer"]["show5_fixture_lease"]["restore"])
        self.assertEqual(self.main["mode"], "queued")

    def test_jitsi_starts_muted_in_attended_prejoin(self):
        command = endpoint.fixed_operations(self.config)["start_jitsi"]
        for setting in ("prejoinConfig.enabled=true", "startWithAudioMuted=true", "startWithVideoMuted=true"):
            self.assertIn(setting, command)
        self.assertNotIn("input keyevent", command)
        self.assertNotIn("media_projection", json.dumps(self.package))

    def test_operator_can_select_direct_jitsi_with_media_enabled(self):
        from render_remote_dashboard import render_dashboard
        config = dict(self.config, jitsi_auto_join=True,
                      jitsi_room_url="https://meet.example.invalid/call")
        command = endpoint.fixed_operations(config)["start_jitsi"]
        self.assertIn("org.jitsi.meet://meet.example.invalid/call#", command)
        for setting in ("prejoinConfig.enabled=false", "startWithAudioMuted=false",
                        "startWithVideoMuted=false", "requireDisplayName=false"):
            self.assertIn(setting, command)
        self.assertIn("camera and microphone enabled", json.dumps(render_dashboard(config)))
        self.assertNotIn("jitsi_auto_join", json.dumps(endpoint.render_package(config)["script"]["show5_fixture_command"]["fields"]))
        for invalid in ("true", "false", 1, None, []):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                endpoint.render_package(dict(self.config, jitsi_auto_join=invalid))

    def test_jitsi_stop_is_confirmed_before_microphone_restore(self):
        branch = next(row for row in self.main["sequence"] if "old_mode == 'jitsi'" in json.dumps(row.get("if", [])))
        self.assertEqual(branch["then"][0]["data"]["operation"], "stop_jitsi")
        restores = branch["then"][1]["then"]
        self.assertIn("Saved microphone state", json.dumps(restores[0]))
        self.assertEqual(restores[-1]["service"], "input_boolean.turn_off")
        self.assertEqual(restores[-1]["target"]["entity_id"], "input_boolean.show5_fixture_restore_mute_pending")
        self.assertFalse(restores[-2]["continue_on_timeout"])

    def test_lease_is_running_before_jitsi_mute_or_launch(self):
        sequence = self.main["sequence"]
        start_index = next(i for i, row in enumerate(sequence) if row.get("service") == "timer.start")
        mute_index = next(i for i, row in enumerate(sequence) if "{{ mode == 'jitsi' }}" in json.dumps(row.get("if", [])))
        self.assertLess(start_index, mute_index)
        self.assertIn("120", json.dumps(sequence[:7]))

    def test_only_owned_apps_are_stopped_and_vaca_is_never_stopped(self):
        commands = endpoint.fixed_operations(self.config)
        stopped = {command.split("am force-stop ", 1)[1].split()[0] for command in commands.values() if "am force-stop " in command}
        self.assertEqual(stopped, set(self.config["app_ids"].values()))
        self.assertNotIn(endpoint.VACA_PACKAGE, stopped)
        self.assertNotIn("com.pas.webcam", stopped)
        self.assertIn("android.intent.category.HOME", commands["home"])
        self.assertIn("input keyevent 224", commands["home"])

    def test_display_retries_same_id_expiry_and_home_omits_camera_fields(self):
        sequence = self.scripts["show5_fixture_display"]["sequence"]
        variables = sequence[3]["variables"]
        self.assertIn("+ 15", variables["expires_at"])
        repeat = sequence[4]["repeat"]
        self.assertEqual(repeat["count"], 4)
        self.assertEqual(repeat["sequence"][1]["timeout"], {"seconds": 3})
        self.assertIn("input_text.show5_fixture_display_ack", repeat["sequence"][1]["wait_template"])
        ack = self.package["automation"][0]
        self.assertEqual(ack["trigger"][0]["event_type"], "show5_remote_ack")
        self.assertEqual(ack["trigger"][0]["event_data"], {"target": self.config["prefix"]})
        self.assertNotIn("variables", repeat["sequence"][0])
        event_rows = [row for row in walk(repeat) if isinstance(row, dict) and row.get("event") == "show5_remote_display"]
        self.assertEqual(len(event_rows), 2)
        for row in event_rows:
            self.assertEqual(row["event_data"]["target"], self.config["prefix"])
            self.assertEqual(row["event_data"]["command_id"], "{{ command_id }}")
            self.assertEqual(row["event_data"]["expires_at"], "{{ expires_at }}")
        home = next(row["event_data"] for row in event_rows if row["event_data"]["command"] == "home")
        self.assertNotIn("role", home)
        self.assertNotIn("seconds", home)

    def test_expiry_restart_reconnect_cleanup_cannot_end_new_session(self):
        for automation in self.package["automation"][1:]:
            calls = actions(automation, "script.show5_fixture_command")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["data"]["mode"], "home")
            self.assertIn("_expected_token", calls[0]["data"])
        self.assertIn("Expired cleanup request ignored", json.dumps(self.main))
        self.assertIn("timer.cancel", json.dumps(self.package["automation"][2]))

    def test_interrupted_cleanup_rearms_bounded_recovery_before_stop(self):
        sequence = self.main["sequence"]
        rearm_index = next(i for i, row in enumerate(sequence) if any(a.get("data", {}).get("duration") == 60 for a in actions(row, "timer.start")))
        stop_index = next(i for i, row in enumerate(sequence) if any(a.get("data", {}).get("operation") == "stop_jitsi" for a in actions(row, "script.show5_fixture_adb_fixed")))
        self.assertLess(rearm_index, stop_index)
        self.assertIn("< 3", json.dumps(sequence[rearm_index]))
        self.assertEqual(self.package["input_number"]["show5_fixture_cleanup_attempts"]["max"], 3)

    def test_optional_native_app_is_not_advertised_when_unbound(self):
        del self.config["app_ids"]["ottplay_native"]
        package = endpoint.render_package(self.config)
        fields = package["script"]["show5_fixture_command"]["fields"]
        self.assertNotIn("ottplay_native", fields["mode"]["selector"]["select"]["options"])
        self.assertNotIn("start_ottplay_native", endpoint.fixed_operations(self.config))

    def test_no_tv_presets_omits_unusable_tv_mode_and_empty_selector(self):
        self.config["tv_presets"] = {}
        fields = endpoint.render_package(self.config)["script"]["show5_fixture_command"]["fields"]
        self.assertNotIn("tv", fields["mode"]["selector"]["select"]["options"])
        self.assertNotIn("preset", fields)

    def test_no_private_values_in_public_action_fields_and_no_traces(self):
        fields = json.dumps(self.main["fields"])
        for private in (self.config["serial"], self.config["jitsi_room_url"], self.config["ottplay_url"]):
            self.assertNotIn(private, fields)
        for script in self.scripts.values():
            self.assertEqual(script["trace"]["stored_traces"], 0)
        for automation in self.package["automation"]:
            self.assertEqual(automation["trace"]["stored_traces"], 0)

    def test_audio_never_flows_into_adb_commands(self):
        self.assertNotIn("audio_media_id", json.dumps(endpoint.fixed_operations(self.config)))
        play = actions(self.package, "media_player.play_media")
        self.assertEqual(len(play), 1)
        self.assertEqual(play[0]["target"]["entity_id"], self.config["vaca_media_entity"])
        self.assertEqual(play[0]["data"]["media_content_type"], "music")
        self.assertNotIn("media_next_track", json.dumps(self.package))

    def test_audio_wrapper_uses_own_media_picker_and_serial_coordinator(self):
        wrapper = self.scripts["show5_fixture_play_audio"]
        self.assertEqual(wrapper["fields"]["media"]["selector"]["media"], {"accept": ["audio/*"]})
        self.assertIn("media is mapping", json.dumps(wrapper["sequence"][0]))
        self.assertIn("audio only", json.dumps(wrapper["sequence"][1]))
        self.assertEqual(wrapper["sequence"][2]["service"], "script.show5_fixture_command")
        self.assertEqual(wrapper["sequence"][2]["data"], {"mode": "music", "audio_media_id": "{{ media.media_content_id }}", "lease_minutes": 30})

    def test_output_is_private_exclusive_and_symlink_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "private" / "remote.json"
            endpoint.write_private(output, self.package, root)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                endpoint.write_private(output, {}, root)
            with self.assertRaises(ValueError):
                endpoint.write_private(root / "public.json", {}, root)
            (root / "outside").mkdir()
            (root / "private" / "link").symlink_to(root / "outside", target_is_directory=True)
            with self.assertRaises(ValueError):
                endpoint.write_private(root / "private" / "link" / "escape.json", {}, root)


if __name__ == "__main__":
    unittest.main()
