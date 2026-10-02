#!/usr/bin/env python3
"""Read-only, post-unlock eMMC preservation. This is not a restore procedure.

The caller owns device selection, the operation lock, confirmation and unmounting.
Binary bytes never pass through nas.run's text decoder. Python 3.8 compatible.
"""
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import zlib

from artifacts import ROOT, digest

BLOCKS = {'mmcblk0': '/dev/block/mmcblk0',
          'mmcblk0boot0': '/dev/block/mmcblk0boot0',
          'mmcblk0boot1': '/dev/block/mmcblk0boot1'}
BY_NAME = '/dev/block/platform/bootdevice/by-name/'
REQUIRED = ('boot', 'system', 'userdata', 'metadata', 'persist')
SCOPE = 'post-unlock eMMC user area and boot0/boot1; excludes RPMB; restore not proven'


def _serial(serial):
    if not re.fullmatch(r'[A-Za-z0-9._-]{4,80}', serial or '') or serial in ('.', '..'):
        raise RuntimeError('A complete, safe device serial is required.')


def _private_dir(path):
    relative = path.relative_to(ROOT)
    current = ROOT
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError('Symlink in backup directory.')
        current.mkdir(mode=0o700, exist_ok=True)
        current.chmod(0o700)  # DSM inherited ACLs require an explicit chmod.


def _write(path, text):
    with path.open('x', encoding='utf-8') as out:
        path.chmod(0o600)
        out.write(text)
        out.flush()
        os.fsync(out.fileno())


def _unmounted(text):
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            raise RuntimeError('Malformed mount evidence.')
        source, target = fields[:2]
        if ('mmcblk0' in source or source.startswith(('/dev/block/', '/dev/mapper/'))
                or source == '/dev/root'
                or target in ('/data', '/sdcard', '/cache', '/system', '/persist')):
            raise RuntimeError('Block-backed filesystem still mounted: ' + line)
    if not text.strip():
        raise RuntimeError('Missing mount evidence.')


def validate_gpt(path):
    """Validate both GPT headers, both entry CRCs, mirrors and partition bounds."""
    size = path.stat().st_size
    if size % 512 or size < 68 * 512:
        raise RuntimeError('Invalid eMMC sector geometry.')
    last = size // 512 - 1
    with path.open('rb') as src:
        def header(lba):
            src.seek(lba * 512)
            raw = src.read(512)
            if raw[:8] != b'EFI PART':
                raise RuntimeError('Missing GPT signature.')
            revision, length, checksum, reserved = struct.unpack_from('<IIII', raw, 8)
            if revision != 0x10000 or not 92 <= length <= 512 or reserved:
                raise RuntimeError('Invalid GPT header geometry.')
            check = bytearray(raw[:length])
            check[16:20] = b'\0' * 4
            if zlib.crc32(check) & 0xffffffff != checksum:
                raise RuntimeError('GPT header CRC mismatch.')
            current, other, first, end = struct.unpack_from('<QQQQ', raw, 24)
            start, count, width, array_crc = struct.unpack_from('<QIII', raw, 72)
            if (current != lba or other != (last if lba == 1 else 1)
                    or not 2 < first <= end < last or raw[56:72] == b'\0' * 16
                    or not 1 <= count <= 4096 or not 128 <= width <= 4096
                    or width % 128 or count * width > 16 * 1024 * 1024):
                raise RuntimeError('Invalid GPT locations or entry geometry.')
            sectors = (count * width + 511) // 512
            if ((lba == 1 and not (2 <= start and start + sectors <= first))
                    or (lba == last and not (end < start and start + sectors <= last))):
                raise RuntimeError('GPT entry array overlaps usable sectors/header.')
            src.seek(start * 512)
            entries = src.read(count * width)
            if len(entries) != count * width or zlib.crc32(entries) & 0xffffffff != array_crc:
                raise RuntimeError('GPT entry-array CRC mismatch.')
            return (first, end, raw[56:72], count, width, entries)
        primary, backup = header(1), header(last)
    if primary != backup:
        raise RuntimeError('Primary and backup GPT disagree.')
    first, end, _, count, width, entries = primary
    partitions, ranges, ids = {}, [], set()
    for i in range(count):
        entry = entries[i * width:(i + 1) * width]
        if entry[:16] == b'\0' * 16:
            continue
        start, stop = struct.unpack_from('<QQ', entry, 32)
        guid = entry[16:32]
        if not first <= start <= stop <= end or guid == b'\0' * 16 or guid in ids:
            raise RuntimeError('Invalid GPT partition bounds or unique GUID.')
        ids.add(guid)
        name = entry[56:128].decode('utf-16le').split('\0', 1)[0]
        if not name or name in partitions:
            raise RuntimeError('Missing/duplicate GPT partition name.')
        partitions[name] = {'index': i + 1, 'first_lba': start, 'last_lba': stop}
        ranges.append((start, stop))
    ranges.sort()
    if any(a[1] >= b[0] for a, b in zip(ranges, ranges[1:])):
        raise RuntimeError('Overlapping GPT partitions.')
    if not set(REQUIRED).issubset(partitions):
        raise RuntimeError('GPT lacks required cronos partitions.')
    return partitions


def _capture(dev, block, path):
    """Capture shell-v2 binary stdout in-container; preserve separate stderr/status."""
    container = '/work/' + path.relative_to(ROOT).as_posix()
    err, status = container + '.stderr', container + '.exit'
    cmd = ('umask 077; adb start-server >/tmp/rawbackup-adb-start.log 2>&1 || '
           '{ cat /tmp/rawbackup-adb-start.log >&2; exit 1; }; '
           'adb -s %s shell -T cat %s >%s 2>%s; rc=$?; '
           'printf "%%s\\n" "$rc" >%s; exit "$rc"') % tuple(
               shlex.quote(s) for s in (dev.serial, block, container, err, status))
    dev.command('bash', '-c', cmd, timeout=7200)
    for item in (path, Path(str(path) + '.stderr'), Path(str(path) + '.exit')):
        if item.is_symlink() or not item.is_file():
            raise RuntimeError('Missing/unsafe capture output.')
        item.chmod(0o600)
    if Path(str(path) + '.exit').read_text().strip() != '0':
        raise RuntimeError('Remote cat did not exit successfully.')
    if Path(str(path) + '.stderr').stat().st_size:
        raise RuntimeError('ADB/remote cat emitted stderr; inspect the private capture log.')


def _verify_manifest(path, serial):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Missing/unsafe raw backup manifest.')
    record = json.loads(path.read_text())
    if (record.get('schema') != 1 or record.get('kind') != 'raw-emmc'
            or record.get('serial') != serial or record.get('product') != 'cronos'
            or record.get('scope') != SCOPE or set(record.get('files', {})) != set(BLOCKS)):
        raise RuntimeError('Invalid raw backup identity/scope.')
    source = record['source']
    props = dict(re.findall(r'^\[([^]]+)\]: \[(.*)\]\r?$', source['properties'], re.M))
    if (source['adb_serial'] != serial or 'shell_v2' not in source['features']
            or not props.get('ro.twrp.version')
            or 'cronos' not in [props.get(k, '').lower() for k in
                               ('ro.product.device', 'ro.build.product', 'ro.product.vendor.device')]
            or BY_NAME + 'metadata' not in source['fstab']
            or BY_NAME + 'userdata' not in source['fstab']
            or not source['symlinks'].strip()):
        raise RuntimeError('Missing/incorrect raw backup source evidence.')
    expected_checks = ['initial'] + [name + '-' + stage for name in BLOCKS
                                    for stage in ('before-stream', 'after-stream', 'after-hash')]
    if list(source['mount_checks']) != expected_checks:
        raise RuntimeError('Missing mount evidence around stream/hash.')
    for mounts in source['mount_checks'].values():
        _unmounted(mounts)
    for name, block in BLOCKS.items():
        item = record['files'][name]
        image = path.parent / (name + '.img')
        expected = source['block_sizes'][name]
        if (item.get('path') != image.name or item.get('source') != block
                or not isinstance(expected, int) or expected <= 0 or expected % 512
                or (name != 'mmcblk0' and expected != 4 * 1024 * 1024)
                or item.get('size') != expected or image.is_symlink() or not image.is_file()
                or image.stat().st_size != expected
                or not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', ''))
                or item['sha256'] != item.get('source_sha256') or digest(image) != item['sha256']):
            raise RuntimeError('Raw image size/hash/source mismatch: ' + name)
        prefix = path.parent / (name + '.img.partial')
        if (Path(str(prefix) + '.exit').is_symlink()
                or Path(str(prefix) + '.stderr').is_symlink()
                or Path(str(prefix) + '.exit').read_text().strip() != '0'
                or Path(str(prefix) + '.stderr').stat().st_size):
            raise RuntimeError('Invalid binary capture completion evidence.')
    partitions = validate_gpt(path.parent / 'mmcblk0.img')
    for name in REQUIRED:
        expected = '/dev/block/mmcblk0p%d' % partitions[name]['index']
        if source['by_name'].get(name) != expected:
            raise RuntimeError('Observed by-name mapping disagrees with GPT: ' + name)
    if record.get('gpt') != partitions:
        raise RuntimeError('Recorded GPT differs from the image.')
    return path


def verify_raw_backup(serial):
    """Rehash and structurally verify the newest raw backup for this exact serial."""
    _serial(serial)
    base = ROOT / 'backups' / serial
    candidates = sorted(base.glob('raw-*/raw-backup.json'), reverse=True)
    if not candidates:
        raise RuntimeError('No raw eMMC backup exists for this exact serial.')
    path = candidates[0]
    if any(p.is_symlink() for p in (ROOT / 'backups', base, path.parent)):
        raise RuntimeError('Symlink in raw backup path.')
    return _verify_manifest(path, serial)


def create_raw_backup(dev):
    """Preserve all three areas. No device writes, unmounts, prompts or restores."""
    _serial(dev.serial)
    dev.adb_probe(recovery=True)
    features = dev.adb('features').replace(',', '\n').split()
    if 'shell_v2' not in features:
        raise RuntimeError('shell_v2 is required for binary transport and remote exit status.')
    adb_serial = dev.adb('get-serialno')
    if adb_serial != dev.serial:
        raise RuntimeError('ADB serial does not match the selected device.')
    source = {'features': features, 'adb_serial': adb_serial,
              'properties': dev.adb('shell', '-T', 'getprop'),
              'fstab': dev.adb('shell', '-T', 'cat', '/etc/recovery.fstab'),
              'symlinks': dev.adb('shell', '-T', 'ls', '-l', BY_NAME),
              'by_name': {}, 'block_sizes': {}, 'mount_checks': {}}
    for name in REQUIRED:
        target = dev.adb('shell', '-T', 'readlink', '-f', BY_NAME + name)
        if not re.fullmatch(r'/dev/block/mmcblk0p[1-9][0-9]*', target):
            raise RuntimeError('Unexpected eMMC mapping for ' + name)
        source['by_name'][name] = target
    for name, block in BLOCKS.items():
        output = dev.adb('shell', '-T', 'blockdev', '--getsize64', block)
        if not re.fullmatch(r'[1-9][0-9]*', output):
            raise RuntimeError('Invalid blockdev size: ' + name)
        size = int(output)
        if size % 512 or (name != 'mmcblk0' and size != 4 * 1024 * 1024):
            raise RuntimeError('Unexpected eMMC geometry: ' + name)
        source['block_sizes'][name] = size
    if shutil.disk_usage(ROOT).free < sum(source['block_sizes'].values()) + 1024**3:
        raise RuntimeError('Insufficient NAS space for all eMMC areas plus 1 GiB margin.')

    def mounts(label):
        value = dev.adb('shell', '-T', 'cat', '/proc/mounts')
        _unmounted(value)
        source['mount_checks'][label] = value

    mounts('initial')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = ROOT / 'backups' / dev.serial / ('raw-' + stamp)
    _private_dir(target)
    _write(target / 'source-initial.json', json.dumps(source, indent=2) + '\n')
    record = {'schema': 1, 'kind': 'raw-emmc', 'product': 'cronos', 'serial': dev.serial,
              'created_utc': stamp, 'scope': SCOPE, 'source': source, 'files': {}}
    for name, block in BLOCKS.items():
        partial = target / (name + '.img.partial')
        mounts(name + '-before-stream')
        print('Streaming %s (%d bytes) directly to NAS...' % (name, source['block_sizes'][name]), flush=True)
        _capture(dev, block, partial)
        mounts(name + '-after-stream')
        if partial.stat().st_size != source['block_sizes'][name]:
            raise RuntimeError('Truncated/oversized raw capture: ' + name)
        raw_hash = dev.adb('shell', '-T', 'sha256sum', block, timeout=7200)
        match = re.fullmatch(r'([0-9a-f]{64})\s+' + re.escape(block), raw_hash)
        if not match:
            raise RuntimeError('Invalid remote source SHA256 response: ' + name)
        mounts(name + '-after-hash')
        checksum = digest(partial)
        if checksum != match.group(1):
            raise RuntimeError('Remote and NAS SHA256 disagree: ' + name)
        with partial.open('rb') as out:
            os.fsync(out.fileno())
        image = target / (name + '.img')
        partial.rename(image)
        record['files'][name] = {'path': image.name, 'source': block,
                                 'size': image.stat().st_size, 'sha256': checksum,
                                 'source_sha256': match.group(1)}
        if name == 'mmcblk0':
            record['gpt'] = validate_gpt(image)
        print('Preserved and hash-matched ' + name, flush=True)
    pending = target / 'raw-backup.pending.json'
    _write(pending, json.dumps(record, indent=2) + '\n')
    _verify_manifest(pending, dev.serial)
    final = target / 'raw-backup.json'
    pending.rename(final)
    directory = os.open(str(target), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    print('Verified post-unlock raw preservation:', final, flush=True)
    print(SCOPE, flush=True)
    return final
