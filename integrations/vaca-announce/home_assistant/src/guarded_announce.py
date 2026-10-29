"""HA adapter for the additive guarded VACA announcement protocol."""
from __future__ import annotations
import asyncio
import hashlib
import json
import math
import re
import uuid
from urllib.parse import urlsplit
from pathlib import Path
import aiohttp
from wyoming.event import Event
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import ffmpeg
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from .guarded_announce_core import (
    AnnouncementError, AnnouncementManager, CAPABILITIES, PROTOCOL, MAX_ENCODED_BYTES,
    STATUSES, decode_pcm, validate_id,
)

KEY = 'vaca_guarded_announcements'
RPC_TIMEOUT_SECONDS = 5.0
OPTIONS_KEY = 'guarded_announcement_guards'
GUARD_FILE = 'vaca_guarded_announcement_guards.json'
ENTITY_ID = re.compile(r'[a-z0-9_]+\.[a-z0-9_]+\Z')
GUARDS = {'room': {'idle'}, 'intercom': {'idle'}, 'dnd': {'off'},
          'media': {'idle', 'paused', 'off'}, 'sip': {'idle'}}
PROXY_PATH = re.compile(r'/api/tts_proxy/[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z')

def valid_guard_mapping(mapping):
    return isinstance(mapping, dict) and set(mapping) == set(GUARDS) and all(
        isinstance(value, str) and ENTITY_ID.fullmatch(value) for value in mapping.values())


def load_guard_file(path):
    """Read one bounded private mapping, rejecting duplicate keys and partial data."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate mapping key')
            result[key] = value
        return result
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(65537)
    except FileNotFoundError:
        return {}
    except OSError:
        raise HomeAssistantError('Cannot read guarded announcement guard file') from None
    try:
        if len(raw) > 65536:
            raise ValueError('Mapping too large')
        result = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(result, dict) or len(result) > 256:
            raise ValueError('Invalid mapping')
        for entity_id, mapping in result.items():
            if not ENTITY_ID.fullmatch(entity_id) or not entity_id.startswith('assist_satellite.') or not valid_guard_mapping(mapping):
                raise ValueError('Invalid mapping')
        return result
    except (ValueError, TypeError, UnicodeError):
        raise HomeAssistantError('Invalid guarded announcement guard file') from None


def unsupported(reason='guarded_protocol_unavailable'):
    return dict(protocol=PROTOCOL, **{key: False for key in CAPABILITIES},
                guard_scope='coordinated_vaca_sip', external_busy_policy='observe_and_abort',
                global_android_exclusion=False, reason=reason)

def validate_journal(data):
    if data is None:
        return {}
    if not isinstance(data, dict) or len(data) > 1024:
        raise HomeAssistantError('Invalid guarded announcement receipt store')
    for key, record in data.items():
        try:
            validate_id(record['request_id'])
            valid = (
                record['status'] in STATUSES
                and isinstance(record['entity_id'], str)
                and record['entity_id'].startswith('assist_satellite.')
                and key == AnnouncementManager.key(record['entity_id'], record['request_id'])
                and isinstance(record['expires_at'], (float, int))
                and math.isfinite(record['expires_at'])
                and re.fullmatch(r'[0-9a-f]{64}', record['owner'])
                and re.fullmatch(r'[0-9a-f]{64}', record['fingerprint'])
                and isinstance(record['claimed'], bool)
                and isinstance(record['claim_sent'], bool)
            )
            if not valid:
                raise ValueError('Invalid receipt')
        except (KeyError, TypeError, AssertionError, ValueError):
            raise HomeAssistantError('Invalid guarded announcement receipt store') from None
    return data

async def async_setup_guarded(hass):
    if KEY in hass.data:
        return
    guard_mappings = await hass.async_add_executor_job(load_guard_file, hass.config.path(GUARD_FILE))
    store = Store(hass, 1, KEY)
    manager = AnnouncementManager(store.async_save, records=validate_journal(await store.async_load()), guard_mappings=guard_mappings)
    await manager.persist()
    hass.data[KEY] = manager
    async def handle(call):
        try:
            data = dict(call.data)
            entity_id = data.pop('entity_id', None)
            if not isinstance(entity_id, str) or entity_id not in manager.adapters:
                raise AnnouncementError('guarded_satellite_unavailable')
            user_id = call.context.user_id
            user = await hass.auth.async_get_user(user_id) if user_id else None
            if user is None or not user.is_active or not user.permissions.check_entity(entity_id, POLICY_CONTROL):
                raise AnnouncementError('authenticated_entity_control_required')
            owner = hashlib.sha256(user_id.encode()).hexdigest()
            if call.service == 'announcement_capabilities':
                if data:
                    raise AnnouncementError('unexpected_fields')
                return await manager.adapters[entity_id].capabilities()
            if call.service == 'announcement_submit':
                return await manager.submit(entity_id, owner, data)
            if set(data) != {'request_id'}:
                raise AnnouncementError('unexpected_fields')
            if call.service == 'announcement_status':
                return await manager.status(entity_id, data['request_id'])
            return await manager.stop(entity_id, owner, data['request_id'])
        except AnnouncementError as exc:
            raise HomeAssistantError(str(exc)) from None
    for name in ('announcement_submit', 'announcement_status', 'announcement_stop', 'announcement_capabilities'):
        hass.services.async_register('vaca', name, handle, supports_response=SupportsResponse.ONLY)

class GuardedTransport:
    def __init__(self, entity):
        self.entity = entity
        self.pending = {}
        self.generation = 0
        self.rpc_lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()

    @property
    def manager(self):
        return self.entity.hass.data[KEY]

    async def added(self):
        self.manager.adapters[self.entity.entity_id] = self

    async def removed(self):
        await self.manager.detach(self.entity.entity_id, self)
        self.disconnected()

    def disconnected(self):
        old_generation = self.generation
        self.generation += 1
        if self.entity.entity_id and KEY in self.entity.hass.data:
            self.entity.hass.async_create_task(self.manager.connection_lost(self.entity.entity_id, self, old_generation))
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ConnectionError('satellite_disconnected'))

    def guard_mapping(self):
        options = self.entity.config_entry.options
        if OPTIONS_KEY in options:
            return options[OPTIONS_KEY]
        return self.manager.guard_mappings.get(self.entity.entity_id, {})

    def guard_states(self):
        mapping = self.guard_mapping()
        if not valid_guard_mapping(mapping):
            return None
        states = {}
        for role, entity_id in mapping.items():
            if not isinstance(entity_id, str):
                return None
            state = self.entity.hass.states.get(entity_id)
            if state is None or state.state in {'unknown', 'unavailable'}:
                return None
            states[role] = state.state
        return states

    def backend_busy_reason(self):
        backend = self.entity.hass.data.get('show5_intercom')
        if backend is None:
            return ''
        try:
            if backend.recovery_pending or backend.guard.cleanup_error:
                return 'intercom_recovery_pending'
            if backend.guard.active is not None or backend.room.call is not None or backend.guard.lock.locked() or backend.room.lock.locked():
                return 'intercom_busy'
        except AttributeError:
            return 'guard_state_unavailable'
        return ''

    def busy_reason(self):
        if reason := self.backend_busy_reason():
            return reason
        states = self.guard_states()
        if states is None:
            return 'guard_state_unavailable'
        for role, state in states.items():
            if state not in GUARDS[role]:
                return role + '_busy'
        mapping = self.guard_mapping()
        room = self.entity.hass.states.get(mapping['room'])
        sip = self.entity.hass.states.get(mapping['sip'])
        if room.attributes.get('busy') is not False or room.attributes.get('owner') != 'idle':
            return 'room_busy'
        if sip.attributes.get('lease_held') is not False or sip.attributes.get('call_id') is not None:
            return 'sip_busy'
        if self.entity.state != 'idle':
            return 'assist_busy'
        return ''

    def validate_media(self, media):
        try:
            parsed = urlsplit(media)
            parsed.port  # Validate malformed ports before any request is accepted.
        except (ValueError, TypeError):
            raise AnnouncementError('invalid_media_id') from None
        if parsed.query or parsed.fragment or parsed.username or parsed.password or not PROXY_PATH.fullmatch(parsed.path):
            raise AnnouncementError('only_prepared_ha_tts_media_supported')
        if parsed.scheme or parsed.netloc:
            origins = set()
            config = self.entity.hass.config
            for url in (config.internal_url, config.external_url):
                if url:
                    part = urlsplit(url)
                    origins.add((part.scheme, part.hostname, part.port or (443 if part.scheme == 'https' else 80)))
            port = config.api.port if config.api else 8123
            origins.add(('http', '127.0.0.1', port))
            if parsed.scheme not in {'http', 'https'} or (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)) not in origins:
                raise AnnouncementError('unapproved_media_origin')
        return parsed.path

    async def decode(self, media):
        path = self.validate_media(media)
        config = self.entity.hass.config
        port = config.api.port if config.api else 8123
        url = f'http://127.0.0.1:{port}' + path
        session = async_get_clientsession(self.entity.hass)
        async with session.get(url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=20)) as response:
            if response.status != 200:
                raise AnnouncementError('audio_fetch_failed')
            if response.content_length is not None and response.content_length > MAX_ENCODED_BYTES:
                raise AnnouncementError('audio_too_large')
            data = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                data.extend(chunk)
                if len(data) > MAX_ENCODED_BYTES:
                    raise AnnouncementError('audio_too_large')
        return await decode_pcm(bytes(data), ffmpeg.get_ffmpeg_manager(self.entity.hass).binary)

    async def send(self, op, request_id, *, payload=None, _generation=None, **data):
        if _generation is not None and _generation != self.generation:
            raise ConnectionError('satellite_reconnected')
        client = self.entity._client
        if client is None or not client.can_write_event():
            raise ConnectionError('satellite_disconnected')
        async with self.send_lock:
            if _generation is not None and _generation != self.generation:
                raise ConnectionError('satellite_reconnected')
            async with asyncio.timeout(5):
                await client.write_event(Event(type='guarded-announce',
                    data=dict(op=op, request_id=request_id, **data), payload=payload))
                if not client.can_write_event():
                    raise ConnectionError('satellite_disconnected')

    async def rpc(self, op, request_id, _generation=None, **data):
        key = (request_id, op)
        # The budget includes queueing for the lock, sending, and receiving.
        # A second HTTP caller must not wait five seconds behind another five.
        async with asyncio.timeout(RPC_TIMEOUT_SECONDS):
            async with self.rpc_lock:
                future = asyncio.get_running_loop().create_future()
                self.pending[key] = future
                try:
                    await self.send(op, request_id, _generation=_generation, **data)
                    return await future
                finally:
                    if self.pending.get(key) is future:
                        self.pending.pop(key, None)

    def receive(self, event):
        if event.type != 'guarded-announce-result':
            return False
        data = event.data
        if not isinstance(data, dict):
            return True
        if not isinstance(data.get('request_id'), str) or not isinstance(data.get('op'), str):
            return True
        key = (data.get('request_id'), data.get('op'))
        future = self.pending.get(key)
        if future is not None and not future.done():
            future.set_result(data)
        if self.entity.entity_id in self.manager.adapters:
            self.entity.hass.async_create_task(self.manager.receipt(self.entity.entity_id, data))
        return True

    async def capabilities(self):
        if self.guard_states() is None:
            return unsupported('guard_state_unavailable')
        request_id = 'announce-' + uuid.uuid4().hex + '-000'
        try:
            data = await self.rpc('capabilities', request_id)
        except Exception:
            return unsupported()
        result = unsupported()
        if data.get('protocol') != PROTOCOL:
            return result
        for key in CAPABILITIES:
            result[key] = data.get(key) is True
        result['reason'] = 'ready' if all(result[key] for key in CAPABILITIES) else 'native_guard_unavailable'
        return result
