"""Exercise optional receiver registration without a real HA frontend."""
import types
import unittest
from unittest.mock import AsyncMock

from test_contract import extract


class CallPanelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.register = AsyncMock()
        self.hass = types.SimpleNamespace(data={})
        self.setup_panel = extract('__init__.py', 'register_call_panel', {
            'frontend': types.SimpleNamespace(DATA_PANELS='panels'),
            'panel_custom': types.SimpleNamespace(async_register_panel=self.register),
        })
        self.config = {'call_panel': True, 'video_enabled': True, 'adb_entity': 'media_player.test'}

    async def test_disabled_panel_has_no_frontend_effect(self):
        await self.setup_panel(self.hass, {})
        self.register.assert_not_awaited()

    async def test_video_and_adapter_are_required(self):
        for key, value in [('video_enabled', False), ('adb_entity', None)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                await self.setup_panel(self.hass, {**self.config, key: value})
        self.register.assert_not_awaited()

    async def test_existing_route_is_preserved(self):
        existing = object()
        self.hass.data['panels'] = {'show5-call': existing}
        with self.assertRaises(ValueError):
            await self.setup_panel(self.hass, self.config)
        self.register.assert_not_awaited()
        self.assertIs(self.hass.data['panels']['show5-call'], existing)

    async def test_fixed_local_receiver_requires_admin(self):
        await self.setup_panel(self.hass, self.config)
        self.register.assert_awaited_once_with(
            self.hass, frontend_url_path='show5-call', webcomponent_name='show5-call-panel',
            module_url='/local/show5-call-panel.js', require_admin=True,
        )

    async def test_registration_error_is_not_reported_as_success(self):
        self.register.side_effect = RuntimeError('registration failed')
        with self.assertRaises(RuntimeError):
            await self.setup_panel(self.hass, self.config)
