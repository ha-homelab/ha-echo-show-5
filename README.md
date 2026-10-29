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

## October 29: installed capability audit

Both Shows are available and run VACA `0.13.4+myshka.10-sip.1` / 7010.
The audit confirms one real light sensor per device, existing HA lux entities,
bundled SSH binaries, an Android Bluetooth sink profile, and different installed
media players. It separates observed functions from untested expansion options.
The earlier SIP pilot verified HA-controlled pair calls and microphone return.

[Measured baseline, priorities and limitations](docs/installed-capabilities.md) ·
[Remote access](docs/android-remote-access.md) · [Permissions](docs/android-permissions-and-limits.md).

The October 20 section below is a historical checkpoint; its Show 2 availability
and application version do not describe the October 29 installation.

## October 20: listener lifecycle verified on Show 1

**Show 1 runs `myshka.9` / `7009` with “Привет, мышка” and “Hey Jarvis”.**
Myshka remains at **0.50**; Jarvis retains its independent five-evaluation mean
**> 0.97**. One microphone supplies both paths and the separate local Stop command.
The update waits for the old listener to close before replacement and handles
a disabled primary without starting microphone capture.
This build also attempts the remaining shutdown cleanup steps if an earlier step fails.

The build passed **62 JVM tests**. Show 1 passed **six Android tests**, live
configuration-restart and None-primary checks, **three actual microphone
mute/unmute cycles** and an app restart. HA settings, HTTPS verification,
permissions and display settings were preserved. **Show 2 is unavailable,
last verified on `.4`.** Physical voice acceptance remains pending.

[Enable the second phrase](docs/wiki/Mixed-wake-words.md) ·
[Measurements and limits](docs/wiki/Validation.md#october-20-shutdown-checkpoint) ·
[Processing diagram](docs/assets/mixed-wake-pipeline.svg).
Five README languages and four runtime UI languages remain available.

## Earlier verified checkpoints

- [October 20, `.8`](docs/wiki/Validation.md#october-20-lifecycle-checkpoint): serialized listener replacement and disabled-primary validation.
- [October 19, `.7`](docs/wiki/Validation.md#october-19-mixed-wake-checkpoint): first verified mixed Myshka/Jarvis installation.
- [October 19, `.6`](docs/wiki/Validation.md#october-19-current-checkpoint): retained-key update, HTTPS verification, reference replay and separate voice-backend timings.
- [October 16, `.4`](docs/wiki/Validation.md#pr-69-follow-up-myshka4-build-and-show-2-checks): Show 2 model-inventory regression and microphone recovery.
- [October 16, `.3`](docs/wiki/Validation.md#october-16-installed-state-and-replay-checks): both Shows, exact-frontend replay and microphone lifecycle checks. The [single-phrase diagram](docs/assets/exact-oww-pipeline.svg) describes this earlier configuration.

These records keep their original versions, dates and limits; they do not establish acoustic acceptance of a later APK.

## What it does

- **Hands-free Assist:** exact ONNX **“Привет, мышка”** at **0.50**, with optional bundled **“Hey Jarvis”** using its own calibrated temporal gate. The older two-model microWakeWord mode remains available separately. Private models are not distributed. [Voice setup and switching](docs/wiki/Voice-and-wake-words.md).
- **A screen suited to five inches:** a large clock, full-screen Front/Porch video on motion, bounded manual camera viewing and return to the clock. Video preserves proportions; the ready-frame gate suppresses Android's stretched play placeholder. [Display guide](docs/wiki/Display-media-and-calls.md).
- **An HA remote endpoint:** announcements, music, fixed TV streams, our OTT-play FOSS Capacitor client, a separate OTT web route and optional OttPlayer. Home/Stop ends the owned activity and restores the clock. [Remote controls](docs/remote-endpoint.md).
- **Calls on your Jitsi installation:** a fixed room, explicit join policy, microphone handoff and bounded cleanup. The standalone camera/intercom pilot remains a separate experimental option. [Calls and intercom](docs/wiki/Display-media-and-calls.md#jitsi-and-intercom).
- **Choice of voice backend:** Homeway, independent FCC cloud speech/conversation, or local Russian conversation and Silero speech with FCC cloud recognition. Selection is per satellite; fallback is manual. [Privacy boundaries and outage procedure](docs/wiki/Voice-and-wake-words.md#choose-and-switch-an-assistant).
- **Localization:** English, Russian, German, Spanish and French project entry points, plus the clock interface's own locale configuration. Interface language, speech language and wake model are independent. Detailed technical runbooks and wiki pages are maintained in English. [Coverage and contribution rules](docs/wiki/Localization.md).

## Earlier display and voice validation

The [October 15 record](docs/wiki/Validation.md#october-15-installed-state-and-recovery-checks) covers `dualwake.2`, display `20261015-r11`, 48 synthetic layout renders and the installed recovery checks. The [October 14 record](integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) preserves the earlier Piper/Irina pipeline and service-level announcements. The [October 2 conversion snapshot](docs/preparation-status.md) is historical.

Physical phrase recognition, audible-response quality, power-loss recovery and a multi-day soak remain separate acceptance work. Completed API calls, loaded models and file replay are narrower evidence.

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

[CONTRIBUTING](CONTRIBUTING.md) and [CI](https://github.com/ha-homelab/ha-echo-show-5/blob/main/.github/workflows/tests.yml) describe the complete required checks and separate voice runtimes. Tests do not authorize writes or certify a device. [Release packaging](docs/release-packaging.md) publishes a reviewed **integration-source suite**, not firmware or an APK. [Release policy](RELEASING.md) · [bounded RC fuzzing](docs/fuzzing.md) · [versioning](docs/VERSIONING.md) · [security reporting](SECURITY.md) · [security design](docs/security-design.md) · [third-party notices](THIRD_PARTY_NOTICES.md).

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
