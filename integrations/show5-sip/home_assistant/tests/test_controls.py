"""Offline boundary/lifecycle tests. No Home Assistant, Android, SIP or network."""
import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/show5_sip"
PACKAGE = "show5_sip_offline"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package


def load(name):
    spec = importlib.util.spec_from_file_location(PACKAGE + "." + name, COMPONENT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


protocol, controller = load("protocol"), load("controller")
MARKER = "a" * 32
SERIAL = "EXAMPLE123456"
CALL = "11111111-1111-4111-8111-111111111111"
CONFIG = {"endpoint_id": "show_one", "name": "Show one", "adb_entity": "media_player.show_one_adb",
          "serial": SERIAL, "contacts": [{"id": "kitchen", "label": "Kitchen"}]}


def state(**changes):
    value = {"schema": 1, "endpoint_id": "show_one", "configured": True, "config_sha256": "a" * 64,
             "config_error": None, "registration": "registered", "state": "idle",
             "call_id": None, "contact_id": None, "lease_held": False, "last_error": None,
             "last_command_id": None, "last_command_result": None, "last_command_error": None}
    return value | changes


def response(value, marker=MARKER):
    return f"SHOW5_SIP_BEGIN_{marker}\nRow: 0 json={json.dumps(value)}\nSHOW5_SIP_END_{marker}\n"


class ProtocolTests(unittest.TestCase):
    def test_status_is_exact_sanitized_contract(self):
        self.assertEqual(protocol.parse_status(response(state()), MARKER, "show_one").public(),
                         {k: v for k, v in state().items() if k != "schema"})

    def test_status_from_other_endpoint_is_rejected(self):
        with self.assertRaisesRegex(protocol.ProtocolError, "wrong_endpoint"):
            protocol.parse_status(response(state(endpoint_id="show_two")), MARKER, "show_one")

    def test_stale_adb_attribute_never_counts_as_a_fresh_read(self):
        with self.assertRaisesRegex(protocol.ProtocolError, "uncorrelated"):
            protocol.parse_status(response(state(), "b" * 32), MARKER, "show_one")

    def test_duplicate_and_reversed_markers_rejected(self):
        for text in (response(state()) + f"SHOW5_SIP_END_{MARKER}\n",
                     f"SHOW5_SIP_END_{MARKER}\nSHOW5_SIP_BEGIN_{MARKER}\n"):
            with self.subTest(text=text), self.assertRaises(protocol.ProtocolError):
                protocol.parse_status(text, MARKER, "show_one")

    def test_extra_rows_error_output_or_missing_provider_rejected(self):
        for payload in ("No result found.", "Error while accessing provider", "Row: 0 json={}\nRow: 1 json={}"):
            text = f"SHOW5_SIP_BEGIN_{MARKER}\n{payload}\nSHOW5_SIP_END_{MARKER}"
            with self.subTest(payload=payload), self.assertRaises(protocol.ProtocolError):
                protocol.parse_status(text, MARKER, "show_one")

    def test_status_never_exposes_an_added_credential_field(self):
        with self.assertRaisesRegex(protocol.ProtocolError, "unsupported_status_schema"):
            protocol.parse_status(response(state(password="private")), MARKER, "show_one")

    def test_json_duplicate_field_rejected(self):
        text = response(state()).replace('"schema": 1,', '"schema": 1, "schema": 2,')
        with self.assertRaisesRegex(protocol.ProtocolError, "duplicate_status_field"):
            protocol.parse_status(text, MARKER, "show_one")

    def test_wrong_field_types_and_unbounded_error_text_rejected(self):
        cases = [{"schema": True}, {"registration": []}, {"state": "connected"}, {"lease_held": 1},
                 {"call_id": "shell;command"}, {"contact_id": "sip:someone@example.invalid"},
                 {"last_error": "failed at https://example.invalid/private"}, {"last_error": "x" * 65},
                 {"last_command_id": "not-a-uuid"}, {"last_command_result": []},
                 {"last_command_result": "accepted"}, {"last_command_error": "failed"}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(protocol.ProtocolError):
                protocol.parse_status(response(state(**changes)), MARKER, "show_one")

    def test_call_states_require_an_identity(self):
        for phase in ("ringing", "preparing", "dialing", "active"):
            with self.subTest(phase=phase), self.assertRaisesRegex(protocol.ProtocolError, "missing_call_id"):
                protocol.parse_status(response(state(state=phase)), MARKER, "show_one")

    def test_crash_cleanup_can_end_without_resurrecting_a_call_id(self):
        result = protocol.parse_status(response(state(state="ending", lease_held=True)), MARKER, "show_one")
        self.assertIsNone(result.call_id)
        self.assertTrue(result.lease_held)

    def test_native_protocol_mismatch_error_is_a_sanitized_code(self):
        result = protocol.parse_status(response(state(state="ending", lease_held=True,
            last_error="lease_protocol_mismatch")), MARKER, "show_one")
        self.assertEqual(result.last_error, "lease_protocol_mismatch")

    def test_full_device_identity_and_nonroot_shell_guard_all_commands(self):
        for command in (protocol.status_command(SERIAL, MARKER), protocol.control_command(
                SERIAL, MARKER, "hangup", command_id=str(uuid.uuid4()), expected_call_id=CALL),
                protocol.foreground_command(SERIAL, MARKER)):
            self.assertIn('getprop ro.serialno)" = EXAMPLE123456', command)
            self.assertIn('getprop ro.product.device)" = cronos', command)
            self.assertIn('id -u)" = 2000', command)
            self.assertNotIn("force-stop", command)

    def test_shell_or_raw_uri_inputs_cannot_enter_commands(self):
        for value in ("kitchen;id", "$(id)", "sip:kitchen@example.invalid", "kitchen\nother"):
            with self.subTest(value=value), self.assertRaises(protocol.ProtocolError):
                protocol.control_command(SERIAL, MARKER, "dial", command_id=str(uuid.uuid4()), contact_id=value)
        with self.assertRaises(protocol.ProtocolError):
            protocol.status_command("SERIAL;id", MARKER)

    def test_action_shape_rejects_extra_routing_information(self):
        cases = [("dial", {"contact_id": "kitchen", "expected_call_id": CALL}),
                 ("hangup", {"contact_id": "kitchen", "expected_call_id": CALL}),
                 ("answer", {}), ("stop", {})]
        for command, fields in cases:
            with self.subTest(command=command), self.assertRaises(protocol.ProtocolError):
                protocol.control_command(SERIAL, MARKER, command, command_id=str(uuid.uuid4()), **fields)

    def test_configuration_rejects_uri_password_duplicate_or_unknown_fields(self):
        cases = [CONFIG | {"password": "private"}, CONFIG | {"serial": "short"},
                 CONFIG | {"adb_entity": "switch.anything"},
                 CONFIG | {"contacts": [{"id": "kitchen", "label": "Kitchen", "address": "sip:1@example.invalid"}]},
                 CONFIG | {"contacts": CONFIG["contacts"] * 2}]
        for config in cases:
            with self.subTest(config=config), self.assertRaises(protocol.ProtocolError):
                protocol.validate_endpoint(config)


class FakeADB:
    def __init__(self, initial=None, acknowledge=True, reject=False):
        self.status = initial or state()
        self.acknowledge, self.reject = acknowledge, reject
        self.events = []
        self.contexts = []

    async def __call__(self, command, context):
        self.contexts.append(context)
        marker = re.search(r"SHOW5_SIP_BEGIN_([0-9a-f]{32})", command)[1]
        if "content query" in command:
            self.events.append("query")
            await asyncio.sleep(0)
            return response(self.status, marker)
        if "am start -W" in command:
            self.events.append("foreground")
            return f"SHOW5_SIP_BEGIN_{marker}\nStatus: ok\nSHOW5_SIP_END_{marker}"
        self.events.append("broadcast")
        command_id = re.search(r"--es request_id ([0-9a-f-]+)", command)[1]
        if self.acknowledge:
            self.status = self.status | {"last_command_id": command_id,
                "last_command_result": "rejected" if self.reject else "accepted",
                "last_command_error": "lease_unavailable" if self.reject else None}
        return f"SHOW5_SIP_BEGIN_{marker}\nBroadcast completed: result=0\nSHOW5_SIP_END_{marker}"


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_dial_requires_application_acknowledgement(self):
        adb = FakeADB()
        endpoint = controller.Endpoint(CONFIG, adb)
        result = await endpoint.command("dial", contact_id="kitchen", context="operator")
        self.assertEqual(adb.events, ["query", "foreground", "broadcast", "query"])
        self.assertEqual(adb.contexts, ["operator"] * 4)
        self.assertEqual(result.last_command_result, "accepted")
        # Shell success and app acceptance do not claim media connection.
        self.assertEqual(result.state, "idle")

    async def test_timeout_never_resends_an_uncertain_dial(self):
        adb = FakeADB(acknowledge=False)
        endpoint = controller.Endpoint(CONFIG, adb, acknowledgement_timeout=.03, poll_delay=.001)
        with self.assertRaisesRegex(protocol.ProtocolError, "command_acknowledgement_timeout"):
            await endpoint.command("dial", contact_id="kitchen")
        self.assertEqual(adb.events.count("broadcast"), 1)

    async def test_device_rejection_is_not_reported_as_success(self):
        adb = FakeADB(reject=True)
        with self.assertRaisesRegex(protocol.ProtocolError, "lease_unavailable"):
            await controller.Endpoint(CONFIG, adb).command("dial", contact_id="kitchen")

    async def test_failed_foreground_launch_does_not_start_a_call(self):
        adb = FakeADB()
        async def execute(command, context):
            output = await adb(command, context)
            return output.replace("Status: ok", "Error: activity missing")
        with self.assertRaisesRegex(protocol.ProtocolError, "foreground_launch_failed"):
            await controller.Endpoint(CONFIG, execute).command("dial", contact_id="kitchen")
        self.assertNotIn("broadcast", adb.events)

    async def test_unknown_contact_is_not_broadcast(self):
        adb = FakeADB()
        with self.assertRaisesRegex(protocol.ProtocolError, "contact_not_allowed"):
            await controller.Endpoint(CONFIG, adb).command("dial", contact_id="other")
        self.assertNotIn("broadcast", adb.events)

    async def test_unregistered_busy_or_pending_cleanup_refuse_dial(self):
        for initial in (state(configured=False), state(registration="failed"), state(state="ringing", call_id=CALL),
                        state(lease_held=True), state(call_id=CALL), state(state="error", lease_held=True)):
            adb = FakeADB(initial)
            with self.subTest(initial=initial), self.assertRaises(protocol.ProtocolError):
                await controller.Endpoint(CONFIG, adb).command("dial", contact_id="kitchen")
            self.assertNotIn("broadcast", adb.events)

    async def test_recovered_error_allows_manual_retry_without_stale_lease(self):
        adb = FakeADB(state(state="error", last_error="call_failed"))
        result = await controller.Endpoint(CONFIG, adb).command("dial", contact_id="kitchen")
        self.assertEqual(result.last_command_result, "accepted")
        self.assertEqual(adb.events.count("broadcast"), 1)

    async def test_answer_decline_and_hangup_refuse_a_replaced_call(self):
        for command in ("answer", "decline", "hangup"):
            adb = FakeADB(state(state="ringing", call_id="new-call"))
            with self.subTest(command=command), self.assertRaisesRegex(protocol.ProtocolError, "call_changed"):
                await controller.Endpoint(CONFIG, adb).command(command, expected_call_id=CALL)
            self.assertNotIn("broadcast", adb.events)

    async def test_answer_and_decline_only_apply_while_ringing(self):
        for command in ("answer", "decline"):
            adb = FakeADB(state(state="active", call_id=CALL, lease_held=True))
            with self.subTest(command=command), self.assertRaisesRegex(protocol.ProtocolError, "not_ringing"):
                await controller.Endpoint(CONFIG, adb).command(command, expected_call_id=CALL)
            self.assertNotIn("broadcast", adb.events)

    async def test_hangup_acceptance_retains_pending_state(self):
        adb = FakeADB(state(state="ending", call_id=CALL, lease_held=True))
        result = await controller.Endpoint(CONFIG, adb).command("hangup", expected_call_id=CALL)
        self.assertEqual((result.state, result.lease_held), ("ending", True))
        self.assertNotIn("foreground", adb.events)

    async def test_stale_ack_for_another_request_is_not_accepted(self):
        adb = FakeADB(state(last_command_id=str(uuid.uuid4()), last_command_result="accepted"), acknowledge=False)
        with self.assertRaisesRegex(protocol.ProtocolError, "command_acknowledgement_timeout"):
            await controller.Endpoint(CONFIG, adb, acknowledgement_timeout=.03, poll_delay=.001).command("dial", contact_id="kitchen")

    async def test_concurrent_controls_recheck_after_previous_control(self):
        adb = FakeADB()
        base = adb.__call__
        async def execute(command, context):
            result = await base(command, context)
            if "am broadcast" in command:
                adb.status.update(state="preparing", call_id=CALL, contact_id="kitchen")
            return result
        endpoint = controller.Endpoint(CONFIG, execute)
        results = await asyncio.gather(endpoint.command("dial", contact_id="kitchen"),
                                       endpoint.command("dial", contact_id="kitchen"), return_exceptions=True)
        self.assertEqual(adb.events.count("broadcast"), 1)
        self.assertEqual(sum(isinstance(item, protocol.ProtocolError) for item in results), 1)


class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_operator_gate_covers_service_and_button_contexts(self):
        tree = ast.parse((COMPONENT / "__init__.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "require_operator")
        namespace = {"HomeAssistantError": RuntimeError}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "operator_gate", "exec"), namespace)
        for user_id, active, admin, control in [(None, True, True, True), ("u", False, True, True),
                                               ("u", True, False, True), ("u", True, True, False),
                                               ("u", True, True, True)]:
            user = types.SimpleNamespace(is_active=active, is_admin=admin,
                                         permissions=types.SimpleNamespace(check_entity=lambda *_: control))
            async def get_user(_):
                return user
            hass = types.SimpleNamespace(auth=types.SimpleNamespace(async_get_user=get_user))
            namespace["POLICY_CONTROL"] = "control"
            context = types.SimpleNamespace(user_id=user_id)
            if user_id and active and admin and control:
                await namespace["require_operator"](hass, context, CONFIG["adb_entity"])
            else:
                with self.assertRaises(RuntimeError):
                    await namespace["require_operator"](hass, context, CONFIG["adb_entity"])


class FlowAbort(Exception):
    pass


class FakeConfigFlow:
    """Minimal HA flow lifecycle stand-in; validation is actual integration code."""
    def __init_subclass__(cls, **kwargs):
        pass

    def __init__(self):
        self.entries = []
        self.unique_id = None
        self.updated = None

    async def async_set_unique_id(self, value):
        self.unique_id = value

    def _async_current_entries(self):
        return self.entries

    def _abort_if_unique_id_configured(self, updates=None):
        if any(entry.unique_id == self.unique_id for entry in self.entries):
            self.updated = updates
            raise FlowAbort("already_configured")

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse((COMPONENT / "config_flow.py").read_text())
        definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
        namespace = {"json": json, "vol": types.SimpleNamespace(Schema=lambda value: value,
            Required=lambda value: value), "ConfigFlow": FakeConfigFlow,
            "DOMAIN": protocol.DOMAIN, "ProtocolError": protocol.ProtocolError,
            "validate_endpoint": protocol.validate_endpoint}
        exec(compile(ast.Module(body=definitions, type_ignores=[]), "config_flow", "exec"), namespace)
        self.flow = namespace["ShowSipConfigFlow"]()

    async def test_admin_user_form_creates_valid_reviewed_binding(self):
        form = await self.flow.async_step_user()
        self.assertEqual((form["type"], form["step_id"], form["errors"]), ("form", "user", {}))
        result = await self.flow.async_step_user({"endpoint": json.dumps(CONFIG)})
        self.assertEqual(result, {"type": "create_entry", "title": CONFIG["name"], "data": CONFIG})

    async def test_user_input_rejects_malformed_duplicate_unbounded_and_secret_fields(self):
        inputs = [{}, {"endpoint": "[]"}, {"endpoint": "{"}, {"endpoint": " " * 16385},
                  {"endpoint": json.dumps(CONFIG | {"password": "never-store"})},
                  {"endpoint": json.dumps(CONFIG), "serial": "unreviewed"},
                  {"endpoint": json.dumps(CONFIG).replace('"endpoint_id":', '"name": "Shadow", "endpoint_id":')}]
        for value in inputs:
            with self.subTest(value=str(value)[:100]):
                result = await self.flow.async_step_user(value)
                self.assertEqual(result["type"], "form")
                self.assertEqual(result["errors"], {"endpoint": "invalid_configuration"})
                self.assertIsNone(self.flow.unique_id)

    async def test_duplicate_physical_or_adb_binding_is_rejected(self):
        for field in ("serial", "adb_entity"):
            other = CONFIG | {"endpoint_id": "other", "serial": "OTHER123456",
                              "adb_entity": "media_player.other_adb"}
            other[field] = CONFIG[field]
            self.flow.entries = [types.SimpleNamespace(unique_id="other", data=other)]
            with self.subTest(field=field):
                result = await self.flow.async_step_user({"endpoint": json.dumps(CONFIG)})
                self.assertEqual(result, {"type": "abort", "reason": "duplicate_endpoint"})

    async def test_identical_user_retry_reuses_entry_without_writing(self):
        self.flow.entries = [types.SimpleNamespace(unique_id="show_one", data=dict(CONFIG))]
        with self.assertRaisesRegex(FlowAbort, "already_configured"):
            await self.flow.async_step_user({"endpoint": json.dumps(CONFIG)})
        self.assertIsNone(self.flow.updated)

    async def test_user_retry_cannot_replace_existing_mapping(self):
        self.flow.entries = [types.SimpleNamespace(unique_id="show_one", data=dict(CONFIG))]
        result = await self.flow.async_step_user({"endpoint": json.dumps(CONFIG | {"serial": "OTHER123456"})})
        self.assertEqual(result, {"type": "abort", "reason": "endpoint_id_in_use"})
        self.assertIsNone(self.flow.updated)

    async def test_yaml_import_remains_supported_and_updates_existing_entry(self):
        created = await self.flow.async_step_import(CONFIG)
        self.assertEqual(created["data"], CONFIG)
        self.flow.entries = [types.SimpleNamespace(unique_id="show_one", data=dict(CONFIG))]
        updated = CONFIG | {"name": "Show kitchen"}
        with self.assertRaisesRegex(FlowAbort, "already_configured"):
            await self.flow.async_step_import(updated)
        self.assertEqual(self.flow.updated, updated)
        invalid = await self.flow.async_step_import(CONFIG | {"secret": "never-store"})
        self.assertEqual(invalid, {"type": "abort", "reason": "invalid_configuration"})


if __name__ == "__main__":
    unittest.main()
