"""Exercise actual source-defined backend steps with inert HA service fakes."""
import ast
import asyncio
import pathlib
import secrets
import shlex
import types
import unittest
from unittest.mock import Mock


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "custom_components/show5_intercom/__init__.py"


class BackendDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = Mock()
        self.budgets = []

        def timeout(seconds):
            self.budgets.append(seconds)
            # Real cancellation, accelerated so no test waits eight seconds.
            return asyncio.timeout(.02)

        namespace = {
            "asyncio": types.SimpleNamespace(timeout=timeout, sleep=asyncio.sleep,
                                             CancelledError=asyncio.CancelledError),
            "_LOGGER": self.logger, "secrets": secrets, "shlex": shlex,
            "Context": lambda **kwargs: kwargs,
            "CAMERA": "test.camera", "COMPANION": "test.companion",
        }
        tree = ast.parse(SOURCE.read_text())
        nodes = [node for node in tree.body
                 if getattr(node, "name", None) in {"diagnostic_step", "Backend"}
                 or isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "_DIAGNOSTIC_PHASES"
                     for target in node.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
        self.step = namespace["diagnostic_step"]
        self.backend = object.__new__(namespace["Backend"])
        self.backend.config = {"mute_entity": "switch.test", "adb_entity": "media_player.test"}
        self.backend.guard = types.SimpleNamespace(active=None)
        self.state = types.SimpleNamespace(state="off", attributes={})
        self.backend.hass = types.SimpleNamespace(
            states=types.SimpleNamespace(get=lambda _: self.state),
            services=types.SimpleNamespace(has_service=lambda *_: True, async_call=self.call),
        )
        self.calls = []

    async def call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))
        if domain == "switch":
            self.state.state = "on" if service == "turn_on" else "off"
        else:
            self.state.attributes["adb_response"] = data["command"].rsplit(" && echo ", 1)[1]

    def messages(self):
        return [call.args[0] % call.args[1:] for call in self.logger.method_calls]

    async def test_mute_service_and_readback_have_separate_eight_second_budgets(self):
        await self.backend.set_mute(True)
        self.assertEqual(self.budgets, [8, 8])
        self.assertEqual(self.messages(), [
            "SHOW5_BACKEND_STEP mute_on_call begin None",
            "SHOW5_BACKEND_STEP mute_on_call success None",
            "SHOW5_BACKEND_STEP mute_on_readback begin None",
            "SHOW5_BACKEND_STEP mute_on_readback success None",
        ])
        self.assertEqual(self.calls[0][3]["context"], {})

    async def test_hung_switch_service_is_bounded_before_readback(self):
        cancelled = []
        async def hung(*args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
        self.backend.hass.services.async_call = hung
        with self.assertRaises(TimeoutError):
            await self.backend.set_mute(True)
        self.assertEqual(cancelled, [True])
        self.assertEqual(self.budgets, [8])
        self.assertEqual(self.messages()[-1], "SHOW5_BACKEND_STEP mute_on_call failed TimeoutError")

    async def test_readback_timeout_is_distinct_from_successful_service_call(self):
        async def no_state_change(*args, **kwargs):
            return None
        self.backend.hass.services.async_call = no_state_change
        with self.assertRaises(TimeoutError):
            await self.backend.set_mute(True)
        self.assertEqual(self.budgets, [8, 8])
        self.assertEqual(self.messages()[-1], "SHOW5_BACKEND_STEP mute_on_readback failed TimeoutError")

    async def test_adb_success_keeps_marker_verification_and_twelve_second_budget(self):
        await self.backend.adb("stop_camera", {"user_id": "test-user"})
        self.assertEqual(self.budgets, [12])
        self.assertEqual(self.calls[0][3]["context"], {"user_id": "test-user"})
        self.assertEqual(self.messages(), [
            "SHOW5_BACKEND_STEP adb_stop_camera begin None",
            "SHOW5_BACKEND_STEP adb_stop_camera success None",
        ])
        self.assertNotIn("am force-stop", str(self.messages()))
        self.assertNotIn("test-user", str(self.messages()))

    async def test_unconfirmed_adb_response_reports_fixed_action_without_output(self):
        async def wrong_marker(*args, **kwargs):
            self.state.attributes["adb_response"] = "private address/output"
        self.backend.hass.services.async_call = wrong_marker
        with self.assertRaises(ValueError):
            await self.backend.adb("wake")
        self.assertEqual(self.messages()[-1], "SHOW5_BACKEND_STEP adb_wake failed ValueError")
        self.assertNotIn("private", str(self.messages()))

    async def test_missing_adapter_is_classified_without_issuing_service_call(self):
        self.backend.hass.services.has_service = lambda *_: False
        with self.assertRaises(ValueError):
            await self.backend.adb("probe")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.messages()[-1], "SHOW5_BACKEND_STEP adb_probe failed ValueError")

    async def test_external_error_class_and_message_are_not_logged(self):
        PrivateTokenError = type("PrivateTokenError", (Exception,), {})
        async def failure():
            raise PrivateTokenError("https://secret:password@example.invalid")
        with self.assertRaises(PrivateTokenError):
            await self.step("adb_probe", failure)
        self.assertEqual(self.messages()[-1], "SHOW5_BACKEND_STEP adb_probe failed OtherError")
        self.assertNotIn("secret", str(self.messages()))
        self.assertNotIn("PrivateTokenError", str(self.messages()))
        self.assertTrue(all(not call.kwargs for call in self.logger.method_calls))

    async def test_cancelled_operation_is_logged_and_still_propagates(self):
        async def cancelled():
            raise asyncio.CancelledError("private details")
        with self.assertRaises(asyncio.CancelledError):
            await self.step("adb_wake", cancelled)
        self.assertEqual(self.messages()[-1], "SHOW5_BACKEND_STEP adb_wake failed CancelledError")

    async def test_lightweight_receiver_starts_fresh_and_default_route_is_preserved(self):
        for enabled, route in [(False, "echo-show/receive"), (True, "show5-call")]:
            with self.subTest(call_panel=enabled):
                self.backend.config["call_panel"] = enabled
                await self.backend.adb("open_calls")
                command = self.calls[-1][2]["command"]
                self.assertIn("homeassistant://navigate/" + route + "?server=default", command)
                self.assertEqual(command.startswith("am force-stop test.companion && "), enabled)
                self.assertTrue(command.rsplit(" && echo ", 1)[1].startswith("SHOW5_"))

    async def test_untrusted_phase_cannot_enter_diagnostics(self):
        async def unreachable():
            self.fail("untrusted phase executed")
        with self.assertRaises(ValueError):
            await self.step("private address", unreachable)
        self.assertEqual(self.messages(), [])


if __name__ == "__main__":
    unittest.main()
