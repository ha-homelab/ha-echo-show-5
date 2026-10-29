#!/usr/bin/env python3
"""Maintainer-only: derive deterministic patch metadata from a verified source tree."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def build(source):
    edits = {}
    edits['__init__.py'] = [
        ['from .models import DomainDataItem', 'from .models import DomainDataItem\nfrom .guarded_announce import async_setup_guarded'],
        ['    async_register_websocket_api(hass)\n', '    await async_setup_guarded(hass)\n    async_register_websocket_api(hass)\n'],
    ]
    source_text = (source / 'assist_satellite.py').read_text()
    start = source_text.index('    async def async_announce(')
    end = source_text.index('    async def async_start_conversation(', start)
    original = source_text[start:end]
    lines = original.splitlines()
    signature = lines[0]
    body = '\n'.join(lines[1:]).rstrip() + '\n'
    body = body.replace('stderr=asyncio.subprocess.PIPE', 'stderr=asyncio.subprocess.DEVNULL')
    body = body.replace('            assert preannounce_proc.stdout is not None', '            processes.append(preannounce_proc)\n            assert preannounce_proc.stdout is not None')
    body = body.replace('            assert proc.stdout is not None', '            processes.append(proc)\n            assert proc.stdout is not None')
    body = body.replace('        finally:\n            await self._client.write_event(AudioStop().event())',
        '            await asyncio.wait_for(proc.wait(), 5)\n            if proc.returncode != 0 or timestamp == 0:\n                raise ConnectionError("Announcement audio could not be decoded")\n        finally:\n            await self._client.write_event(AudioStop().event())')
    body = body.replace('                    _LOGGER.debug("Did not receive played event for announcement")',
        '                    raise TimeoutError("Announcement playback was not confirmed") from None')
    wrapped = signature + '\n        processes = []\n        try:\n            async with asyncio.timeout(125):\n'
    wrapped += ''.join('        ' + line + '\n' for line in body.splitlines())
    wrapped += '        finally:\n            for process in processes:\n                if process.returncode is None:\n                    process.kill()\n                await process.wait()\n\n'
    edits['assist_satellite.py'] = [
        ['from .entity import VASatelliteEntity', 'from .entity import VASatelliteEntity\nfrom .guarded_announce import GuardedTransport'],
        ['        self.stream_tts = False\n\n    async def on_restart',
         '        self.stream_tts = False\n        self.guarded_announcer = GuardedTransport(self)\n\n    async def async_added_to_hass(self) -> None:\n        await super().async_added_to_hass()\n        await self.guarded_announcer.added()\n\n    async def _disconnect(self) -> None:\n        self.guarded_announcer.disconnected()\n        await super()._disconnect()\n\n    async def on_restart'],
        ['        """Run when entity will be removed from hass."""\n        try:',
         '        """Run when entity will be removed from hass."""\n        await self.guarded_announcer.removed()\n        try:'],
        ['        """Handle received custom events."""\n',
         '        """Handle received custom events."""\n        if event and self.guarded_announcer.receive(event):\n            return False, None\n'],
        [original, wrapped],
    ]
    services_path = source / 'services.yaml'
    services = services_path.read_text() if services_path.exists() else ''
    service_addition = (HERE / 'services.fragment.yaml').read_text()
    if services:
        edits['services.yaml'] = [[services, services.rstrip() + '\n\n' + service_addition]]
    manifest = {}
    for relative, replacements in edits.items():
        before = (source / relative).read_text()
        after = before
        for old, new in replacements:
            if after.count(old) != 1:
                raise ValueError('Ambiguous source anchor: ' + relative)
            after = after.replace(old, new, 1)
        manifest[relative] = {'before_sha256': hashlib.sha256(before.encode()).hexdigest(),
                              'after_sha256': hashlib.sha256(after.encode()).hexdigest(),
                              'replacements': replacements}
    # Keep upstream service definitions out of the patch; append against a unique EOF sentinel.
    if services:
        manifest['services.yaml'].pop('replacements')
        manifest['services.yaml']['append'] = '\n' + service_addition if services.endswith('\n') else '\n\n' + service_addition
    else:
        manifest['services.yaml'] = {'before_sha256': None, 'after_sha256': hashlib.sha256(service_addition.encode()).hexdigest(), 'append': service_addition}
    dependencies = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in ('client.py', 'custom.py', 'entity.py', 'manifest.json')}
    (HERE / 'source-dependencies.json').write_text(json.dumps(dependencies, indent=2) + '\n')
    (HERE / 'overlay.json').write_text(json.dumps(manifest, indent=2) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    build(parser.parse_args().source)
