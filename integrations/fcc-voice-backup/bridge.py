"""Wyoming conversation service for FCC's Anthropic-compatible text API.

Speech recognition and synthesis are separate Wyoming services. This process
has no Home Assistant token, device tools, CLI execution, or shared chat memory.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from wyoming.asr import Transcript
from wyoming.error import Error
from wyoming.event import Event
from wyoming.handle import Handled
from wyoming.info import Attribution, Describe, Info, HandleModel, HandleProgram
from wyoming.server import AsyncEventHandler, AsyncServer

VERSION = "0.1.1"
MAX_INPUT_CHARACTERS = 2000
MAX_RESPONSE_BYTES = 256 * 1024
SYSTEM = (
    "Ты резервный голосовой собеседник Home Assistant. Отвечай по-русски, "
    "кратко, обычно одним-двумя предложениями, без Markdown. "
    "Тебе не предоставлены инструменты управления домом, состояние устройств, "
    "интернет-поиск или часы. Не утверждай, что выполнил действие, и не "
    "выдумывай текущее состояние. Если просят управлять устройством, сообщи, "
    "что нужна стандартная команда Home Assistant. Не показывай рассуждения."
)


class BridgeError(Exception):
    """Fixed public message; upstream payloads and credentials stay private."""


@dataclass(frozen=True)
class Config:
    base_url: str
    model: str
    token: str = ""
    timeout: float = 30.0

    def __post_init__(self):
        parsed = urlsplit(self.base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/")):
            raise BridgeError("FCC_BASE_URL must be the gateway root without credentials or a path")
        prefixes = ("anthropic/open_router/", "claude-3-freecc-no-thinking/open_router/")
        if (not self.model.startswith(prefixes) or not self.model.endswith(":free")
                or any(c.isspace() for c in self.model)):
            raise BridgeError("FCC_MODEL must be an explicit FCC OpenRouter :free model ID")
        if not 1 <= self.timeout <= 60:
            raise BridgeError("FCC_TIMEOUT_SECONDS must be between 1 and 60")

    @classmethod
    def from_env(cls):
        token_file = os.environ.get("FCC_API_KEY_FILE")
        token = Path(token_file).read_text().strip() if token_file else os.environ.get("FCC_API_KEY", "")
        return cls(
            base_url=os.environ["FCC_BASE_URL"].rstrip("/"),
            model=os.environ.get("FCC_MODEL", "anthropic/open_router/liquid/lfm-2.5-2.6b:free"),
            token=token,
            timeout=float(os.environ.get("FCC_TIMEOUT_SECONDS", "30")),
        )


def request_body(text: str, model: str) -> dict:
    text = text.strip()
    if not text:
        raise BridgeError("Пустой запрос.")
    if len(text) > MAX_INPUT_CHARACTERS:
        raise BridgeError("Запрос слишком длинный. Скажите короче.")
    return {
        "model": model,
        "max_tokens": 1024,
        "stream": False,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": text}],
    }


def response_text(payload: dict) -> str:
    if not isinstance(payload, dict) or payload.get("type") != "message":
        raise BridgeError("FCC вернул некорректный ответ.")
    if payload.get("stop_reason") not in ("end_turn", "stop_sequence"):
        raise BridgeError("FCC не завершил текстовый ответ. Повторите вопрос короче.")
    blocks = payload.get("content")
    if not isinstance(blocks, list) or any(not isinstance(b, dict) for b in blocks):
        raise BridgeError("FCC вернул некорректный ответ.")
    if any(b.get("type") not in ("text", "thinking", "redacted_thinking") for b in blocks):
        raise BridgeError("Резервный собеседник не выполняет действия с устройствами.")
    texts = [b.get("text") for b in blocks if b.get("type") == "text"]
    if any(not isinstance(t, str) for t in texts):
        raise BridgeError("FCC вернул некорректный ответ.")
    answer = "\n".join(texts).strip()
    if not answer or len(answer) > 4000:
        raise BridgeError("FCC не вернул подходящий голосовой ответ.")
    return answer


class FCCClient:
    def __init__(self, config: Config, session: aiohttp.ClientSession):
        self.config = config
        self.session = session
        self._busy = False

    async def ask(self, text: str) -> str:
        payload = request_body(text, self.config.model)
        # Reject overlapping requests; do not queue stale spoken commands.
        if self._busy:
            raise BridgeError("Резервный собеседник занят. Повторите через несколько секунд.")
        self._busy = True
        headers = {"anthropic-version": "2023-06-01"}
        if self.config.token:
            headers["Authorization"] = "Bearer " + self.config.token
        try:
            async with self.session.post(
                self.config.base_url.rstrip("/") + "/v1/messages",
                json=payload, headers=headers, allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status == 429:
                    raise BridgeError("Достигнут лимит резервного сервиса. Попробуйте позже.")
                if response.status != 200:
                    raise BridgeError("Резервный сервис FCC сейчас недоступен.")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise BridgeError("FCC вернул слишком большой ответ.")
                import json
                try:
                    return response_text(json.loads(raw))
                except (ValueError, UnicodeError):
                    raise BridgeError("FCC вернул некорректный ответ.") from None
        except asyncio.TimeoutError:
            raise BridgeError("FCC не успел ответить. Попробуйте позже.") from None
        except aiohttp.ClientError:
            raise BridgeError("Соединение с резервным сервисом FCC недоступно.") from None
        finally:
            self._busy = False


def service_info() -> Info:
    attribution = Attribution(name="FCC Voice Backup", url="https://github.com/ha-homelab/ha-echo-show-5")
    return Info(handle=[HandleProgram(
        name="FCC Voice Backup", attribution=attribution, installed=True,
        description="Stateless Russian Q&A via FCC; use HA local intents for device commands",
        version=VERSION, supports_home_control=False, models=[HandleModel(
            name="fcc-russian", attribution=attribution, installed=True,
            description="Explicit free FCC text model", version=VERSION, languages=["ru", "ru-RU"],
        )],
    )])


class Handler(AsyncEventHandler):
    def __init__(self, client: FCCClient, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(service_info().event())
        elif Transcript.is_type(event.type):
            try:
                text = Transcript.from_event(event).text
                if not isinstance(text, str):
                    raise BridgeError("Некорректный текст запроса.")
                answer = await self.client.ask(text)
                await self.write_event(Handled(text=answer).event())
            except BridgeError as error:
                logging.warning("FCC request did not complete")
                await self.write_event(Error(text=str(error), code="fcc-backup-error").event())
                return False
        return True


async def main():
    config = Config.from_env()
    uri = os.environ.get("WYOMING_URI", "tcp://0.0.0.0:10400")
    async with aiohttp.ClientSession(trust_env=False) as session:
        client = FCCClient(config, session)
        server = AsyncServer.from_uri(uri)
        logging.info("FCC voice conversation bridge ready")
        await server.run(lambda reader, writer: Handler(client, reader, writer))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        asyncio.run(main())
    except (BridgeError, KeyError, ValueError, OSError):
        logging.error("Invalid startup configuration or service failure; inspect private configuration")
        raise SystemExit(2)
