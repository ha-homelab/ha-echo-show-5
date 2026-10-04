#!/usr/bin/env python3
"""Render native Assist commands with private, explicit satellite routing.

No request text is used as a service, entity, URL or media identifier. Output is
an HA package in ignored private storage; this program makes no network calls.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from render_remote_endpoint import write_private

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "play": (["[пожалуйста] (включи|играй|поставь) музыку [из (плекса|plex)]"],
             ["[please] play [some] music [from plex]"]),
    "pause": (["[пожалуйста] (останови|выключи|поставь на паузу) музыку"],
              ["[please] (stop|pause) [the] music"]),
    "resume": (["[пожалуйста] (продолжи|возобнови) (музыку|воспроизведение музыки)"],
               ["[please] resume [the] music"]),
    "next": (["[пожалуйста] [включи] (следующий трек|следующую песню)"],
             ["[please] [play] [the] next (track|song)"]),
    "volume": (["[пожалуйста] [(сделай|установи|поставь)] громкость {level} [процентов]"],
               ["[please] [set [the]] volume [to] {level} [percent]"]),
    "home": (["[пожалуйста] (покажи|верни|включи) часы"],
             ["[please] (show [the]|return to [the]) clock"]),
    "ottplay_native": (["[пожалуйста] (открой|запусти|включи) (отт|оттплей|ottplay|ott play)"],
                       ["[please] (open|start) (ottplay|ott play)"]),
    "camera_front": (["[пожалуйста] (покажи|включи) (камеру фронт|фронт камеру|переднюю камеру)"],
                     ["[please] show [the] front camera"]),
    "camera_porch": (["[пожалуйста] (покажи|включи) (камеру порч|порч камеру|камеру крыльца)"],
                     ["[please] show [the] porch camera"]),
}
MUSIC_COMMANDS = ("play", "pause", "resume", "next", "volume")


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def validate_config(config):
    if not isinstance(config, dict) or set(config) != {"prefix", "default_tracks", "plex_provider", "endpoints"}:
        raise ValueError("Expected documented voice routing fields only")
    c = copy.deepcopy(config)
    if not _matches(r"[a-z][a-z0-9_]{0,30}", c["prefix"]):
        raise ValueError("Invalid prefix")
    if not _matches(r"plex--[a-zA-Z0-9_-]+", c["plex_provider"]):
        raise ValueError("Expected configured Plex provider")
    tracks = c["default_tracks"]
    if (not isinstance(tracks, list) or not 1 <= len(tracks) <= 25
            or not all(isinstance(uri, str) for uri in tracks)
            or len(set(tracks)) != len(tracks)):
        raise ValueError("One to twenty-five distinct approved tracks required")
    for uri in tracks:
        if not _matches("(?:" + re.escape(c["plex_provider"]) + r"://track/[A-Za-z0-9/_-]+|library://track/[0-9]+)", uri):
            raise ValueError("Expected an approved Plex or cached library track URI")
    if not isinstance(c["endpoints"], dict) or not 1 <= len(c["endpoints"]) <= 12:
        raise ValueError("One to twelve endpoints required")
    unique = {key: set() for key in ("devices", "satellites", "aliases_ru", "aliases_en", "music_entity", "remote_script")}
    for key, e in c["endpoints"].items():
        if not _matches(r"[a-z][a-z0-9_]{0,20}", key) or key == "origin":
            raise ValueError("Invalid endpoint key")
        required = {"devices", "satellites", "aliases_ru", "aliases_en", "music_entity"}
        if not isinstance(e, dict) or not required <= set(e) or set(e) - required - {"remote_script"}:
            raise ValueError("Invalid endpoint fields")
        for field, pattern in (("music_entity", r"media_player\.[a-z0-9_]+"), ("remote_script", r"script\.[a-z0-9_]+")):
            if field not in e:
                continue
            if not _matches(pattern, e[field]) or e[field] in unique[field]:
                raise ValueError("Invalid or shared endpoint service binding")
            unique[field].add(e[field])
        for field, pattern in (("devices", r"[a-f0-9]{32}"), ("satellites", r"assist_satellite\.[a-z0-9_]+"),
                               ("aliases_ru", r"[а-яёa-z0-9]+(?: [а-яёa-z0-9]+)*"),
                               ("aliases_en", r"[a-z0-9]+(?: [a-z0-9]+)*")):
            values = e[field]
            if not isinstance(values, list) or not 1 <= len(values) <= 8:
                raise ValueError("Nonempty bounded identity/alias lists required")
            for value in values:
                if not _matches(pattern, value) or len(value) > 100 or value in unique[field]:
                    raise ValueError("Invalid or ambiguous identity/alias")
                unique[field].add(value)
    return c


def _service(name, entity=None, **data):
    value = {"action": name}
    if entity:
        value["target"] = {"entity_id": entity}
    if data:
        value["data"] = data
    return value


def _if(condition, then, otherwise=None):
    result = {"if": condition, "then": then}
    if otherwise is not None:
        result["else"] = otherwise
    return result


def _result(message, success=False):
    return [{"variables": {"result": {"success": success, "message": message}}},
            {"stop": "Return native command result", "response_variable": "result"}]


def endpoint_script(c, key, e):
    player = e["music_entity"]
    state = "states(" + repr(player) + ")"
    remote = e.get("remote_script")
    return_home = [_service(remote, mode="home")] if remote else []
    seq = [
        _if("{{ command | default('') not in " + repr(list(COMMANDS)) + " }}",
            _result("Эта команда не поддерживается.")),
        _if("{{ command in " + repr(list(MUSIC_COMMANDS)) + " and not has_value(" + repr(player) + ") }}",
            _result("Музыкальный проигрыватель этого устройства сейчас недоступен.")),
        _if("{{ command == 'volume' and not ((level | default('') | string) is match('^(100|[0-9]{1,2})$')) }}",
            _result("Укажите громкость числом от 0 до 100.")),
    ]
    # A script field is not trusted merely because it usually comes from our
    # automation. Check the command and numeric input before any service call.
    play = list(return_home)
    get_queue = _service("music_assistant.get_queue", player)
    get_queue["response_variable"] = "queue_response"
    play += [get_queue, {"variables": {"plex_queue":
        "{% set queue = queue_response.get(" + repr(player) + ", {}) or {} %}"
        "{% set item = queue.get('current_item') or {} %}"
        "{{ queue.get('items', 0) | int(0) > 0 and "
        "((item.get('stream_details') or {}).get('provider') == " + repr(c["plex_provider"]) +
        " or ((item.get('media_item') or {}).get('uri') or '').startswith(" + repr(c["plex_provider"] + "://") + ")) }}"}},
        _if("{{ plex_queue }}", [_if("{{ " + state + " != 'playing' }}", [_service("media_player.media_play", player)])],
            [_service("music_assistant.play_media", player, media_id=c["default_tracks"], media_type="track", enqueue="replace")])]
    branches = [{"conditions": "{{ command == 'play' }}", "sequence": play + _result("Включаю музыку из Плекса.", True)}]
    for command, service, message in (("pause", "media_pause", "Музыка на паузе."),
                                       ("resume", "media_play", "Продолжаю музыку."),
                                       ("next", "media_next_track", "Переключаю на следующий трек.")):
        steps = list(return_home) if command == "resume" else []
        branches.append({"conditions": "{{ command == " + repr(command) + " }}", "sequence": steps + [_service("media_player." + service, player)] + _result(message, True)})
    branches.append({"conditions": "{{ command == 'volume' }}", "sequence": [
        _service("media_player.volume_set", player, volume_level="{{ (level | int) / 100 }}")]
        + _result("Громкость установлена.", True)})
    for mode, message in (("home", "Показываю часы."), ("ottplay_native", "Открываю OTTPlay."),
                          ("camera_front", "Показываю переднюю камеру."), ("camera_porch", "Показываю камеру крыльца.")):
        steps = _result("У этого устройства нет настроенного экрана.")
        if remote:
            steps = [_if("{{ " + state + " in ['playing', 'paused', 'buffering'] }}", [_service("media_player.media_stop", player)]),
                     _service(remote, mode=mode)] + _result(message, True)
        branches.append({"conditions": "{{ command == " + repr(mode) + " }}", "sequence": steps})
    seq.append({"choose": branches})
    return {"alias": c["prefix"] + ": native voice " + key, "mode": "queued", "max": 5,
            "trace": {"stored_traces": 0},
            "fields": {"command": {"required": True, "selector": {"select": {"options": list(COMMANDS)}}},
                       "level": {"selector": {"text": {"multiline": False}}}}, "sequence": seq}


def render_package(config):
    c = validate_config(config)
    scripts = {c["prefix"] + "_" + key: endpoint_script(c, key, e) for key, e in c["endpoints"].items()}
    devices = {value: key for key, e in c["endpoints"].items() for value in e["devices"]}
    satellites = {value: key for key, e in c["endpoints"].items() for value in e["satellites"]}
    services = {key: "script." + c["prefix"] + "_" + key for key in c["endpoints"]}
    triggers = []
    for command, (ru, en) in COMMANDS.items():
        # Register named targets first: an unbounded sentence slot such as
        # {level} could otherwise consume "on the second show" as its value.
        for key, e in c["endpoints"].items():
            explicit = [s + " на " + alias for s in ru for alias in e["aliases_ru"]]
            explicit += [s + " on [the] " + alias for s in en for alias in e["aliases_en"]]
            triggers.append({"platform": "conversation", "id": command + ":" + key, "command": explicit})
        triggers.append({"platform": "conversation", "id": command + ":origin", "command": ru + en})
    action = [
        {"variables": {"device_routes": devices, "satellite_routes": satellites, "endpoint_services": services,
                       "command": "{{ trigger.id.split(':')[0] }}", "requested": "{{ trigger.id.split(':')[1] }}"}},
        {"variables": {"endpoint": "{{ requested if requested != 'origin' else satellite_routes.get(trigger.satellite_id | default('', true), device_routes.get(trigger.device_id | default('', true), '')) }}"}},
        _if("{{ endpoint not in endpoint_services }}", [
            {"set_conversation_response": "Не удалось определить устройство. Укажите, на каком устройстве выполнить команду."},
            {"stop": "Unknown origin; no action taken"}]),
        {"action": "{{ endpoint_services[endpoint] }}", "data": {"command": "{{ command }}", "level": "{{ trigger.slots.get('level', '') }}"}, "response_variable": "command_result"},
        {"set_conversation_response": "{{ command_result.get('message', 'Не удалось выполнить команду.') }}"},
    ]
    return {"script": scripts, "automation": [{"id": c["prefix"] + "_sentences", "alias": c["prefix"] + ": route native Assist commands",
              "mode": "parallel", "max": 12, "trace": {"stored_traces": 0}, "trigger": triggers, "action": action}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        write_private(args.output, render_package(json.loads(args.config.read_text())), root=ROOT)
    except (ValueError, OSError):
        parser.error("Invalid private bindings or unavailable output; no HA changes were made")
    print("Rendered a private native voice package. No HA changes were made.")


if __name__ == "__main__":
    main()
