"""Mock the HA boundary; never import or contact a real HA instance."""
import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ID = 'announce-' + 'a' * 32 + '-225'

class Event:
    def __init__(self, type, data=None, payload=None):
        self.type, self.data, self.payload = type, data, payload

class Store:
    def __init__(self, *args): self.data = None
    async def async_load(self): return self.data
    async def async_save(self, data): self.data = data

class HomeAssistantError(Exception): pass

def load():
    names = ('homeassistant', 'homeassistant.auth', 'homeassistant.auth.permissions',
             'homeassistant.auth.permissions.const', 'homeassistant.components',
             'homeassistant.core', 'homeassistant.exceptions', 'homeassistant.helpers',
             'homeassistant.helpers.aiohttp_client', 'homeassistant.helpers.storage',
             'wyoming', 'wyoming.event', 'guarded_fixture', 'aiohttp')
    modules = {name: types.ModuleType(name) for name in names}
    modules['guarded_fixture'].__path__ = [str(ROOT / 'src')]
    modules['homeassistant.auth.permissions.const'].POLICY_CONTROL = 'control'
    modules['homeassistant.components'].ffmpeg = types.SimpleNamespace()
    modules['homeassistant.core'].SupportsResponse = types.SimpleNamespace(ONLY='only')
    modules['homeassistant.exceptions'].HomeAssistantError = HomeAssistantError
    modules['homeassistant.helpers.aiohttp_client'].async_get_clientsession = lambda hass: hass.session
    modules['homeassistant.helpers.storage'].Store = Store
    modules['wyoming.event'].Event = Event
    modules['aiohttp'].ClientTimeout = lambda **kw: kw
    with patch.dict(sys.modules, modules):
        for name in ('guarded_announce_core', 'guarded_announce'):
            spec = importlib.util.spec_from_file_location('guarded_fixture.' + name, ROOT / 'src' / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        return sys.modules['guarded_fixture.guarded_announce'], sys.modules['guarded_fixture.guarded_announce_core']

adapter, core = load()

class HA:
    def __init__(self):
        self.data = {}
        self.config = types.SimpleNamespace(internal_url='http://ha.local:8123', external_url='https://ha.example.test', api=types.SimpleNamespace(port=8123), path=lambda name: '/not-present-guard-fixture/' + name)
        self.values = {}
        self.states = types.SimpleNamespace(get=lambda key: self.values.get(key))
        self.registered = {}
        self.services = types.SimpleNamespace(async_register=lambda domain, name, fn, **kw: self.registered.update({name: (fn, kw)}))
        self.allowed = True
        async def user(uid):
            return types.SimpleNamespace(is_active=True, permissions=types.SimpleNamespace(check_entity=lambda e, p: self.allowed)) if uid else None
        self.auth = types.SimpleNamespace(async_get_user=user)
    def async_create_task(self, coroutine): return asyncio.create_task(coroutine)
    async def async_add_executor_job(self, fn, *args): return fn(*args)

class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ha = HA()
        await adapter.async_setup_guarded(self.ha)
        self.entity = types.SimpleNamespace(entity_id='assist_satellite.test', hass=self.ha, state='idle', _client=None,
                                            config_entry=types.SimpleNamespace(options={}))
        mapping = {role: 'test.' + role for role in adapter.GUARDS}
        self.entity.config_entry.options[adapter.OPTIONS_KEY] = mapping
        for role, entity_id in mapping.items():
            state = 'off' if role == 'dnd' else 'idle'
            self.ha.values[entity_id] = types.SimpleNamespace(state=state, attributes={'busy': False, 'owner': 'idle', 'lease_held': False, 'call_id': None})
        self.transport = adapter.GuardedTransport(self.entity)
        await self.transport.added()
        self.sent = []
        async def send(event): self.sent.append(event)
        self.entity._client = types.SimpleNamespace(write_event=send, can_write_event=lambda: True)
    async def asyncTearDown(self):
        await self.transport.removed()
        await asyncio.sleep(0)
    def call(self, service, data, uid='test-user'):
        return self.ha.registered[service][0](types.SimpleNamespace(service=service, data=data, context=types.SimpleNamespace(user_id=uid)))
    def test_media_allows_only_prepared_ha_tts_paths(self):
        for media in ['/api/tts_proxy/test.wav', 'http://ha.local:8123/api/tts_proxy/test.wav', 'https://ha.example.test/api/tts_proxy/test.wav']:
            self.assertEqual(self.transport.validate_media(media), '/api/tts_proxy/test.wav')
        for media in ['file:///tmp/test.wav', 'https://evil.test/api/tts_proxy/test.wav', 'http://ha.local:8123/api/tts_proxy/../x', '/api/tts_proxy/%2fetc', '//evil.test/api/tts_proxy/x', '/api/tts_proxy/x?token=secret', 'https://user:secret@ha.example.test/api/tts_proxy/test.wav', 'media-source://tts/anything']:
            with self.subTest(media=media), self.assertRaises(core.AnnouncementError):
                self.transport.validate_media(media)
    def test_unavailable_guard_fails_closed(self):
        self.assertEqual(self.transport.busy_reason(), '')
        self.ha.values['test.dnd'].state = 'unavailable'
        self.assertEqual(self.transport.busy_reason(), 'guard_state_unavailable')
    def test_sip_lease_and_room_ownership_are_checked(self):
        self.ha.values['test.sip'].attributes['lease_held'] = True
        self.assertEqual(self.transport.busy_reason(), 'sip_busy')
        self.ha.values['test.sip'].attributes['lease_held'] = False
        self.ha.values['test.room'].attributes['busy'] = True
        self.assertEqual(self.transport.busy_reason(), 'room_busy')
    def test_intercom_recovery_or_active_call_blocks(self):
        backend = types.SimpleNamespace(recovery_pending=False, guard=types.SimpleNamespace(active=None, cleanup_error=False, lock=asyncio.Lock()), room=types.SimpleNamespace(call=None, lock=asyncio.Lock()))
        self.ha.data['show5_intercom'] = backend
        self.assertEqual(self.transport.busy_reason(), '')
        backend.room.call = {'example': True}
        self.assertEqual(self.transport.busy_reason(), 'intercom_busy')
        backend.room.call = None; backend.recovery_pending = True
        self.assertEqual(self.transport.busy_reason(), 'intercom_recovery_pending')
    async def test_missing_mapping_capability_query_does_not_send(self):
        self.entity.config_entry.options = {}
        result = await self.transport.capabilities()
        self.assertFalse(result['atomic_idle_guard'])
        self.assertEqual(self.sent, [])
    async def test_matching_rpc_and_capabilities_are_read_only(self):
        async def send(event):
            self.sent.append(event)
            self.transport.receive(Event('guarded-announce-result', dict(event.data, protocol=core.PROTOCOL,
                status='accepted', **{key: True for key in core.CAPABILITIES})))
        self.entity._client.write_event = send
        result = await self.transport.capabilities()
        self.assertTrue(all(result[key] for key in core.CAPABILITIES))
        self.assertEqual([event.data['op'] for event in self.sent], ['capabilities'])
        self.assertEqual(self.ha.data[adapter.KEY].records, {})
    async def test_wrong_id_or_operation_does_not_satisfy_rpc(self):
        task = asyncio.create_task(self.transport.rpc('status', ID))
        await asyncio.sleep(0)
        self.transport.receive(Event('guarded-announce-result', {'op': 'cancel', 'request_id': ID, 'status': 'stopped'}))
        self.transport.receive(Event('guarded-announce-result', {'op': 'status', 'request_id': 'other', 'status': 'completed'}))
        self.assertFalse(task.done())
        self.transport.receive(Event('guarded-announce-result', {'op': 'status', 'request_id': ID, 'status': 'unknown'}))
        self.assertEqual((await task)['status'], 'unknown')
    async def test_generation_mismatch_prevents_new_connection_send(self):
        generation = self.transport.generation
        self.transport.disconnected()
        with self.assertRaisesRegex(ConnectionError, 'satellite_reconnected'):
            await self.transport.send('audio-start', ID, _generation=generation)
        self.assertEqual(self.sent, [])
    async def test_services_require_response_and_permission(self):
        self.assertEqual(set(self.ha.registered), {'announcement_submit', 'announcement_status', 'announcement_stop', 'announcement_capabilities'})
        self.assertTrue(all(kw['supports_response'] == 'only' for _, kw in self.ha.registered.values()))
        self.ha.allowed = False
        with self.assertRaisesRegex(HomeAssistantError, 'authenticated_entity_control_required'):
            await self.call('announcement_status', {'entity_id': self.entity.entity_id, 'request_id': ID})
        self.assertEqual(self.sent, [])
    async def test_unknown_entity_and_request_cannot_play_or_stop(self):
        with self.assertRaisesRegex(HomeAssistantError, 'guarded_satellite_unavailable'):
            await self.call('announcement_status', {'entity_id': 'media_player.other', 'request_id': ID})
        result = await self.call('announcement_stop', {'entity_id': self.entity.entity_id, 'request_id': ID})
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.sent, [])

    async def test_file_mapping_fallback_and_explicit_option_precedence(self):
        original = dict(self.entity.config_entry.options[adapter.OPTIONS_KEY])
        self.transport.manager.guard_mappings[self.entity.entity_id] = original
        self.entity.config_entry.options = {}
        self.assertEqual(self.transport.busy_reason(), '')
        self.entity.config_entry.options[adapter.OPTIONS_KEY] = dict(original, dnd='test.other_dnd')
        self.ha.values['test.other_dnd'] = types.SimpleNamespace(state='on', attributes={})
        self.assertEqual(self.transport.busy_reason(), 'dnd_busy')
        # An explicit invalid option never falls back to a valid file mapping.
        self.entity.config_entry.options[adapter.OPTIONS_KEY] = {}
        self.assertEqual(self.transport.busy_reason(), 'guard_state_unavailable')

    async def test_guard_file_is_loaded_only_once_by_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / adapter.GUARD_FILE
            mapping = {self.entity.entity_id: dict(self.entity.config_entry.options[adapter.OPTIONS_KEY])}
            path.write_text(json.dumps(mapping))
            ha = HA()
            ha.config.path = lambda name: str(Path(directory) / name)
            await adapter.async_setup_guarded(ha)
            self.assertEqual(ha.data[adapter.KEY].guard_mappings, mapping)
            path.write_text('invalid JSON')
            await adapter.async_setup_guarded(ha)
            self.assertEqual(ha.data[adapter.KEY].guard_mappings, mapping)

    async def test_invalid_guard_file_does_not_partially_register_services(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / adapter.GUARD_FILE
            valid = dict(self.entity.config_entry.options[adapter.OPTIONS_KEY])
            path.write_text(json.dumps({self.entity.entity_id: valid, 'assist_satellite.broken': {'room': 'test.room'}}))
            ha = HA(); ha.config.path = lambda name: str(Path(directory) / name)
            with self.assertRaisesRegex(HomeAssistantError, 'Invalid guarded announcement guard file'):
                await adapter.async_setup_guarded(ha)
            self.assertNotIn(adapter.KEY, ha.data)
            self.assertEqual(ha.registered, {})

    def test_guard_file_strict_validation(self):
        valid = {self.entity.entity_id: dict(self.entity.config_entry.options[adapter.OPTIONS_KEY])}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / adapter.GUARD_FILE
            self.assertEqual(adapter.load_guard_file(path), {})
            for raw in ['[]', 'null', '{broken', '{"x":{},"x":{}}', json.dumps({'media_player.wrong': next(iter(valid.values()))}), json.dumps({self.entity.entity_id: {'room': 'test.room'}}), ' ' * 65537]:
                path.write_text(raw)
                with self.subTest(raw=raw[:40]), self.assertRaises(HomeAssistantError):
                    adapter.load_guard_file(path)
            path.write_text(json.dumps(valid))
            self.assertEqual(adapter.load_guard_file(path), valid)

    async def test_rpc_timeout_includes_waiting_for_existing_lock(self):
        await self.transport.rpc_lock.acquire()
        try:
            with patch.object(adapter, 'RPC_TIMEOUT_SECONDS', 0.02):
                # The outer budget is a test watchdog, not the RPC implementation.
                async with asyncio.timeout(0.5):
                    with self.assertRaises(TimeoutError):
                        await self.transport.rpc('status', ID)
            self.assertTrue(self.transport.rpc_lock.locked())
            self.assertEqual(self.transport.pending, {})
            self.assertEqual(self.sent, [])
        finally:
            self.transport.rpc_lock.release()

    async def test_rpc_cancel_waiting_for_lock_preserves_current_owner(self):
        await self.transport.rpc_lock.acquire()
        try:
            task = asyncio.create_task(self.transport.rpc('status', ID))
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(self.transport.rpc_lock.locked())
            self.assertEqual(self.transport.pending, {})
            self.assertEqual(self.sent, [])
        finally:
            self.transport.rpc_lock.release()

    async def test_rpc_cancel_after_send_removes_pending_and_releases_lock(self):
        task = asyncio.create_task(self.transport.rpc('status', ID))
        await asyncio.sleep(0)
        self.assertIn((ID, 'status'), self.transport.pending)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.transport.pending, {})
        self.assertFalse(self.transport.rpc_lock.locked())
        self.transport.receive(Event('guarded-announce-result', {'op': 'status', 'request_id': ID, 'status': 'unknown'}))
        await asyncio.sleep(0)
        self.assertEqual([event.data['op'] for event in self.sent], ['status'])

    async def test_rpc_receive_timeout_removes_pending_and_releases_lock(self):
        with patch.object(adapter, 'RPC_TIMEOUT_SECONDS', 0.02):
            with self.assertRaises(TimeoutError):
                await self.transport.rpc('status', ID)
        self.assertEqual(self.transport.pending, {})
        self.assertFalse(self.transport.rpc_lock.locked())
        self.assertEqual([event.data['op'] for event in self.sent], ['status'])

if __name__ == '__main__': unittest.main()
