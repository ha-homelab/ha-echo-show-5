import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import artifacts
import nas


SERIAL = 'TESTSHOW123456'


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [mock.patch.object(nas, 'ROOT', self.root), mock.patch.object(artifacts, 'ROOT', self.root)]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.temp.cleanup()

    def row(self, serial=SERIAL):
        return dict(port='1-3', serial=serial, vendor='1949', node='/dev/bus/usb/001/008')

    def make_device(self, responses):
        dev = object.__new__(nas.Device)
        dev.port, dev.serial = '1-3', SERIAL
        dev.command = mock.Mock(side_effect=responses)
        return dev

    def make_backup(self):
        folder = self.root / 'backups' / SERIAL / '20261002T000000Z'
        folder.mkdir(parents=True)
        boot = bytearray(8192)
        boot[:8] = b'ANDROID!'
        for offset, value in ((8, 2048), (16, 2048), (24, 0), (36, 2048)):
            struct.pack_into('<I', boot, offset, value)
        (folder / 'boot.emmc.win').write_bytes(boot)
        for name in ('system.ext4.win000', 'data.ext4.win000'):
            with tarfile.open(folder / name, 'w:gz') as arc:
                item = tarfile.TarInfo('example.txt')
                payload = b'Fixture data, never real device data.'
                item.size = len(payload)
                arc.addfile(item, io.BytesIO(payload))
        (folder / 'recovery.log').write_text('[BACKUP COMPLETED IN 5 SECONDS]\n')
        self.record_backup(folder)
        return folder

    def record_backup(self, folder):
        entries = [dict(path=p.name, size=p.stat().st_size, sha256=artifacts.digest(p))
                   for p in folder.iterdir() if '.win' in p.name]
        data = dict(serial=SERIAL, product='cronos', files=entries,
                    completion_evidence='[BACKUP COMPLETED IN 5 SECONDS]',
                    recovery_log_sha256=artifacts.digest(folder / 'recovery.log'))
        (folder / 'backup.json').write_text(json.dumps(data))

    def make_artifact(self, name, contents=None, product='cronos'):
        (self.root / 'downloads').mkdir(exist_ok=True)
        p = self.root / 'downloads' / name
        if contents is not None:
            p.write_bytes(contents)
        else:
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('META-INF/com/android/metadata', 'pre-device=' + product + '\n')
        (self.root / 'lineage-artifact.json').write_text(json.dumps(dict(name=name,
            size=p.stat().st_size, sha256=artifacts.digest(p), url='https://example.invalid/rom.zip')))
        return p

    def make_unlock_package(self, product='cronos'):
        package = self.root / 'vendor' / 'amonet'
        names = ['device.prop', 'fastbrick.sh', 'profile.sh', 'bin/fastboot', 'bin/fastboot32',
                 'bin/fastbrick.img', 'bin/preloader.img', 'bin/lk.bin', 'bin/tz.img',
                 'bin/tee-payload.bin', 'bin/cronos-kaeru.bin', 'bin/twrp.img']
        for name in names:
            p = package / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('Synthetic fixture, not executable firmware: ' + name)
        (package / 'device.prop').write_text('DEVICE=' + product + '\nDEVICE_TYPE_ID=A1XWJRHALS1REP\n')
        downloads = self.root / 'downloads'
        downloads.mkdir()
        archive = downloads / 'amonet.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name in names:
                z.write(package / name, 'amonet/' + name)
        checksum = artifacts.digest(archive)
        (self.root / 'amonet-artifact.json').write_text(json.dumps(dict(name=archive.name,
            size=archive.stat().st_size, sha256=checksum)))
        review = dict(release='2.0.1', product='cronos', archive_sha256=checksum,
                      files={name: artifacts.digest(package / name) for name in names})
        (self.root / 'amonet-review.json').write_text(json.dumps(review))
        private = self.root / 'private'
        private.mkdir(exist_ok=True)
        (private / 'host-release-validation.json').write_text(json.dumps(dict(
            schema_version=1, product='cronos', archive_sha256=checksum,
            passed_without_usb=True, image_id='fixture-image')))
        return package

    def test_select_requires_exact_serial(self):
        with self.assertRaises(ValueError):
            nas.select_device([self.row()], '1-3', '123456')

    def test_select_rejects_ambiguous_port(self):
        with self.assertRaises(ValueError):
            nas.select_device([self.row(), self.row()], '1-3', SERIAL)

    def test_select_rejects_unknown_vendor(self):
        row = self.row()
        row['vendor'] = 'f400'
        with self.assertRaises(ValueError):
            nas.select_device([row], '1-3', SERIAL)

    def test_fastboot_rejects_dot_before_further_commands(self):
        dev = self.make_device([SERIAL + '\tfastboot', 'product: BISCUIT'])
        with self.assertRaises(RuntimeError):
            dev.fastboot_probe()
        self.assertEqual(dev.command.call_count, 2)

    def test_fastboot_rejects_multiple_devices(self):
        dev = self.make_device([SERIAL + '\tfastboot\nDOT123\tfastboot'])
        with self.assertRaises(RuntimeError):
            dev.fastboot_probe()
        self.assertEqual(dev.command.call_count, 1)

    def test_fastboot_accepts_supported_identity(self):
        dev = self.make_device([SERIAL + '\tfastboot', '(bootloader) product: CRONOS',
                                'unlock_status: false', 'lk_build_desc: test'])
        self.assertEqual(dev.fastboot_probe()['product'], 'CRONOS')

    def test_recovery_rejects_normal_android(self):
        dev = self.make_device(['List of devices attached\n' + SERIAL + '\tdevice',
                                '[ro.product.device]: [cronos]\n[ro.build.version.release]: [11]'])
        with self.assertRaises(RuntimeError):
            dev.adb_probe()

    def test_active_dot_container_blocks_device_operation(self):
        with mock.patch.object(nas, 'run', return_value='ha-echo-pilot-fixture'), self.assertRaises(RuntimeError):
            nas.ensure_idle()

    def test_usb_permissions_restored_after_failure(self):
        info = SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_ino=10, st_rdev=22, st_uid=0, st_gid=0)
        node = mock.Mock()
        node.stat.return_value = info
        node.exists.return_value = True
        row = self.row()
        with mock.patch.object(nas, 'Path', return_value=node), mock.patch.object(nas, 'run') as run, \
                mock.patch.object(nas, 'usb_inventory', return_value=[row]):
            with self.assertRaises(ValueError):
                with nas.usb_group_access(row):
                    self.assertEqual(run.call_args.args[0][3], '0660')
                    raise ValueError('device command failed')
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0][3], '0600')

    def test_usb_permissions_do_not_modify_replacement_node(self):
        before = SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_ino=10, st_rdev=22, st_uid=0, st_gid=0)
        after = SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_ino=11, st_rdev=22, st_uid=0, st_gid=0)
        node = mock.Mock()
        node.stat.side_effect = [before, after]
        node.exists.return_value = True
        with mock.patch.object(nas, 'Path', return_value=node), mock.patch.object(nas, 'run') as run, \
                mock.patch.object(nas, 'usb_inventory', return_value=[self.row()]):
            with nas.usb_group_access(self.row()):
                pass
            self.assertEqual(run.call_count, 1)

    def test_usb_group_access_needs_no_change_when_already_allowed(self):
        node = mock.Mock()
        node.stat.return_value = SimpleNamespace(st_mode=stat.S_IFCHR | 0o660)
        with mock.patch.object(nas, 'Path', return_value=node), mock.patch.object(nas, 'run') as run:
            with nas.usb_group_access(self.row()):
                pass
            run.assert_not_called()

    def test_missing_unlock_archive_never_opens_device(self):
        dev = mock.Mock()
        with self.assertRaises(FileNotFoundError):
            nas.unlock(dev)
        self.assertFalse(dev.fastboot_probe.called)
        self.assertFalse(dev.command.called)

    def test_complete_audited_unlock_tree(self):
        self.make_unlock_package()
        self.assertEqual(nas.verify_unlock_package()['product'], 'cronos')

    def test_public_release_audit_without_private_host_evidence_is_rejected(self):
        self.make_unlock_package()
        (self.root / 'private' / 'host-release-validation.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'validate_host_release'):
            nas.verify_unlock_package()

    def test_changed_unlock_payload_rejected(self):
        package = self.make_unlock_package()
        (package / 'bin/fastbrick.img').write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            nas.verify_unlock_package()

    def test_unreviewed_file_in_unlock_tree_rejected(self):
        package = self.make_unlock_package()
        (package / 'extra.sh').write_text('extra')
        with self.assertRaises(RuntimeError):
            nas.verify_unlock_package()

    def test_matching_hashes_do_not_allow_wrong_package_model(self):
        self.make_unlock_package(product='biscuit')
        with self.assertRaises(RuntimeError):
            nas.verify_unlock_package()

    def test_changed_host_image_blocks_unlock_before_device_access(self):
        self.make_unlock_package()
        dev = mock.Mock(image='different-image')
        with self.assertRaises(RuntimeError):
            nas.unlock(dev)
        self.assertFalse(dev.fastboot_probe.called)
        self.assertFalse(dev.command.called)

    def test_backup_valid_fixture(self):
        folder = self.make_backup()
        self.assertEqual(nas.verify_backup(SERIAL), folder / 'backup.json')

    def test_backup_corruption_is_detected(self):
        folder = self.make_backup()
        with (folder / 'boot.emmc.win').open('ab') as f:
            f.write(b'corruption')
        with self.assertRaises(RuntimeError):
            nas.verify_backup(SERIAL)

    def test_backup_missing_first_split_is_detected(self):
        folder = self.make_backup()
        (folder / 'data.ext4.win000').rename(folder / 'data.ext4.win001')
        self.record_backup(folder)
        with self.assertRaises(RuntimeError):
            nas.verify_backup(SERIAL)

    def test_hash_matching_garbage_is_not_a_backup(self):
        folder = self.make_backup()
        (folder / 'data.ext4.win000').write_bytes(b'not a backup')
        self.record_backup(folder)
        with self.assertRaises((RuntimeError, tarfile.TarError)):
            nas.verify_backup(SERIAL)

    def test_backup_requires_completion_evidence(self):
        folder = self.make_backup()
        p = folder / 'backup.json'
        data = json.loads(p.read_text())
        data.pop('completion_evidence')
        p.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError):
            nas.verify_backup(SERIAL)

    def test_backup_rejects_other_serial(self):
        self.make_backup()
        with self.assertRaises(RuntimeError):
            nas.verify_backup('OTHER123456')

    def test_raw_backup_marker_alone_does_not_authorize_install(self):
        folder = self.root / 'backups' / SERIAL / 'raw-20261002T000000Z'
        folder.mkdir(parents=True)
        (folder / 'raw-backup.json').write_text('{}')
        import rawbackup
        with mock.patch.object(rawbackup, 'ROOT', self.root), self.assertRaises(RuntimeError):
            nas.verify_backup(SERIAL)

    def test_format_without_backup_never_opens_device(self):
        dev = mock.Mock(serial=SERIAL)
        with self.assertRaises(RuntimeError):
            nas.prepare_partition(dev, 'format-data')
        dev.adb_probe.assert_not_called()
        dev.command.assert_not_called()

    def test_enable_system_writes_requires_zero_readback(self):
        self.make_backup()
        dev = mock.Mock(serial=SERIAL)
        dev.adb.return_value = 'tw_mount_system_ro = 0\r\n'
        with mock.patch.object(nas, 'confirm'), mock.patch.object(nas, 'twrp_step') as step, \
                mock.patch('builtins.print'):
            nas.prepare_partition(dev, 'enable-system-writes')
        step.assert_called_once_with(dev, ['remountrw'])
        dev.adb.assert_called_once_with('shell', 'twrp', 'get', 'tw_mount_system_ro', timeout=15)

    def test_enable_system_writes_rejects_nonzero_unknown_or_ambiguous_readback(self):
        self.make_backup()
        for response in ('tw_mount_system_ro = 2', 'tw_mount_system_ro = unknown', '',
                         'unrelated = 0', 'tw_mount_system_ro = 0\ntw_mount_system_ro = 2'):
            with self.subTest(response=response):
                dev = mock.Mock(serial=SERIAL)
                dev.adb.return_value = response
                with mock.patch.object(nas, 'confirm'), mock.patch.object(nas, 'twrp_step') as step, \
                        mock.patch('builtins.print'), self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                    nas.prepare_partition(dev, 'enable-system-writes')
                step.assert_called_once_with(dev, ['remountrw'])
                dev.adb.assert_called_once_with('shell', 'twrp', 'get', 'tw_mount_system_ro', timeout=15)

    def test_enable_system_writes_query_failure_stops_without_retry(self):
        self.make_backup()
        for error in (nas.subprocess.TimeoutExpired('adb', 15), RuntimeError('ADB disconnected')):
            with self.subTest(error=type(error).__name__):
                dev = mock.Mock(serial=SERIAL)
                dev.adb.side_effect = error
                with mock.patch.object(nas, 'confirm'), mock.patch.object(nas, 'twrp_step') as step, \
                        mock.patch('builtins.print'), self.assertRaisesRegex(RuntimeError, 'failed or timed out'):
                    nas.prepare_partition(dev, 'enable-system-writes')
                step.assert_called_once_with(dev, ['remountrw'])
                dev.adb.assert_called_once_with('shell', 'twrp', 'get', 'tw_mount_system_ro', timeout=15)

    def test_old_recovery_log_cannot_verify_new_operation(self):
        old = "I:Command 'format data' received\nI:Done reading ORS command from command line\n"
        dev = mock.Mock(serial=SERIAL)
        dev.adb.side_effect = [old, old, 'rootfs / rootfs rw 0 0']
        with self.assertRaisesRegex(RuntimeError, 'No matching new'):
            nas.twrp_step(dev, ['format', 'data'])

    def test_corrupt_twrp_backup_cannot_fall_back_to_raw_marker(self):
        folder = self.make_backup()
        (folder / 'boot.emmc.win').write_bytes(b'corrupt')
        raw_folder = self.root / 'backups' / SERIAL / 'raw-20261002T000000Z'
        raw_folder.mkdir()
        (raw_folder / 'raw-backup.json').write_text('{}')
        import rawbackup
        with mock.patch.object(rawbackup, 'verify_raw_backup') as verify_raw:
            with self.assertRaises(RuntimeError):
                nas.verify_backup(SERIAL)
            verify_raw.assert_not_called()

    def test_rom_correct_metadata(self):
        p = self.make_artifact('lineage.zip')
        self.assertEqual(artifacts.verify('lineage'), p)

    def test_rom_wrong_model_rejected(self):
        self.make_artifact('lineage.zip', product='biscuit')
        with self.assertRaises(ValueError):
            artifacts.verify('lineage')

    def test_rom_wrong_file_type_rejected(self):
        self.make_artifact('wrong-model.img', contents=b'not a ROM')
        with self.assertRaises(ValueError):
            artifacts.verify('lineage')

    def test_writes_cannot_be_confirmed_without_terminal(self):
        with mock.patch('sys.stdin.isatty', return_value=False), self.assertRaises(RuntimeError):
            nas.confirm('unlock', SERIAL)


if __name__ == '__main__':
    unittest.main()
