"""Correlated idle-only announcements; no Home Assistant dependency."""
from __future__ import annotations
import asyncio
import hashlib
import re
import time

PROTOCOL = 'cisco-announcement-v1'
REQUEST_ID = re.compile(r'announce-[0-9a-f]{32}-[0-9]{3}\Z')
CAPABILITIES = ('atomic_idle_guard', 'dedup', 'owned_cancel', 'honest_completion', 'deadline_enforced')
BUSY_POLICIES = frozenset({'skip', 'duck_music'})
STATUSES = frozenset({'accepted', 'playing', 'completed', 'skipped', 'failed', 'stopped', 'unknown'})
TERMINAL = frozenset({'completed', 'skipped', 'failed', 'stopped'})
MAX_SECONDS = 300
MAX_AUDIO_SECONDS = 120
MAX_PCM_BYTES = 22050 * 2 * MAX_AUDIO_SECONDS
MAX_ENCODED_BYTES = 8 * 1024 * 1024

class AnnouncementError(ValueError):
    """A deliberately non-sensitive public error."""

def validate_id(value):
    if not isinstance(value, str) or not REQUEST_ID.fullmatch(value):
        raise AnnouncementError('invalid_request_id')
    return value

def busy_policy(value='skip'):
    if not isinstance(value, str) or value not in BUSY_POLICIES:
        raise AnnouncementError('unsupported_policy')
    return value

def validate_submission(data, now):
    if set(data) - {'request_id', 'media_id', 'expires_at', 'preannounce', 'busy_policy'}:
        raise AnnouncementError('unexpected_fields')
    request_id = validate_id(data.get('request_id'))
    media = data.get('media_id')
    if not isinstance(media, str) or not media or len(media) > 4096:
        raise AnnouncementError('invalid_media_id')
    expiry = data.get('expires_at')
    if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or not now < expiry <= now + MAX_SECONDS:
        raise AnnouncementError('expired_or_invalid_deadline')
    busy_policy(data.get('busy_policy', 'skip'))
    if data.get('preannounce', False) is not False:
        raise AnnouncementError('unsupported_policy')
    return request_id, media, float(expiry)

def capable(data, policy='skip'):
    if not isinstance(data, dict) or data.get('protocol') != PROTOCOL or not all(data.get(key) is True for key in CAPABILITIES):
        return False
    return policy == 'skip' or (policy == 'duck_music' and data.get('duck_music') is True
        and data.get('duck_music_player') == 'vaca' and data.get('duck_music_scope') == 'owned_player')

def public(record):
    return {key: record[key] for key in ('request_id', 'status', 'reason') if key in record}

def digest(media, expiry, policy='skip'):
    policy = busy_policy(policy)
    original = media + '\n' + repr(expiry)
    value = original if policy == 'skip' else 'duck_music\n' + original
    return hashlib.sha256(value.encode()).hexdigest()

def media_fingerprint(media, policy='skip'):
    policy = busy_policy(policy)
    value = media if policy == 'skip' else 'duck_music\n' + media
    return hashlib.sha256(value.encode()).hexdigest()

def safe_reason(value):
    return value if isinstance(value, str) and re.fullmatch(r'[a-z0-9_]{1,80}', value) else 'device_receipt'

async def decode_pcm(encoded, binary, *, timeout=20):
    """Decode bounded bytes; ffmpeg never receives a URL or credentials."""
    if not encoded or len(encoded) > MAX_ENCODED_BYTES:
        raise AnnouncementError('invalid_audio_size')
    proc = await asyncio.create_subprocess_exec(
        binary, '-nostdin', '-hide_banner', '-loglevel', 'error', '-protocol_whitelist', 'pipe', '-i', 'pipe:0',
        '-f', 's16le', '-ac', '1', '-ar', '22050', 'pipe:1',
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    async def feed():
        try:
            proc.stdin.write(encoded)
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            proc.stdin.close()
    writer = asyncio.create_task(feed())
    try:
        async with asyncio.timeout(timeout):
            output = bytearray()
            while block := await proc.stdout.read(16384):
                output.extend(block)
                if len(output) > MAX_PCM_BYTES:
                    raise AnnouncementError('audio_too_long')
            await writer
            if await proc.wait() != 0:
                raise AnnouncementError('decode_failed')
            if not output or len(output) % 2:
                raise AnnouncementError('empty_or_invalid_audio')
            return bytes(output)
    except TimeoutError as exc:
        raise AnnouncementError('decode_timeout') from exc
    finally:
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        # Drain pipe backpressure after termination so subprocess transports close.
        while await proc.stdout.read(16384):
            pass
        await proc.wait()

class AnnouncementManager:
    """Persist reservation before side effects; never replay an uncertain attempt."""
    def __init__(self, save, *, clock=time.time, records=None, guard_mappings=None):
        self.save, self.clock = save, clock
        self.lock = asyncio.Lock()
        self.records = records or {}
        self.guard_mappings = guard_mappings or {}
        self.adapters = {}
        self.tasks = {}
        self.task_owners = {}
        for record in self.records.values():
            if record.get('status') in {'accepted', 'playing'}:
                record.update(status='unknown', reason='home_assistant_restarted')

    @staticmethod
    def key(entity, request_id):
        return entity + ':' + request_id

    async def persist(self):
        await self.save({key: dict(value) for key, value in self.records.items()})

    async def set_status(self, key, status, reason=''):
        async with self.lock:
            record = self.records[key]
            if record['status'] not in TERMINAL:
                record.update(status=status, reason=reason)
                await self.persist()
            return public(record)

    async def submit(self, entity, owner, data):
        request_id = validate_id(data.get('request_id'))
        media, raw_expiry = data.get('media_id'), data.get('expires_at')
        if not isinstance(media, str) or isinstance(raw_expiry, bool) or not isinstance(raw_expiry, (float, int)):
            raise AnnouncementError('invalid_submission')
        # Validate all policy fields even when this is a duplicate.
        policy = busy_policy(data.get('busy_policy', 'skip'))
        if set(data) - {'request_id', 'media_id', 'expires_at', 'preannounce', 'busy_policy'} or data.get('preannounce', False) is not False:
            raise AnnouncementError('unsupported_policy')
        fingerprint = digest(media, float(raw_expiry), policy)
        key = self.key(entity, request_id)
        async with self.lock:
            existing = self.records.get(key)
            if existing:
                if existing['owner'] != owner or existing['fingerprint'] != fingerprint:
                    raise AnnouncementError('request_conflict')
                return public(existing)
            request_id, media, expiry = validate_submission(data, self.clock())
            adapter = self.adapters.get(entity)
            if adapter is None:
                raise AnnouncementError('satellite_unavailable')
            adapter.validate_media(media)
            for old in list(self.records):
                record = self.records[old]
                if record['expires_at'] < self.clock() - 86400 and record['status'] in TERMINAL | {'unknown'}:
                    del self.records[old]
            if len(self.records) >= 1024:
                raise AnnouncementError('receipt_capacity_reached')
            if any(r['entity_id'] == entity and r['status'] in {'accepted', 'playing'} for r in self.records.values()):
                status, reason = 'skipped', 'announcement_busy'
            elif reason := adapter.busy_reason(policy):
                status = 'skipped'
            else:
                status, reason = 'accepted', 'queued'
            record = dict(entity_id=entity, request_id=request_id, owner=owner, fingerprint=fingerprint,
                          expires_at=expiry, status=status, reason=reason, claimed=False, claim_sent=False, busy_policy=policy)
            self.records[key] = record
            try:
                await self.persist()
            except Exception:
                del self.records[key]
                raise AnnouncementError('receipt_storage_failed') from None
            if status == 'accepted':
                generation = getattr(adapter, 'generation', 0)
                self.task_owners[key] = (adapter, generation)
                task = asyncio.create_task(self.run(key, media, adapter, generation))
                self.tasks[key] = task
                def finished(_):
                    if self.tasks.get(key) is task:
                        self.tasks.pop(key, None)
                        self.task_owners.pop(key, None)
                task.add_done_callback(finished)
            return public(record)

    async def run(self, key, media, adapter, generation):
        record = self.records[key]
        request_id = record['request_id']
        policy = record.get('busy_policy', 'skip')
        try:
            async with asyncio.timeout(max(0.001, record['expires_at'] - self.clock())):
                if not capable(await adapter.capabilities(), policy):
                    await self.set_status(key, 'skipped', 'duck_music_unavailable' if policy == 'duck_music' else 'guarded_protocol_unavailable')
                    return
                pcm = await adapter.decode(media)
                if not pcm or len(pcm) > MAX_PCM_BYTES or len(pcm) % 2:
                    raise AnnouncementError('empty_or_invalid_audio')
                if self.clock() + len(pcm) / 44100 + 1 >= record['expires_at']:
                    await self.set_status(key, 'skipped', 'insufficient_time')
                    return
                if getattr(adapter, 'generation', 0) != generation:
                    raise AnnouncementError('satellite_reconnected')
                if reason := adapter.busy_reason(policy):
                    await self.set_status(key, 'skipped', reason)
                    return
                async with self.lock:
                    record['claim_sent'] = True
                    await self.persist()
                reply = await adapter.rpc('claim', request_id, expires_at=int(record['expires_at']),
                                          payload_fingerprint=media_fingerprint(media, policy), _generation=generation,
                                          **({'busy_policy': policy} if policy != 'skip' else {}))
                status = reply.get('status')
                if (policy == 'duck_music' and status in {'accepted', 'playing', 'completed', 'stopped'}
                        and reply.get('busy_policy') != policy):
                    await self.set_status(key, 'unknown', 'invalid_policy_receipt')
                    await self.cancel_native(adapter, request_id)
                    return
                if status not in {'accepted', 'playing'}:
                    await self.set_status(key, status if status in STATUSES else 'unknown', safe_reason(reply.get('reason')))
                    return
                deduplicated = reply.get('deduplicated')
                if not isinstance(deduplicated, bool) or (status == 'playing' and not deduplicated):
                    await self.set_status(key, 'unknown', 'invalid_claim_receipt')
                    return
                async with self.lock:
                    record['claimed'] = True
                    await self.persist()
                if record['status'] in TERMINAL:
                    return
                if deduplicated:
                    await self.set_status(key, status, 'existing_native_request')
                    while record['status'] not in TERMINAL:
                        if reason := adapter.busy_reason(policy):
                            raise AnnouncementError(reason)
                        await self.status(record['entity_id'], request_id)
                        await asyncio.sleep(0.35)
                    return
                await adapter.send('audio-start', request_id, rate=22050, width=2, channels=1, _generation=generation)
                for sequence, offset in enumerate(range(0, len(pcm), 16384)):
                    if record['status'] in TERMINAL:
                        return
                    if reason := adapter.busy_reason(policy):
                        raise AnnouncementError(reason)
                    await adapter.send('audio-chunk', request_id, payload=pcm[offset:offset + 16384], sequence=sequence, _generation=generation)
                await adapter.send('audio-stop', request_id, _generation=generation)
                while record['status'] not in TERMINAL:
                    if reason := adapter.busy_reason(policy):
                        raise AnnouncementError(reason)
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            await self.set_status(key, 'unknown' if record['claim_sent'] else 'failed', 'deadline_or_transport_timeout')
            if record['claim_sent']:
                await self.cancel_native(adapter, request_id)
        except AnnouncementError as exc:
            await self.set_status(key, 'unknown' if record['claim_sent'] else 'failed', str(exc))
            if record['claim_sent']:
                await self.cancel_native(adapter, request_id)
        except Exception:
            await self.set_status(key, 'unknown' if record['claim_sent'] else 'failed', 'transport_or_decode_failed')
            if record['claim_sent']:
                await self.cancel_native(adapter, request_id)

    async def cancel_native(self, adapter, request_id):
        try:
            async with asyncio.timeout(3):
                await adapter.rpc('cancel', request_id)
        except Exception:
            pass

    async def receipt(self, entity, data):
        key = self.key(entity, str(data.get('request_id')))
        status = data.get('status')
        if key not in self.records or status not in STATUSES:
            return
        if data.get('op') not in {'event', 'audio-start', 'audio-chunk', 'audio-stop'}:
            return
        record = self.records[key]
        if record.get('busy_policy', 'skip') == 'duck_music' and data.get('busy_policy') != 'duck_music':
            return
        if not record.get('claim_sent') or status == 'accepted':
            return
        if status == 'playing' and record['status'] == 'unknown':
            return
        await self.set_status(key, status, safe_reason(data.get('reason')))

    async def status(self, entity, request_id):
        validate_id(request_id)
        key = self.key(entity, request_id)
        record = self.records.get(key)
        if not record:
            return dict(request_id=request_id, status='unknown', reason='request_not_found')
        if record['status'] not in TERMINAL and record.get('claim_sent') and entity in self.adapters:
            try:
                reply = await self.adapters[entity].rpc('status', request_id)
                matching_policy = record.get('busy_policy', 'skip') != 'duck_music' or reply.get('busy_policy') == 'duck_music'
                if matching_policy and reply.get('status') in TERMINAL | {'unknown', 'playing'}:
                    await self.set_status(key, reply['status'], safe_reason(reply.get('reason')))
            except Exception:
                pass
        return public(record)

    async def stop(self, entity, owner, request_id):
        validate_id(request_id)
        key = self.key(entity, request_id)
        record = self.records.get(key)
        if not record:
            return dict(request_id=request_id, status='unknown', reason='request_not_found')
        if record['owner'] != owner:
            raise AnnouncementError('request_not_owned')
        if record['status'] in TERMINAL:
            return public(record)
        task = self.tasks.get(key)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        adapter = self.adapters.get(entity)
        if not record.get('claim_sent'):
            return await self.set_status(key, 'stopped', 'cancelled_before_playback')
        if adapter is None:
            return await self.set_status(key, 'unknown', 'satellite_unavailable')
        try:
            reply = await adapter.rpc('cancel', request_id)
            status = reply.get('status')
            if record.get('busy_policy', 'skip') == 'duck_music' and reply.get('busy_policy') != 'duck_music':
                return await self.set_status(key, 'unknown', 'invalid_policy_receipt')
            return await self.set_status(key, status if status in TERMINAL else 'unknown', safe_reason(reply.get('reason')))
        except Exception:
            return await self.set_status(key, 'unknown', 'cancel_unconfirmed')

    async def detach(self, entity, adapter):
        if self.adapters.get(entity) is adapter:
            self.adapters.pop(entity, None)
        await self.connection_lost(entity, adapter)

    async def connection_lost(self, entity, adapter, generation=None):
        for key, task in list(self.tasks.items()):
            owned_adapter, owned_generation = self.task_owners.get(key, (None, None))
            if self.records[key]['entity_id'] == entity and owned_adapter is adapter and (generation is None or owned_generation == generation):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await self.set_status(key, 'unknown', 'satellite_disconnected')
