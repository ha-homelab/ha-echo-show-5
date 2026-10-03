# Echo Show 5 Gen2 → Android → Home Assistant

Tools and an attended runbook for reusing an **Amazon Echo Show 5, second generation (2021), codename `cronos`**, as an Android Home Assistant display and voice client. This project targets a physical **x86_64 Synology NAS** as the USB host, controlled over SSH from a separate computer.

**Validation status, 2026-10-02:** a physical cronos device has completed the guarded TWRP conversion and first **Android 11 / LineageOS 18.1** boot. The raw backups passed validation on both NAS and workstation, and the pinned **Home Assistant Companion minimal APK installed successfully**. Companion is authenticated to HA and renders the existing dashboard. Optional **VACA 0.13.4** is installed with a local custom model, a running wake-word engine and an idle HA satellite connection. After settling onboarding permissions, VACA restarted unattended through one normal Android reboot, reconnected to HA and kept capture active with Companion back in the foreground. Controlled physical voice, power-cycle and multi-day reliability tests remain pending. See [validation status](docs/preparation-status.md) for the evidence and remaining checks.

The [camera pilot](docs/camera-and-intercom.md) delivered authenticated **640×480 MJPEG at 5.19 fps over a 20-second sample**, while Companion stayed in the foreground and VACA capture remained active. A later zero-camera condition cleared after an ordinary Android reboot with hardware privacy off. Android then reported one camera, and manual camera/Companion startup returned two different fresh authenticated JPEG frames. The cause of the earlier loss remains unresolved. A later [Wi-Fi ADB reboot check](docs/android-and-home-assistant.md#persistent-wi-fi-adb-on-the-tested-rom) passed: authenticated network access returned after an ordinary reboot without using USB commands. Trusted USB remains a [recovery fallback](docs/camera-and-intercom.md#manual-recovery-after-an-android-reboot). Camera boot start is off; full unattended recovery and power-loss behavior remain unverified.

The optional [HA intercom integration](integrations/show5-intercom/README.md) passed live checks for 100 ms of silent talkback data, a one-second microphone reply, membership guards and service/microphone restoration. Synthetic signaling and isolated WebView camera/microphone capture passed. A real attempt through the lightweight receiver reached Answer and caller offer submission, but **a complete call through the HA WebRTC card and physical audibility remain unverified**. Cleanup restored fresh camera frames and the microphone baseline. Keep experimental video outside the [daily-use configuration](integrations/show5-intercom/README.md#daily-use-configuration-without-experimental-video). The home panel rendered at 960×480. After disabling Always-on Display, remote sleep reported display OFF and wake restored ON; this does not establish deep CPU sleep. [Portable HA examples](examples/home-assistant/README.md) provide announcement, media, screen and navigation scripts. See the integration's [tested results](integrations/show5-intercom/README.md#tested-results) for exact scope and the remaining unattended-recovery limits.

The separate [native Jitsi pilot](docs/jitsi-calls.md) uses a verified F-Droid APK and an operator-controlled conference server. An attended two-party test confirmed received video in both directions and audio transport from the Show. Explicit HA End restored fresh camera video, VACA capture and Companion home. Physical audibility, intelligibility and echo behavior still need acceptance. The HA controls use a two-minute lease, attended Join and explicit End/restoration.

## Conversion route

Stock Show 5 Gen2 → **amonet-cronos 2.0.1** → TWRP → verified off-device backup → **unofficial LineageOS 18.1 v0.4 / Android 11** → **Home Assistant Companion 2026.8.4 minimal** → your Home Assistant server.

The initial unlock modifies the boot chain before the first backup. Installing Android replaces Fire OS and Alexa and requires data formatting. The Android port has limitations documented in [the Home Assistant guide](docs/android-and-home-assistant.md). This is an attended hardware conversion, with separate commands for each stage; connecting USB does not trigger a write.

This is a **Show 5 Gen2** project. Echo Dot/EchoLocal, Show 5 Gen1, Show 8 and other device images are incompatible with this route.

## Requirements

- A confirmed Show 5 **Gen2 / 2021 / cronos**, its normal AC power adapter, and a micro-USB **data** cable.
- A physical x86_64 Synology host with Docker, Python 3.8 or newer, SSH access, and sufficient private storage for backups. The tested DSM environment is recorded in [validation status](docs/preparation-status.md).
- A workstation with Python 3, SSH and rsync. The Linux release binaries run on the NAS, not directly on macOS.
- An existing Home Assistant server reachable from the Show's Wi-Fi. Voice use needs a working Assist pipeline with speech-to-text and text-to-speech.
- The pinned third-party artifacts, acquired separately as described in the runbook. Firmware, APKs and downloaded vendor trees are intentionally absent from Git.

## Start here

Clone this repository, then read [the runbook](docs/runbook.md) before connecting an untouched unit or starting a write. Configure your own SSH destination and project directory, acquire and verify the artifacts, then build and validate the host image. The preparation commands and fresh-clone procedure are in that document.

Once preparation is complete, these commands inspect the host and USB inventory:

```bash
python3 scripts/remote.py preflight
python3 scripts/remote.py inventory
```

Select the **physical USB port and complete observed serial** of your Show. `PORT` and `FULL_SERIAL` in the documentation are placeholders; never select the first device or copy an identifier from another Echo. For a stock unit in FASTBOOT:

```bash
python3 scripts/remote.py probe-fastboot --port PORT --serial FULL_SERIAL
```

For a unit already unlocked and in TWRP, use `probe-recovery` instead. Do not repeat the exploit solely to follow the guide from its beginning. Every write stage requires identity checks and an exact typed action/serial phrase. Only the selected USB node is mapped into a nonroot, network-disabled container.

## Project contents

- [Installation runbook](docs/runbook.md): host setup, device identification, unlock, backup, formatting, ROM and APK installation.
- [Android and Home Assistant](docs/android-and-home-assistant.md): dashboard, Assist, optional wake word and acceptance tests.
- [Private custom wake word with VACA](docs/vaca-private-wakeword.md): optional pinned APK, private model handling and deployment/acceptance boundaries.
- [Camera and intercom pilot](docs/camera-and-intercom.md): optional authenticated HTTPS camera, HA MJPEG setup and microphone ownership for experimental half-duplex audio.
- [Compact Show dashboard](docs/show-dashboard.md): portable native-card template for home, camera, screen, voice, music and planned calls, with private local rendering.
- [HA intercom integration](integrations/show5-intercom/README.md): administrator-only talkback, optional listening/video, deployment steps and recovery boundaries.
- [FCC voice backup](docs/fcc-voice-backup.md): parallel Homeway/FCC pipelines, independent cloud audio and guarded device switching.
- [Native Jitsi calls](docs/jitsi-calls.md): pinned Android app, own-server configuration, administrator Start/End controls and attended acceptance.
- [Portable HA examples](examples/home-assistant/README.md): announcement helper and fixed media, screen and dashboard-navigation scripts.
- [Release audit](docs/release-audit.md): the actual amonet archive and bundled host tools.
- [Source audit](docs/upstream-audit.md): why the GitHub source checkout alone does not replace the release.
- [Script review](docs/script-review.md) and [validation status](docs/preparation-status.md): verification and remaining limitations.
- [Amonet metadata](amonet-artifact.json), [reviewed file inventory](amonet-review.json), [ROM metadata](lineage-artifact.json), [Companion metadata](companion-artifact.json), [optional VACA metadata](vaca-artifact.json), [optional camera metadata](androidipcamera-artifact.json) and [optional Jitsi metadata](jitsi-artifact.json): pinned provenance and integrity checks.
- `host/synology/`: separate Docker host definition.
- `scripts/` and `tests/`: explicit stages and regression checks.
- `templates/home-assistant/`: public dashboard placeholders; keep the filled entity mapping and rendered configuration in `private/`.

## Local data and maintenance

Keep downloaded files in `downloads/`, extracted third-party code in `vendor/`, backups in `backups/`, logs in `logs/`, and host keys or local records in `private/`. These directories are ignored. Keep HA URLs, access tokens, Wi-Fi credentials, device inventories and household-specific test records outside public documentation. `.gitignore` does not remove files already committed; inspect the staged diff before publishing.

```bash
python3 scripts/artifacts.py fetch lineage companion
python3 scripts/artifacts.py verify lineage companion
python3 -m unittest discover -s tests -v
```

The pinned Companion minimal app includes ARMv7 support and does not need GApps. Third-party code and firmware retain their upstream terms; this repository provides metadata and preparation tooling rather than redistributing their binaries.
