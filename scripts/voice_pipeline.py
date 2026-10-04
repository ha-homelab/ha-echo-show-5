#!/usr/bin/env python3
"""Guarded HA voice-backend switching (Python 3.8+, install dependency: aiohttp).

Set an HTTPS HA_URL and exactly one of HA_TOKEN or HA_TOKEN_FILE. HTTP is allowed
for loopback or with the explicit HA_ALLOW_INSECURE_HTTP=1 operator opt-in.
Mapping and snapshots
belong under this project's ignored private/ directory. status is read-only;
switch/restore are dry runs unless --apply is supplied. --include-default is a
separate opt-in for HA's global preferred pipeline, including during restore.

HA has no transactional compare-and-set API. This tool rechecks values/revisions
before writes, verifies readback, and refuses observable drift; an external write
between check and service execution (or an identical preferred-value rewrite)
cannot be excluded. Stop competing automations while switching. A failed or
interrupted request with an unknown outcome is journaled for manual inspection.
No raw HA errors, URLs, tokens, pipeline names or entity IDs are printed.
"""
import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit, urlunsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = ('homeway', 'fcc')
ENGINE_FIELDS = {'stt_engine': 'stt', 'tts_engine': 'tts',
                 'conversation_engine': 'conversation'}


class SafeError(Exception):
    """A fixed diagnostic code, safe to show without raw server data."""


def require(condition, code):
    if not condition:
        raise SafeError(code)


def text_value(value):
    return isinstance(value, str) and 0 < len(value) <= 255 and not any(
        ord(char) < 32 for char in value)


def private_path(path):
    private = ROOT.resolve() / 'private'
    require(private.resolve() == private, 'private_directory_symlink')
    destination = Path(os.path.abspath(str(path)))
    require(destination.resolve() == destination and private in destination.parents,
            'path_must_be_inside_project_private')
    return destination


def read_json(path):
    try:
        return json.loads(private_path(path).read_text())
    except SafeError:
        raise
    except (OSError, ValueError):
        raise SafeError('private_json_read_failed') from None


def _fsync_directory(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_snapshot(path, value, initial=False):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Persist every directory entry down from the existing repository root.
    # Syncing only the leaf would not preserve newly created parent directories.
    parent = path.parent
    ancestors = []
    while parent != ROOT.resolve():
        ancestors.append(parent.parent)
        parent = parent.parent
    for ancestor in reversed(ancestors):
        _fsync_directory(ancestor)
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if initial:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_directory(path.parent)
        return
    fd, temporary = tempfile.mkstemp(prefix='.voice-pipeline-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def mutation_lock(origin):
    import fcntl
    path = private_path(ROOT / 'private' / ('voice-pipeline-' + origin[:16] + '.lock'))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600), 'w') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafeError('another_local_switch_is_running') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def load_mapping(value):
    require(isinstance(value, dict) and set(value) ==
            {'version', 'backends', 'assistant_selects'} and value['version'] == 1,
            'invalid_mapping')
    backends = value['backends']
    require(isinstance(backends, dict) and set(backends) == set(BACKENDS), 'invalid_backends')
    for backend in backends.values():
        require(isinstance(backend, dict) and set(backend) == {'pipeline'}, 'invalid_backend')
        ref = backend['pipeline']
        require(isinstance(ref, dict) and set(ref) in ({'id'}, {'name'}) and
                all(text_value(item) and 'replace_me' not in item for item in ref.values()),
                'pipeline_requires_exact_id_or_name')
    entities = value['assistant_selects']
    require(isinstance(entities, list) and 1 <= len(entities) <= 16 and
            all(isinstance(item, str) and re.fullmatch(r'select\.[a-z0-9_]+', item)
                and 'replace_me' not in item for item in entities), 'invalid_assistant_selects')
    require(len(entities) == len(set(entities)), 'duplicate_assistant_select')
    return value


def credentials(environ):
    raw = environ.get('HA_URL', '')
    try:
        parsed = urlsplit(raw)
        require(parsed.scheme in ('http', 'https') and parsed.hostname and
                not parsed.username and not parsed.password and not parsed.query and
                not parsed.fragment, 'invalid_ha_url')
        parsed.port
    except (ValueError, SafeError):
        raise SafeError('invalid_ha_url') from None
    require(parsed.scheme == 'https' or
            parsed.hostname in ('localhost', '127.0.0.1', '::1') or
            environ.get('HA_ALLOW_INSECURE_HTTP') == '1', 'ha_url_requires_https')
    url = urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
    token, token_file = environ.get('HA_TOKEN'), environ.get('HA_TOKEN_FILE')
    require(bool(token) != bool(token_file), 'set_exactly_one_token_source')
    if token_file:
        try:
            token = Path(token_file).read_text().strip()
        except OSError:
            raise SafeError('token_file_read_failed') from None
    require(isinstance(token, str) and token.strip() == token and token and
            not any(char.isspace() for char in token), 'invalid_ha_token')
    return url, token


class HAClient:
    """Sequential WS client; aiohttp is optional until a live command is run."""
    def __init__(self, url, token):
        self.url, self.token = url, token
        self.origin = hashlib.sha256(url.encode()).hexdigest()
        self.session = self.ws = None
        self.sequence = 0

    async def __aenter__(self):
        try:
            import aiohttp
        except ImportError:
            raise SafeError('install_aiohttp_dependency') from None
        async def reject_redirect(*args):
            raise SafeError('ha_redirect_rejected')
        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(reject_redirect)
        self.session = aiohttp.ClientSession(trace_configs=[trace],
                                            timeout=aiohttp.ClientTimeout(total=20))
        try:
            address = self.url.replace('https:', 'wss:', 1).replace('http:', 'ws:', 1)
            self.ws = await asyncio.wait_for(
                self.session.ws_connect(address + '/api/websocket', heartbeat=30), 20)
            require((await self.receive()).get('type') == 'auth_required', 'invalid_ha_handshake')
            await self.ws.send_json({'type': 'auth', 'access_token': self.token})
            require((await self.receive()).get('type') == 'auth_ok', 'ha_authentication_failed')
            return self
        except BaseException:
            await self.session.close()
            raise

    async def __aexit__(self, *args):
        await self.session.close()

    async def receive(self):
        message = await asyncio.wait_for(self.ws.receive_json(), 15)
        require(isinstance(message, dict), 'invalid_ha_message')
        return message

    async def request(self, kind, **data):
        self.sequence += 1
        request_id = self.sequence
        await self.ws.send_json(dict(data, id=request_id, type=kind))
        async def result():
            while True:
                message = await self.receive()
                if message.get('id') != request_id:
                    continue
                require(message.get('type') == 'result', 'invalid_ha_result')
                require(message.get('success') is True, 'ha_request_rejected')
                return message.get('result')
        return await asyncio.wait_for(result(), 20)

    async def inventory(self):
        pipelines = await self.request('assist_pipeline/pipeline/list')
        states = await self.request('get_states')
        require(isinstance(pipelines, dict) and isinstance(pipelines.get('pipelines'), list)
                and isinstance(states, list), 'invalid_ha_inventory')
        return {'pipelines': pipelines['pipelines'],
                'preferred': pipelines.get('preferred_pipeline'),
                'states': {row['entity_id']: row for row in states}}

    async def write(self, change, value):
        if change['kind'] == 'preferred':
            await self.request('assist_pipeline/pipeline/set_preferred', pipeline_id=value)
        else:
            await self.request('call_service', domain='select', service='select_option',
                               service_data={'entity_id': change['entity_id'], 'option': value})


def resolve_pipeline(inventory, reference):
    key, value = next(iter(reference.items()))
    matches = [item for item in inventory['pipelines'] if item.get(key) == value]
    require(len(matches) == 1, 'pipeline_missing_or_ambiguous')
    pipeline = matches[0]
    require(text_value(pipeline.get('id')) and text_value(pipeline.get('name')),
            'invalid_pipeline')
    require(sum(item.get('name') == pipeline['name'] for item in inventory['pipelines']) == 1,
            'pipeline_name_not_unique')
    return pipeline


def validate_engines(inventory, pipeline):
    for key, domain in ENGINE_FIELDS.items():
        entity = pipeline.get(key)
        require(isinstance(entity, str) and re.fullmatch(domain + r'\.[a-z0-9_]+', entity),
                'pipeline_requires_entity_engines')
        row = inventory['states'].get(entity)
        # Stateless providers normally report unknown; unavailable is the failure state.
        require(isinstance(row, dict) and isinstance(row.get('state'), str) and
                row['state'] != 'unavailable', 'pipeline_engine_unavailable')


def selector(inventory, entity):
    row = inventory['states'].get(entity)
    require(isinstance(row, dict), 'assistant_select_missing')
    options = row.get('attributes', {}).get('options')
    require(isinstance(options, list) and all(text_value(item) for item in options),
            'invalid_assistant_options')
    require(row.get('state') not in ('unavailable', 'unknown') and row.get('state') in options,
            'assistant_select_unavailable')
    require(text_value(row.get('last_updated')), 'assistant_revision_missing')
    return row, options


def observe(inventory, change):
    if change['kind'] == 'preferred':
        value = inventory['preferred']
        require(text_value(value), 'preferred_pipeline_missing')
        return {'value': value}
    row, _ = selector(inventory, change['entity_id'])
    return {'value': row['state'], 'revision': row['last_updated'],
            'context': row.get('context', {}).get('id')}


def option_pipeline(inventory, option):
    return resolve_pipeline(inventory, {'id': inventory['preferred']} if option == 'preferred'
                            else {'name': option})


def target_available(inventory, change, value, engines=True):
    if change['kind'] == 'preferred':
        pipeline = resolve_pipeline(inventory, {'id': value})
    else:
        _, options = selector(inventory, change['entity_id'])
        require(value in options, 'target_not_in_assistant_options')
        pipeline = option_pipeline(inventory, value) if engines else None
    if engines:
        if 'target_pipeline_id' in change:
            require(pipeline['id'] == change['target_pipeline_id'], 'target_pipeline_changed')
        validate_engines(inventory, pipeline)


def plan_switch(inventory, mapping, backend, include_default=False):
    pipeline = resolve_pipeline(inventory, mapping['backends'][backend]['pipeline'])
    validate_engines(inventory, pipeline)
    changes = []
    for entity in mapping['assistant_selects']:
        item = {'kind': 'select', 'entity_id': entity, 'after_value': pipeline['name'],
                'target_pipeline_id': pipeline['id']}
        target_available(inventory, item, item['after_value'])
        item['before'] = observe(inventory, item)
        item['before_pipeline_id'] = option_pipeline(inventory, item['before']['value'])['id']
        if item['before']['value'] != item['after_value']:
            changes.append(item)
    if include_default:
        item = {'kind': 'preferred', 'after_value': pipeline['id'],
                'target_pipeline_id': pipeline['id']}
        item['before'] = observe(inventory, item)
        item['before_pipeline_id'] = item['before']['value']
        if item['before']['value'] != item['after_value']:
            changes.append(item)
    return changes


def status(inventory, mapping):
    result = {'command': 'status', 'backends': {}, 'selectors': []}
    names = {}
    for backend in BACKENDS:
        try:
            pipeline = resolve_pipeline(inventory, mapping['backends'][backend]['pipeline'])
            names[backend] = pipeline['name']
            plan_switch(inventory, mapping, backend)
            result['backends'][backend] = {'ready': True}
        except SafeError as exc:
            result['backends'][backend] = {'ready': False, 'reason': str(exc)}
    for index, entity in enumerate(mapping['assistant_selects']):
        row = inventory['states'].get(entity, {})
        try:
            selector(inventory, entity)
            available = True
        except SafeError:
            available = False
        result['selectors'].append({'index': index, 'available': available,
            'backend': next((key for key, value in names.items() if value == row.get('state')), None)})
    return result


def validate_snapshot(snapshot, origin, include_default):
    require(isinstance(snapshot, dict) and snapshot.get('version') == 1 and
            snapshot.get('origin_sha256') == origin, 'snapshot_instance_mismatch')
    changes = snapshot.get('changes')
    require(isinstance(changes, list) and len(changes) <= 17, 'invalid_snapshot')
    seen = set()
    for item in changes:
        require(isinstance(item, dict) and item.get('kind') in ('select', 'preferred'),
                'invalid_snapshot_change')
        entity = item.get('entity_id', '')
        if item['kind'] == 'select':
            require(isinstance(entity, str) and re.fullmatch(r'select\.[a-z0-9_]+', entity),
                    'invalid_snapshot_entity')
        else:
            require(include_default, 'default_restore_requires_include_default')
        identity = (item['kind'], entity)
        require(identity not in seen, 'duplicate_snapshot_change')
        seen.add(identity)
        require(isinstance(item.get('before'), dict) and text_value(item['before'].get('value'))
                and text_value(item.get('after_value'))
                and text_value(item.get('before_pipeline_id'))
                and text_value(item.get('target_pipeline_id')), 'invalid_snapshot_value')
        require(item.get('status') in ('applied', 'rolled_back', 'restored', 'planned'),
                'snapshot_has_uncertain_changes')
        if item['status'] == 'applied':
            require(isinstance(item.get('after'), dict) and
                    item['after'].get('value') == item['after_value'], 'invalid_snapshot_readback')
            if item['kind'] == 'select':
                require(text_value(item['after'].get('revision')), 'invalid_snapshot_revision')
    return changes


async def wait_value(client, change, value):
    # Successful service responses can precede an integration's state publication.
    for attempt in range(10):
        current = observe(await client.inventory(), change)
        if current['value'] == value:
            return current
        if attempt != 9:
            await asyncio.sleep(0.2)
    raise SafeError('write_readback_not_confirmed')


async def rollback(client, journal, snapshot_path):
    complete = True
    for item in reversed(journal['changes']):
        if item['status'] != 'applied':
            if item['status'] == 'write_pending':
                complete = False
            continue
        try:
            inventory = await client.inventory()
            require(observe(inventory, item) == item['after'], 'rollback_concurrent_change')
            target_available(inventory, item, item['before']['value'], engines=False)
            item['status'] = 'rollback_pending'
            save_snapshot(snapshot_path, journal)
            await client.write(item, item['before']['value'])
            await wait_value(client, item, item['before']['value'])
            item['status'] = 'rolled_back'
        except Exception:
            complete = False
            if item['status'] == 'applied':
                item['status'] = 'conflict'
        save_snapshot(snapshot_path, journal)
    return complete


async def execute(client, changes, snapshot_path, operation='switch'):
    if not changes:
        return {'command': operation, 'applied': False, 'changes': 0, 'noop': True}
    journal = {'version': 1, 'origin_sha256': client.origin,
               'created_at': datetime.now(timezone.utc).isoformat(),
               'operation': operation, 'changes': [dict(item, status='planned') for item in changes]}
    save_snapshot(snapshot_path, journal, initial=True)
    try:
        for item in journal['changes']:
            inventory = await client.inventory()
            require(observe(inventory, item) == item['before'], 'concurrent_change_detected')
            target_available(inventory, item, item['after_value'])
            item['status'] = 'write_pending'
            save_snapshot(snapshot_path, journal)
            await client.write(item, item['after_value'])
            item['after'] = await wait_value(client, item, item['after_value'])
            item['status'] = 'applied'
            save_snapshot(snapshot_path, journal)
        # Recheck all completed writes; do not quietly accept an external overwrite.
        inventory = await client.inventory()
        require(all(observe(inventory, item) == item['after'] for item in journal['changes']),
                'concurrent_change_detected')
    except (Exception, asyncio.CancelledError):
        complete = await rollback(client, journal, snapshot_path)
        raise SafeError('switch_failed_rolled_back' if complete else
                        'switch_failed_manual_recovery_required') from None
    return {'command': operation, 'applied': True, 'changes': len(changes), 'noop': False,
            'snapshot': str(private_path(snapshot_path).relative_to(ROOT.resolve()))}


async def plan_restore(client, snapshot, include_default=False):
    entries = validate_snapshot(snapshot, client.origin, include_default)
    inventory = await client.inventory()
    target_inventory = dict(inventory)
    changes = []
    for item in reversed(entries):
        if item['status'] != 'applied':
            continue
        require(observe(inventory, item) == item['after'], 'restore_concurrent_change')
        change = {'kind': item['kind'], 'before': item['after'],
                  'after_value': item['before']['value'],
                  'target_pipeline_id': item['before_pipeline_id'],
                  'before_pipeline_id': item['target_pipeline_id']}
        if item['kind'] == 'select':
            change['entity_id'] = item['entity_id']
        target_available(target_inventory, change, change['after_value'])
        if item['kind'] == 'preferred':
            target_inventory['preferred'] = change['after_value']
        changes.append(change)
    return changes


def generated_snapshot():
    return ROOT / 'private' / 'voice-pipeline' / (uuid.uuid4().hex + '.json')


async def run(args):
    url, token = credentials(os.environ)
    async with HAClient(url, token) as client:
        if args.command == 'restore':
            original = read_json(args.snapshot)
            changes = await plan_restore(client, original, args.include_default)
            if not args.apply:
                return {'command': 'restore', 'dry_run': True, 'changes': len(changes)}
            with mutation_lock(client.origin):
                changes = await plan_restore(client, original, args.include_default)
                result = await execute(client, changes, generated_snapshot(), operation='restore')
                for item in original['changes']:
                    if item['status'] == 'applied':
                        item['status'] = 'restored'
                save_snapshot(args.snapshot, original)
                return result
        require(args.mapping is not None, 'mapping_required')
        mapping = load_mapping(read_json(args.mapping))
        inventory = await client.inventory()
        if args.command == 'status':
            return status(inventory, mapping)
        changes = plan_switch(inventory, mapping, args.backend, args.include_default)
        if not args.apply:
            return {'command': 'switch', 'backend': args.backend, 'dry_run': True,
                    'changes': len(changes), 'includes_default': args.include_default}
        snapshot = args.snapshot or generated_snapshot()
        with mutation_lock(client.origin):
            changes = plan_switch(await client.inventory(), mapping, args.backend, args.include_default)
            return await execute(client, changes, snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, help='JSON mapping under project private/')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    switch = commands.add_parser('switch')
    switch.add_argument('--backend', choices=BACKENDS, required=True)
    switch.add_argument('--snapshot', type=Path, help='New private snapshot (never overwritten)')
    restore = commands.add_parser('restore')
    restore.add_argument('--snapshot', type=Path, required=True)
    for command in (switch, restore):
        mode = command.add_mutually_exclusive_group()
        mode.add_argument('--apply', action='store_true', help='Apply; omitted means dry run')
        mode.add_argument('--dry-run', action='store_true', help='Explicit read-only preview (default)')
        command.add_argument('--include-default', action='store_true',
                             help='Explicitly include HA global preferred pipeline')
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args)), sort_keys=True))
    except SafeError as exc:
        parser.exit(1, 'Voice pipeline operation stopped: ' + str(exc) + '\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Interrupted; inspect the private snapshot before retrying.\n')
    except Exception:
        parser.exit(1, 'Voice pipeline operation failed; inspect the private snapshot and connectivity.\n')


if __name__ == '__main__':
    main()
