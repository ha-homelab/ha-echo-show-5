#!/usr/bin/env python3
"""Staged Show 5 Gen2 operations on the physical Synology host. No default writes."""
import argparse
import contextlib
import datetime
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import struct
import stat
import tarfile

from artifacts import ROOT, digest, verify

DOCKER = '/usr/local/bin/docker'
IMAGE = 'ha-echo-show5-host:2026-10-01'
PRODUCTS = {'CRONOS', 'AEOCN'}  # Script labels / upstream README identifiers.


def run(args, timeout=45):
    p = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, encoding='utf-8', errors='replace', timeout=timeout)
    if p.returncode:
        raise RuntimeError('Command failed (%s): %s\n%s' % (p.returncode, args[0], p.stdout))
    return p.stdout.strip()


def docker(*args):
    return ['sudo', '-n', DOCKER] + list(args)


def usb_inventory(base=Path('/sys/bus/usb/devices')):
    result = []
    for p in sorted(base.iterdir()):
        if not (p / 'idVendor').exists():
            continue
        def read(name):
            f = p / name
            return f.read_text().strip() if f.exists() else ''
        if read('idVendor') == '1d6b':
            continue
        result.append(dict(port=p.name, vendor=read('idVendor'), product_id=read('idProduct'),
                           description=read('product'), serial=read('serial'),
                           node='/dev/bus/usb/%03d/%03d' % (int(read('busnum')), int(read('devnum')))))
    return result


def validate_serial(serial):
    if not re.fullmatch(r'[A-Za-z0-9._-]{4,80}', serial or ''):
        raise ValueError('A complete USB/fastboot/ADB serial is required, not a suffix or wildcard.')


def select_device(rows, port, serial):
    validate_serial(serial)
    found = [r for r in rows if r['port'] == port]
    if len(found) != 1:
        raise ValueError('Selected physical USB port is absent or ambiguous. Run inventory again.')
    row = found[0]
    if row['serial'] != serial:
        raise ValueError('USB serial does not match. Do not assume serials survive a mode change; inspect again.')
    if row['vendor'] not in {'0bb4', '1949', '18d1', '0e8d'}:
        raise ValueError('Unrecognized USB vendor; no tools will open this USB node.')
    return row


def ensure_idle():
    names = run(docker('ps', '--format', '{{.Names}}')).splitlines()
    busy = [n for n in names if n.startswith(('ha-echo-', 'ha-echo-show5-'))]
    if busy:
        raise RuntimeError('Another Echo operation is running: ' + ', '.join(busy) + '. Finish it first.')


def image_id():
    actual = run(docker('image', 'inspect', IMAGE, '--format', '{{.Id}}'))
    record = ROOT / 'private' / 'host-image.json'
    if not record.exists() or json.loads(record.read_text())['image_id'] != actual:
        raise RuntimeError('Host image has not been recorded, or its tag changed. Run prepare-host.')
    return actual


@contextlib.contextmanager
def usb_group_access(row):
    """Temporarily allow the mapped node's own group; preserve owner/other bits."""
    node = Path(row['node'])
    before = node.stat()
    if not stat.S_ISCHR(before.st_mode):
        raise RuntimeError('Selected USB node is not a character device.')
    mode = stat.S_IMODE(before.st_mode)
    changed = mode & 0o060 != 0o060
    if changed:
        run(['sudo', '-n', 'chmod', '%04o' % (mode | 0o060), str(node)])
    try:
        yield
    finally:
        if changed and node.exists():
            after = node.stat()
            still_selected = any(r['port'] == row['port'] and r['serial'] == row['serial']
                                 and r['node'] == row['node'] for r in usb_inventory())
            if still_selected and (before.st_ino, before.st_rdev, before.st_uid, before.st_gid) == (
                    after.st_ino, after.st_rdev, after.st_uid, after.st_gid):
                run(['sudo', '-n', 'chmod', '%04o' % mode, str(node)])


class Device:
    def __init__(self, port, serial):
        self.port, self.serial = port, serial
        self.row = select_device(usb_inventory(), port, serial)
        self.image = image_id()

    def command(self, *args, interactive=False, timeout=60):
        # Re-resolve before EVERY command: USB addresses change after a reboot.
        row = select_device(usb_inventory(), self.port, self.serial)
        if row['node'] != self.row['node']:
            raise RuntimeError('USB node changed during this stage. Stop and run inventory/probe again.')
        home = ROOT / 'private' / 'adb-home'
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        # DSM can inherit administrator-only ACLs despite mkdir(mode=0700).
        # Explicit chmod gives this nonroot UID access without administrator GID.
        home.parent.chmod(0o700)
        home.chmod(0o700)
        node_gid = Path(row['node']).stat().st_gid
        cmd = docker('run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
                     '--security-opt', 'no-new-privileges', '--name', 'ha-echo-show5-' + str(os.getpid()),
                     '--user', '%d:%d' % (os.getuid(), os.getgid()), '--group-add', str(node_gid),
                     '--env', 'HOME=/work/private/adb-home', '--env', 'TERM=xterm',
                     '--mount', 'type=bind,src=%s,dst=/work' % ROOT,
                     '--device', row['node'] + ':' + row['node'])
        if interactive:
            cmd += ['-it']
        # A fresh isolated ADB server starts in each container; persist its key,
        # but keep its startup banner out of machine-readable command output.
        command = list(args)
        if command and command[0] == 'adb':
            command = ['bash', '-c',
                       'adb start-server >/tmp/show5-adb-start.log 2>&1 || '
                       '{ cat /tmp/show5-adb-start.log >&2; exit 1; }; exec "$@"',
                       'show5-adb'] + command
        cmd += [self.image] + command
        # DSM creates these nodes root-only (0600). Keep the container nonroot;
        # temporarily grant RW to the node's existing group, then restore it.
        with usb_group_access(row):
            if interactive:
                # Do not impose a host timeout on an ongoing firmware write.
                if subprocess.call(cmd):
                    raise RuntimeError('Interactive operation failed; inspect its output before continuing.')
                return ''
            return run(cmd, timeout=timeout)

    def adb(self, *args, timeout=60):
        return self.command('adb', '-s', self.serial, *args, timeout=timeout)

    def fastboot_probe(self):
        devices = self.command('fastboot', 'devices').splitlines()
        if len(devices) != 1 or devices[0].split()[:2] != [self.serial, 'fastboot']:
            raise RuntimeError('Expected exactly the selected fastboot device.')
        raw = self.command('fastboot', '-s', self.serial, 'getvar', 'product')
        match = re.search(r'(?:\(bootloader\)\s*)?product:\s*(\S+)', raw)
        if not match or match.group(1).upper() not in PRODUCTS:
            raise RuntimeError('Not a confirmed Show 5 Gen2 product. Raw response: ' + raw)
        info = {'product': match.group(1), 'serial_suffix': self.serial[-6:], 'port': self.port}
        for key in ('unlock_status', 'lk_build_desc'):
            info[key] = self.command('fastboot', '-s', self.serial, 'getvar', key)
        return info

    def adb_probe(self, recovery=True):
        raw = self.command('adb', 'devices')
        devices = [line.split() for line in raw.splitlines()
                   if line and not line.startswith(('List of devices', '*'))]
        if len(devices) != 1 or devices[0][0] != self.serial or devices[0][1] not in ('device', 'recovery'):
            raise RuntimeError('Expected exactly the selected, authorized ADB device: ' + raw)
        text = self.adb('shell', 'getprop')
        props = dict(re.findall(r'^\[([^]]+)\]: \[(.*)\]\r?$', text, re.M))
        identifiers = [props.get(k, '').lower() for k in
                       ('ro.product.device', 'ro.build.product', 'ro.product.vendor.device')]
        if 'cronos' not in identifiers:
            raise RuntimeError('ADB properties do not identify cronos; refusing device writes.')
        if recovery and not props.get('ro.twrp.version'):
            raise RuntimeError('This is not confirmed TWRP recovery.')
        if not recovery and (props.get('ro.build.version.release') != '11'
                             or not props.get('ro.lineage.version', '').startswith('18.1')
                             or props.get('sys.boot_completed') != '1'):
            raise RuntimeError('Expected fully booted LineageOS 18.1 / Android 11 on cronos.')
        return {k: props.get(k, '') for k in ('ro.product.device', 'ro.build.product',
                'ro.twrp.version', 'ro.build.version.release', 'ro.lineage.version', 'sys.boot_completed')}


def confirm(action, serial):
    phrase = action.upper() + ' ' + serial
    if not sys.stdin.isatty():
        raise RuntimeError('Writes require an interactive terminal; there is no --yes mode.')
    if input('Type "%s" to continue: ' % phrase) != phrase:
        raise RuntimeError('Cancelled. No requested write was started.')


def backup_root(serial):
    validate_serial(serial)
    return ROOT / 'backups' / serial


def validate_backup_payloads(files):
    """Check TWRP split sets and contents without extracting device files."""
    for partition in ('boot', 'system', 'data'):
        pattern = re.compile(partition + r'\.([A-Za-z0-9_-]+)\.win(\d*)')
        found = [(f, pattern.fullmatch(f.name)) for f in files]
        found = [(f, m) for f, m in found if m]
        if not found or len({m.group(1) for _, m in found}) != 1:
            raise RuntimeError('Missing or ambiguous backup partition: ' + partition)
        suffixes = [m.group(2) for _, m in found]
        if '' in suffixes:
            if len(suffixes) != 1:
                raise RuntimeError('Mixed split/unsplit backup: ' + partition)
        elif sorted(suffixes) != ['%03d' % i for i in range(len(suffixes))]:
            raise RuntimeError('Missing/duplicate split segment: ' + partition)
        if partition == 'boot':
            if len(found) != 1 or found[0][1].group(1) != 'emmc':
                raise RuntimeError('Unexpected boot image format; inspect the real recovery layout.')
            f = found[0][0]
            with f.open('rb') as src:
                header = src.read(40)
            if len(header) < 40 or header[:8] != b'ANDROID!':
                raise RuntimeError('Invalid Android boot image header.')
            kernel, ramdisk, second, page = [struct.unpack_from('<I', header, x)[0] for x in (8, 16, 24, 36)]
            if page not in (2048, 4096, 8192, 16384) or not kernel:
                raise RuntimeError('Unexpected Android boot image geometry.')
            needed = page + sum(((n + page - 1) // page) * page for n in (kernel, ramdisk, second))
            if f.stat().st_size < needed:
                raise RuntimeError('Truncated boot image.')
        else:
            regular_files = 0
            for f, _ in found:
                with f.open('rb') as src:
                    compressed = src.read(2) == b'\x1f\x8b'
                if compressed:
                    # Consume through the gzip trailer, checking CRC/length too.
                    with gzip.open(f, 'rb') as src:
                        for _ in iter(lambda: src.read(4 * 1024 * 1024), b''):
                            pass
                with tarfile.open(f, 'r|*') as archive:
                    for entry in archive:
                        if entry.isfile():
                            regular_files += 1
                            stream = archive.extractfile(entry)
                            for _ in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                                pass
            if not regular_files:
                raise RuntimeError('No regular files in ' + partition + ' backup; inspect the backup scope.')


def verify_backup(serial):
    # No marker alone authorizes a wipe/install: rehash every actual backup file.
    candidates = sorted(backup_root(serial).glob('*/backup.json'), reverse=True)
    if not candidates:
        if list(backup_root(serial).glob('*/raw-backup.json')):
            from rawbackup import verify_raw_backup
            return verify_raw_backup(serial)
        raise RuntimeError('No verified off-device backup for this full serial.')
    path = candidates[0]
    data = json.loads(path.read_text())
    if data.get('serial') != serial or data.get('product') != 'cronos' or not data.get('files'):
        raise RuntimeError('Invalid backup manifest.')
    evidence = data.get('completion_evidence', '')
    if not re.search(r'backup complet(?:e|ed)', evidence, re.I):
        raise RuntimeError('No positive completion evidence for this backup operation.')
    if digest(path.parent / 'recovery.log') != data.get('recovery_log_sha256'):
        raise RuntimeError('Recovery log does not match the completion record.')
    files = []
    for entry in data['files']:
        rel = Path(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('Unsafe backup path.')
        f = path.parent / rel
        if f.is_symlink() or f.stat().st_size != entry['size'] or digest(f) != entry['sha256']:
            raise RuntimeError('Backup failed size/SHA256 verification: ' + str(f))
        if entry['size'] > 0:
            files.append(f)
    validate_backup_payloads(files)
    return path


def create_backup(dev):
    props = dev.adb_probe()
    if shutil.disk_usage(ROOT).free < 16 * 1024**3:
        raise RuntimeError('Keep at least 16 GiB free on the NAS before a backup.')
    confirm('backup', dev.serial)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = backup_root(dev.serial) / stamp
    target.mkdir(parents=True, mode=0o700)
    for directory in (ROOT / 'backups', backup_root(dev.serial), target):
        directory.chmod(0o700)
    # The TWRP interface is documented at twrp.me/faq/openrecoveryscript.html.
    name = 'Show5-' + stamp
    before_log = dev.adb('shell', 'cat', '/tmp/recovery.log')
    (target / 'partition-layout.txt').write_text(dev.adb('shell', 'cat', '/etc/recovery.fstab'))
    (target / 'storage-before.txt').write_text(dev.adb('shell', 'df', '-k', '/data', '/sdcard'))
    output = dev.adb('shell', 'twrp', 'backup', 'BSD', name, timeout=1800)
    (target / 'twrp-command.log').write_text(output + '\n')
    after_log = dev.adb('shell', 'cat', '/tmp/recovery.log')
    (target / 'recovery.log').write_text(after_log)
    new_log = after_log[len(before_log):] if after_log.startswith(before_log) else ''
    current_output = output + '\n' + new_log
    completion = re.search(r'[^\n]*backup complet(?:e|ed)[^\n]*', current_output, re.I)
    if not completion or re.search(r'(backup failed|unable to|failed to|error|not enough)', current_output, re.I):
        raise RuntimeError('TWRP reported a possible backup failure. No completion marker written.')
    listing = dev.adb('shell', 'find', '/sdcard/TWRP/BACKUPS', '-type', 'f').splitlines()
    files = [s.strip() for s in listing if '/' + name + '/' in s]
    if not files:
        raise RuntimeError('TWRP backup files not found; inspect recovery.log and storage/decryption.')
    records = []
    for index, remote in enumerate(files):
        if not re.fullmatch(r'/sdcard/TWRP/BACKUPS/[A-Za-z0-9._/-]+', remote) or '..' in Path(remote).parts:
            raise RuntimeError('Unexpected backup path: ' + remote)
        size = int(dev.adb('shell', 'stat', '-c', '%s', remote).strip())
        remote_hash = dev.adb('shell', 'sha256sum', remote).split()[0]
        if not re.fullmatch('[0-9a-f]{64}', remote_hash):
            raise RuntimeError('Could not hash backup on the device.')
        rel = Path('files') / Path(remote).relative_to('/sdcard/TWRP/BACKUPS')
        (target / rel.parent).mkdir(parents=True, exist_ok=True)
        container_path = '/work/' + str((target / rel).relative_to(ROOT))
        dev.adb('pull', remote, container_path, timeout=1800)
        if (target / rel).stat().st_size != size or digest(target / rel) != remote_hash:
            raise RuntimeError('Off-device backup copy is corrupt or incomplete.')
        records.append({'path': str(rel), 'source': remote, 'size': size, 'sha256': remote_hash})
    manifest = dict(serial=dev.serial, product='cronos', created_at=stamp, properties=props,
                    scope='TWRP Boot/System/Data after unlock; excludes internal shared media and early bootloader.',
                    completion_evidence=completion.group(0), recovery_log_sha256=digest(target / 'recovery.log'),
                    files=records)
    (target / 'backup.json').write_text(json.dumps(manifest, indent=2) + '\n')
    try:
        verified = verify_backup(dev.serial)
    except Exception:
        (target / 'backup.json').rename(target / 'backup.incomplete.json')
        raise
    print('Verified off-device backup:', verified)
    print('This is a post-unlock backup, not an untouched stock/eMMC image. Internal shared media is excluded.')


def verify_unlock_package():
    """Validate the release and its complete audited tree without opening USB."""
    archive = verify('amonet')
    review = json.loads((ROOT / 'amonet-review.json').read_text())
    if review.get('release') != '2.0.1' or review.get('product') != 'cronos' or review.get('archive_sha256') != digest(archive):
        raise RuntimeError('No matching release audit. Source-only checkout cannot unlock a device.')
    files = review.get('files', {})
    required = {'device.prop', 'fastbrick.sh', 'profile.sh', 'bin/fastboot', 'bin/fastboot32',
                'bin/fastbrick.img', 'bin/preloader.img', 'bin/lk.bin', 'bin/tz.img',
                'bin/tee-payload.bin', 'bin/cronos-kaeru.bin', 'bin/twrp.img'}
    if not required.issubset(files):
        raise RuntimeError('Incomplete audited amonet package.')
    package = ROOT / 'vendor' / 'amonet'
    paths = list(package.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise RuntimeError('Symlinks are not allowed in the audited release tree.')
    actual = {str(p.relative_to(package)) for p in paths if p.is_file()}
    if actual != set(files):
        raise RuntimeError('Release tree has missing or unreviewed files. Restore the original package.')
    for name, expected in files.items():
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('Invalid amonet audit path.')
        f = ROOT / 'vendor' / 'amonet' / rel
        if f.is_symlink() or digest(f) != expected:
            raise RuntimeError('Amonet extracted file differs from its audit: ' + name)
    props = dict(line.split('=', 1) for line in (package / 'device.prop').read_text().splitlines() if '=' in line)
    if props.get('DEVICE') != 'cronos' or props.get('DEVICE_TYPE_ID') != 'A1XWJRHALS1REP':
        raise RuntimeError('Release metadata is not Echo Show 5 Gen2 / cronos.')
    evidence = ROOT / 'private' / 'host-release-validation.json'
    if not evidence.is_file() or evidence.is_symlink():
        raise RuntimeError('Run scripts/validate_host_release.py on this NAS before using the release.')
    validation = json.loads(evidence.read_text())
    if (validation.get('schema_version') != 1 or validation.get('product') != 'cronos'
            or validation.get('archive_sha256') != review['archive_sha256']
            or validation.get('passed_without_usb') is not True):
        raise RuntimeError('No matching private no-USB host validation for this release.')
    review['host_validation'] = validation
    return review


def unlock(dev):
    review = verify_unlock_package()
    if dev.image != review['host_validation'].get('image_id'):
        raise RuntimeError('Host image changed after release validation. Repeat its no-USB runtime check.')
    info = dev.fastboot_probe()
    if not re.search(r'unlock_status:\s*false\b', info['unlock_status'], re.I):
        raise RuntimeError('Expected a locked device; do not rerun fastbrick on an unlocked Show.')
    print(json.dumps(info, indent=2))
    confirm('unlock', dev.serial)
    dev.fastboot_probe()  # Recheck selection immediately before the upstream script.
    print('Keep stock AC power and USB connected. Follow the upstream prompts; do not interrupt the write.')
    dev.command('bash', '-c', 'cd /work/vendor/amonet && exec bash ./fastbrick.sh', interactive=True)
    print('Upstream process ended. This alone does not prove success. Wait for TWRP, rerun inventory/probe-recovery.')


def stage_rom(dev):
    rom = verify('lineage')
    print('Verified backup:', verify_backup(dev.serial))
    dev.adb_probe()
    confirm('stage-rom', dev.serial)
    dev.adb('shell', 'mkdir', '-p', '/sdcard/Download')
    remote = '/sdcard/Download/' + rom.name
    print(dev.adb('push', '/work/downloads/' + rom.name, remote, timeout=900))
    if dev.adb('shell', 'sha256sum', remote).split()[0] != digest(rom):
        raise RuntimeError('Device ROM SHA256 mismatch. Do not install.')
    print('ROM verified on the device. Follow the runbook for install-rom and final Format Data.')


def twrp_step(dev, command):
    """Run one attended CLI operation and retain its fresh recovery evidence.

    TWRP's CLI exit status is not the operation result. The caller must inspect
    the recorded log and independently check the filesystem/installed image.
    """
    before = dev.adb('shell', 'cat', '/tmp/recovery.log')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = ROOT / 'logs' / dev.serial / (stamp + '-' + command[0])
    target.mkdir(parents=True, mode=0o700)
    for directory in (ROOT / 'logs', ROOT / 'logs' / dev.serial, target):
        directory.chmod(0o700)
    (target / 'before.log').write_text(before)
    (target / 'command.json').write_text(json.dumps(command) + '\n')
    try:
        dev.command('adb', '-s', dev.serial, 'shell', 'twrp', *command, interactive=True)
    finally:
        after = dev.adb('shell', 'cat', '/tmp/recovery.log')
        (target / 'after.log').write_text(after)
    if not after.startswith(before):
        raise RuntimeError('Recovery log changed unexpectedly; inspect ' + str(target))
    fresh = after[len(before):]
    (target / 'operation.log').write_text(fresh)
    (target / 'mounts-after.txt').write_text(dev.adb('shell', 'cat', '/proc/mounts'))
    expected = "Command '%s' received" % ' '.join(command)
    if expected not in fresh:
        raise RuntimeError('No matching new recovery command evidence; inspect ' + str(target))
    print('New recovery evidence:', target / 'operation.log')
    print(fresh)
    print('CLI completion alone is NOT success. Verify the resulting filesystem or image before the next stage.')


def prepare_partition(dev, action):
    commands = {'format-data': ['format', 'data'], 'wipe-data': ['wipe', 'data'],
                'wipe-system': ['wipe', 'system'], 'wipe-cache': ['wipe', 'cache']}
    command = commands[action]
    print('Verified backup:', verify_backup(dev.serial))
    dev.adb_probe()
    confirm(action, dev.serial)
    twrp_step(dev, command)


def install_rom(dev):
    rom = verify('lineage')
    print('Verified backup:', verify_backup(dev.serial))
    dev.adb_probe()
    remote = '/sdcard/Download/' + rom.name
    if dev.adb('shell', 'sha256sum', remote).split()[0] != digest(rom):
        raise RuntimeError('Stage the exact verified ROM first.')
    confirm('install-rom', dev.serial)
    # Live output and no outer write timeout; inspect TWRP result on screen.
    twrp_step(dev, ['install', remote])
    print('Inspect TWRP for installation success. Then Format Data again and reboot System as documented.')


def install_companion(dev):
    apk = verify('companion')
    dev.adb_probe(recovery=False)
    confirm('install-companion', dev.serial)
    print(dev.adb('install', '-r', '/work/downloads/' + apk.name, timeout=300))
    print('Open Home Assistant on screen, sign in, and follow docs/android-and-home-assistant.md.')


def prepare_host():
    # No USB mapping, host ADB daemon or shared Echo container is used here.
    run(docker('build', '-t', IMAGE, str(ROOT / 'host' / 'synology')), timeout=1200)
    actual = run(docker('image', 'inspect', IMAGE, '--format', '{{.Id}}'))
    versions = run(docker('run', '--rm', '--network', 'none', '--cap-drop', 'ALL', actual,
                         'bash', '-c', 'adb version && fastboot --version && python3 --version'))
    private = ROOT / 'private'
    private.mkdir(exist_ok=True, mode=0o700)
    (private / 'host-image.json').write_text(json.dumps({'image_id': actual, 'tag': IMAGE,
        'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'versions': versions}, indent=2) + '\n')
    print(versions)
    print('Recorded host image:', actual)
    from validate_host_release import validate_host_release
    print('Validated unlock host without USB:', validate_host_release(actual))


@contextlib.contextmanager
def operation_lock():
    private = ROOT / 'private'
    private.mkdir(exist_ok=True, mode=0o700)
    with (private / 'operation.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ensure_idle()
        yield


def main():
    os.umask(0o077)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['inventory', 'preflight', 'prepare-host', 'probe-fastboot',
        'probe-recovery', 'probe-android', 'unlock', 'backup', 'backup-raw', 'verify-backup', 'stage-rom',
        'install-rom', 'install-companion', 'format-data', 'wipe-data', 'wipe-system', 'wipe-cache'])
    ap.add_argument('--port', help='Exact physical USB port from inventory, e.g. 1-3')
    ap.add_argument('--serial', help='Complete observed serial; never a suffix')
    args = ap.parse_args()
    if args.action == 'inventory':
        print(json.dumps(usb_inventory(), indent=2))
    elif args.action == 'preflight':
        print('Architecture:', run(['uname', '-m']))
        print('Free space GiB:', round(shutil.disk_usage(ROOT).free / 1024**3, 1))
        print('Image:', image_id())
        print('Running Echo containers:', run(docker('ps', '--format', '{{.Names}}', '--filter', 'name=ha-echo')) or 'none')
        for kind in ('lineage', 'companion', 'amonet'):
            try:
                print(kind + ': VERIFIED ' + str(verify(kind)))
            except (OSError, ValueError, KeyError) as e:
                print(kind + ': NOT READY: ' + str(e))
        try:
            review = verify_unlock_package()
            if review['host_validation'].get('image_id') != image_id():
                raise RuntimeError('Host image differs from the tested image.')
            print('Unlock package: AUDITED; bundled host tools tested without USB. Device checks still required.')
        except (OSError, ValueError, RuntimeError, KeyError) as e:
            print('Unlock package: NOT READY: ' + str(e))
        print('No USB node was opened.')
    elif args.action == 'prepare-host':
        prepare_host()
    elif args.action == 'verify-backup':
        print(verify_backup(args.serial))
    else:
        if not args.port or not args.serial:
            ap.error('--port and --serial are required for this stage')
        with operation_lock():
            dev = Device(args.port, args.serial)
            if args.action == 'backup-raw':
                from rawbackup import create_raw_backup
                dev.adb_probe()
                confirm('backup-raw', dev.serial)
                print('Verified off-device raw backup:', create_raw_backup(dev))
                return
            if args.action in ('format-data', 'wipe-data', 'wipe-system', 'wipe-cache'):
                prepare_partition(dev, args.action)
                return
            actions = {'probe-fastboot': lambda: print(json.dumps(dev.fastboot_probe(), indent=2)),
                       'probe-recovery': lambda: print(json.dumps(dev.adb_probe(), indent=2)),
                       'probe-android': lambda: print(json.dumps(dev.adb_probe(False), indent=2)),
                       'unlock': lambda: unlock(dev), 'backup': lambda: create_backup(dev),
                       'stage-rom': lambda: stage_rom(dev), 'install-rom': lambda: install_rom(dev),
                       'install-companion': lambda: install_companion(dev)}
            actions[args.action]()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, tarfile.TarError, EOFError, subprocess.SubprocessError) as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        sys.exit(1)
