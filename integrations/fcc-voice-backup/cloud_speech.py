"""Bounded Wyoming speech using FCC's NVIDIA cloud credential and ASR route.

Audio and transcripts stay in memory. This trusted-network listener has no
authentication: expose only a private ClusterIP, never a public TCP port.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
from typing import Protocol

import grpc
from riva.client.proto import riva_asr_pb2 as rasr
from riva.client.proto import riva_asr_pb2_grpc as rasr_grpc
from riva.client.proto import riva_audio_pb2 as raudio
from riva.client.proto import riva_tts_pb2 as rtts
from riva.client.proto import riva_tts_pb2_grpc as rtts_grpc
from wyoming.asr import Transcript
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.error import Error
from wyoming.event import Event, async_write_event
from wyoming.info import AsrModel, AsrProgram, Attribution, Info, TtsProgram, TtsVoice

VERSION = "0.1.0"
RIVA_TARGET = "grpc.nvcf.nvidia.com:443"
ASR_FUNCTION_ID = "71203149-d3b7-4460-8231-1be2543a1fca"
TTS_FUNCTION_ID = "ddacc747-1269-4fab-bfd9-8f593dead106"
TTS_VOICE = "Chatterbox-Multilingual.ru-RU.Male"
TTS_RATE = 22050
MAX_TTS_CHARACTERS = 1000
MAX_TTS_SEGMENT_CHARACTERS = 200
MAX_TTS_AUDIO_BYTES = TTS_RATE * 2 * 60
TTS_CHUNK_BYTES = TTS_RATE * 2 // 5
MODEL_NAME = "nvidia/parakeet-1.1b-rnnt-multilingual-asr"
RATE, WIDTH, CHANNELS = 16000, 2, 1
MAX_AUDIO_BYTES = RATE * WIDTH * 30
MAX_CHUNK_BYTES = RATE * WIDTH * 2
MAX_HEADER_BYTES = 4096
MAX_DATA_BYTES = 8192
MAX_CHUNKS = 4000
MAX_TEXT_CHARACTERS = 4000
MAX_CONNECTIONS = 8
CAPTURE_SECONDS = 45
IDLE_SECONDS = 10
ERRORS = {
    "busy": "Облачный голосовой сервис занят. Повторите позже.",
    "invalid-event": "Некорректный запрос распознавания.",
    "invalid-audio": "Нужен звук PCM16, 16000 Гц, один канал, до 30 секунд.",
    "invalid-text": "Для озвучивания нужен обычный текст до 1000 символов.",
    "timeout": "Облачный голосовой сервис не успел ответить.",
    "provider-auth": "Доступ к облачному голосовому сервису не подтверждён.",
    "provider-unavailable": "Облачный голосовой сервис временно недоступен.",
    "no-speech": "Речь не распознана.",
}


class SpeechError(Exception):
    def __init__(self, code: str):
        self.code = code if code in ERRORS else "provider-unavailable"
        super().__init__(ERRORS[self.code])


@dataclass(frozen=True)
class Config:
    api_key: str = field(repr=False)
    rpc_timeout: float = 30

    def __post_init__(self):
        if not (16 <= len(self.api_key) <= 4096) or not self.api_key.isascii() or any(c.isspace() for c in self.api_key):
            raise ValueError("Invalid cloud speech credential")
        if not 1 <= self.rpc_timeout <= 30:
            raise ValueError("Cloud speech deadline must be 1 to 30 seconds")

    @classmethod
    def from_env(cls):
        with Path(os.environ["NVIDIA_API_KEY_FILE"]).open() as stream:
            key = stream.read(4097).strip()
        return cls(key, float(os.environ.get("NVIDIA_RPC_TIMEOUT_SECONDS", "30")))


class SpeechProvider(Protocol):
    async def transcribe(self, pcm: bytes) -> str: ...
    async def synthesize(self, text: str) -> bytes: ...


def text_segments(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TTS_CHARACTERS:
        raise SpeechError("invalid-text")
    # No SSML, voice cloning, pronunciation dictionaries, or other controls.
    if "<" in text or ">" in text or any(ord(c) < 32 and c not in "\n\r\t" for c in text):
        raise SpeechError("invalid-text")
    remaining = " ".join(text.split())
    segments = []
    while len(remaining) > MAX_TTS_SEGMENT_CHARACTERS:
        prefix = remaining[:MAX_TTS_SEGMENT_CHARACTERS + 1]
        sentences = list(re.finditer(r"[.!?…]\s", prefix))
        split = sentences[-1].end() if sentences and sentences[-1].end() >= 100 else prefix.rfind(" ")
        if split <= 0:
            raise SpeechError("invalid-text")
        segments.append(remaining[:split].strip())
        remaining = remaining[split:].strip()
    if remaining:
        segments.append(remaining)
    if len(segments) > 10 or any(len(s) > MAX_TTS_SEGMENT_CHARACTERS for s in segments):
        raise SpeechError("invalid-text")
    return segments


def rpc_error(exc: grpc.aio.AioRpcError) -> SpeechError:
    if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
        return SpeechError("timeout")
    if exc.code() in {grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED}:
        return SpeechError("provider-auth")
    return SpeechError("provider-unavailable")


def transcript_text(response: rasr.RecognizeResponse) -> str:
    # Riva may return multiple final segments; never discard everything but[0].
    parts = [result.alternatives[0].transcript.strip()
             for result in response.results if result.alternatives]
    text = " ".join(part for part in parts if part)
    if not text:
        raise SpeechError("no-speech")
    if len(text) > MAX_TEXT_CHARACTERS:
        raise SpeechError("provider-unavailable")
    return text


class NvidiaSpeechProvider:
    def __init__(self, config: Config, channel=None):
        self.config = config
        # Injected channels are only for offline tests; runtime target/TLS fixed.
        self.channel = channel or grpc.aio.secure_channel(
            RIVA_TARGET, grpc.ssl_channel_credentials(),
            options=[("grpc.max_receive_message_length", MAX_TTS_AUDIO_BYTES + 8192),
                     ("grpc.max_send_message_length", MAX_AUDIO_BYTES + 8192)],
        )
        self.stub = rasr_grpc.RivaSpeechRecognitionStub(self.channel)
        self.tts_stub = rtts_grpc.RivaSpeechSynthesisStub(self.channel)

    async def transcribe(self, pcm: bytes) -> str:
        request = rasr.RecognizeRequest(
            config=rasr.RecognitionConfig(
                encoding=raudio.LINEAR_PCM, sample_rate_hertz=RATE,
                audio_channel_count=CHANNELS, max_alternatives=1,
                # Same model/function as FCC; explicit Russian avoids guessing.
                language_code="ru-RU", verbatim_transcripts=True,
            ), audio=pcm,
        )
        try:
            response = await self.stub.Recognize(
                request, timeout=self.config.rpc_timeout,
                metadata=(("function-id", ASR_FUNCTION_ID),
                          ("authorization", "Bearer " + self.config.api_key)),
            )
        except grpc.aio.AioRpcError as exc:
            raise rpc_error(exc) from None
        return transcript_text(response)

    async def synthesize(self, text: str) -> bytes:
        segments = text_segments(text)
        audio = bytearray()
        deadline = asyncio.get_running_loop().time() + self.config.rpc_timeout
        try:
            for segment in segments:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise SpeechError("timeout")
                request = rtts.SynthesizeSpeechRequest(
                    text=segment, language_code="ru-RU", voice_name=TTS_VOICE,
                    encoding=raudio.LINEAR_PCM, sample_rate_hz=TTS_RATE,
                )
                result = await self.tts_stub.Synthesize(
                    request, timeout=remaining,
                    metadata=(("function-id", TTS_FUNCTION_ID),
                              ("authorization", "Bearer " + self.config.api_key)),
                )
                if not result.audio or len(result.audio) % 2 or len(audio) + len(result.audio) > MAX_TTS_AUDIO_BYTES:
                    raise SpeechError("provider-unavailable")
                audio.extend(result.audio)
        except grpc.aio.AioRpcError as exc:
            raise rpc_error(exc) from None
        # Do not emit partial speech if a later segment failed.
        return bytes(audio)

    async def close(self):
        await self.channel.close()


def service_info() -> Info:
    attribution = Attribution(name="FCC Cloud Speech", url="https://github.com/ha-homelab/ha-echo-show-5")
    return Info(asr=[AsrProgram(
        name="FCC Cloud Speech", description="Cloud Parakeet ASR; no local model",
        attribution=attribution, installed=True, version=VERSION,
        requires_external_vad=True, supports_transcript_streaming=False,
        models=[AsrModel(name=MODEL_NAME, description="NVIDIA Parakeet multilingual ASR",
                         attribution=attribution, installed=True, version=VERSION,
                         languages=["ru", "ru-RU"])],
    )], tts=[TtsProgram(
        name="FCC Cloud Speech", description="Cloud Chatterbox Russian TTS",
        attribution=attribution, installed=True, version=VERSION,
        supports_synthesize_streaming=False,
        voices=[TtsVoice(name=TTS_VOICE, description="Russian male cloud voice",
                         attribution=attribution, installed=True, version=VERSION,
                         languages=["ru", "ru-RU"])],
    )])


def _length(header: dict, name: str, maximum: int) -> int:
    value = header.get(name, 0)
    if type(value) is not int or not 0 <= value <= maximum:
        raise SpeechError("invalid-event")
    return value


async def read_event(reader: asyncio.StreamReader) -> Event | None:
    """Validate Wyoming lengths before reading/allocating binary bodies."""
    try:
        line = await reader.readline()
        if not line:
            return None
        if len(line) > MAX_HEADER_BYTES or not line.endswith(b"\n"):
            raise SpeechError("invalid-event")
        header = json.loads(line)
        if not isinstance(header, dict) or not isinstance(header.get("type"), str) or header["type"] not in {
            "describe", "transcribe", "audio-start", "audio-chunk", "audio-stop", "synthesize"
        }:
            raise SpeechError("invalid-event")
        data_length = _length(header, "data_length", MAX_DATA_BYTES)
        payload_length = _length(header, "payload_length", MAX_CHUNK_BYTES)
        if payload_length and header["type"] != "audio-chunk":
            raise SpeechError("invalid-event")
        data = header.get("data", {})
        if not isinstance(data, dict):
            raise SpeechError("invalid-event")
        if data_length:
            extra = json.loads(await reader.readexactly(data_length))
            if not isinstance(extra, dict):
                raise SpeechError("invalid-event")
            data.update(extra)
        payload = await reader.readexactly(payload_length) if payload_length else None
        return Event(type=header["type"], data=data, payload=payload)
    except (ValueError, UnicodeError, asyncio.IncompleteReadError, RecursionError):
        raise SpeechError("invalid-event") from None


def validate_format(event: Event):
    expected = {"rate": RATE, "width": WIDTH, "channels": CHANNELS}
    if any(type(event.data.get(k)) is not int or event.data[k] != v for k, v in expected.items()):
        raise SpeechError("invalid-audio")


class SpeechService:
    """One capture/RPC lease; ASR provider can be replaced independently of wire IO."""
    def __init__(self, provider: SpeechProvider, rpc_timeout: float = 30):
        self.provider = provider
        self.rpc_timeout = rpc_timeout
        self.owner = None
        self.connections = 0

    async def _request(self, reader, operation):
        call = asyncio.create_task(operation)
        disconnect = asyncio.create_task(reader.read(1))
        try:
            async with asyncio.timeout(self.rpc_timeout + 1):
                done, _ = await asyncio.wait({call, disconnect}, return_when=asyncio.FIRST_COMPLETED)
                if disconnect in done:
                    if disconnect.result():
                        raise SpeechError("invalid-event")
                    raise ConnectionError("Client disconnected")
                return await call
        finally:
            for task in (call, disconnect):
                if not task.done():
                    task.cancel()
            await asyncio.gather(call, disconnect, return_exceptions=True)

    async def handle_client(self, reader, writer):
        token = object()
        audio = bytearray()
        state, chunks, expires = "idle", 0, 0.0
        self.connections += 1
        try:
            if self.connections > MAX_CONNECTIONS:
                raise SpeechError("busy")
            while True:
                timeout = IDLE_SECONDS
                if self.owner is token:
                    timeout = min(timeout, expires - asyncio.get_running_loop().time())
                if timeout <= 0:
                    raise SpeechError("timeout")
                event = await asyncio.wait_for(read_event(reader), timeout=timeout)
                if event is None:
                    break
                if event.type == "describe" and state == "idle":
                    await asyncio.wait_for(async_write_event(service_info().event(), writer), 5)
                elif event.type == "synthesize" and state == "idle":
                    voice = event.data.get("voice")
                    if voice is None:
                        voice = {}
                    if not isinstance(voice, dict) or voice.get("name") not in (None, "", TTS_VOICE) or voice.get("language") not in (None, "", "ru", "ru-RU") or voice.get("speaker") is not None or event.data.get("text_format") not in (None, "", "text"):
                        raise SpeechError("invalid-text")
                    text = event.data.get("text")
                    text_segments(text)
                    if self.owner is not None:
                        raise SpeechError("busy")
                    self.owner = token
                    pcm = await self._request(reader, self.provider.synthesize(text))
                    if not pcm or len(pcm) % 2 or len(pcm) > MAX_TTS_AUDIO_BYTES:
                        raise SpeechError("provider-unavailable")
                    async with asyncio.timeout(10):
                        await async_write_event(AudioStart(rate=TTS_RATE, width=2, channels=1).event(), writer)
                        for offset in range(0, len(pcm), TTS_CHUNK_BYTES):
                            await async_write_event(AudioChunk(rate=TTS_RATE, width=2, channels=1, audio=pcm[offset:offset + TTS_CHUNK_BYTES]).event(), writer)
                        await async_write_event(AudioStop().event(), writer)
                    del pcm
                    self.owner = None
                elif event.type == "transcribe" and state == "idle":
                    if event.data.get("language") not in (None, "", "ru", "ru-RU") or event.data.get("name") not in (None, "", MODEL_NAME):
                        raise SpeechError("invalid-event")
                    if self.owner is not None:
                        raise SpeechError("busy")
                    self.owner = token
                    state = "requested"
                    expires = asyncio.get_running_loop().time() + CAPTURE_SECONDS
                elif event.type == "audio-start" and state == "requested":
                    validate_format(event)
                    state = "audio"
                elif event.type == "audio-chunk" and state == "audio":
                    validate_format(event)
                    payload = event.payload or b""
                    chunks += 1
                    if not payload or len(payload) % WIDTH or len(payload) > MAX_CHUNK_BYTES or len(audio) + len(payload) > MAX_AUDIO_BYTES or chunks > MAX_CHUNKS:
                        raise SpeechError("invalid-audio")
                    audio.extend(payload)
                elif event.type == "audio-stop" and state == "audio":
                    if not audio:
                        raise SpeechError("invalid-audio")
                    text = await self._request(reader, self.provider.transcribe(bytes(audio)))
                    await asyncio.wait_for(async_write_event(Transcript(text=text, language="ru").event(), writer), 5)
                    audio.clear()
                    self.owner = None
                    state, chunks = "idle", 0
                else:
                    raise SpeechError("invalid-event")
        except (SpeechError, TimeoutError) as exc:
            code = exc.code if isinstance(exc, SpeechError) else "timeout"
            # Only fixed category codes; never audio, transcript, key, or exceptions.
            logging.warning("FCC_CLOUD_SPEECH_FAILURE %s", code)
            with contextlib.suppress(ConnectionError, TimeoutError):
                await asyncio.wait_for(async_write_event(Error(text=ERRORS[code], code=code).event(), writer), 2)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        except Exception:
            logging.error("FCC_CLOUD_SPEECH_FAILURE provider-unavailable")
            with contextlib.suppress(ConnectionError, TimeoutError):
                await asyncio.wait_for(async_write_event(Error(text=ERRORS["provider-unavailable"], code="provider-unavailable").event(), writer), 2)
        finally:
            audio.clear()
            if self.owner is token:
                self.owner = None
            self.connections -= 1
            writer.close()
            with contextlib.suppress(ConnectionError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 2)


async def main():
    config = Config.from_env()
    provider = NvidiaSpeechProvider(config)
    service = SpeechService(provider, config.rpc_timeout)
    try:
        server = await asyncio.start_server(service.handle_client, "0.0.0.0", 10500, limit=MAX_HEADER_BYTES)
        logging.info("FCC cloud speech ready")
        async with server:
            await server.serve_forever()
    finally:
        await provider.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        asyncio.run(main())
    except (ValueError, KeyError, OSError):
        logging.error("FCC cloud speech startup configuration failed")
        raise SystemExit(2)
