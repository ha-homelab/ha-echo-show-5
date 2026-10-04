import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

import aiohttp
from aiohttp import web
from wyoming.asr import Transcript
from wyoming.info import Describe

spec = importlib.util.spec_from_file_location("fcc_bridge", Path(__file__).parents[1] / "bridge.py")
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)
MODEL = "anthropic/open_router/liquid/lfm-2.5-2.6b:free"


class ContentTests(unittest.TestCase):
    def test_no_paid_alias_or_credential_url(self):
        for model in ["claude-sonnet", "open_router/openrouter/free", "claude-3-freecc-no-thinking/open_router/google/gemini-2.5-flash"]:
            with self.assertRaises(bridge.BridgeError):
                bridge.Config("http://localhost:8082", model)
        with self.assertRaises(bridge.BridgeError):
            bridge.Config("https://user:secret@example.org", MODEL)

    def test_gateway_transport_requires_tls_except_local_endpoints(self):
        for host in ("gateway.example.org", "192.168.1.2", "localhost.example.org",
                     "gateway.svc.cluster.local.example.org", "[2001:db8::1]"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(bridge.BridgeError, "must use HTTPS"):
                    bridge.Config("http://" + host, MODEL, "synthetic-token")
                bridge.Config("https://" + host, MODEL, "synthetic-token")
        for host in ("localhost", "127.0.0.1", "[::1]",
                     "fcc-voice-gateway.homeassistant.svc.cluster.local"):
            with self.subTest(host=host):
                bridge.Config("http://" + host + ":8082", MODEL, "synthetic-token")

    def test_normal_alias_does_not_force_mandatory_reasoning_off(self):
        config = bridge.Config("http://localhost:8082", MODEL)
        body = bridge.request_body("Тест", config.model)
        self.assertEqual(body["model"], MODEL)
        self.assertNotIn("thinking", body)
        self.assertNotIn("output_config", body)

    def test_input_is_not_silently_truncated(self):
        for text in ["  ", "a" * (bridge.MAX_INPUT_CHARACTERS + 1)]:
            with self.assertRaises(bridge.BridgeError):
                bridge.request_body(text, MODEL)

    def test_final_text_only_and_no_incomplete_action_reply(self):
        p = {"type": "message", "stop_reason": "end_turn", "content": [
            {"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": "Готово."}]}
        self.assertEqual(bridge.response_text(p), "Готово.")
        for stop in ["max_tokens", "tool_use", None]:
            with self.assertRaises(bridge.BridgeError):
                bridge.response_text({**p, "stop_reason": stop})
        with self.assertRaises(bridge.BridgeError):
            bridge.response_text({**p, "content": [{"type": "tool_use", "name": "turn_on"}]})


class WireTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.status = 200
        self.delay = 0
        self.huge = False

        async def receive(request):
            self.calls.append({"body": await request.json(), "auth": request.headers.get("Authorization")})
            await asyncio.sleep(self.delay)
            if self.status != 200:
                return web.Response(status=self.status, text="upstream-secret-detail")
            if self.huge:
                return web.Response(body=b"x" * (bridge.MAX_RESPONSE_BYTES + 1))
            return web.json_response({"type": "message", "stop_reason": "end_turn", "content": [{"type": "text", "text": "Лёд легче воды."}]})

        app = web.Application()
        app.router.add_post("/v1/messages", receive)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.session = aiohttp.ClientSession()
        self.client = bridge.FCCClient(bridge.Config(f"http://127.0.0.1:{port}", MODEL, "synthetic-token", 1), self.session)

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def test_one_stateless_request_uses_compatible_bearer_auth(self):
        self.assertEqual(await self.client.ask("Почему лёд плавает?"), "Лёд легче воды.")
        self.assertEqual(await self.client.ask("А небо?"), "Лёд легче воды.")
        self.assertEqual(self.calls[0]["auth"], "Bearer synthetic-token")
        self.assertEqual(self.calls[1]["body"]["messages"], [{"role": "user", "content": "А небо?"}])
        self.assertNotIn("tools", self.calls[0]["body"])
        self.assertEqual(self.calls[0]["body"]["model"], MODEL)

    async def test_rate_limit_and_server_errors_are_not_retried_or_leaked(self):
        for code in [429, 500, 401, 302]:
            self.status = code
            before = len(self.calls)
            with self.assertRaises(bridge.BridgeError) as got:
                await self.client.ask("Тест")
            self.assertNotIn("upstream-secret", str(got.exception))
            self.assertEqual(len(self.calls), before + 1)

    async def test_busy_requests_fail_without_queueing(self):
        self.delay = 0.1
        first = asyncio.create_task(self.client.ask("Первый"))
        while not self.calls:
            await asyncio.sleep(0.005)
        with self.assertRaises(bridge.BridgeError):
            await self.client.ask("Второй")
        await first
        self.assertEqual(len(self.calls), 1)

    async def test_timeout_releases_busy_flag(self):
        self.delay = 1.2
        with self.assertRaises(bridge.BridgeError):
            await self.client.ask("Тест")
        self.assertFalse(self.client._busy)

    async def test_response_size_is_bounded(self):
        self.huge = True
        with self.assertRaises(bridge.BridgeError):
            await self.client.ask("Тест")

    async def test_wyoming_describe_and_transcript(self):
        handler = object.__new__(bridge.Handler)
        handler.client = self.client
        events = []
        async def write(event): events.append(event)
        handler.write_event = write
        self.assertTrue(await handler.handle_event(Describe().event()))
        self.assertEqual(events[0].type, "info")
        self.assertIn("ru", events[0].data["handle"][0]["models"][0]["languages"])
        self.assertFalse(events[0].data["handle"][0]["supports_home_control"])
        self.assertFalse(events[0].data.get("intent"))
        self.assertTrue(await handler.handle_event(Transcript(text="Тест").event()))
        self.assertEqual(events[-1].type, "handled")
        self.assertEqual(events[-1].data["text"], "Лёд легче воды.")
        self.status = 429
        self.assertFalse(await handler.handle_event(Transcript(text="Тест").event()))
        self.assertEqual(events[-1].type, "error")


if __name__ == "__main__":
    unittest.main()
