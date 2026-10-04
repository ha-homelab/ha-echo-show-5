#!/usr/bin/env python3
"""Render a device-bound Home Assistant package; never contact HA or Android.

The operator supplies ignored local JSON, including fixed app/TV/Jitsi URLs.
Output is JSON (also valid YAML) under this repository's private directory.
The public command script accepts modes, preset names and audio media IDs only.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shlex
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VACA_PACKAGE = "com.msp1974.vacompanion"
MODES = ("home", "stop", "camera_front", "camera_porch", "music", "tv",
         "ottplay", "ottplay_native", "ottplayer", "jitsi")
ACTIVE_MODES = ("idle",) + MODES[2:]
MARKER = "{{ 'SHOW5_' ~ now().strftime('%Y%m%d%H%M%S%f') ~ '_' ~ (range(10000, 99999) | random) }}"


def _text(value, key, limit=2048):
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(part in value for part in ("{{", "{%", "{#"))):
        raise ValueError("Invalid text binding: " + key)
    return value


def _url(value, key, room=False):
    _text(value, key)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ("https", "http") and parsed.hostname
                 and parsed.username is None and parsed.password is None
                 and not parsed.fragment and not any(c.isspace() for c in value))
        parsed.port  # Validate malformed/non-numeric ports without reporting the URL.
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Expected a fixed HTTP(S) URL without credentials/fragment: " + key)
    if room and (parsed.scheme != "https" or parsed.query
                 or not re.fullmatch(r"/[A-Za-z0-9_-]+", parsed.path)):
        raise ValueError("Jitsi room must be one HTTPS room path without query/fragment")
    return value


def validate_config(config):
    required = {"prefix", "serial", "adb_entity", "vaca_mute_entity",
                "vaca_media_entity", "vaca_refresh_entity", "jitsi_room_url",
                "ottplay_url", "app_ids", "tv_presets"}
    if (not isinstance(config, dict) or not required <= set(config)
            or set(config) - required - {"clock_path"}):
        raise ValueError("Config must contain the documented bindings only")
    c = copy.deepcopy(config)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", _text(c["prefix"], "prefix")):
        raise ValueError("Invalid entity prefix")
    if not re.fullmatch(r"[A-Z0-9]{12,32}", _text(c["serial"], "serial")):
        raise ValueError("A full uppercase Android serial is required")
    for key, domain in (("adb_entity", "media_player"), ("vaca_media_entity", "media_player"),
                        ("vaca_mute_entity", "switch"), ("vaca_refresh_entity", "button")):
        if not re.fullmatch(domain + r"\.[a-z0-9_]+", _text(c[key], key)):
            raise ValueError("Wrong entity domain: " + key)
    if c["adb_entity"] == c["vaca_media_entity"]:
        raise ValueError("ADB and VACA media entities must be distinct")
    apps = c["app_ids"]
    required_apps = {"vlc", "jitsi", "browser", "ottplayer"}
    if (not isinstance(apps, dict) or not required_apps <= set(apps)
            or set(apps) - required_apps - {"ottplay_native"}):
        raise ValueError("app_ids requires vlc, jitsi, browser, ottplayer; optional ottplay_native")
    for key, value in apps.items():
        if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+",
                             _text(value, "app_ids." + key, 200))
                or value == VACA_PACKAGE):
            raise ValueError("Invalid owned app package: " + key)
    if len(set(apps.values())) != len(apps):
        raise ValueError("Owned app packages must be distinct")
    _url(c["jitsi_room_url"], "jitsi_room_url", room=True)
    _url(c["ottplay_url"], "ottplay_url")
    if "clock_path" in c and not re.fullmatch(r"/[A-Za-z0-9_./-]+", _text(c["clock_path"], "clock_path")):
        raise ValueError("clock_path is documentation only and must be a local path")
    presets = c["tv_presets"]
    if not isinstance(presets, dict) or len(presets) > 50:
        raise ValueError("tv_presets must contain at most 50 named fixed URLs")
    for key, value in presets.items():
        if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key)
                or not isinstance(value, dict) or set(value) != {"label", "url"}):
            raise ValueError("Each TV preset needs a safe key, label and fixed URL")
        _text(value["label"], "TV label", 100)
        _url(value["url"], "TV preset URL")
    return c


def guarded_command(serial, command):
    """Every operation verifies identity and unprivileged ADB shell ownership."""
    return ('[ "$(getprop ro.serialno)" = ' + shlex.quote(serial) + ' ] && '
            '[ "$(getprop ro.product.device)" = cronos ] && '
            '[ "$(id -u)" = 2000 ] && ( ' + command + ' )')


def _launch(arguments):
    # am can return zero while printing an intent resolution error.
    return ('result=$(am start -W ' + arguments + ' 2>&1) && '
            'case "$result" in *Error:*|*Exception*) false ;; *) true ;; esac')


def fixed_operations(c):
    apps = c["app_ids"]
    operations = {"home": "input keyevent 224 && " + _launch("-a android.intent.action.MAIN -c android.intent.category.HOME -p " + VACA_PACKAGE)}
    for key, package in apps.items():
        quoted = shlex.quote(package)
        operations["probe_" + key] = "pm path " + quoted + " 2>/dev/null | grep -q '^package:'"
        operations["stop_" + key] = "am force-stop " + quoted
    room = urlsplit(c["jitsi_room_url"])
    jitsi_uri = ("org.jitsi.meet://" + room.netloc + room.path
                 + "#config.prejoinConfig.enabled=true&config.startWithAudioMuted=true&config.startWithVideoMuted=true")
    operations["start_jitsi"] = _launch("-a android.intent.action.VIEW -d " + shlex.quote(jitsi_uri) + " -p " + shlex.quote(apps["jitsi"]))
    operations["start_ottplay"] = _launch("-a android.intent.action.VIEW -d " + shlex.quote(c["ottplay_url"]) + " -p " + shlex.quote(apps["browser"]))
    for key in ("ottplayer", "ottplay_native"):
        if key in apps:
            # Launcher filters need not include DEFAULT; an implicit am start
            # may fail even when package-manager resolves the launcher.
            package = shlex.quote(apps[key])
            operations["start_" + key] = (
                'component=$(cmd package resolve-activity --brief '
                '-a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p '
                + package + ' | tail -n 1) && case "$component" in '
                + package + '/*) ' + _launch('-n "$component"')
                + ' ;; *) false ;; esac')
    for key, preset in c["tv_presets"].items():
        operations["tv_" + key] = _launch("-a android.intent.action.VIEW -d " + shlex.quote(preset["url"]) + " -t 'video/*' -p " + shlex.quote(apps["vlc"]))
    return {key: guarded_command(c["serial"], command) for key, command in operations.items()}


def _service(service, entity=None, **data):
    action = {"service": service}
    if entity:
        action["target"] = {"entity_id": entity}
    if data:
        action["data"] = data
    return action


def _if(condition, then, otherwise=None):
    value = {"if": [{"condition": "template", "value_template": condition}], "then": then}
    if otherwise is not None:
        value["else"] = otherwise
    return value


def _require(condition, message):
    return _if("{{ not (" + condition + ") }}", [{"stop": message, "error": True}])


def _script(alias, sequence, fields=None, mode="single"):
    script = {"alias": alias, "mode": mode, "trace": {"stored_traces": 0}, "sequence": sequence}
    if mode == "queued":
        script["max"] = 10
    if fields:
        script["fields"] = fields
    return script


def render_package(config):
    c = validate_config(config)
    prefix = c["prefix"]
    entity = lambda domain, name: domain + "." + prefix + "_" + name
    active = entity("input_select", "active_mode")
    prior = entity("input_boolean", "prior_mute")
    pending = entity("input_boolean", "restore_mute_pending")
    token = entity("input_text", "lease_token")
    ack = entity("input_text", "display_ack")
    attempts = entity("input_number", "cleanup_attempts")
    timer = entity("timer", "lease")
    adb_script = entity("script", "adb_fixed")
    display_script = entity("script", "display")
    command_script = entity("script", "command")
    operations = fixed_operations(c)
    call_adb = lambda op: _service(adb_script, operation=op)
    state = lambda eid: "states(" + repr(eid) + ")"
    is_on = lambda eid: "is_state(" + repr(eid) + ", 'on')"
    scripts = {}
    scripts[prefix + "_adb_fixed"] = _script(prefix + ": verified fixed Android operation", [
        {"variables": {"fixed_commands": operations}},
        _require("operation is defined and operation is string and operation in fixed_commands", "Unknown fixed Android operation"),
        {"variables": {"response_marker": MARKER}},
        _service("androidtv.adb_command", c["adb_entity"], command="{{ fixed_commands[operation] ~ ' && echo ' ~ response_marker }}"),
        _require("(state_attr(" + repr(c["adb_entity"]) + ", 'adb_response') | default('', true) | string | trim).endswith(response_marker)",
                 "Android operation not confirmed: check this device identity, connectivity and app installation"),
    ], {"operation": {"required": True, "selector": {"select": {"options": sorted(operations)}}}})

    # One command ID/expiry across retries makes reconnect delivery idempotent.
    scripts[prefix + "_display"] = _script(prefix + ": wake clock / camera display", [
        _require("command is defined and command is string and command in ['home', 'camera']", "Invalid display command"),
        _require("command == 'home' or (role is defined and role is string and role in ['front', 'porch'] and seconds is defined and seconds is number and seconds is not boolean and 5 <= seconds <= 120)", "Invalid camera display parameters"),
        call_adb("home"),
        {"variables": {"command_id": MARKER, "expires_at": "{{ as_timestamp(now()) + 15 }}"}},
        {"repeat": {"count": 4, "sequence": [
            _if("{{ command == 'camera' }}", [{"event": "show5_remote_display", "event_data": {
                "target": prefix, "command_id": "{{ command_id }}", "command": "camera",
                "role": "{{ role }}", "seconds": "{{ seconds }}", "expires_at": "{{ expires_at }}"}}],
                [{"event": "show5_remote_display", "event_data": {
                    "target": prefix, "command_id": "{{ command_id }}", "command": "home", "expires_at": "{{ expires_at }}"}}]),
            # A permanent event automation records ACK before/after this waiter.
            # An event waiter registered after emit would lose immediate ACKs.
            {"wait_template": "{{ " + state(ack) + " in [command_id ~ '|ok', command_id ~ '|error'] }}",
             "timeout": {"seconds": 3}, "continue_on_timeout": True},
            _if("{{ wait.completed }}", [
                _require(state(ack) + " == command_id ~ '|ok'", "Display rejected the command"),
                {"stop": "Display acknowledged"}]),
        ]}},
        {"stop": "Display did not acknowledge; check foreground VACA and its HA connection", "error": True},
    ])

    # No public command parameter is interpolated into Android shell text.
    available_modes = [mode for mode in MODES
                       if (mode != "ottplay_native" or "ottplay_native" in c["app_ids"])
                       and (mode != "tv" or c["tv_presets"])]
    field_options = [{"value": key, "label": value["label"]} for key, value in c["tv_presets"].items()]
    fields = {
        "mode": {"required": True, "selector": {"select": {"options": available_modes}}},
        "preset": {"selector": {"select": {"options": field_options}}},
        "audio_media_id": {"description": "Audio only: HA media-source ID or an HTTP(S) audio stream; never an Android command.", "selector": {"text": {"multiline": False}}},
        "lease_minutes": {"default": 30, "selector": {"number": {"min": 1, "max": 120, "mode": "box"}}},
        "camera_seconds": {"default": 120, "selector": {"number": {"min": 5, "max": 120, "mode": "box"}}},
    }
    if not field_options:
        del fields["preset"]
    sequence = [
        _require("mode is defined and mode is string and mode in " + repr(available_modes), "Unknown remote mode"),
        _require("lease_minutes is not defined or (lease_minutes is number and lease_minutes is not boolean and 1 <= lease_minutes <= 120)", "Lease must be 1 to 120 minutes"),
        _require("camera_seconds is not defined or (camera_seconds is number and camera_seconds is not boolean and 5 <= camera_seconds <= 120)", "Camera duration must be 5 to 120 seconds"),
        _require("preset is not defined or (preset is string and (preset == '' or (mode == 'tv' and preset in " + repr(list(c["tv_presets"])) + ")))", "Use a configured TV preset name only"),
        _require("mode != 'tv' or (preset is defined and preset in " + repr(list(c["tv_presets"])) + ")", "Select a configured TV preset"),
        _require("audio_media_id is not defined or (audio_media_id is string and (audio_media_id == '' or mode == 'music'))", "Audio media ID is allowed only for music"),
        _require("mode != 'music' or (audio_media_id is defined and audio_media_id is string and 0 < audio_media_id | length <= 2048 and audio_media_id is match('^(media-source://|https?://)[^\\s\\x00-\\x1f]+$'))", "Music requires an audio media-source ID or HTTP(S) audio URL"),
        _require("_expected_token is not defined or (_expected_token is string and _expected_token | length <= 80)", "Invalid session token"),
        _if("{{ _expected_token is defined and _expected_token != " + state(token) + " }}", [{"stop": "Expired cleanup request ignored"}]),
        _require(state(active) + " in " + repr(list(ACTIVE_MODES)) + " and " + state(pending) + " in ['on', 'off']", "Remote session helpers are unavailable"),
        {"variables": {"old_mode": "{{ " + state(active) + " }}"}},
    ]
    # Installation checks precede cleanup, mute or helper changes.
    app_for_mode = {"tv": "vlc", "ottplay": "browser", "ottplayer": "ottplayer", "jitsi": "jitsi"}
    if "ottplay_native" in c["app_ids"]:
        app_for_mode["ottplay_native"] = "ottplay_native"
    sequence.append({"choose": [{"conditions": "{{ mode == " + repr(mode) + " }}", "sequence": [call_adb("probe_" + app)]} for mode, app in app_for_mode.items()]})
    # Up to three retry opportunities survive cleanup errors. Successful cleanup
    # cancels this recovery timer. A fresh manual command resets the retry budget.
    sequence.append(_if("{{ _expected_token is not defined }}", [_service("input_number.set_value", attempts, value=0)]))
    sequence.append(_if("{{ old_mode != 'idle' or " + is_on(pending) + " }}", [
        _if("{{ (" + state(attempts) + " | int(0)) < 3 }}", [
            _service("input_number.increment", attempts),
            _service("timer.start", timer, duration=60),
        ], [_service("timer.cancel", timer)]),
    ], [_service("timer.cancel", timer)]))
    # A failed stop preserves persisted ownership and keeps a call microphone muted.
    cleanup = {"tv": "vlc", "ottplay": "browser", "ottplayer": "ottplayer"}
    if "ottplay_native" in c["app_ids"]:
        cleanup["ottplay_native"] = "ottplay_native"
    sequence.append({"choose": [{"conditions": "{{ old_mode == " + repr(mode) + " }}", "sequence": [call_adb("stop_" + app)]} for mode, app in cleanup.items()] + [
        {"conditions": "{{ old_mode == 'music' }}", "sequence": [_service("media_player.media_stop", c["vaca_media_entity"])]}]})
    sequence.append(_if("{{ old_mode == 'jitsi' or " + is_on(pending) + " }}", [
        call_adb("stop_jitsi"),
        _if("{{ " + is_on(pending) + " }}", [
            _require(state(prior) + " in ['on', 'off']", "Saved microphone state unavailable"),
            _if("{{ " + is_on(prior) + " }}", [_service("switch.turn_on", c["vaca_mute_entity"])], [_service("switch.turn_off", c["vaca_mute_entity"])]),
            {"wait_template": "{{ " + state(c["vaca_mute_entity"]) + " == " + state(prior) + " }}", "timeout": {"seconds": 5}, "continue_on_timeout": False},
            _service("input_boolean.turn_off", pending),
        ]),
    ]))
    sequence.extend([
        _if("{{ mode in ['home', 'stop'] }}", [
            _service(display_script, command="home"),
            _service("timer.cancel", timer),
            _service("input_select.select_option", active, option="idle"),
            _service("input_number.set_value", attempts, value=0),
            {"stop": "Returned to clock"}]),
        _service("timer.cancel", timer),
        _service("input_select.select_option", active, option="idle"),
        _service("input_number.set_value", attempts, value=0),
        {"variables": {"session_token": MARKER}},
        _service("input_text.set_value", token, value="{{ session_token }}"),
        _service("input_select.select_option", active, option="{{ mode }}"),
        _service("timer.start", timer, duration="{{ (camera_seconds | default(120) | int) if mode in ['camera_front', 'camera_porch'] else ((lease_minutes | default(30)) * 60) | int }}"),
        _if("{{ mode == 'jitsi' }}", [
            _require(state(c["vaca_mute_entity"]) + " in ['on', 'off']", "VACA microphone state unavailable"),
            _if("{{ " + is_on(c["vaca_mute_entity"]) + " }}", [_service("input_boolean.turn_on", prior)], [_service("input_boolean.turn_off", prior)]),
            _service("input_boolean.turn_on", pending),
            _service("switch.turn_on", c["vaca_mute_entity"]),
            {"wait_template": "{{ " + is_on(c["vaca_mute_entity"]) + " }}", "timeout": {"seconds": 5}, "continue_on_timeout": False},
        ]),
        {"choose": [
            {"conditions": "{{ mode in ['camera_front', 'camera_porch'] }}", "sequence": [_service(display_script, command="camera", role="{{ 'front' if mode == 'camera_front' else 'porch' }}", seconds="{{ camera_seconds | default(120) | int }}")]},
            {"conditions": "{{ mode == 'music' }}", "sequence": [_service(display_script, command="home"), _service("media_player.play_media", c["vaca_media_entity"], media_content_id="{{ audio_media_id }}", media_content_type="music")]},
            {"conditions": "{{ mode == 'tv' }}", "sequence": [call_adb("{{ 'tv_' ~ preset }}")]},
        ] + [{"conditions": "{{ mode == " + repr(mode) + " }}", "sequence": [call_adb("start_" + mode)]} for mode in app_for_mode if mode != "tv"]},
    ])
    scripts[prefix + "_command"] = _script(prefix + ": remote endpoint", sequence, fields, "queued")
    scripts[prefix + "_refresh"] = _script(prefix + ": refresh own VACA", [_service("button.press", c["vaca_refresh_entity"])])
    scripts[prefix + "_play_audio"] = _script(prefix + ": choose music or radio", [
        _require("media is defined and media is mapping and media.get('media_content_id') is string", "Select an audio item in the media browser"),
        _require("media.get('media_content_type', 'music') is string and (media.get('media_content_type', 'music') in ['music', 'audio', 'podcast', 'radio'] or media.get('media_content_type', '').startswith('audio/'))", "This player accepts audio only"),
        _service(command_script, mode="music", audio_media_id="{{ media.media_content_id }}", lease_minutes=30),
    ], {"media": {"required": True, "selector": {"media": {"accept": ["audio/*"]}}}})

    needs_cleanup = "{{ " + state(active) + " not in ['idle', 'unknown', 'unavailable'] or " + is_on(pending) + " }}"
    cleanup_call = _service(command_script, mode="home", _expected_token="{{ " + state(token) + " }}")
    automations = [
        {"id": prefix + "_remote_ack", "alias": prefix + ": record display acknowledgement", "mode": "queued", "max": 10,
         "trigger": [{"platform": "event", "event_type": "show5_remote_ack", "event_data": {"target": prefix}}],
         "condition": [{"condition": "template", "value_template": "{{ trigger.event.data.get('command_id') is string and trigger.event.data.command_id is match('^[A-Za-z0-9_-]{1,80}$') and trigger.event.data.get('status') in ['ok', 'error'] }}"}],
         "action": [_service("input_text.set_value", ack, value="{{ trigger.event.data.command_id ~ '|' ~ trigger.event.data.status }}")],
         "trace": {"stored_traces": 0}},
        {"id": prefix + "_remote_expiry", "alias": prefix + ": end owned session on expiry", "mode": "single",
         "trigger": [{"platform": "event", "event_type": "timer.finished", "event_data": {"entity_id": timer}}],
         "condition": [{"condition": "state", "entity_id": timer, "state": "idle"}, {"condition": "template", "value_template": needs_cleanup}],
         "action": [cleanup_call], "trace": {"stored_traces": 0}},
        {"id": prefix + "_remote_restart", "alias": prefix + ": recover owned session after HA restart", "mode": "single",
         "trigger": [{"platform": "homeassistant", "event": "start"}],
         "condition": [{"condition": "template", "value_template": needs_cleanup}],
         "action": [_service("timer.cancel", timer), cleanup_call], "trace": {"stored_traces": 0}},
        {"id": prefix + "_remote_reconnect", "alias": prefix + ": retry interrupted cleanup on reconnect", "mode": "single",
         "trigger": [{"platform": "state", "entity_id": [c["adb_entity"], c["vaca_mute_entity"]], "from": old} for old in ("unavailable", "unknown")],
         "condition": [{"condition": "template", "value_template": needs_cleanup},
                       {"condition": "state", "entity_id": timer, "state": "idle"},
                       {"condition": "template", "value_template": "{{ " + state(c["adb_entity"]) + " not in ['unknown', 'unavailable'] and " + state(c["vaca_mute_entity"]) + " in ['on', 'off'] }}"}],
         "action": [cleanup_call], "trace": {"stored_traces": 0}},
    ]
    return {
        "input_select": {prefix + "_active_mode": {"name": prefix + " active mode", "options": list(ACTIVE_MODES)}},
        "input_boolean": {prefix + "_prior_mute": {"name": prefix + " saved microphone mute"}, prefix + "_restore_mute_pending": {"name": prefix + " microphone restoration pending"}},
        "input_text": {prefix + "_lease_token": {"name": prefix + " session token", "max": 80}, prefix + "_display_ack": {"name": prefix + " display acknowledgement", "max": 86}},
        "input_number": {prefix + "_cleanup_attempts": {"name": prefix + " interrupted cleanup attempts", "min": 0, "max": 3, "step": 1, "mode": "box"}},
        "timer": {prefix + "_lease": {"name": prefix + " remote session", "duration": "00:30:00", "restore": True}},
        "script": scripts,
        "automation": automations,
    }


def write_private(output, value, root=ROOT):
    root = root.resolve()
    private = (root / "private").resolve()
    destination = output.resolve()
    if private != root / "private" or private not in destination.parents:
        raise ValueError("Rendered package must stay inside this repository's private directory")
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        write_private(args.output, render_package(config))
    except (ValueError, OSError):
        # File/config errors can otherwise expose embedded operator credentials.
        parser.error("Invalid local bindings or unavailable private output; no HA changes were made")
    print("Rendered a private HA package. No HA or Android changes were made.")


if __name__ == "__main__":
    main()
