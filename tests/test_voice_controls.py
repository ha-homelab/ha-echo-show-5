"""Routing and native HA execution; runtime cases use only fake media services."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_voice_controls as voice

try:
    from homeassistant import loader
    from homeassistant.bootstrap import async_load_base_functionality
    from homeassistant.config_entries import ConfigEntries
    from homeassistant.core import HomeAssistant, SupportsResponse
    from homeassistant.helpers.script import Script
    from homeassistant.helpers import config_validation as cv
    from homeassistant.setup import async_setup_component
    from homeassistant.components.conversation.trigger import TRIGGER_SCHEMA
    from hassil import Intents, recognize
except ImportError:
    HA_AVAILABLE = False
else:
    HA_AVAILABLE = True


def fixture():
    return {"prefix": "voice_test", "plex_provider": "plex--fixture",
            "default_tracks": ["plex--fixture://track//library/metadata/123", "library://track/456"],
            "endpoints": {
                "show": {"devices": ["1" * 32], "satellites": ["assist_satellite.show_fixture"],
                         "aliases_ru": ["втором шоу"], "aliases_en": ["second show"],
                         "music_entity": "media_player.show_music", "remote_script": "script.show_remote"},
                "dot": {"devices": ["2" * 32], "satellites": ["assist_satellite.dot_fixture"],
                        "aliases_ru": ["первом эхо"], "aliases_en": ["first echo"],
                        "music_entity": "media_player.dot_music"}}}


class VoiceValidationTest(unittest.TestCase):
    def test_input_immutable_and_json_roundtrip(self):
        c = fixture()
        expected = copy.deepcopy(c)
        package = voice.render_package(c)
        self.assertEqual(json.loads(json.dumps(package)), package)
        self.assertEqual(c, expected)

    def test_injection_and_ambiguous_routes_rejected(self):
        for field, value in (("devices", ["{{ states }}"]), ("satellites", ["script.other"]),
                             ("aliases_ru", ["шоу|везде"]), ("aliases_en", ["{target}"]),
                             ("music_entity", "media_player.x {{ evil }}"),
                             ("remote_script", "shell_command.execute")):
            c = fixture(); c["endpoints"]["show"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                voice.render_package(c)
        for field in ("devices", "satellites", "aliases_ru", "aliases_en", "music_entity"):
            c = fixture(); c["endpoints"]["dot"][field] = c["endpoints"]["show"][field]
            with self.subTest(duplicate=field), self.assertRaises(ValueError):
                voice.render_package(c)

    def test_transcript_cannot_select_url_or_provider(self):
        for uri in ("https://example.invalid/music", "plex--other://playlist/1", "plex--fixture://playlist/{{ secret }}"):
            c = fixture(); c["default_tracks"] = [uri]
            with self.assertRaises(ValueError):
                voice.render_package(c)
        for tracks in ([], [None], [{}], ["library://track/1"] * 2,
                       ["library://track/" + str(i) for i in range(26)]):
            c = fixture(); c["default_tracks"] = tracks
            with self.assertRaises(ValueError):
                voice.render_package(c)


@unittest.skipUnless(HA_AVAILABLE, "Requires deployed HA runtime for isolated execution")
class VoiceRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="native-voice-test-")
        self.hass = HomeAssistant(self.temp.name)
        loader.async_setup(self.hass)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        self.hass.config.skip_pip = True
        self.assertTrue(await async_load_base_functionality(self.hass))
        self.calls = []
        self.queue = {"items": 0, "current_item": None}
        for p in ("media_player.show_music", "media_player.dot_music"):
            self.hass.states.async_set(p, "idle")
        self.hass.services.async_register("music_assistant", "get_queue", self.get_queue, supports_response=SupportsResponse.ONLY)
        self.hass.services.async_register("music_assistant", "play_media", self.record)
        for s in ("media_play", "media_pause", "media_stop", "media_next_track", "volume_set"):
            self.hass.services.async_register("media_player", s, self.record)
        self.package = voice.render_package(fixture())
        self.assertTrue(await async_setup_component(self.hass, "script", {"script": self.package["script"]}))
        self.hass.services.async_register("script", "show_remote", self.record)
        await self.hass.async_start()

    async def asyncTearDown(self):
        await self.hass.async_stop(force=True)
        self.temp.cleanup()

    async def get_queue(self, call):
        return {call.data["entity_id"][0]: self.queue}

    async def record(self, call):
        self.calls.append((call.domain, call.service, dict(call.data)))

    async def request(self, command, endpoint="origin", device="1" * 32, satellite=None, level=""):
        script = Script(self.hass, cv.SCRIPT_SCHEMA(self.package["automation"][0]["action"]), "Test native routing", "automation")
        return await script.async_run({"trigger": {"id": command + ":" + endpoint, "device_id": device,
                                      "satellite_id": satellite, "slots": {"level": level}}})

    async def test_known_origin_and_explicit_target_are_isolated(self):
        for target, device, expected in (("origin", "1" * 32, "media_player.show_music"),
                                         ("origin", "2" * 32, "media_player.dot_music"),
                                         ("show", None, "media_player.show_music")):
            self.calls.clear()
            response = await self.request("play", target, device)
            self.assertTrue(response.conversation_response)
            media = [c for c in self.calls if c[0] == "music_assistant"]
            self.assertEqual(len(media), 1)
            self.assertEqual(media[0][2]["entity_id"], [expected])
            self.assertEqual(media[0][2]["media_id"], fixture()["default_tracks"])

    async def test_satellite_origin_wins_and_unknown_origin_does_nothing(self):
        await self.request("pause", device="2" * 32, satellite="assist_satellite.show_fixture")
        self.assertEqual(self.calls[-1][2]["entity_id"], ["media_player.show_music"])
        self.calls.clear()
        for device in (None, "3" * 32):
            result = await self.request("play", device=device)
            self.assertIn("Укажите", result.conversation_response)
        self.assertEqual(self.calls, [])

    async def test_volume_rejects_unbounded_or_nonnumeric_text(self):
        for level in ("-1", "101", "0.3", "NaN", "{{ 30 }}", "50; service", "", "fifty"):
            result = await self.request("volume", level=level)
            self.assertIn("0 до 100", result.conversation_response)
        self.assertEqual(self.calls, [])
        for level in ("0", "35", "100"):
            await self.request("volume", level=level)
            self.assertEqual(self.calls[-1][2]["volume_level"], int(level) / 100)

    async def test_reuses_plex_queue_without_replacing_or_restarting_playback(self):
        from enum import StrEnum
        class MediaType(StrEnum):
            TRACK = "track"
        self.queue = {"items": 100, "current_item": {"media_item": {"uri": "library://track/1", "media_type": MediaType.TRACK},
                      "stream_details": {"provider": "plex--fixture"}}}
        await self.request("play")
        self.assertEqual([c[1] for c in self.calls], ["show_remote", "media_play"])
        self.calls.clear()
        self.hass.states.async_set("media_player.show_music", "playing")
        await self.request("play")
        self.assertEqual([c[1] for c in self.calls], ["show_remote"])

    async def test_restored_library_queue_uses_exact_available_plex_mapping(self):
        self.queue = {"items": 16472, "current_item": {"media_item": {
            "uri": "library://track/1", "provider_mappings": [
                {"provider_instance": "plex--fixture", "provider_domain": "plex", "available": True}]},
            "stream_details": None}}
        await self.request("play", device="2" * 32)
        self.assertEqual([c[1] for c in self.calls], ["media_play"])
        self.assertEqual(self.calls[0][2]["entity_id"], ["media_player.dot_music"])

    async def test_mapping_does_not_claim_other_or_unavailable_sources(self):
        cases = [
            ({"provider_instance": "plex--other", "provider_domain": "plex", "available": True}, None),
            ({"provider_instance": "plex--fixture", "provider_domain": "plex", "available": False}, None),
            ({"provider_instance": "plex--fixture", "provider_domain": "plex", "available": True}, {"provider": "other-provider"}),
        ]
        for mapping, stream in cases:
            self.calls.clear()
            self.queue = {"items": 12, "current_item": {"media_item": {
                "uri": "library://track/1", "provider_mappings": [mapping]}, "stream_details": stream}}
            await self.request("play", device="2" * 32)
            self.assertEqual([c[1] for c in self.calls], ["play_media"])
            self.assertEqual(self.calls[0][2]["media_id"], fixture()["default_tracks"])

    async def test_unavailable_music_and_screenless_dot_start_nothing(self):
        self.hass.states.async_set("media_player.show_music", "unavailable")
        self.assertIn("недоступен", (await self.request("play")).conversation_response)
        self.assertIn("нет настроенного экрана", (await self.request("camera_front", device="2" * 32)).conversation_response)
        self.assertEqual(self.calls, [])

    async def test_screen_transition_stops_only_its_own_music_first(self):
        self.hass.states.async_set("media_player.dot_music", "playing")
        # Idle is not proof of a closed MA session: VACA reports it while
        # buffering. Each screen handoff must send Stop through the MA wrapper.
        for state in ("playing", "paused", "buffering", "idle"):
            self.hass.states.async_set("media_player.show_music", state)
            for mode in ("home", "ottplay_native", "camera_front", "camera_porch"):
                with self.subTest(state=state, mode=mode):
                    self.calls.clear()
                    await self.request(mode)
                    self.assertEqual([c[1] for c in self.calls], ["media_stop", "show_remote"])
                    self.assertEqual(self.calls[0][2]["entity_id"], ["media_player.show_music"])
                    self.assertEqual(self.calls[1][2]["mode"], mode)

    async def test_screen_handoff_remains_available_without_music_assistant(self):
        for state in ("unavailable", "unknown", None):
            if state is None:
                self.hass.states.async_remove("media_player.show_music")
            else:
                self.hass.states.async_set("media_player.show_music", state)
            for mode in ("home", "ottplay_native", "camera_front", "camera_porch"):
                with self.subTest(state=state, mode=mode):
                    self.calls.clear()
                    result = await self.request(mode)
                    self.assertTrue(result.conversation_response)
                    self.assertEqual([c[1] for c in self.calls], ["show_remote"])
                    self.assertEqual(self.calls[0][2]["mode"], mode)

    async def test_failed_music_stop_prevents_screen_handoff_success(self):
        async def fail(call):
            from homeassistant.exceptions import HomeAssistantError
            raise HomeAssistantError("Synthetic Stop failure")
        self.hass.services.async_register("media_player", "media_stop", fail)
        with self.assertRaises(Exception):
            await self.request("home")
        self.assertEqual(self.calls, [])

    async def test_transport_and_service_failures_are_not_reported_as_success(self):
        for command, expected in (("pause", "media_pause"), ("resume", "media_play"), ("next", "media_next_track")):
            self.calls.clear(); await self.request(command)
            self.assertEqual(self.calls[-1][1], expected)
        async def fail(call):
            from homeassistant.exceptions import HomeAssistantError
            raise HomeAssistantError("Synthetic player failure")
        self.hass.services.async_register("media_player", "media_pause", fail)
        with self.assertRaises(Exception):
            await self.request("pause")

    async def test_sentence_schema_recognition_and_unrelated_commands(self):
        triggers = self.package["automation"][0]["trigger"]
        for trigger in triggers:
            TRIGGER_SCHEMA(trigger)
        intents = Intents.from_dict({"language": "ru", "lists": {"level": {"wildcard": True}}, "intents": {
            t["id"]: {"data": [{"sentences": t["command"]}]} for t in triggers}})
        for phrase, intent in (("включи музыку", "play:origin"), ("играй музыку на втором шоу", "play:show"),
                               ("останови музыку", "pause:origin"), ("покажи часы", "home:origin"),
                               ("установи громкость 35 процентов", "volume:origin"),
                               ("show front camera on the second show", "camera_front:show")):
            with self.subTest(phrase=phrase):
                result = recognize(phrase, intents)
                self.assertEqual(result.intent.name, intent)
                if intent == "volume:origin":
                    self.assertEqual(result.entities["level"].value.strip(), "35")
        explicit_volume = recognize("установи громкость 35 процентов на втором шоу", intents)
        self.assertEqual(explicit_volume.intent.name, "volume:show")
        self.assertEqual(explicit_volume.entities["level"].value.strip(), "35")
        for phrase in ("включи свет", "играй Кукутики", "какая погода", "включи канал новости", "расскажи о музыке"):
            self.assertIsNone(recognize(phrase, intents))


if __name__ == "__main__":
    unittest.main()
