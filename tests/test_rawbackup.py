"""Synthetic local-only tests. No Docker, NAS, ADB or USB access."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import rawbackup as raw


SERIAL = 'TESTSHOW123456'
MOUNTS = 'rootfs / rootfs rw 0 0\ntmpfs /tmp tmpfs rw 0 0\n'


def gpt_image(entries_change=None, backup_change=None):
    image = bytearray(256 * 512)
    entries = bytearray(8 * 128)
    for i, name in enumerate(raw.REQUIRED):
        offset = i * 128
        entries[offset:offset + 16] = b'T' * 16
        entries[offset + 16:offset + 32] = bytes([i + 1]) * 16
        struct.pack_into('<QQ', entries, offset + 32, 10 + 8 * i, 13 + 8 * i)
        encoded = name.encode('utf-16le')
        entries[offset + 56:offset + 56 + len(encoded)] = encoded
    if entries_change:
        entries_change(entries)

    def header(current, other, start, data):
        result = bytearray(512)
        struct.pack_into('<8sIIIIQQQQ16sQIII', result, 0,
                         b'EFI PART', 0x10000, 92, 0, 0, current, other,
                         10, 245, b'D' * 16, start, 8, 128,
                         zlib.crc32(data) & 0xffffffff)
        struct.pack_into('<I', result, 16, zlib.crc32(result[:92]) & 0xffffffff)
        return result

    backup = bytearray(entries)
    if backup_change:
        backup_change(backup)
    image[512:1024] = header(1, 255, 2, entries)
    image[1024:2048] = entries
    image[253 * 512:255 * 512] = backup
    image[255 * 512:] = header(255, 1, 253, backup)
    return bytes(image)


class FakeDevice:
    serial = SERIAL

    def __init__(self):
        self.images = {raw.BLOCKS['mmcblk0']: gpt_image(),
                       raw.BLOCKS['mmcblk0boot0']: b'A' * (4 * 1024**2),
                       raw.BLOCKS['mmcblk0boot1']: b'B' * (4 * 1024**2)}
        self.mounts = MOUNTS
        self.features = 'stat_v2\ncmd\nshell_v2'
        self.bad_hash = False
        self.calls = []

    def adb_probe(self, recovery):
        assert recovery

    def adb(self, *args, **kwargs):
        self.calls.append(args)
        if args == ('features',):
            return self.features
        if args == ('get-serialno',):
            return self.serial
        if args == ('shell', '-T', 'getprop'):
            return '[ro.product.device]: [cronos]\n[ro.twrp.version]: [3.7.0]'
        if args == ('shell', '-T', 'cat', '/etc/recovery.fstab'):
            return raw.BY_NAME + 'userdata /data ext4 encryptable=' + raw.BY_NAME + 'metadata'
        if args == ('shell', '-T', 'ls', '-l', raw.BY_NAME):
            return 'userdata -> /dev/block/mmcblk0p3'
        if args[:4] == ('shell', '-T', 'readlink', '-f'):
            return '/dev/block/mmcblk0p%d' % (raw.REQUIRED.index(args[4].split('/')[-1]) + 1)
        if args[:4] == ('shell', '-T', 'blockdev', '--getsize64'):
            return str(len(self.images[args[4]]))
        if args == ('shell', '-T', 'cat', '/proc/mounts'):
            return self.mounts
        if args[:3] == ('shell', '-T', 'sha256sum'):
            value = '0' * 64 if self.bad_hash else hashlib.sha256(self.images[args[3]]).hexdigest()
            return value + '  ' + args[3]
        raise AssertionError('Unexpected fake request: ' + repr(args))


def capture_fake(dev, block, path):
    path.write_bytes(dev.images[block])
    Path(str(path) + '.stderr').write_bytes(b'')
    Path(str(path) + '.exit').write_text('0\n')


class RawBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(raw, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def image(self, data):
        path = self.root / 'test.img'
        path.write_bytes(data)
        return path

    def create(self, dev=None, capture=capture_fake):
        with patch.object(raw, '_capture', side_effect=capture), patch.object(raw, 'print'):
            return raw.create_raw_backup(dev or FakeDevice())

    def change_record(self, path, mutate):
        record = json.loads(path.read_text())
        mutate(record)
        path.write_text(json.dumps(record))

    def test_valid_both_gpts(self):
        partitions = raw.validate_gpt(self.image(gpt_image()))
        self.assertEqual(partitions['userdata']['index'], 3)

    def test_primary_and_backup_header_crc(self):
        for start in (512, 255 * 512):
            with self.subTest(start=start):
                data = bytearray(gpt_image())
                data[start + 56] ^= 1
                with self.assertRaisesRegex(RuntimeError, 'header CRC'):
                    raw.validate_gpt(self.image(data))

    def test_primary_and_backup_array_crc(self):
        for start in (1024, 253 * 512):
            with self.subTest(start=start):
                data = bytearray(gpt_image())
                data[start + 56] ^= 1
                with self.assertRaisesRegex(RuntimeError, 'entry-array CRC'):
                    raw.validate_gpt(self.image(data))

    def test_missing_signature_and_truncated_geometry(self):
        for data in (b'\0' * (256 * 512), gpt_image()[:-1]):
            with self.assertRaises(RuntimeError):
                raw.validate_gpt(self.image(data))

    def test_valid_crc_but_mirrors_disagree(self):
        data = gpt_image(backup_change=lambda e: e.__setitem__(56, ord('x')))
        with self.assertRaisesRegex(RuntimeError, 'disagree'):
            raw.validate_gpt(self.image(data))

    def test_partition_out_of_bounds(self):
        for start, end in ((9, 13), (10, 246), (13, 10)):
            data = gpt_image(entries_change=lambda e: struct.pack_into('<QQ', e, 32, start, end))
            with self.assertRaisesRegex(RuntimeError, 'partition bounds'):
                raw.validate_gpt(self.image(data))

    def test_partition_overlap(self):
        data = gpt_image(entries_change=lambda e: struct.pack_into('<QQ', e, 128 + 32, 13, 20))
        with self.assertRaisesRegex(RuntimeError, 'Overlapping'):
            raw.validate_gpt(self.image(data))

    def test_missing_required_partition(self):
        data = gpt_image(entries_change=lambda e: e.__setitem__(56, ord('x')))
        with self.assertRaisesRegex(RuntimeError, 'required cronos'):
            raw.validate_gpt(self.image(data))

    def test_mount_gate_rejects_partitions_aliases_and_empty(self):
        for mounts in ('', '/dev/block/mmcblk0p16 /data ext4 rw 0 0',
                       '/dev/block/dm-0 /x ext4 rw 0 0',
                       '/dev/block/platform/bootdevice/by-name/cache /cache ext4 rw 0 0',
                       '/dev/mmcblk0p1 /x ext4 rw 0 0', 'tmpfs /sdcard tmpfs rw 0 0'):
            with self.assertRaises(RuntimeError):
                raw._unmounted(mounts)
        raw._unmounted(MOUNTS)

    def test_create_and_reverify_with_private_directories(self):
        path = self.create()
        self.assertEqual(raw.verify_raw_backup(SERIAL), path)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse((path.parent / 'raw-backup.pending.json').exists())

    def test_rejects_missing_shell_v2_before_capture(self):
        dev = FakeDevice()
        dev.features = 'stat_v2\ncmd'
        with self.assertRaisesRegex(RuntimeError, 'shell_v2'):
            self.create(dev)

    def test_mounted_source_stops_before_capture(self):
        dev = FakeDevice()
        dev.mounts = '/dev/block/mmcblk0p16 /data ext4 rw 0 0'
        with patch.object(raw, '_capture') as capture:
            with self.assertRaisesRegex(RuntimeError, 'mounted'):
                raw.create_raw_backup(dev)
            capture.assert_not_called()

    def test_failed_hash_and_truncated_capture_leave_no_marker(self):
        dev = FakeDevice()
        dev.bad_hash = True
        with self.assertRaisesRegex(RuntimeError, 'SHA256 disagree'):
            self.create(dev)
        self.assertFalse(list(self.root.glob('backups/*/raw-*/raw-backup.json')))

        def truncated(device, block, path):
            capture_fake(device, block, path)
            path.write_bytes(b'x')
        with self.assertRaisesRegex(RuntimeError, 'Truncated'):
            self.create(capture=truncated)
        self.assertFalse(list(self.root.glob('backups/*/raw-*/raw-backup.json')))

    def test_verify_rejects_modified_image_and_wrong_serial(self):
        path = self.create()
        image = path.parent / 'mmcblk0boot1.img'
        with image.open('r+b') as out:
            out.write(b'X')
        with self.assertRaisesRegex(RuntimeError, 'size/hash'):
            raw.verify_raw_backup(SERIAL)
        with self.assertRaises(RuntimeError):
            raw.verify_raw_backup('TESTSHOWOTHER')

    def test_verify_rejects_source_metadata_mapping_and_scope(self):
        path = self.create()
        original = path.read_text()
        for mutate in (lambda r: r.update(serial='TESTSHOWOTHER'),
                       lambda r: r.update(scope='pristine stock'),
                       lambda r: r['source'].update(properties='[ro.product.device]: [other]'),
                       lambda r: r['source']['by_name'].update(userdata='/dev/block/mmcblk0p9'),
                       lambda r: r['source']['mount_checks'].pop('mmcblk0-after-hash'),
                       lambda r: r['source']['block_sizes'].update(mmcblk0boot0=1024)):
            path.write_text(original)
            self.change_record(path, mutate)
            with self.assertRaises(RuntimeError):
                raw.verify_raw_backup(SERIAL)

    def test_verify_rejects_stderr_nonzero_exit_and_symlinks(self):
        path = self.create()
        stderr = path.parent / 'mmcblk0.img.partial.stderr'
        stderr.write_text('read failure\n')
        with self.assertRaisesRegex(RuntimeError, 'completion evidence'):
            raw.verify_raw_backup(SERIAL)
        stderr.write_text('')
        status = path.parent / 'mmcblk0.img.partial.exit'
        status.write_text('7')
        with self.assertRaisesRegex(RuntimeError, 'completion evidence'):
            raw.verify_raw_backup(SERIAL)
        status.write_text('0')
        image = path.parent / 'mmcblk0boot0.img'
        image.rename(path.parent / 'elsewhere')
        image.symlink_to(path.parent / 'elsewhere')
        with self.assertRaisesRegex(RuntimeError, 'size/hash'):
            raw.verify_raw_backup(SERIAL)

    def test_binary_transport_redirects_before_host_decoder(self):
        path = self.root / 'image.partial'
        calls = []

        class CaptureDevice:
            serial = SERIAL

            def command(self, *args, **kwargs):
                calls.append((args, kwargs))
                path.write_bytes(bytes(range(256)))
                Path(str(path) + '.stderr').write_bytes(b'')
                Path(str(path) + '.exit').write_text('0\n')
        raw._capture(CaptureDevice(), raw.BLOCKS['mmcblk0'], path)
        args, options = calls[0]
        self.assertEqual(args[:2], ('bash', '-c'))
        self.assertIn('shell -T cat /dev/block/mmcblk0 >/work/image.partial 2>', args[2])
        self.assertIn('exit "$rc"', args[2])
        self.assertEqual(options, {'timeout': 7200})
        self.assertEqual(path.read_bytes(), bytes(range(256)))


if __name__ == '__main__':
    unittest.main()
