# Echo Show 5 Gen2 → Android → Home Assistant

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15595/badge)](https://www.bestpractices.dev/projects/15595)

[![Fuzzing: RC only](https://img.shields.io/badge/fuzzing-RC_only-blue)](docs/fuzzing.md)

**English** · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Reuse an **Amazon Echo Show 5, second generation (2021), codename `cronos`**, as a Home Assistant voice satellite, readable clock, motion-camera display and remotely controlled media/call endpoint. This repository contains the attended conversion tools, local application patches, integrations and recovery documentation. It does not contain firmware, APKs, private wake models or household credentials.

**Documentation:** [topic index](docs/README.md) · [translation policy](docs/i18n.md).

**Start with the [project wiki](docs/wiki/Home.md), or the [conversion runbook](docs/runbook.md) for an untouched device.** Already running Android? Use the [installation and update guide](docs/wiki/Installation-and-recovery.md); do not repeat the unlock.

![Architecture: the Show connects to Home Assistant; voice, cameras, media and calls have separate data paths.](docs/assets/architecture.svg)

[Conversion process and results](docs/wiki/Process-and-results.md) · [Startup recovery diagram](docs/assets/startup-recovery.svg) · [Validation chart](docs/assets/validation-checks.svg)


[![Clock display in perspective](docs/assets/clock-hero.png)](docs/assets/clock-screenshot.jpg)

The real display page (revision `20261015-r11`) captured in desktop Chrome at
960 × 480 with the public example configuration. It shows only the local clock;
no Home Assistant login, camera feed or device was used. Click for the flat original.

## October 16: single-phrase ONNX trial

### PR #69 follow-up: myshka.4

**`0.13.4+myshka.4` / `7004` is installed and locally verified on Show 2.** The original signing certificate is retained and all **18 JVM tests** pass. Show 2 passed the targeted Android inventory regression: **one test, five metadata cases, 0.624 seconds**. Invalid optional metadata no longer removes custom models from the list; actual engine loading still rejects invalid assets. Show 2 also passed one actual microphone close/reopen cycle and a normal app restart, preserving settings, brightness, permissions and authenticated nonroot ADB. End-to-end voice acceptance remains pending. Show 1 is unreachable and remains last verified on `.3`. The earlier `.3` replay below is separate evidence, not a new `.4` replay.

### Verified myshka.3 baseline

**APK installed and reference replay passed on both Shows.** VACA `0.13.4+myshka.3` / `7003` passed **18 JVM tests**, and each Show passed **two Android instrumentation tests** using **four existing private fixtures: 294 embeddings, 234 classifier windows and 11 positive windows**. All threshold decisions matched the reference. File replay does not record the room or establish acoustic recognition.

Both Shows are configured for only **“Привет, мышка”** through the exact ONNX frontend at **0.50** (**5.0 in HA**), with “Hey Jarvis” removed from the active selection and the separate Stop command retained. **Both passed three microphone mute/unmute cycles with verified capture closure/reopening, plus a normal app restart**, preserving HA settings, brightness, permissions and nonroot ADB. Spoken activation, audible responses, distance, Stop during playback, power-loss recovery and a multi-day soak remain pending. The two-model microWakeWord capability and its October 15 baseline remain documented below.

[Wake-model rollout: process and results](docs/wiki/Wake-model-rollout.md) · [Technical guide](docs/openwakeword-myshka.md) · [Validation graphic](docs/assets/wake-validation.svg)

![One microphone supplies the exact ONNX activation pipeline and the separate Stop detector. The 80 ms audio chunk is not a measured wake latency.](docs/assets/exact-oww-pipeline.svg)

## What it does

- **Hands-free Assist:** choose the opt-in single-phrase ONNX trial or the existing two-model microWakeWord capability. The recorded October 15 microWakeWord baseline uses **“Привет, мышка”** and **“Hey Jarvis”** at a shared **0.35** threshold; the new ONNX trial uses one phrase at **0.50**. These thresholds belong to different models and do not imply comparable sensitivity. Private models are not distributed. [Voice setup and switching](docs/wiki/Voice-and-wake-words.md).
- **A screen suited to five inches:** a large clock, full-screen Front/Porch video on motion, bounded manual camera viewing and return to the clock. Video preserves proportions; the ready-frame gate suppresses Android's stretched play placeholder. [Display guide](docs/wiki/Display-media-and-calls.md).
- **An HA remote endpoint:** announcements, music, fixed TV streams, our OTT-play FOSS Capacitor client, a separate OTT web route and optional OttPlayer. Home/Stop ends the owned activity and restores the clock. [Remote controls](docs/remote-endpoint.md).
- **Calls on your Jitsi installation:** a fixed room, explicit join policy, microphone handoff and bounded cleanup. The standalone camera/intercom pilot remains a separate experimental option. [Calls and intercom](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Choice of voice backend:** Homeway, independent FCC cloud speech/conversation, or local Russian conversation and Piper speech with FCC cloud recognition. Selection is per satellite; fallback is manual. [Privacy boundaries and outage procedure](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Localization:** English, Russian, German, Spanish and French project entry points, plus the clock interface's own locale configuration. Interface language, speech language and wake model are independent. Detailed technical runbooks and wiki pages are maintained in English. [Coverage and contribution rules](docs/wiki/Localization.md).

## Current validation

**October 15, 2026 baseline:** the built `dualwake.2` patch fixes detector cleanup, and display revision `20261015-r11` combines English, Russian, German and Spanish localization with retry handling when the MQTT command is not yet available during HA startup. A set of **48 synthetic desktop layout renders** showed no clipping in the exercised cases. Both updates were verified installed on both Shows at that checkpoint. Each device passed three software microphone mute/unmute cycles and a normal app restart, restoring both models and capture. Physical phrase recognition remains unverified; see [current rollout evidence](docs/wiki/Validation.md).

The **October 14, 2026 deployment baseline** has two converted Shows on Android 11 / unofficial LineageOS 18.1, with both activation models loaded after a normal **application restart**, existing HA identities preserved and sequential HA announcements completed. Both use the **Local Russian Home** pipeline and **Irina** speech. Recognition still sends audio to the cloud. [Dual-wake build evidence](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) · [voice deployment history](docs/fcc-voice-backup.md).

**Deliberate physical recognition of both phrases, audible-response quality, power-loss recovery and a multi-day soak remain pending for the dual-wake build.** A loaded model, an idle satellite or completed service call does not establish those results. Earlier camera, brightness, media and Jitsi tests have their own dated scope. The [validation guide](docs/wiki/Validation.md) separates those observations; the [October 2 conversion snapshot](docs/preparation-status.md) is historical and contains superseded voice settings.

## Compatible hardware and conversion route

**Show 5 Gen2 / `cronos` only.** Echo Dot/EchoLocal, Show 5 Gen1, Show 8 and other images are not interchangeable.

```text
Stock cronos → amonet-cronos 2.0.1 → TWRP → verified off-device backup
             → LineageOS 18.1 v0.4 / Android 11 → Companion + optional VACA
```

The initial unlock changes the boot chain **before the first backup**. Installing Android replaces Fire OS/Alexa and formats data. The backup route is not a tested generic return-to-stock procedure. Follow the [runbook's checkpoints](docs/runbook.md) and the [artifact audit](docs/release-audit.md), not this diagram alone.

You need:

- The confirmed device, its normal **AC adapter**, and a micro-USB **data** cable. USB does not replace the power adapter.
- A physical **x86_64 Synology NAS** with Docker, Python 3.8+, SSH and private backup storage, plus a workstation with Python, SSH and rsync. Linux release tools execute on the NAS.
- A reachable Home Assistant server; voice also needs a working Assist pipeline.
- Independently downloaded, pinned artifacts. The runbook explains verification and XDA's manual-download fallback.

After configuring your own host and preparing its image as described in the runbook, these commands only inspect readiness and USB inventory:

```bash
python3 scripts/remote.py preflight
python3 scripts/remote.py inventory
```

Every device operation must use the **observed physical USB port and complete serial**. Never select “the first Echo.” Write stages have separate identity and confirmation gates. Connecting a cable does not initiate conversion.

## Documentation map

- [Wiki home](docs/wiki/Home.md): task-based navigation, diagrams and terminology.
- [Architecture and data paths](docs/wiki/Architecture.md): local/cloud boundaries, camera routing and Jitsi media.
- [Installation, update and recovery](docs/wiki/Installation-and-recovery.md): stock conversion versus an existing Android installation, signing keys and rollback.
- [Voice and wake-model choices](docs/wiki/Voice-and-wake-words.md): threshold semantics, model privacy, assistant switching and tests.
- [Display, media and calls](docs/wiki/Display-media-and-calls.md): brightness, color, full-screen video and remote activities.
- [Troubleshooting](docs/wiki/Troubleshooting.md): isolate the failing layer before reinstalling.
- [Validation](docs/wiki/Validation.md): automated, service-level and physical acceptance.
- [Localization](docs/wiki/Localization.md) and [maintenance](docs/wiki/Maintenance.md): language coverage, versioned static assets, patches and publication.

Detailed implementation guides: [Android/HA](docs/android-and-home-assistant.md), [VACA private models](docs/vaca-private-wakeword.md), [dual-wake source](integrations/vaca-dual-wake/README.md), [clock integration](integrations/show5-display/README.md), [FCC backup](docs/fcc-voice-backup.md), [native voice controls](docs/native-voice-controls.md), [Jitsi](docs/jitsi-calls.md), [camera pilot](docs/camera-and-intercom.md), [intercom](integrations/show5-intercom/README.md), [OTT command server](docs/ott-command-server.md), [stable addresses](docs/stable-network-addresses.md), [portable HA examples](examples/home-assistant/README.md).

## Development and private data

Keep downloads in `downloads/`, extracted upstream trees in `vendor/`, backups in `backups/`, logs in `logs/`, and keys, filled mappings, recordings and device evidence in `private/`. These are ignored; `.gitignore` cannot remove something already committed. Inspect the staged diff before publication. Never place credentials in HA's unauthenticated `/local` files.

Run the relevant offline suites from the repository root:

```bash
python3 scripts/check_docs.py
python3 -m unittest discover -s tests -v
node --test integrations/show5-display/tests/*.cjs
python3 -m unittest discover -s integrations/show5-display/tests -p 'test_*.py' -v
python3 -m unittest discover -s integrations/show5-intercom/tests -v
```

[CONTRIBUTING](CONTRIBUTING.md) and [CI](.github/workflows/tests.yml) describe the complete required checks and separate voice runtimes. Tests do not authorize writes or certify a device. [Release packaging](docs/release-packaging.md) publishes a reviewed **integration-source suite**, not firmware or an APK. [Release policy](RELEASING.md) · [bounded RC fuzzing](docs/fuzzing.md) · [versioning](docs/VERSIONING.md) · [security reporting](SECURITY.md) · [security design](docs/security-design.md) · [third-party notices](THIRD_PARTY_NOTICES.md).

## Related projects

- [EchoMuse on emOS](https://github.com/ha-homelab/ha-echomuse) covers a separate
  Dot software stack. Its firmware and access methods are not this Android Show route.

- [Echo Dot 2 conversion](https://github.com/ha-homelab/ha-echo-dot) documents the
  EchoLocal voice-satellite route for different hardware. Do not interchange
  its firmware, backups or USB recovery procedure with this runbook.
- [Amazon Echo Home Energy](https://github.com/4alvit/amazon-echo-home-voice)
  is a read-only Alexa skill for an unmodified Echo, with a separate account and
  deployment setup.
- [HA Homelab project directory](https://github.com/ha-homelab) lists the other
  public integrations and hardware guides.

## License

Original project code and documentation are available under the [MIT license](LICENSE). [Third-party notices](THIRD_PARTY_NOTICES.md) preserve separate terms for included or referenced upstream material. This grant does not relicense firmware, models, recordings, datasets or other third-party artifacts.


## Project maintenance

[Contribution guide](CONTRIBUTING.md) · [Security policy](SECURITY.md) ·
[Governance](GOVERNANCE.md) · [Code of Conduct](CODE_OF_CONDUCT.md) ·
[Roadmap](ROADMAP.md) · [Quality evidence and limits](docs/quality.md)

## Screenshot artwork

See [capture provenance and regeneration](docs/screenshot-artwork.md).
