"""Native Jitsi handoff contracts; no HA server, Android or network access."""
import asyncio
import re
import secrets
import shlex
import subprocess
import types
import unittest
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlsplit

from test_contract import extract
from test_lease import lease


class Invalid(ValueError):
    pass


class JitsiURLTests(unittest.TestCase):
    def setUp(self):
        self.namespace = {"re": re, "urlsplit": urlsplit,
                          "vol": types.SimpleNamespace(Invalid=Invalid)}
        self.validate = extract("__init__.py", "validate_jitsi_room", self.namespace)
        self.uri = extract("__init__.py", "jitsi_launch_uri", self.namespace)

    def test_fixed_https_room_and_nondefault_port(self):
        self.assertEqual(self.validate("https://meet.example.invalid:8080/show-room"),
                         "https://meet.example.invalid:8080/show-room")
        result = self.uri("https://meet.example.invalid:8080/show-room")
        self.assertEqual(result, "org.jitsi.meet://meet.example.invalid:8080/show-room"
                         "#config.prejoinConfig.enabled=true&config.startWithAudioMuted=true&config.startWithVideoMuted=true")

    def test_reject_credentials_overrides_shell_characters_and_ambiguous_routes(self):
        invalid = [None, "http://meet.example/room", "org.jitsi.meet://meet.example/room",
                   "https://user:password@meet.example/room", "https://meet.example/room?jwt=secret",
                   "https://meet.example/room#config.startWithAudioMuted=false", "https://meet.example/a/b",
                   "https://meet.example/../room", "https://meet.example/%72oom", "https://meet.example/",
                   "https://meet.example/room';reboot", "https://meet.example/room\n", "https://meet.example:0/room",
                   "https://meet.example:65536/room", "https://-bad.example/room", "https://meet..example/room"]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(Invalid):
                self.validate(value)


class JitsiLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        namespace = {"asyncio": types.SimpleNamespace(sleep=AsyncMock()), "JITSI_SECONDS": 120}
        self.Backend = extract("__init__.py", "Backend", namespace)
        self.backend = object.__new__(self.Backend)
        self.backend.config = {"jitsi_enabled": True, "video_enabled": False, "adb_entity": "media_player.test"}
        self.backend.jitsi_uri = "org.jitsi.meet://meet.example.invalid/room"
        self.backend.room = types.SimpleNamespace(lock=asyncio.Lock(), call=None)
        self.backend.recovery_pending = False
        self.events, self.records = [], []
        self.muted, self.fail_action = False, None
        self.context = types.SimpleNamespace(user_id="administrator")

        async def snapshot():
            return self.muted
        async def mute(value):
            self.events.append(("mute", value)); self.muted = value
        async def adb(action, context=None):
            self.events.append(("adb", action))
            if action == self.fail_action:
                raise RuntimeError("private backend details")
        async def camera():
            self.events.append(("camera_control",))
        async def journal(record):
            self.events.append(("journal", record)); self.records.append(record)
        self.backend.snapshot, self.backend.set_mute, self.backend.adb = snapshot, mute, adb
        self.backend.wait_camera = camera
        self.backend.report_recovery_error = Mock()
        self.backend.guard = lease.LeaseGuard(snapshot, self.backend.prepare, self.backend.restore, journal)

    async def asyncTearDown(self):
        self.fail_action = None
        if self.backend.guard.active:
            active = self.backend.guard.active
            await self.backend.guard.end(active.token, active.owner)

    async def test_start_journal_precedes_mutation_and_releases_both_capture_hosts(self):
        await self.backend.start_jitsi(self.context)
        self.assertEqual(self.events, [
            ("adb", "probe"), ("adb", "probe_jitsi"),
            ("journal", {"mode": "jitsi", "prior_muted": False}),
            ("mute", True), ("adb", "stop_camera"), ("adb", "stop_companion"),
            ("adb", "wake"), ("adb", "start_jitsi"),
        ])
        active = self.backend.guard.active
        self.assertEqual((active.owner, active.mode), ("administrator:jitsi", "jitsi"))
        self.assertLessEqual(active.deadline - __import__("time").monotonic(), 120)

    async def test_end_restores_camera_home_and_exact_prior_mute(self):
        self.muted = True
        await self.backend.start_jitsi(self.context)
        self.events.clear()
        await self.backend.end_jitsi()
        self.assertEqual(self.events, [("adb", "stop_jitsi"), ("adb", "start_camera"),
                         ("camera_control",), ("adb", "start_companion"), ("mute", True), ("journal", None)])
        self.assertIsNone(self.backend.guard.active)
        await self.backend.end_jitsi()  # idempotent, no extra device operation
        self.assertEqual(len(self.events), 6)

    async def test_uninstalled_app_does_not_mute_or_write_journal(self):
        self.fail_action = "probe_jitsi"
        with self.assertRaises(RuntimeError):
            await self.backend.start_jitsi(self.context)
        self.assertFalse(self.muted)
        self.assertEqual(self.records, [])
        self.assertIsNone(self.backend.guard.active)

    async def test_disabled_pending_recovery_or_video_invitation_cannot_start(self):
        for attr, value in [("enabled", False), ("recovery", True), ("call", {})]:
            self.backend.config["jitsi_enabled"] = value if attr == "enabled" else True
            self.backend.recovery_pending = value if attr == "recovery" else False
            self.backend.room.call = {"id": "pending"} if attr == "call" else None
            with self.subTest(attr=attr), self.assertRaises(ValueError):
                await self.backend.start_jitsi(self.context)
        self.assertEqual(self.events, [])

    async def test_repeated_start_and_cross_mode_end_preserve_current_session(self):
        await self.backend.start_jitsi(self.context)
        active = self.backend.guard.active
        with self.assertRaises(ValueError):
            await self.backend.start_jitsi(self.context)
        self.assertIs(self.backend.guard.active, active)
        await self.backend.end_jitsi()
        active = await self.backend.guard.acquire("other", "talk")
        with self.assertRaises(ValueError):
            await self.backend.end_jitsi()
        self.assertIs(self.backend.guard.active, active)

    async def test_failed_launch_restores_resources_and_prior_unmuted_state(self):
        self.fail_action = "start_jitsi"
        with self.assertRaises(RuntimeError):
            await self.backend.start_jitsi(self.context)
        self.assertFalse(self.muted)
        self.assertIsNone(self.backend.guard.active)
        self.assertEqual(self.records[-1], None)
        self.assertIn(("adb", "stop_jitsi"), self.events)

    async def test_timeout_uses_same_native_app_restoration(self):
        await self.backend.guard.acquire("administrator:jitsi", "jitsi", seconds=.01)
        await asyncio.sleep(.04)
        self.assertIsNone(self.backend.guard.active)
        self.assertFalse(self.muted)
        self.assertIn(("adb", "stop_jitsi"), self.events)

    async def test_restart_recovers_jitsi_even_when_new_starts_are_disabled(self):
        self.backend.config["jitsi_enabled"] = False
        await self.backend.guard.recover({"mode": "jitsi", "prior_muted": True})
        self.assertTrue(self.muted)
        self.assertEqual(self.events[0], ("adb", "stop_jitsi"))
        self.assertIsNone(self.backend.guard.active)

    async def test_failed_restore_retains_lease_and_retry_restores(self):
        await self.backend.start_jitsi(self.context)
        self.fail_action = "stop_jitsi"
        with self.assertRaises(RuntimeError):
            await self.backend.end_jitsi()
        self.assertTrue(self.backend.guard.cleanup_error)
        self.assertIsNotNone(self.records[-1])
        self.backend.report_recovery_error.assert_called_once()
        self.fail_action = None
        await self.backend.end_jitsi()
        self.assertIsNone(self.backend.guard.active)


class JitsiServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.backend = types.SimpleNamespace(config={"mute_entity": "switch.test", "adb_entity": "media_player.test"},
                                             start_jitsi=AsyncMock(), end_jitsi=AsyncMock())
        self.user = types.SimpleNamespace(is_admin=True, is_active=True,
                     permissions=types.SimpleNamespace(check_entity=lambda *_: True))
        self.hass = types.SimpleNamespace(data={"show5_intercom": self.backend},
                                         auth=types.SimpleNamespace(async_get_user=AsyncMock(return_value=self.user)))
        self.handle = extract("__init__.py", "handle_jitsi_service", {
            "DOMAIN": "show5_intercom", "POLICY_CONTROL": "control", "HomeAssistantError": Invalid})
        self.call = types.SimpleNamespace(service="jitsi_start", context=types.SimpleNamespace(user_id="admin"))

    async def test_admin_start_preserves_context_and_admin_end_is_separate(self):
        await self.handle(self.hass, self.call)
        self.backend.start_jitsi.assert_awaited_once_with(self.call.context)
        self.call.service = "jitsi_end"
        await self.handle(self.hass, self.call)
        self.backend.end_jitsi.assert_awaited_once_with()

    async def test_missing_system_inactive_or_nonadmin_context_denied(self):
        for kind in ("system", "missing", "inactive", "nonadmin"):
            self.call.context.user_id = None if kind == "system" else "admin"
            self.user.is_active = kind != "inactive"
            self.user.is_admin = kind != "nonadmin"
            self.hass.auth.async_get_user.return_value = None if kind == "missing" else self.user
            with self.subTest(kind=kind), self.assertRaises(Invalid):
                await self.handle(self.hass, self.call)
        self.backend.start_jitsi.assert_not_awaited()

    async def test_both_target_permissions_are_required(self):
        for denied in ("switch.test", "media_player.test"):
            self.user.permissions.check_entity = lambda entity, _: entity != denied
            with self.subTest(denied=denied), self.assertRaises(Invalid):
                await self.handle(self.hass, self.call)
        self.backend.start_jitsi.assert_not_awaited()

    async def test_service_failure_does_not_expose_private_url_or_command(self):
        self.backend.start_jitsi.side_effect = RuntimeError("https://private.example/secret am start")
        with self.assertRaises(Invalid) as caught:
            await self.handle(self.hass, self.call)
        self.assertEqual(str(caught.exception), "Jitsi handoff failed; check the Show intercom status")


class JitsiADBTests(unittest.IsolatedAsyncioTestCase):
    async def test_launch_output_is_private_and_failure_cannot_emit_success_marker(self):
        state = types.SimpleNamespace(attributes={})
        captured = []
        exit_code = 0
        async def call(domain, service, data, **kwargs):
            command = data["command"]
            self.assertIn(" >/dev/null 2>&1 && echo SHOW5_", command)
            # A local shell function stands in for Android am. It deliberately
            # prints the private intent to stdout AND stderr before returning.
            stub = "am() { printf '%s\\n' \"$*\"; printf '%s\\n' \"$*\" >&2; return " + str(exit_code) + "; }; "
            result = subprocess.run(["bash", "-c", stub + command], capture_output=True, text=True, check=False)
            captured.append(result)
            state.attributes["adb_response"] = result.stdout
        async def step(phase, operation):
            await operation()
        Backend = extract("__init__.py", "Backend", {
            "asyncio": asyncio, "secrets": secrets, "shlex": shlex,
            "CAMERA": "camera", "COMPANION": "companion", "JITSI": "org.jitsi.meet",
            "diagnostic_step": step, "Context": lambda **kwargs: kwargs,
        })
        backend = object.__new__(Backend)
        backend.config = {"adb_entity": "media_player.test"}
        backend.jitsi_uri = "org.jitsi.meet://private.example/room#config.startWithAudioMuted=true&config.startWithVideoMuted=true"
        backend.guard = types.SimpleNamespace(active=None)
        backend.hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda _: state),
                            services=types.SimpleNamespace(has_service=lambda *_: True, async_call=call))
        await backend.adb("start_jitsi")
        self.assertEqual(captured[-1].returncode, 0)
        self.assertRegex(captured[-1].stdout, r"^SHOW5_[0-9a-f]{24}\n$")
        self.assertEqual(captured[-1].stderr, "")
        exit_code = 7
        with self.assertRaises(ValueError):
            await backend.adb("start_jitsi")
        self.assertEqual(captured[-1].returncode, 7)
        self.assertEqual(captured[-1].stdout, "")
        self.assertEqual(captured[-1].stderr, "")

    async def test_launch_uses_one_quoted_fixed_uri_and_fixed_package(self):
        calls = []
        state = types.SimpleNamespace(attributes={})
        async def call(domain, service, data, **kwargs):
            calls.append(data["command"])
            state.attributes["adb_response"] = data["command"].rsplit(" && echo ", 1)[1]
        async def step(phase, operation):
            await operation()
        Backend = extract("__init__.py", "Backend", {
            "asyncio": asyncio, "secrets": secrets, "shlex": shlex,
            "CAMERA": "camera", "COMPANION": "companion", "JITSI": "org.jitsi.meet",
            "diagnostic_step": step, "Context": lambda **kwargs: kwargs,
        })
        backend = object.__new__(Backend)
        backend.config = {"adb_entity": "media_player.test"}
        backend.jitsi_uri = "org.jitsi.meet://meet.example.invalid/room#config.prejoinConfig.enabled=true&config.startWithAudioMuted=true&config.startWithVideoMuted=true"
        backend.guard = types.SimpleNamespace(active=None)
        backend.hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda _: state),
                            services=types.SimpleNamespace(has_service=lambda *_: True, async_call=call))
        await backend.adb("start_jitsi")
        args = shlex.split(calls[0].split(" && echo ")[0])
        self.assertEqual(args[args.index("-d") + 1], backend.jitsi_uri)
        self.assertEqual(args[args.index("-p") + 1], "org.jitsi.meet")
        backend.jitsi_uri = None
        with self.assertRaises(ValueError):
            await backend.adb("start_jitsi")


if __name__ == "__main__":
    unittest.main()
