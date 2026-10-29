"""Strict, credential-free Show SIP protocol; no Home Assistant imports."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shlex
import uuid

DOMAIN = "show5_sip"
PACKAGE = "org.hahomelab.show5sip"
AUTHORITY = "content://" + PACKAGE
ACTION = PACKAGE + ".CONTROL"
REGISTRATIONS = frozenset({"unconfigured", "registering", "registered", "failed"})
STATES = frozenset({"idle", "ringing", "preparing", "dialing", "active", "ending", "error"})
COMMANDS = frozenset({"dial", "answer", "decline", "hangup"})
SLUG = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
CALL_ID = re.compile(r"[A-Za-z0-9_-]{1,96}\Z")
MARKER = re.compile(r"[0-9a-f]{32}\Z")


class ProtocolError(ValueError):
    """Only fixed error codes cross the control boundary."""


def slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise ProtocolError("invalid_identifier")
    return value


def call_id(value):
    if not isinstance(value, str) or not CALL_ID.fullmatch(value):
        raise ProtocolError("invalid_call_id")
    return value


def request_id(value):
    if not isinstance(value, str):
        raise ProtocolError("invalid_request_id")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except ValueError:
        raise ProtocolError("invalid_request_id") from None
    return value


def validate_endpoint(value):
    if not isinstance(value, dict) or set(value) != {"endpoint_id", "name", "adb_entity", "serial", "contacts"}:
        raise ProtocolError("invalid_endpoint_configuration")
    out = dict(value)
    slug(out["endpoint_id"])
    if not isinstance(out["name"], str) or not 1 <= len(out["name"]) <= 64 or any(ord(c) < 32 for c in out["name"]):
        raise ProtocolError("invalid_endpoint_name")
    if not isinstance(out["adb_entity"], str) or not re.fullmatch(r"media_player\.[a-z0-9_]{1,100}", out["adb_entity"]):
        raise ProtocolError("invalid_adb_entity")
    if not isinstance(out["serial"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", out["serial"]):
        raise ProtocolError("invalid_serial")
    if not isinstance(out["contacts"], list) or not 1 <= len(out["contacts"]) <= 32:
        raise ProtocolError("invalid_contacts")
    contacts = []
    for contact in out["contacts"]:
        if not isinstance(contact, dict) or set(contact) != {"id", "label"}:
            raise ProtocolError("invalid_contact")
        slug(contact["id"])
        if not isinstance(contact["label"], str) or not 1 <= len(contact["label"]) <= 64 or any(ord(c) < 32 for c in contact["label"]):
            raise ProtocolError("invalid_contact_label")
        contacts.append(dict(contact))
    if len({c["id"] for c in contacts}) != len(contacts):
        raise ProtocolError("duplicate_contact")
    out["contacts"] = contacts
    return out


def guarded(serial, body, marker):
    """Correlate each response to this invocation and full Android identity."""
    if not isinstance(serial, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", serial):
        raise ProtocolError("invalid_serial")
    if not isinstance(marker, str) or not MARKER.fullmatch(marker):
        raise ProtocolError("invalid_marker")
    return (
        '[ "$(getprop ro.serialno)" = ' + shlex.quote(serial) + ' ] && '
        '[ "$(getprop ro.product.device)" = cronos ] && '
        '[ "$(id -u)" = 2000 ] && '
        "printf '%s\\n' " + shlex.quote("SHOW5_SIP_BEGIN_" + marker) + " && "
        + body + " && printf '%s\\n' " + shlex.quote("SHOW5_SIP_END_" + marker)
    )


def status_command(serial, marker):
    return guarded(serial, "content query --uri " + AUTHORITY + "/status", marker)


def foreground_command(serial, marker):
    # Activity launch is an explicit operator action. It never selects or answers a call.
    body = ("output=$(am start -W -n " + PACKAGE + "/.MainActivity 2>&1) && "
            "case \"$output\" in *Error:*|*Exception*) exit 1 ;; "
            "*'Status: ok'*) printf '%s\\n' \"$output\" ;; *) exit 1 ;; esac")
    return guarded(serial, body, marker)


def control_command(serial, marker, command, *, command_id, contact_id=None, expected_call_id=None):
    if command not in COMMANDS:
        raise ProtocolError("invalid_command")
    args = ["am", "broadcast", "--receiver-foreground", "-a", ACTION, "-p", PACKAGE,
            "--es", "command", command, "--es", "request_id", request_id(command_id)]
    if command == "dial":
        if expected_call_id is not None:
            raise ProtocolError("unexpected_call_id")
        args += ["--es", "contact_id", slug(contact_id)]
    else:
        if contact_id is not None:
            raise ProtocolError("unexpected_contact_id")
        args += ["--es", "expected_call_id", call_id(expected_call_id)]
    return guarded(serial, shlex.join(args), marker)


def extract_output(output, marker):
    if not isinstance(output, str) or len(output) > 16384:
        raise ProtocolError("invalid_adb_response")
    begin, end = "SHOW5_SIP_BEGIN_" + marker, "SHOW5_SIP_END_" + marker
    lines = output.replace("\r\n", "\n").splitlines()
    if lines.count(begin) != 1 or lines.count(end) != 1:
        raise ProtocolError("uncorrelated_adb_response")
    first, last = lines.index(begin), lines.index(end)
    if first >= last or any(line.strip() for line in lines[last + 1:]):
        raise ProtocolError("invalid_adb_response")
    return "\n".join(lines[first + 1:last]).strip()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate_status_field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Status:
    endpoint_id: str
    configured: bool
    config_sha256: str | None
    config_error: str | None
    registration: str
    state: str
    call_id: str | None
    contact_id: str | None
    lease_held: bool
    last_error: str | None
    last_command_id: str | None
    last_command_result: str | None
    last_command_error: str | None

    def public(self):
        """Only the documented allowlist is exposed in HA state and responses."""
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


def parse_status(output, marker, endpoint_id):
    content = extract_output(output, marker)
    if len(content) > 8192 or not content.startswith("Row: 0 json="):
        raise ProtocolError("invalid_status_row")
    try:
        value = json.loads(content.removeprefix("Row: 0 json="), object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, TypeError, RecursionError):
        raise ProtocolError("invalid_status_json") from None
    required = {"schema", "endpoint_id", "configured", "config_sha256", "config_error", "registration", "state", "call_id", "contact_id", "lease_held", "last_error", "last_command_id", "last_command_result", "last_command_error"}
    if not isinstance(value, dict) or set(value) != required or type(value["schema"]) is not int or value["schema"] != 1:
        raise ProtocolError("unsupported_status_schema")
    if value["endpoint_id"] != endpoint_id:
        raise ProtocolError("wrong_endpoint")
    if type(value["configured"]) is not bool:
        raise ProtocolError("invalid_configuration_state")
    if value["config_sha256"] is not None and (not isinstance(value["config_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["config_sha256"])):
        raise ProtocolError("invalid_configuration_digest")
    if value["config_error"] not in (None, "invalid_config", "config_busy"):
        raise ProtocolError("invalid_configuration_error")
    if not isinstance(value["registration"], str) or value["registration"] not in REGISTRATIONS or not isinstance(value["state"], str) or value["state"] not in STATES:
        raise ProtocolError("invalid_status_state")
    if type(value["lease_held"]) is not bool:
        raise ProtocolError("invalid_lease_state")
    for key in ("call_id", "contact_id"):
        if value[key] is not None:
            (call_id if key == "call_id" else slug)(value[key])
    if value["state"] in {"ringing", "preparing", "dialing", "active"} and value["call_id"] is None:
        raise ProtocolError("missing_call_id")
    for key in ("last_error", "last_command_error"):
        if value[key] is not None and (not isinstance(value[key], str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value[key])):
            raise ProtocolError("invalid_error_code")
    if value["last_command_id"] is not None:
        request_id(value["last_command_id"])
    if value["last_command_result"] not in (None, "accepted", "rejected"):
        raise ProtocolError("invalid_command_receipt")
    if (value["last_command_id"] is None) != (value["last_command_result"] is None):
        raise ProtocolError("incomplete_command_receipt")
    if value["last_command_error"] is not None and value["last_command_result"] != "rejected":
        raise ProtocolError("invalid_command_error")
    value.pop("schema")
    return Status(**value)
