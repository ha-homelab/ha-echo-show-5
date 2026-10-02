# Echo Show 5 Gen2 → Android → Home Assistant

Tools and an attended runbook for reusing an **Amazon Echo Show 5, second generation (2021), codename `cronos`**, as an Android Home Assistant display and voice client. This project targets a physical **x86_64 Synology NAS** as the USB host, controlled over SSH from a separate computer.

**Validation status, 2026-10-02:** the pinned amonet release has unlocked a physical cronos device and booted verified **TWRP 3.7.0_9-0**. A raw off-device backup also passed complete size, hash and GPT validation. This project does **not yet claim** a completed LineageOS installation, Companion installation, or physical Home Assistant acceptance test. See [validation status](docs/preparation-status.md).

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
- [Release audit](docs/release-audit.md): the actual amonet archive and bundled host tools.
- [Source audit](docs/upstream-audit.md): why the GitHub source checkout alone does not replace the release.
- [Script review](docs/script-review.md) and [validation status](docs/preparation-status.md): verification and remaining limitations.
- [Amonet metadata](amonet-artifact.json), [reviewed file inventory](amonet-review.json), [ROM metadata](lineage-artifact.json) and [Companion metadata](companion-artifact.json): pinned provenance and integrity checks.
- `host/synology/`: separate Docker host definition.
- `scripts/` and `tests/`: explicit stages and regression checks.

## Local data and maintenance

Keep downloaded files in `downloads/`, extracted third-party code in `vendor/`, backups in `backups/`, logs in `logs/`, and host keys or local records in `private/`. These directories are ignored. Keep HA URLs, access tokens, Wi-Fi credentials, device inventories and household-specific test records outside public documentation. `.gitignore` does not remove files already committed; inspect the staged diff before publishing.

```bash
python3 scripts/artifacts.py fetch lineage companion
python3 scripts/artifacts.py verify lineage companion
python3 -m unittest discover -s tests -v
```

The pinned Companion minimal app includes ARMv7 support and does not need GApps. Third-party code and firmware retain their upstream terms; this repository provides metadata and preparation tooling rather than redistributing their binaries.
