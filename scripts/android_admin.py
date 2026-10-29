#!/usr/bin/env python3
"""Bounded Android administration over an existing SSH or direct LAN route.

No device shell, root, listener setup or firmware operation is exposed. Local
ADB uses its normal key; first use may require approval on the Android screen.
"""
import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAGING = "/sdcard/Download/Show5Admin"
PACKAGES = ("com.msp1974.vacompanion", "io.homeassistant.companion.android.minimal",
            "org.hahomelab.show5sip", "org.jitsi.meet", "org.videolan.vlc", "play.ott.foss", "com.sendspindroid")
PROPERTIES = {"android": "ro.build.version.release", "api": "ro.build.version.sdk",
              "abi": "ro.product.cpu.abilist", "patch": "ro.build.version.security_patch",
              "lineage": "ro.lineage.version"}


class AdminError(Exception):
    """An intentionally sanitized operator error."""


def validate_config(data):
    if not isinstance(data, dict):
        raise AdminError("Configuration must be an object")
    transport = data.get("transport", "ssh")
    if transport not in ("ssh", "direct"):
        raise AdminError("Transport must be ssh or direct")
    fields = {"expected_serial", "device_ip"}
    if transport == "ssh":
        fields.update({"ssh_host", "local_port"})
    if "transport" in data:
        fields.add("transport")
    if set(data) != fields:
        raise AdminError("Use only the documented fields for the selected transport")
    if not isinstance(data["expected_serial"], str) or not re.fullmatch(r"[A-Z0-9]{12,32}", data["expected_serial"]):
        raise AdminError("Expected serial must be the complete Android serial")
    if transport == "ssh":
        if not isinstance(data["ssh_host"], str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}", data["ssh_host"]):
            raise AdminError("SSH host must be a configured host alias without arguments")
        port = data["local_port"]
        if type(port) is not int or not 1024 <= port <= 65535 or port == 5037:
            raise AdminError("Choose an unused local port from 1024 to 65535, excluding 5037")
    if not isinstance(data["device_ip"], str):
        raise AdminError("Device address must be a private IPv4 address")
    try:
        address = ipaddress.IPv4Address(data["device_ip"])
    except (ValueError, TypeError, ipaddress.AddressValueError):
        raise AdminError("Device address must be a private IPv4 address") from None
    if not any(address in network for network in (
            ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"))):
        raise AdminError("Device address must be an RFC1918 address")
    return dict(data)


def private_path(value):
    path = Path(value).expanduser().absolute()
    if path.is_symlink():
        raise AdminError("Private path must not be a symbolic link")
    try:
        path.resolve().relative_to((ROOT / "private").resolve())
    except ValueError:
        raise AdminError("Store configuration, receipts and pulled files under this checkout's private/ directory") from None
    return path


def load_config(path):
    path = private_path(path)
    if not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise AdminError("Configuration must be a private regular file (chmod 600)")
    if path.stat().st_size > 16384:
        raise AdminError("Configuration is too large")
    try:
        return validate_config(json.loads(path.read_text()))
    except (ValueError, UnicodeError):
        raise AdminError("Configuration is not valid JSON") from None


def write_private(path, value):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".admin-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, indent=2)
            out.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(argv, timeout=15):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise AdminError("Local tool failed or timed out; check the configured tools and connection") from None
    if result.returncode or len(result.stdout) > 1024 * 1024:
        # Never echo shell output: it can contain identities, filenames or credentials.
        raise AdminError("Operation failed; no private command output was printed")
    return result.stdout.strip()


def tunnel_argv(config):
    return ["ssh", "-N", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=8",
            "-o", "ControlMaster=no", "-o", "ControlPath=none", "-o", "ControlPersist=no",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", "-L",
            "127.0.0.1:{local_port}:{device_ip}:5555".format(**config), config["ssh_host"]]


def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def tunnel(config):
    if port_open(config["local_port"]):
        raise AdminError("Local port is already in use; choose another to avoid attaching the wrong tunnel")
    process = subprocess.Popen(tunnel_argv(config), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not port_open(config["local_port"]):
            if process.poll() is not None or time.monotonic() >= deadline:
                raise AdminError("SSH forwarding unavailable; verify the existing host key and SSH login")
            time.sleep(0.1)
        if process.poll() is not None:
            raise AdminError("SSH forwarding ended before use")
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


class Android:
    def __init__(self, config, adb="adb"):
        self.config = config
        self.adb = adb
        self.target = (config["device_ip"] + ":5555" if config.get("transport") == "direct"
                       else "127.0.0.1:" + str(config["local_port"]))

    def command(self, *args, timeout=15):
        return run([self.adb, "-s", self.target, *args], timeout)

    def verify(self):
        expected = (("ro.serialno", self.config["expected_serial"]),
                    ("ro.product.device", "cronos"), ("ro.build.version.sdk", "30"),
                    ("ro.adb.secure", "1"))
        for prop, value in expected:
            if self.command("shell", "getprop", prop) != value:
                raise AdminError("Device identity, Android API or secure ADB check failed; nothing changed")
        if self.command("shell", "id", "-u") != "2000":
            raise AdminError("Expected ordinary ADB shell, not root; nothing changed")

    def health(self):
        self.verify()
        data = {key: self.command("shell", "getprop", prop) for key, prop in PROPERTIES.items()}
        memory = self.command("shell", "cat", "/proc/meminfo")
        data["memory_kib"] = {name: int(value) for name, value in
                              re.findall(r"^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+) kB$", memory, re.M)}
        uptime = self.command("shell", "cat", "/proc/uptime").split()
        data["uptime_seconds"] = int(float(uptime[0])) if uptime else None
        disk = self.command("shell", "df", "-k", "/data").splitlines()
        fields = disk[-1].split() if len(disk) > 1 else []
        data["data_free_kib"] = int(fields[3]) if len(fields) >= 6 and fields[3].isdigit() else None
        data["screen"] = {"size": self.command("shell", "wm", "size"),
                          "density": self.command("shell", "wm", "density"),
                          "brightness": self.command("shell", "settings", "get", "system", "screen_brightness"),
                          "brightness_mode": self.command("shell", "settings", "get", "system", "screen_brightness_mode")}
        packages = self.command("shell", "cmd", "package", "list", "packages", "--show-versioncode")
        data["packages"] = {}
        for package in PACKAGES:
            match = re.search(r"^package:" + re.escape(package) + r"\s+versionCode:(\d+)$", packages, re.M)
            data["packages"][package] = int(match[1]) if match else None
        return {"schema": 1, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "identity_verified": True, "transport": "direct_lan_adb" if self.config.get("transport") == "direct" else "ssh_to_lan_adb", "measurements": data,
                "scope": "Android snapshot only; not HA availability, audio/video acceptance or continuous monitoring"}


def staging_path(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", name) or name in (".", ".."):
        raise AdminError("Staged filename must be one plain filename, without directories")
    return STAGING + "/" + name


def inspect_apk(path, expected_package, expected_sha256, aapt2="aapt2"):
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+", expected_package):
        raise AdminError("Expected package ID is invalid")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise AdminError("An independently obtained SHA-256 digest is required")
    path = Path(path).expanduser().resolve()
    if not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024 * 1024:
        raise AdminError("APK must be a regular file no larger than 1 GiB")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256.lower():
        raise AdminError("APK digest does not match")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            abis = sorted({name.split("/")[1] for name in names if re.fullmatch(r"lib/[^/]+/[^/]+\.so", name)})
            if "AndroidManifest.xml" not in names:
                raise AdminError("APK manifest is missing")
    except zipfile.BadZipFile:
        raise AdminError("Invalid APK archive") from None
    if abis and not {"armeabi-v7a", "armeabi"}.intersection(abis):
        raise AdminError("APK native libraries do not support this 32-bit ARM device")
    badging = run([aapt2, "dump", "badging", str(path)], 30)
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)'", badging, re.M)
    minimum = re.search(r"^(?:sdkVersion|minSdkVersion):'(\d+)'", badging, re.M)
    if not package or package[1] != expected_package:
        raise AdminError("APK package ID does not match")
    if not minimum or int(minimum[1]) > 30:
        raise AdminError("APK requires an unsupported Android version")
    if re.search(r"^package:.*\bsplit='", badging, re.M):
        raise AdminError("Split APKs are not supported by this helper")
    return {"package": package[1], "version_code": int(package[2]), "minimum_api": int(minimum[1]),
            "native_abis": abis, "sha256": digest.hexdigest()}


def scrcpy_argv(target, seconds, executable="scrcpy"):
    if type(seconds) is not int or not 10 <= seconds <= 3600:
        raise AdminError("Screen session must be between 10 and 3600 seconds")
    return [executable, "--serial=" + target, "--no-audio", "--max-size=960", "--max-fps=15",
            "--video-bit-rate=2M", "--time-limit=" + str(seconds)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Private device JSON; required except for inspect-apk")
    parser.add_argument("--adb", default="adb")
    sub = parser.add_subparsers(dest="action", required=True)
    health = sub.add_parser("health", help="Save one sanitized snapshot, without changing Android settings")
    health.add_argument("--output", required=True)
    screen = sub.add_parser("screen", help="Open bounded interactive scrcpy without audio capture")
    screen.add_argument("--seconds", type=int, default=900)
    screen.add_argument("--scrcpy", default="scrcpy")
    for action in ("inspect-apk", "install"):
        apk = sub.add_parser(action)
        apk.add_argument("apk")
        apk.add_argument("--package", required=True)
        apk.add_argument("--sha256", required=True)
        apk.add_argument("--aapt2", default="aapt2")
    push = sub.add_parser("push", help="Copy one file into the shared Show5Admin downloads folder")
    push.add_argument("local_file")
    push.add_argument("name")
    pull = sub.add_parser("pull", help="Copy one staged file into this checkout's private/ directory")
    pull.add_argument("name")
    pull.add_argument("local_file")
    args = parser.parse_args(argv)
    try:
        apk_info = None
        if args.action in ("inspect-apk", "install"):
            apk_info = inspect_apk(args.apk, args.package, args.sha256, args.aapt2)
            if args.action == "inspect-apk":
                print(json.dumps(apk_info, indent=2))
                return 0
        if not args.config:
            raise AdminError("--config is required for device actions")
        config = load_config(args.config)
        device = Android(config, args.adb)
        # Validate inputs before opening a connection.
        if args.action == "health":
            private_path(args.output)
        elif args.action == "screen":
            scrcpy_argv(device.target, args.seconds, args.scrcpy)
        elif args.action in ("push", "pull"):
            remote = staging_path(args.name)
            if args.action == "pull":
                local = private_path(args.local_file)
                if local.exists():
                    raise AdminError("Pull destination already exists; choose a new filename")
            else:
                local = Path(args.local_file).expanduser().resolve()
                if not local.is_file():
                    raise AdminError("Push source must be a regular file")
        with (nullcontext() if config.get("transport") == "direct" else tunnel(config)):
            try:
                run([args.adb, "connect", device.target], 15)
                device.verify()
                if args.action == "health":
                    write_private(args.output, device.health())
                    print("Android snapshot saved; identity verified. No availability or media claim is implied.")
                elif args.action == "screen":
                    # scrcpy gets the same ADB binary and target; no device audio is opened.
                    environment = dict(os.environ, ADB=args.adb)
                    result = subprocess.run(scrcpy_argv(device.target, args.seconds, args.scrcpy),
                                            env=environment, timeout=args.seconds + 30, check=False)
                    if result.returncode:
                        raise AdminError("Screen session ended with an error")
                elif args.action == "install":
                    device.verify()
                    if inspect_apk(args.apk, args.package, args.sha256, args.aapt2) != apk_info:
                        raise AdminError("APK changed after the initial inspection")
                    result = device.command("install", "-r", str(Path(args.apk).expanduser().resolve()), timeout=180)
                    if not result.endswith("Success"):
                        raise AdminError("Android did not confirm package installation")
                    installed = device.command("shell", "cmd", "package", "list", "packages", "--show-versioncode", apk_info["package"])
                    wanted = "package:{} versionCode:{}".format(apk_info["package"], apk_info["version_code"])
                    if wanted not in installed.splitlines():
                        raise AdminError("Installed package version could not be confirmed")
                    print("Package installed and version confirmed. Runtime permissions and app acceptance remain separate.")
                elif args.action == "push":
                    device.verify()
                    device.command("shell", "mkdir", "-p", STAGING)
                    device.command("push", str(local), remote, timeout=180)
                    print("File copied into the shared Show5Admin downloads folder.")
                elif args.action == "pull":
                    device.verify()
                    local.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    fd = os.open(local, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(fd)
                    try:
                        device.command("pull", remote, str(local), timeout=180)
                        os.chmod(local, 0o600)
                    except Exception:
                        local.unlink(missing_ok=True)
                        raise
                    print("Staged file saved privately.")
            finally:
                # Direct transports are shared by the workstation ADB server.
                # Leave them connected so another screen/admin session survives.
                if config.get("transport") != "direct":
                    try:
                        run([args.adb, "disconnect", device.target], 5)
                    except AdminError:
                        pass
        return 0
    except (AdminError, OSError, subprocess.TimeoutExpired) as error:
        if isinstance(error, AdminError):
            print(str(error), file=sys.stderr)
        else:
            print("Local operation failed; private details omitted", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
