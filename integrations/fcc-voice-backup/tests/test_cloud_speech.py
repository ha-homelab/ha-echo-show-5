import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import grpc
from wyoming.asr import Transcribe
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.event import Event, async_read_event, async_write_event
from wyoming.info import Describe
from wyoming.tts import Synthesize, SynthesizeVoice

spec = importlib.util.spec_from_file_location("fcc_cloud_speech", Path(__file__).parents[1] / "cloud_speech.py")
cloud = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cloud
spec.loader.exec_module(cloud)


def response(*parts):
    return cloud.rasr.RecognizeResponse(results=[
        cloud.rasr.SpeechRecognitionResult(alternatives=[
            cloud.rasr.SpeechRecognitionAlternative(transcript=part)
        ]) for part in parts
    ])


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.tts_calls = []
        self.delay = 0
        self.error = None
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.tts_audio = b"\0" * 22050

    async def transcribe(self, pcm):
        self.calls.append(pcm)
        self.started.set()
        try:
            await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
            return "Синтетическая проверка."
        except asyncio.CancelledError:
            self.cancelled.set()
            raise

    async def synthesize(self, text):
        self.tts_calls.append(text)
        self.started.set()
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.tts_audio


class ContentTests(unittest.TestCase):
    def test_config_bounds_and_secret_repr(self):
        config = cloud.Config("synthetic-key-12345")
        self.assertNotIn("synthetic-key", repr(config))
        for key in ["", "short", "x" * 4097, "x" * 16 + "\n", "ключ" * 10]:
            with self.assertRaises(ValueError):
                cloud.Config(key)
        for timeout in [0, 31, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                cloud.Config("synthetic-key-12345", timeout)

    def test_all_final_segments_are_assembled(self):
        self.assertEqual(cloud.transcript_text(response(" Первая часть. ", "", "Вторая часть.")), "Первая часть. Вторая часть.")
        for value in [response(), response("  ")]:
            with self.assertRaises(cloud.SpeechError) as caught:
                cloud.transcript_text(value)
            self.assertEqual(caught.exception.code, "no-speech")
        with self.assertRaises(cloud.SpeechError):
            cloud.transcript_text(response("x" * (cloud.MAX_TEXT_CHARACTERS + 1)))

    def test_runtime_channel_is_fixed_and_tls(self):
        with patch.object(cloud.grpc.aio, "secure_channel") as factory:
            cloud.NvidiaSpeechProvider(cloud.Config("synthetic-key-12345"))
        self.assertEqual(factory.call_args.args[0], "grpc.nvcf.nvidia.com:443")
        self.assertIsInstance(factory.call_args.args[1], grpc.ChannelCredentials)

    def test_plaintext_segmentation_keeps_all_words_and_limits(self):
        text = "Первая фраза. " * 65
        parts = cloud.text_segments(text)
        self.assertEqual(" ".join(parts), " ".join(text.split()))
        self.assertTrue(all(0 < len(p) <= 200 for p in parts))
        self.assertLessEqual(len(parts), 10)
        for invalid in [None, 42, " ", "x" * 1001, "<speak>Тест</speak>", "x\0y", "x" * 201]:
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaises(cloud.SpeechError):
                    cloud.text_segments(invalid)

    def test_segmentation_prefers_a_sentence_boundary_with_headroom(self):
        first = "Первое предложение " * 6 + "завершено."
        text = first + " " + "Следующее слово " * 15
        parts = cloud.text_segments(text)
        self.assertEqual(parts[0], first)
        self.assertEqual(" ".join(parts), text.strip())


class WireTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.provider = FakeProvider()
        self.service = cloud.SpeechService(self.provider, rpc_timeout=1)
        self.server = await asyncio.start_server(self.service.handle_client, "127.0.0.1", 0, limit=cloud.MAX_HEADER_BYTES)
        self.port = self.server.sockets[0].getsockname()[1]
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
        self.server.close()
        await self.server.wait_closed()
        for _ in range(100):
            if self.service.connections == 0:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(self.service.connections, 0)
        self.assertIsNone(self.service.owner)

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(writer)
        return reader, writer

    async def event(self, reader):
        return await asyncio.wait_for(async_read_event(reader), 3)

    async def start(self, writer):
        await async_write_event(Transcribe(language="ru").event(), writer)
        await async_write_event(AudioStart(rate=16000, width=2, channels=1).event(), writer)

    async def audio(self, writer, payload=b"\0" * 3200, **format_changes):
        fmt = {"rate": 16000, "width": 2, "channels": 1, **format_changes}
        await async_write_event(AudioChunk(audio=payload, **fmt).event(), writer)

    async def test_describe_advertises_cloud_asr_and_russian_tts(self):
        reader, writer = await self.connect()
        await async_write_event(Describe().event(), writer)
        info = await self.event(reader)
        self.assertEqual(info.type, "info")
        self.assertIn("ru", info.data["asr"][0]["models"][0]["languages"])
        self.assertTrue(info.data["asr"][0]["requires_external_vad"])
        voice = info.data["tts"][0]["voices"][0]
        self.assertEqual(voice["name"], cloud.TTS_VOICE)
        self.assertEqual(voice["languages"], ["ru", "ru-RU"])
        self.assertFalse(info.data.get("handle"))
        self.assertFalse(self.provider.calls)

    async def test_real_wyoming_exchange_and_reuse(self):
        reader, writer = await self.connect()
        for _ in range(2):
            await self.start(writer)
            await self.audio(writer)
            await self.audio(writer)
            await async_write_event(AudioStop().event(), writer)
            result = await self.event(reader)
            self.assertEqual(result.type, "transcript")
            self.assertEqual(result.data["language"], "ru")
        self.assertEqual([len(p) for p in self.provider.calls], [6400, 6400])

    async def test_thirty_seconds_accepted_but_not_one_sample_more(self):
        reader, writer = await self.connect()
        await self.start(writer)
        for _ in range(15):
            await self.audio(writer, b"\0" * cloud.MAX_CHUNK_BYTES)
        await async_write_event(AudioStop().event(), writer)
        self.assertEqual((await self.event(reader)).type, "transcript")
        self.assertEqual(len(self.provider.calls[0]), cloud.MAX_AUDIO_BYTES)
        await self.start(writer)
        for _ in range(15):
            await self.audio(writer, b"\0" * cloud.MAX_CHUNK_BYTES)
        await self.audio(writer, b"\0\0")
        self.assertEqual((await self.event(reader)).data["code"], "invalid-audio")
        self.assertEqual(len(self.provider.calls), 1)

    async def test_chunk_format_cannot_change(self):
        for changes in [{"rate": 48000}, {"width": 4}, {"channels": 2}, {"rate": 16000.0}, {"channels": True}]:
            with self.subTest(changes=changes):
                reader, writer = await self.connect()
                await self.start(writer)
                await self.audio(writer, **changes)
                self.assertEqual((await self.event(reader)).data["code"], "invalid-audio")
        self.assertFalse(self.provider.calls)

    async def test_empty_or_partial_pcm_sample_rejected(self):
        for payload in [b"", b"x"]:
            reader, writer = await self.connect()
            await self.start(writer)
            await self.audio(writer, payload)
            self.assertEqual((await self.event(reader)).data["code"], "invalid-audio")
        self.assertFalse(self.provider.calls)

    async def test_capture_requires_requested_sequence(self):
        for event in [AudioStop().event(), AudioStart(rate=16000, width=2, channels=1).event(), Event(type="synthesize-start", data={"text": "x"})]:
            reader, writer = await self.connect()
            await async_write_event(event, writer)
            self.assertEqual((await self.event(reader)).data["code"], "invalid-event")

    async def test_unknown_language_or_model_not_sent_upstream(self):
        for event in [Transcribe(language="en").event(), Transcribe(name="other/model").event()]:
            reader, writer = await self.connect()
            await async_write_event(event, writer)
            self.assertEqual((await self.event(reader)).data["code"], "invalid-event")
        self.assertFalse(self.provider.calls)

    async def test_declared_lengths_bounded_before_body_read(self):
        headers = [
            {"type": "audio-chunk", "payload_length": cloud.MAX_CHUNK_BYTES + 1},
            {"type": "transcribe", "data_length": cloud.MAX_DATA_BYTES + 1},
            {"type": "transcribe", "data_length": -1},
            {"type": "transcribe", "data_length": True},
            {"type": "transcribe", "data_length": "5"},
            {"type": "transcribe", "payload_length": 1},
            {"type": "transcribe", "data": []},
        ]
        for header in headers:
            reader, writer = await self.connect()
            writer.write(json.dumps(header).encode() + b"\n")
            await writer.drain()
            self.assertEqual((await self.event(reader)).data["code"], "invalid-event")

    async def test_malformed_and_oversized_headers(self):
        for header in [b"not-json\n", b"[]\n", b"x" * (cloud.MAX_HEADER_BYTES + 1) + b"\n"]:
            reader, writer = await self.connect()
            writer.write(header)
            await writer.drain()
            self.assertEqual((await self.event(reader)).data["code"], "invalid-event")

    async def test_one_global_capture_and_inference_lease(self):
        reader, writer = await self.connect()
        await self.start(writer)
        other, other_writer = await self.connect()
        await async_write_event(Transcribe().event(), other_writer)
        self.assertEqual((await self.event(other)).data["code"], "busy")
        self.provider.delay = 0.1
        await self.audio(writer)
        await async_write_event(AudioStop().event(), writer)
        await asyncio.wait_for(self.provider.started.wait(), 1)
        third, third_writer = await self.connect()
        await async_write_event(Transcribe().event(), third_writer)
        self.assertEqual((await self.event(third)).data["code"], "busy")
        self.assertEqual((await self.event(reader)).type, "transcript")
        self.assertEqual(len(self.provider.calls), 1)

    async def test_disconnect_cancels_upstream_and_releases_lease(self):
        reader, writer = await self.connect()
        self.provider.delay = 10
        await self.start(writer)
        await self.audio(writer)
        await async_write_event(AudioStop().event(), writer)
        await asyncio.wait_for(self.provider.started.wait(), 1)
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(self.provider.cancelled.wait(), 1)
        await asyncio.sleep(0.02)
        self.assertIsNone(self.service.owner)

    async def test_error_details_are_not_logged_or_returned(self):
        self.provider.error = RuntimeError("synthetic-secret-do-not-log")
        reader, writer = await self.connect()
        with self.assertLogs(level="ERROR") as captured:
            await self.start(writer)
            await self.audio(writer)
            await async_write_event(AudioStop().event(), writer)
            event = await self.event(reader)
        self.assertEqual(event.data["code"], "provider-unavailable")
        self.assertNotIn("synthetic-secret", str(event.data) + str(captured.output))

    async def test_capture_timeout_releases_busy_lease(self):
        reader, writer = await self.connect()
        with patch.object(cloud, "IDLE_SECONDS", 0.05):
            await self.start(writer)
            event = await self.event(reader)
        self.assertEqual(event.data["code"], "timeout")

    async def test_tts_wire_frames_are_pcm16_mono_22050_and_complete(self):
        for voice in [SynthesizeVoice(language="ru"), SynthesizeVoice(language="ru-RU"), SynthesizeVoice(name=cloud.TTS_VOICE)]:
            reader, writer = await self.connect()
            await async_write_event(Synthesize(text="Синтетическая проверка.", voice=voice).event(), writer)
            start = await self.event(reader)
            self.assertEqual(start.type, "audio-start")
            self.assertEqual((start.data["rate"], start.data["width"], start.data["channels"]), (22050, 2, 1))
            pcm = bytearray()
            while True:
                event = await self.event(reader)
                if event.type == "audio-stop":
                    break
                self.assertEqual(event.type, "audio-chunk")
                self.assertEqual(event.data["rate"], 22050)
                self.assertEqual(event.data["width"], 2)
                self.assertEqual(event.data["channels"], 1)
                self.assertLessEqual(len(event.payload), cloud.TTS_CHUNK_BYTES)
                pcm.extend(event.payload)
            self.assertEqual(pcm, self.provider.tts_audio)

    async def test_tts_rejects_ssml_voice_override_and_bad_input(self):
        invalid = [
            {"text": "x" * 1001}, {"text": "x", "text_format": "ssml"},
            {"text": "<speak>Тест</speak>"}, {"text": "x", "voice": []},
            {"text": "x", "voice": {"name": "cloned-voice"}},
            {"text": "x", "voice": {"language": "en"}},
            {"text": "x", "voice": {"speaker": "another"}},
        ]
        for data in invalid:
            reader, writer = await self.connect()
            await async_write_event(Event(type="synthesize", data=data), writer)
            self.assertEqual((await self.event(reader)).data["code"], "invalid-text")
        self.assertFalse(self.provider.tts_calls)

    async def test_tts_and_asr_share_busy_lease(self):
        self.provider.delay = 0.1
        reader, writer = await self.connect()
        await async_write_event(Synthesize(text="Тест.").event(), writer)
        await asyncio.wait_for(self.provider.started.wait(), 1)
        for event in [Transcribe(language="ru").event(), Synthesize(text="Другой.").event()]:
            other, other_writer = await self.connect()
            await async_write_event(event, other_writer)
            self.assertEqual((await self.event(other)).data["code"], "busy")
        self.assertEqual((await self.event(reader)).type, "audio-start")
        while (await self.event(reader)).type != "audio-stop":
            pass
        self.assertFalse(self.provider.calls)
        self.assertEqual(len(self.provider.tts_calls), 1)

    async def test_invalid_provider_pcm_fails_before_audio_start(self):
        for pcm in [b"", b"x", b"\0" * (cloud.MAX_TTS_AUDIO_BYTES + 2)]:
            self.provider.tts_audio = pcm
            reader, writer = await self.connect()
            await async_write_event(Synthesize(text="Тест.").event(), writer)
            event = await self.event(reader)
            self.assertEqual(event.type, "error")
            self.assertEqual(event.data["code"], "provider-unavailable")


class GrpcTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.tts_requests = []
        self.delay = 0
        self.failure = None
        self.tts_audio = b"\0" * 22050
        outer = self

        class Servicer(cloud.rasr_grpc.RivaSpeechRecognitionServicer):
            async def Recognize(self, request, context):
                outer.requests.append((request, dict(context.invocation_metadata()), context.time_remaining()))
                if outer.failure:
                    await context.abort(outer.failure, "synthetic-private-upstream-detail")
                await asyncio.sleep(outer.delay)
                return response("Один.", "Два.")

        class TtsServicer(cloud.rtts_grpc.RivaSpeechSynthesisServicer):
            async def Synthesize(self, request, context):
                outer.tts_requests.append((request, dict(context.invocation_metadata()), context.time_remaining()))
                if outer.failure:
                    await context.abort(outer.failure, "synthetic-private-upstream-detail")
                await asyncio.sleep(outer.delay)
                return cloud.rtts.SynthesizeSpeechResponse(audio=outer.tts_audio)

        self.server = grpc.aio.server()
        cloud.rasr_grpc.add_RivaSpeechRecognitionServicer_to_server(Servicer(), self.server)
        cloud.rtts_grpc.add_RivaSpeechSynthesisServicer_to_server(TtsServicer(), self.server)
        port = self.server.add_insecure_port("127.0.0.1:0")
        await self.server.start()
        channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
        self.provider = cloud.NvidiaSpeechProvider(cloud.Config("synthetic-key-12345", 1), channel=channel)

    async def asyncTearDown(self):
        await self.provider.close()
        await self.server.stop(0)

    async def test_real_grpc_request_deadline_metadata_and_all_segments(self):
        self.assertEqual(await self.provider.transcribe(b"\0" * 320), "Один. Два.")
        request, metadata, remaining = self.requests[0]
        self.assertEqual(request.config.sample_rate_hertz, 16000)
        self.assertEqual(request.config.language_code, "ru-RU")
        self.assertEqual(request.config.audio_channel_count, 1)
        self.assertEqual(request.config.encoding, cloud.raudio.LINEAR_PCM)
        self.assertEqual(metadata["function-id"], cloud.ASR_FUNCTION_ID)
        self.assertEqual(metadata["authorization"], "Bearer synthetic-key-12345")
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 1.1)

    async def test_actual_grpc_deadline_cancels_slow_rpc(self):
        self.delay = 10
        start = asyncio.get_running_loop().time()
        with self.assertRaises(cloud.SpeechError) as caught:
            await self.provider.transcribe(b"\0" * 320)
        self.assertEqual(caught.exception.code, "timeout")
        self.assertLess(asyncio.get_running_loop().time() - start, 2)

    async def test_auth_and_service_failures_are_fixed_categories(self):
        for status, code in [(grpc.StatusCode.UNAUTHENTICATED, "provider-auth"), (grpc.StatusCode.PERMISSION_DENIED, "provider-auth"), (grpc.StatusCode.UNAVAILABLE, "provider-unavailable")]:
            self.failure = status
            with self.assertRaises(cloud.SpeechError) as caught:
                await self.provider.transcribe(b"\0" * 320)
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("synthetic-private", str(caught.exception))

    async def test_tts_rpc_metadata_voice_segments_and_frame_bytes(self):
        text = "Проверка облачного голоса. " * 20
        pcm = await self.provider.synthesize(text)
        self.assertGreater(len(self.tts_requests), 1)
        self.assertEqual(pcm, self.tts_audio * len(self.tts_requests))
        self.assertEqual(" ".join(r.text for r, _, _ in self.tts_requests), text.strip())
        for request, metadata, remaining in self.tts_requests:
            self.assertEqual(request.language_code, "ru-RU")
            self.assertEqual(request.voice_name, cloud.TTS_VOICE)
            self.assertEqual(request.encoding, cloud.raudio.LINEAR_PCM)
            self.assertEqual(request.sample_rate_hz, 22050)
            self.assertEqual(metadata["function-id"], cloud.TTS_FUNCTION_ID)
            self.assertEqual(metadata["authorization"], "Bearer synthetic-key-12345")
            self.assertLessEqual(len(request.text), 200)
            self.assertLessEqual(remaining, 1.1)

    async def test_tts_total_deadline_is_not_reset_for_each_segment(self):
        self.delay = 0.65
        started = asyncio.get_running_loop().time()
        with self.assertRaises(cloud.SpeechError) as caught:
            await self.provider.synthesize("Синтетический текст. " * 30)
        self.assertEqual(caught.exception.code, "timeout")
        self.assertEqual(len(self.tts_requests), 2)
        self.assertLess(self.tts_requests[1][2], 0.5)
        self.assertLess(asyncio.get_running_loop().time() - started, 1.8)

    async def test_tts_rejects_aggregate_oversize_or_odd_pcm(self):
        for pcm, text in [(b"x", "Тест."), (b"\0" * (cloud.MAX_TTS_AUDIO_BYTES // 2 + 2), "Длинный текст. " * 40)]:
            self.tts_audio = pcm
            with self.assertRaises(cloud.SpeechError) as caught:
                await self.provider.synthesize(text)
            self.assertEqual(caught.exception.code, "provider-unavailable")


if __name__ == "__main__":
    unittest.main()
