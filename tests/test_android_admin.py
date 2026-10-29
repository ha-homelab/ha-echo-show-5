"""Offline administration tests: no SSH session or Android process is started."""
import copy
import hashlib
import importlib.util
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "android_admin.py"
spec = importlib.util.spec_from_file_location("android_admin", MODULE)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def config():
    return {"expected_serial": "G1234567890ABCDE", "ssh_host": "nas-fixture",
            "device_ip": "192.168.50.10", "local_port": 15551}


class ConfigTests(unittest.TestCase):
    def test_config_is_copied_and_only_known_fields_accepted(self):
        original = config()
        self.assertEqual(a.validate_config(original), original)
        self.assertIsNot(a.validate_config(original), original)
        for key in original:
            missing = copy.deepcopy(original)
            del missing[key]
            with self.assertRaises(a.AdminError):
                a.validate_config(missing)
        with self.assertRaises(a.AdminError):
            a.validate_config(dict(original, command="reboot"))

    def test_direct_transport_has_no_ssh_or_port_options(self):
        direct = {"transport": "direct", "expected_serial": config()["expected_serial"], "device_ip": "192.168.50.10"}
        self.assertEqual(a.validate_config(direct), direct)
        self.assertEqual(a.Android(direct).target, "192.168.50.10:5555")
        for changed in (dict(direct, ssh_host="nas"), dict(direct, local_port=12345),
                        dict(direct, transport="other"), dict(direct, device_ip="203.0.113.1")):
            with self.assertRaises(a.AdminError):
                a.validate_config(changed)
        self.assertEqual(a.validate_config(dict(config(), transport="ssh")), dict(config(), transport="ssh"))

    def test_direct_health_never_opens_ssh(self):
        direct = {"transport": "direct", "expected_serial": config()["expected_serial"], "device_ip": "192.168.50.10"}
        with patch.object(a, "load_config", return_value=direct), patch.object(a, "private_path"), \
                patch.object(a, "tunnel") as tunnel, patch.object(a, "write_private") as write, \
                patch.object(a, "run", return_value="") as run, patch.object(a.Android, "verify"), \
                patch.object(a.Android, "health", return_value={"snapshot": True}), redirect_stdout(io.StringIO()):
            self.assertEqual(a.main(["--config", "fixture.json", "health", "--output", "fixture-out.json"]), 0)
        tunnel.assert_not_called()
        write.assert_called_once_with("fixture-out.json", {"snapshot": True})
        self.assertEqual(run.call_args_list[0].args[0], ["adb", "connect", "192.168.50.10:5555"])
        self.assertFalse(any("disconnect" in call.args[0] for call in run.call_args_list))

    def test_rejects_ambiguous_identity_host_or_destination(self):
        for key, values in {
            "expected_serial": ["short", "G1234567890;reboot", "G1234567890ABCDE\n"],
            "ssh_host": ["-oProxyCommand=bad", "user@host", "host name", "$(echo bad)"],
            "device_ip": ["8.8.8.8", "127.0.0.1", "::1", "192.168.1.2;bad", None, 167772161],
            "local_port": [True, 22, 5037, 65536, "15551"],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(a.AdminError):
                    a.validate_config(dict(config(), **{key: value}))

    def test_ssh_listener_is_loopback_and_host_key_check_required(self):
        argv = a.tunnel_argv(config())
        self.assertIn("127.0.0.1:15551:192.168.50.10:5555", argv)
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("ExitOnForwardFailure=yes", argv)
        self.assertIn("BatchMode=yes", argv)
        self.assertIn("ControlPath=none", argv)
        self.assertIn("ControlPersist=no", argv)
        self.assertEqual(argv[-1], "nas-fixture")
        self.assertNotIn("-g", argv)

    def test_tunnel_refuses_an_existing_listener(self):
        with patch.object(a, "port_open", return_value=True), patch.object(a.subprocess, "Popen") as popen:
            with self.assertRaises(a.AdminError):
                with a.tunnel(config()):
                    self.fail("Occupied port must not yield")
            popen.assert_not_called()

    def test_tunnel_is_removed_when_an_operation_fails(self):
        process = MagicMock()
        process.poll.return_value = None
        with patch.object(a, "port_open", side_effect=[False, True]), patch.object(a.subprocess, "Popen", return_value=process):
            with self.assertRaises(a.AdminError):
                with a.tunnel(config()):
                    raise a.AdminError("Operation failed")
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=3)

    def test_private_json_mode_and_path(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(a, "ROOT", Path(directory)):
            out = Path(directory) / "private" / "test.json"
            a.write_private(out, {"status": "test"})
            self.assertEqual(json.loads(out.read_text()), {"status": "test"})
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            with self.assertRaises(a.AdminError):
                a.private_path(Path(directory) / "public.json")
            symlink = out.parent / "linked.json"
            symlink.symlink_to(out)
            with self.assertRaises(a.AdminError):
                a.private_path(symlink)

    def test_config_refuses_group_readable_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(a, "ROOT", Path(directory)):
            out = Path(directory) / "private" / "test.json"
            a.write_private(out, config())
            self.assertEqual(a.load_config(out), config())
            out.chmod(0o640)
            with self.assertRaises(a.AdminError):
                a.load_config(out)

    def test_no_path_traversal_in_shared_file_staging(self):
        self.assertEqual(a.staging_path("album-1.jpg"), a.STAGING + "/album-1.jpg")
        for name in ("../private", "/sdcard/file", "x/y", "-rf", "name;bad", "x\n", "..", ""):
            with self.assertRaises(a.AdminError):
                a.staging_path(name)


class IdentityTests(unittest.TestCase):
    def test_each_identity_mismatch_stops_the_operation(self):
        valid = [config()["expected_serial"], "cronos", "30", "1", "2000"]
        for index in range(len(valid)):
            sequence = list(valid)
            sequence[index] = "wrong"
            device = a.Android(config())
            with patch.object(device, "command", side_effect=sequence) as command:
                with self.assertRaises(a.AdminError):
                    device.verify()
                self.assertEqual(command.call_count, index + 1)

    def test_exact_target_used_and_screen_audio_disabled(self):
        device = a.Android(config())
        with patch.object(a, "run", return_value="ok") as run:
            device.command("shell", "id", "-u")
            self.assertEqual(run.call_args.args[0], ["adb", "-s", "127.0.0.1:15551", "shell", "id", "-u"])
        argv = a.scrcpy_argv(device.target, 60)
        self.assertIn("--no-audio", argv)
        self.assertIn("--serial=127.0.0.1:15551", argv)
        self.assertIn("--time-limit=60", argv)
        self.assertNotIn("--tcpip", argv)
        for value in (0, 3601, True):
            with self.assertRaises(a.AdminError):
                a.scrcpy_argv(device.target, value)

    def test_health_has_measurement_scope_and_no_target_identifiers(self):
        device = a.Android(config())
        outputs = ["11", "30", "armeabi-v7a,armeabi", "2024-02-05", "18.1-fixture",
                   "MemTotal: 1000000 kB\nMemAvailable: 250000 kB\nSwapTotal: 500000 kB\nSwapFree: 100000 kB",
                   "1234.45 2345.66", "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/dm-1 4000000 1000000 3000000 25% /data",
                   "Physical size: 960x480", "Physical density: 195", "255", "0",
                   "package:org.jitsi.meet versionCode:26000001\npackage:private.secret.app versionCode:1"]
        with patch.object(device, "verify") as verify, patch.object(device, "command", side_effect=outputs):
            result = device.health()
        verify.assert_called_once()
        self.assertEqual(result["measurements"]["data_free_kib"], 3000000)
        self.assertEqual(result["measurements"]["uptime_seconds"], 1234)
        self.assertEqual(result["measurements"]["packages"]["org.jitsi.meet"], 26000001)
        rendered = json.dumps(result)
        for private in ("private.secret.app", config()["expected_serial"], config()["device_ip"], config()["ssh_host"]):
            self.assertNotIn(private, rendered)
        self.assertIn("not HA", result["scope"])


class ApkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.apk"
        self.addCleanup(self.temp.cleanup)
        self.badging = "package: name='org.example.fixture' versionCode='4' versionName='1.0'\nminSdkVersion:'26'\n"

    def create(self, abi=None):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"fixture")
            if abi:
                archive.writestr("lib/" + abi + "/libfixture.so", b"fixture")
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_armv7_or_no_native_libraries_accepted(self):
        for abi in (None, "armeabi", "armeabi-v7a"):
            digest = self.create(abi)
            with patch.object(a, "run", return_value=self.badging):
                result = a.inspect_apk(self.path, "org.example.fixture", digest)
            self.assertEqual(result["minimum_api"], 26)
            self.assertEqual(result["version_code"], 4)

    def test_wrong_hash_rejected_before_invoking_aapt(self):
        self.create()
        with patch.object(a, "run") as run, self.assertRaises(a.AdminError):
            a.inspect_apk(self.path, "org.example.fixture", "0" * 64)
        run.assert_not_called()

    def test_64_bit_apk_rejected_before_invoking_aapt(self):
        digest = self.create("arm64-v8a")
        with patch.object(a, "run") as run, self.assertRaises(a.AdminError):
            a.inspect_apk(self.path, "org.example.fixture", digest)
        run.assert_not_called()

    def test_package_api_and_split_must_match(self):
        digest = self.create()
        for badging in (self.badging.replace("org.example.fixture", "org.example.other"),
                        self.badging.replace("'26'", "'31'"),
                        self.badging.replace("versionName='1.0'", "split='arm' versionName='1.0'"),
                        "not a manifest"):
            with patch.object(a, "run", return_value=badging), self.assertRaises(a.AdminError):
                a.inspect_apk(self.path, "org.example.fixture", digest)

    def test_legacy_aapt_sdk_label_remains_supported(self):
        digest = self.create()
        with patch.object(a, "run", return_value=self.badging.replace("minSdkVersion:", "sdkVersion:")):
            self.assertEqual(a.inspect_apk(self.path, "org.example.fixture", digest)["minimum_api"], 26)

    def test_inspect_does_not_open_a_connection(self):
        digest = self.create()
        with patch.object(a, "run", return_value=self.badging), patch.object(a, "tunnel") as tunnel, redirect_stdout(io.StringIO()):
            self.assertEqual(a.main(["inspect-apk", str(self.path), "--package", "org.example.fixture", "--sha256", digest]), 0)
        tunnel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
