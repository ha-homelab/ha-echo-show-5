"""Render optional room features; never contact Home Assistant or Android."""
from __future__ import annotations
import copy
import re
from urllib.parse import urlsplit

SLUG = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")
ENTITY = re.compile(r"([a-z_]+)\.[a-z0-9_]+\Z")
MODES = {"home", "stop", "camera_front", "camera_porch", "music", "tv", "ottplay", "ottplay_native", "ottplayer", "jitsi", "library", "bluetooth", "sendspin"}


def _entity(value, domains):
    match = ENTITY.fullmatch(value) if isinstance(value, str) else None
    if not match or match[1] not in domains:
        raise ValueError("Invalid room entity binding")


def _text(value, limit=120):
    if (not isinstance(value, str) or not 1 <= len(value) <= limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(x in value for x in ("{{", "{%", "{#"))):
        raise ValueError("Invalid room text")
    return value


def _number(value, low, high):
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError("Invalid room numeric setting")


def validate_room(value):
    if not isinstance(value, dict) or set(value) - {"actions", "status", "presence", "announcement", "presence_clear_seconds"}:
        raise ValueError("Unknown room setting")
    room = copy.deepcopy(value)
    actions = room.get("actions", {})
    if not isinstance(actions, dict) or len(actions) > 24:
        raise ValueError("Expected at most 24 room actions")
    for name, action in actions.items():
        if (not isinstance(name, str) or not SLUG.fullmatch(name)
                or name in {"action", "announce", "message", "set_timer", "cancel_timer", "dismiss", "timer_finish", "timer_command", "message_command"}
                or not isinstance(action, dict)):
            raise ValueError("Invalid room action")
        kind = action.get("type")
        if not isinstance(kind, str):
            raise ValueError("Invalid room action type")
        allowed = {"endpoint": {"type", "mode", "preset", "audio_media_id", "camera_seconds", "lease_minutes"},
                   "light": {"type", "entity_id", "operation"}, "climate": {"type", "entity_id", "temperature"},
                   "scene": {"type", "entity_id"}, "script": {"type", "entity_id"},
                   "timer": {"type", "seconds", "label"}}.get(kind)
        if allowed is None or set(action) - allowed:
            raise ValueError("Unknown room action type or field")
        if kind == "endpoint":
            mode = action.get("mode")
            if not isinstance(mode, str) or mode not in MODES:
                raise ValueError("Invalid endpoint action")
            if "preset" in action and (mode != "tv" or not isinstance(action["preset"], str) or not SLUG.fullmatch(action["preset"])):
                raise ValueError("Invalid TV preset")
            if mode == "tv" and "preset" not in action:
                raise ValueError("TV action requires a preset")
            if "audio_media_id" in action:
                media = _text(action["audio_media_id"], 2048)
                try:
                    parsed = urlsplit(media)
                    parsed.port
                except ValueError:
                    raise ValueError("Invalid fixed audio source") from None
                if (mode != "music" or parsed.scheme not in {"http", "https", "media-source"}
                        or not parsed.netloc or parsed.username or parsed.password or any(c.isspace() for c in media)):
                    raise ValueError("Invalid fixed audio source")
            if mode == "music" and "audio_media_id" not in action:
                raise ValueError("Music action requires a source")
            for key, low, high in (("camera_seconds", 5, 120), ("lease_minutes", 1, 120)):
                if key in action:
                    _number(action[key], low, high)
        elif kind in {"light", "climate", "scene", "script"}:
            _entity(action.get("entity_id"), {kind})
            if kind == "light" and action.get("operation") not in {"toggle", "turn_on", "turn_off"}:
                raise ValueError("Invalid light operation")
            if kind == "climate":
                _number(action.get("temperature"), 5, 35)
        else:
            _number(action.get("seconds"), 1, 86400)
            _text(action.get("label"), 80)
    status = room.get("status", {})
    if not isinstance(status, dict) or len(status) > 8:
        raise ValueError("Expected at most eight status entities")
    for key, entity in status.items():
        if not isinstance(key, str) or not SLUG.fullmatch(key):
            raise ValueError("Invalid status key")
        _entity(entity, {"sensor", "binary_sensor", "climate", "weather", "light"})
    presence = room.get("presence", [])
    if not isinstance(presence, list) or len(presence) > 12:
        raise ValueError("Invalid presence inputs")
    for entity in presence:
        _entity(entity, {"binary_sensor"})
    if len(set(presence)) != len(presence):
        raise ValueError("Duplicate presence input")
    if "presence_clear_seconds" in room:
        _number(room["presence_clear_seconds"], 30, 3600)
    announce = room.get("announcement")
    if announce is not None:
        if not isinstance(announce, dict) or set(announce) - {"tts_entity", "language", "quiet_start", "quiet_end", "max_seconds"}:
            raise ValueError("Invalid announcement settings")
        _entity(announce.get("tts_entity"), {"tts"})
        if "language" in announce and (not isinstance(announce["language"], str) or not re.fullmatch(r"[a-z]{2,3}(?:[-_][A-Za-z]{2,8})?", announce["language"])):
            raise ValueError("Invalid TTS language")
        for key, default in (("quiet_start", 22), ("quiet_end", 8)):
            hour = announce.get(key, default)
            if type(hour) is not int or not 0 <= hour <= 23:
                raise ValueError("Invalid quiet hour")
        if "max_seconds" in announce:
            _number(announce["max_seconds"], 5, 60)
    return room


def extend_package(c, package):
    from render_remote_endpoint import _service as service, _script as script, _require as require, _if as when
    prefix, room = c["prefix"], c["room"]
    eid = lambda domain, name: domain + "." + prefix + "_room_" + name
    state = lambda entity: "states(" + repr(entity) + ")"
    on = lambda entity: "is_state(" + repr(entity) + ", 'on')"
    scripts, automations = package["script"], package["automation"]
    command, active, lease = "script." + prefix + "_command", "input_select." + prefix + "_active_mode", "timer." + prefix + "_lease"
    timer, deadline, armed = eid("timer", "timer"), eid("input_datetime", "deadline"), eid("input_boolean", "timer_armed")
    label, reminder = eid("input_text", "timer_label"), eid("input_text", "message_text")
    expiry, visible = eid("input_datetime", "message_deadline"), eid("input_boolean", "message_visible")
    def make(name, sequence, fields=None):
        scripts[prefix + "_room_" + name] = script(prefix + ": " + name.replace("_", " "), sequence, fields, "queued")
    package.setdefault("input_datetime", {}).update({
        prefix + "_room_deadline": {"name": prefix + " room timer deadline", "has_date": True, "has_time": True},
        prefix + "_room_message_deadline": {"name": prefix + " room message expiry", "has_date": True, "has_time": True}})
    package["input_boolean"].update({prefix + "_room_timer_armed": {"name": prefix + " room timer armed"}, prefix + "_room_message_visible": {"name": prefix + " room message visible"}})
    package["input_text"].update({prefix + "_room_timer_label": {"name": prefix + " room timer label", "max": 80}, prefix + "_room_message_text": {"name": prefix + " room message", "max": 240}})
    package["timer"][prefix + "_room_timer"] = {"name": prefix + " room timer", "duration": "00:05:00", "restore": True}
    text_field = {"required": True, "selector": {"text": {"multiline": False}}}
    timestamp_field = {"required": True, "selector": {"number": {"min": 0, "max": 4102444800, "mode": "box"}}}
    make("message", [
        require("message is defined and message is string and 0 < message | length <= 240", "Message must contain 1 to 240 characters"),
        require("expires_at is defined and expires_at is number and expires_at is not boolean and as_timestamp(now()) < expires_at <= as_timestamp(now()) + 3600", "Message expiry must be within one hour"),
        service("input_boolean.turn_off", visible), service("input_text.set_value", reminder, value="{{ message }}"),
        service("input_datetime.set_datetime", expiry, timestamp="{{ expires_at }}"), service("input_boolean.turn_on", visible)],
        {"message": text_field, "expires_at": timestamp_field})
    make("dismiss", [service("input_boolean.turn_off", visible)])
    make("set_timer", [
        require("seconds is defined and seconds is number and seconds is not boolean and 1 <= seconds <= 86400", "Timer must be 1 to 86400 seconds"),
        require("label is defined and label is string and 0 < label | length <= 80", "Timer requires a short label"),
        service("input_boolean.turn_off", armed), service("input_text.set_value", label, value="{{ label }}"),
        service("input_datetime.set_datetime", deadline, timestamp="{{ as_timestamp(now()) + (seconds | int) }}"),
        service("timer.start", timer, duration="{{ seconds | int }}"), service("input_boolean.turn_on", armed)],
        {"seconds": {"required": True, "selector": {"number": {"min": 1, "max": 86400, "mode": "box"}}}, "label": text_field})
    make("cancel_timer", [service("input_boolean.turn_off", armed), service("timer.cancel", timer)])
    due = on(armed) + " and (state_attr(" + repr(deadline) + ", 'timestamp') | float(0)) > 0 and (state_attr(" + repr(deadline) + ", 'timestamp') | float(0)) <= as_timestamp(now())"
    make("timer_finish", [when("{{ " + due + " }}", [
        service(eid("script", "message"), message="{{ 'Timer complete: ' ~ " + state(label) + " }}", expires_at="{{ as_timestamp(now()) + 3600 }}"),
        service("input_boolean.turn_off", armed), service("timer.cancel", timer)])])
    # Serialize complete transactions: a delayed expiry cannot cancel a new
    # timer, and Dismiss cannot be overwritten halfway through a message write.
    message_branches = []
    for operation in ("message", "dismiss"):
        existing = scripts[prefix + "_room_" + operation]
        message_branches.append({"conditions": "{{ operation == " + repr(operation) + " }}", "sequence": existing["sequence"]})
        data = {"operation": operation}
        if operation == "message":
            data.update(message="{{ message }}", expires_at="{{ expires_at }}")
        existing["sequence"] = [service(eid("script", "message_command"), **data)]
    make("message_command", [require("operation is defined and operation in ['message', 'dismiss']", "Unknown message operation"), {"choose": message_branches}])
    timer_branches = []
    for operation in ("set_timer", "cancel_timer", "timer_finish"):
        existing = scripts[prefix + "_room_" + operation]
        timer_branches.append({"conditions": "{{ operation == " + repr(operation) + " }}", "sequence": existing["sequence"]})
        data = {"operation": operation}
        if operation == "set_timer":
            data.update(seconds="{{ seconds }}", label="{{ label }}")
        existing["sequence"] = [service(eid("script", "timer_command"), **data)]
    make("timer_command", [require("operation is defined and operation in ['set_timer', 'cancel_timer', 'timer_finish']", "Unknown timer operation"), {"choose": timer_branches}])
    automations.append({"id": prefix + "_room_timer_reconcile", "alias": prefix + ": reconcile timer expiry and outages", "mode": "single", "trace": {"stored_traces": 0},
                        "trigger": [{"platform": "homeassistant", "event": "start"}, {"platform": "event", "event_type": "timer.finished", "event_data": {"entity_id": timer}}, {"platform": "time_pattern", "minutes": "/1"}],
                        "action": [service(eid("script", "timer_finish"))]})
    defaults = {"home": {"type": "endpoint", "mode": "home"}, "stop": {"type": "endpoint", "mode": "stop"},
                "camera_front": {"type": "endpoint", "mode": "camera_front", "camera_seconds": 60}, "camera_porch": {"type": "endpoint", "mode": "camera_porch", "camera_seconds": 60},
                "jitsi": {"type": "endpoint", "mode": "jitsi", "lease_minutes": 30}, "ottplay": {"type": "endpoint", "mode": "ottplay", "lease_minutes": 120},
                "library": {"type": "endpoint", "mode": "library", "lease_minutes": 120},
                "bluetooth": {"type": "endpoint", "mode": "bluetooth", "lease_minutes": 10},
                "timer_5m": {"type": "timer", "seconds": 300, "label": "Five-minute timer"}}
    if "ottplay_native" in c["app_ids"]:
        defaults["ottplay_native"] = {"type": "endpoint", "mode": "ottplay_native", "lease_minutes": 120}
    if "sendspin" in c["app_ids"]:
        defaults["sendspin"] = {"type": "endpoint", "mode": "sendspin", "lease_minutes": 120}
    defaults.update(room.get("actions", {}))
    choices = []
    for name, item in defaults.items():
        action = dict(item)
        kind = action.pop("type")
        if kind == "endpoint":
            if action["mode"] == "tv" and action["preset"] not in c["tv_presets"]:
                raise ValueError("Room action names an unknown TV preset")
            if action["mode"] == "ottplay_native" and "ottplay_native" not in c["app_ids"]:
                raise ValueError("Room action names an unbound app")
            if action["mode"] == "sendspin" and "sendspin" not in c["app_ids"]:
                raise ValueError("Room action names an unbound app")
            steps = [service(command, **action)]
        elif kind == "timer":
            steps = [service(eid("script", "set_timer"), **action)]
        elif kind == "light":
            steps = [service("light." + action["operation"], action["entity_id"])]
        elif kind == "climate":
            steps = [service("climate.set_temperature", action["entity_id"], temperature=action["temperature"])]
        elif kind == "scene":
            steps = [service("scene.turn_on", action["entity_id"])]
        else:
            steps = [service(action["entity_id"])]
        make(name, steps)
        choices.append({"conditions": "{{ action == " + repr(name) + " }}", "sequence": [service(eid("script", name))]})
    make("action", [require("action is defined and action is string and action in " + repr(sorted(defaults)), "Unknown fixed room action"), {"choose": choices}],
         {"action": {"required": True, "selector": {"select": {"options": sorted(defaults)}}}})
    if room.get("announcement"):
        _add_announcement(c, package, make, service, require, when, state, active)
    _add_sensors(c, package, state, on, active, lease, reminder, expiry, visible)


def _add_announcement(c, package, make, service, require, when, state, active):
    """Use the existing queue and persistent lease, not a parallel TTS worker."""
    prefix, announce = c["prefix"], c["room"]["announcement"]
    call = package["script"][prefix + "_command"]
    fields = {"message": {"required": True, "selector": {"text": {"multiline": False}}},
              "expires_at": {"required": True, "selector": {"number": {"min": 0, "max": 4102444800, "mode": "box"}}}}
    call["fields"].update({key: {k: v for k, v in value.items() if k != "required"} for key, value in fields.items()})
    start, end = announce.get("quiet_start", 22), announce.get("quiet_end", 8)
    quiet = ("false" if start == end else (f"{start} <= now().hour < {end}" if start < end else f"(now().hour >= {start} or now().hour < {end})"))
    guard = when("{{ mode == 'announce' }}", [
        require("message is defined and message is string and 0 < message | length <= 240", "Announcement must contain 1 to 240 characters"),
        require("expires_at is defined and expires_at is number and expires_at is not boolean and as_timestamp(now()) < expires_at <= as_timestamp(now()) + 120", "Announcement is expired or too far in the future"),
        require(state(active) + " == 'idle'", "Announcement rejected while the room is busy"),
        require("not (" + quiet + ")", "Announcement rejected during quiet hours"),
        require(state(c["vaca_media_entity"]) + " not in ['playing', 'buffering', 'unknown', 'unavailable']", "Media player is busy or unavailable"),
    ])
    effect_index = next(i for i, row in enumerate(call["sequence"]) if "old_mode" in row.get("variables", {}))
    call["sequence"].insert(effect_index, guard)
    for row in call["sequence"]:
        for choice in row.get("choose", []):
            if choice.get("conditions") == "{{ old_mode == 'music' }}":
                choice["conditions"] = "{{ old_mode in ['music', 'announce'] }}"
        if row.get("service") == "timer.start":
            expression = row["data"]["duration"][3:-3]
            row["data"]["duration"] = "{{ " + str(int(announce.get("max_seconds", 30))) + " if mode == 'announce' else (" + expression + ") }}"
    data = {"media_player_entity_id": c["vaca_media_entity"], "message": "{{ message }}", "cache": False}
    if "language" in announce:
        data["language"] = announce["language"]
    call["sequence"][-1]["choose"].append({"conditions": "{{ mode == 'announce' }}", "sequence": [service("tts.speak", announce["tts_entity"], **data)]})
    make("announce", [service("script." + prefix + "_command", mode="announce", message="{{ message }}", expires_at="{{ expires_at }}")], fields)


def _add_sensors(c, package, state, on, active, lease, reminder, expiry, visible):
    prefix, room = c["prefix"], c["room"]
    sip = c.get("sip_call_entity")
    sip_busy = "false" if not sip else (state(sip) + " not in ['idle', 'error'] or state_attr(" + repr(sip) + ", 'lease_held') != false or state_attr(" + repr(sip) + ", 'call_id') != none")
    healthy = state(c["adb_entity"]) + " not in ['unknown', 'unavailable'] and " + state(c["vaca_mute_entity"]) + " in ['on', 'off']"
    if sip:
        healthy += " and " + state(sip) + " not in ['unknown', 'unavailable']"
    if "sip_registration_entity" in c:
        healthy += " and " + state(c["sip_registration_entity"]) + " == 'registered'"
    has_message = on(visible) + " and (state_attr(" + repr(expiry) + ", 'timestamp') | float(0)) > as_timestamp(now())"
    sensors = [
        {"name": prefix + " room session", "unique_id": prefix + "_room_session", "state": "{{ 'phone' if (" + sip_busy + ") else " + state(active) + " }}",
         "attributes": {"owner": "{{ 'phone' if (" + sip_busy + ") else " + state(active) + " }}", "busy": "{{ (" + sip_busy + ") or " + state(active) + " != 'idle' }}", "lease_ends_at": "{{ state_attr(" + repr(lease) + ", 'finishes_at') }}"}},
        {"name": prefix + " room health", "unique_id": prefix + "_room_health", "state": "{{ 'ready' if (" + healthy + ") else 'unavailable' }}",
         "attributes": {"scope": "HA entity availability; not an audio/video acceptance test", "adb_state": "{{ " + state(c["adb_entity"]) + " }}", "microphone_muted": "{{ " + state(c["vaca_mute_entity"]) + " }}"}},
        {"name": prefix + " room reminder", "unique_id": prefix + "_room_reminder", "state": "{{ 'active' if (" + has_message + ") else 'none' }}",
         "attributes": {"message": "{{ " + state(reminder) + " if (" + has_message + ") else '' }}", "expires_at": "{{ state_attr(" + repr(expiry) + ", 'timestamp') if (" + has_message + ") else none }}"}},
    ]
    if room.get("status"):
        attrs = {}
        for key, entity in room["status"].items():
            attrs[key] = "{{ {'state': states(" + repr(entity) + "), 'unit': state_attr(" + repr(entity) + ", 'unit_of_measurement'), 'updated_at': states[" + repr(entity) + "].last_updated.isoformat() if states[" + repr(entity) + "] is defined and states[" + repr(entity) + "] is not none else none} }}"
        sensors.append({"name": prefix + " room status", "unique_id": prefix + "_room_status", "state": "configured", "attributes": attrs})
    package.setdefault("template", []).append({"sensor": sensors})
    if room.get("presence"):
        entities = repr(room["presence"])
        package["template"].append({"binary_sensor": [{"name": prefix + " room presence", "unique_id": prefix + "_room_presence", "device_class": "occupancy",
            "availability": "{{ expand(" + entities + ") | selectattr('state', 'eq', 'on') | list | count > 0 or expand(" + entities + ") | selectattr('state', 'in', ['on', 'off']) | list | count == " + str(len(room["presence"])) + " }}",
            "state": "{{ expand(" + entities + ") | selectattr('state', 'eq', 'on') | list | count > 0 }}",
            "delay_off": {"seconds": int(room.get("presence_clear_seconds", 180))}}]})
