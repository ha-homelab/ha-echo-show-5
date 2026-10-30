# Remote screen, file transfer and Android health tools

[`scripts/android_admin.py`](../scripts/android_admin.py) adds an operator tool for
an already authorized **cronos / Android 11** device. By default it uses the
existing SSH login to the NAS, then the device ADB listener. An explicit direct
LAN mode also supports a workstation already allowed to reach that listener.
It does not install an
SSH server, enable Telnet, change ADB settings, grant root or touch firmware.

The available operations are:

- `health`: one timestamped snapshot of versions, RAM, swap, storage, uptime,
  screen settings and the known room apps. Unknown package names, device serials,
  network addresses and account information are omitted from the receipt.
- `screen`: interactive screen and touch control through scrcpy, with audio
  capture disabled, a 960-pixel size limit, 15 fps and a bounded session.
- `push` / `pull`: transfer a named file through a dedicated shared Downloads
  folder. Pull destinations and health receipts stay in ignored `private/`.
- `inspect-apk`: offline SHA-256, package ID, minimum Android API, split APK and
  native ABI checks. It never contacts a device.
- `install`: the same APK checks, then an update preserving app data (`-r`). It
  does not request downgrades, uninstall the previous app or grant every
  permission. Android still enforces its installed-app signature checks.

The source and offline tests are implemented. Hardware acceptance of a specific
screen session, APK and transport remains a separate dated result. A successful
health snapshot says that Android answered; it does not imply that HA, a camera,
audio playback or an ongoing call is healthy.

## Configure one exact device

Install Python 3, Android Platform Tools and a current scrcpy on the operator
computer. APK inspection also needs the Android SDK Build Tools `aapt2`.
For SSH mode, SSH must already work noninteractively with a known host key and
allow the requested forwarding destination. The helper does not accept unknown
SSH host keys automatically or change the NAS forwarding policy.

Create `private/admin/show-one.json`, mode `0600`, with your private bindings:

```json
{
  "expected_serial": "G1234567890ABCDE",
  "ssh_host": "my-nas",
  "device_ip": "192.168.50.10",
  "local_port": 15551
}
```

Use the complete actual Android serial, not a USB address or an abbreviated
label. The example serial and address are placeholders. Use another unused local
port and a separate file for the other Show. A running process on the selected
port causes refusal; the helper never reuses an unidentified tunnel.

Every connected operation checks the serial, `cronos`, API 30, secure ADB and
shell UID 2000. A mismatch stops work. The workstation's normal ADB key is used;
a new workstation may still need the user to accept its debugging prompt on the
Show. The helper does not bypass that approval.

```sh
chmod 600 private/admin/show-one.json
python3 scripts/android_admin.py --config private/admin/show-one.json \
  health --output private/admin/show-one-health.json
python3 scripts/android_admin.py --config private/admin/show-one.json \
  screen --seconds 900
```

In SSH mode, closing the screen session or reaching its time limit disconnects
that local ADB transport and tears down the SSH tunnel. It does not restart the NAS ADB
server or disconnect other device transports. Screen control uses scrcpy's
explicit serial selector, not automatic selection of whichever device appears
first. See the [scrcpy connection reference](https://github.com/Genymobile/scrcpy/blob/master/doc/connection.md).

The SSH listener binds only to `127.0.0.1`. Encryption covers the workstation to
NAS hop. **The NAS-to-Show hop is still the installed legacy ADB transport on the
local network; this does not turn it into TLS ADB.** Keep that hop inside the
existing trusted management network and its access policy. The helper does not
publish port 5555 or an ADB server to the Internet.

## Direct trusted-LAN mode

On **2026-10-29**, the existing NAS SSH service refused this forwarding
destination with `administratively prohibited`, while direct authorized LAN ADB
worked. The tool does not weaken that SSH policy or silently fall back to a
less protected route. Select the intended transport explicitly:

```json
{
  "transport": "direct",
  "expected_serial": "G1234567890ABCDE",
  "device_ip": "192.168.50.10"
}
```

Direct mode accepts neither `ssh_host` nor `local_port`. The same serial, device,
API, secure-ADB and non-root checks apply. Use the same `health`, `screen`, APK
and file commands with this private config. **The whole workstation-to-device
connection is legacy unencrypted LAN ADB**, using the existing authorized key.
It requires the workstation's normal permitted management-network route. No
new listener, firewall rule, key approval bypass or Internet forwarding is
created. Do not use this mode over an untrusted network.

Direct mode leaves the workstation ADB connection open on completion. The
connection is shared with other local tools, so disconnecting it after a health
read could interrupt an existing screen session. Close it separately only when
you have finished every tool using that target.

## File transfer without a device SFTP daemon

A dedicated `/sdcard/Download/Show5Admin/` folder is convenient for ordinary
photos or media imports. It is shared Android storage, so it is not a secret
vault. Only plain filenames are accepted; arbitrary device paths and shell
arguments are not exposed.

```sh
python3 scripts/android_admin.py --config private/admin/show-one.json \
  push /path/to/photo.jpg photo.jpg
python3 scripts/android_admin.py --config private/admin/show-one.json \
  pull photo.jpg private/admin/received-photo.jpg
```

The destination of `pull` must not already exist. Its final mode is `0600`.
For app-private backups continue using the app's existing reviewed backup path;
this helper deliberately does not pretend that shared-storage transfer is an
app-private backup. SFTP on the NAS can remain a separate operator convenience;
SFTP on Android is unnecessary for these operations.

## Inspect and install one selected package

Obtain a release from its publisher, and retain its independently published
SHA-256 or another reviewed release digest. Supplying a digest protects against
accidental substitution; it does not establish that a publisher is trustworthy.
The helper does not download or choose packages automatically.

```sh
python3 scripts/android_admin.py inspect-apk downloads/selected.apk \
  --package org.example.selected \
  --sha256 REPLACE_WITH_REVIEWED_64_HEX_DIGEST \
  --aapt2 /path/to/android-sdk/build-tools/36.0.0/aapt2
python3 scripts/android_admin.py --config private/admin/show-one.json \
  install downloads/selected.apk --package org.example.selected \
  --sha256 REPLACE_WITH_REVIEWED_64_HEX_DIGEST \
  --aapt2 /path/to/android-sdk/build-tools/36.0.0/aapt2
```

A native package must include `armeabi-v7a` or `armeabi`; a Java/Kotlin-only APK
may contain no native libraries. Packages requiring API 31+, mismatched package
IDs, invalid digests and split APK files are refused. An accepted APK may still
require hardware, codecs or Google services absent from this ROM. Installation
is complete only when Android confirms success and the installed version code
matches. Test launch, permissions, reboot behavior and return to voice separately.

Install outside an active call or recording. The helper does not manage the
room session policy and should not be used as a parallel app updater during a
call. Keep the existing previous-version artifact and app backup before an
update; this tool does not perform a destructive rollback.

## Optional radio and multiroom clients: dated compatibility gate

Reviewed **2026-10-29**, using publisher sources:

- **SendspinDroid 2.0.0** is `com.sendspindroid`, minimum API 26. Its release
  requires **Music Assistant 2.10.7 or later**, local-network SendSpin 1.0 and
  encrypted connections. Existing older player identities/groups may need
  remapping. The observed MA 2.10.8 server clears this version gate; it is not a
  playback or synchronization result. Use the publisher APK rather than its
  app-bundle `.aab`. The pinned APK was inspected: version code 20025, minimum
  API 26, ARMv7 included, SHA-256 matching GitHub asset metadata, one valid v2
  APK signer. See [the pinned artifact record](../sendspindroid-artifact.json).
  Device playback is still a separate check.
  [Release notes](https://github.com/chrisuthe/SendspinDroid/releases/tag/v2.0.0),
  [pinned Android build](https://github.com/chrisuthe/SendspinDroid/blob/v2.0.0/android/app/build.gradle.kts).
- **Home Assistant Mobile BLE Proxy 2026.08.3** is
  `com.zen3515.homeassistant_mobile_ble_proxy`, minimum API 24. It runs a visible
  foreground service and an ESPHome-compatible endpoint, with optional Noise
  encryption. Android 11 scanning uses location/Bluetooth permissions and system
  radio/location state. A target beacon or sensor is required to establish
  actual usefulness; installation alone does not prove reception, GATT access
  or recovery under load. Enable Noise and select the intended LAN before
  advertising it to HA. [Publisher documentation](https://github.com/Zen3515/homeassistant-mobile-ble-proxy),
  [pinned manifest](https://github.com/Zen3515/homeassistant-mobile-ble-proxy/blob/v2026.08.3/app/src/main/AndroidManifest.xml),
  [pinned build](https://github.com/Zen3515/homeassistant-mobile-ble-proxy/blob/v2026.08.3/app/build.gradle.kts).

The pinned SendspinDroid artifact is registered in the normal download tool:

```sh
python3 scripts/artifacts.py fetch sendspindroid
python3 scripts/artifacts.py verify sendspindroid
```

These commands enforce the pinned size, SHA-256, APK suffix and archive CRC.
They do not install or launch the package. Use `android_admin.py inspect-apk`
for platform checks, followed by an explicit `install` as shown above.

Neither package supplies a new physical sensor. A phone paired for A2DP audio
and a phone advertising a BLE beacon are different roles. Keep their acceptance
results separate, and stop optional services that conflict with calls or exceed
the available memory budget.

The pinned SendspinDroid manifest exports its launcher, but its server wizard
and settings activities are not exported. No configuration deep link or import
intent is declared. Use normal UI setup or LAN discovery; do not treat private
preference files as a supported provisioning API. This keeps server encryption
identity and future app migrations under the app's control.
[Release manifest](https://github.com/chrisuthe/SendspinDroid/blob/v2.0.0/android/app/src/main/AndroidManifest.xml).

## Validation

The offline suite covers wrong-device refusal, SSH port ownership and teardown,
private outputs, transfer path validation, APK digest/package/API/ABI/split
checks, and redaction of the health result:

```sh
python3 -m unittest discover -s tests -p 'test_android_admin.py'
```

It does not stand in for physical screen, sound, Bluetooth or reboot tests.
