# Echo Show 5 project wiki

[English README](../../README.md) · [Русский](../../README.ru.md) · [Deutsch](../../README.de.md) · [Español](../../README.es.md) · [Français](../../README.fr.md)

This wiki is versioned with the code under `docs/wiki/`. It describes the **Echo Show 5 Gen2 / 2021 / `cronos`** route. It is readable in a local checkout and on GitHub without enabling the separate GitHub Wiki feature. Detailed instructions and evidence remain linked at their source rather than copied into conflicting procedures.

## Guarded announcement candidate

[Direct announcements and ordinary SIP calls](../guarded-announcements.md)
describes request ownership, expiry, honest completion, the shared native guard
and its external-app limits. Build and quiet installation evidence do not replace
attended acoustic acceptance.

## October 29: room endpoint delivery

The **r15** room display and HA policy are deployed on both Shows. Use the
[capability delivery register](../room-capability-delivery.md) for per-device
camera, timer, media and Bluetooth results, including remaining physical limits.
[Room controls](Room-endpoint.md) · [Administration tools](../remote-admin-tools.md) ·
[Runtime diagram](../assets/room-runtime.svg).

## October 29: original installed capability audit

At this earlier inventory checkpoint, both Shows were available and ran VACA
`0.13.4+myshka.10-sip.1` / 7010.
The audit confirms one real light sensor per device, existing HA lux entities,
bundled SSH binaries, an Android Bluetooth sink profile, and different installed
media players. Those app differences and untested candidates describe the
pre-rollout checkpoint; the delivery register above records subsequent changes.
The earlier SIP pilot verified HA-controlled pair calls and microphone return.

[Measured baseline, priorities and limitations](../installed-capabilities.md) ·
[Remote access](../android-remote-access.md) · [Permissions](../android-permissions-and-limits.md).

The October 20 section below is a historical checkpoint; its Show 2 availability
and application version do not describe the October 29 installation.

## October 20: listener lifecycle verified on Show 1

Show 1 runs **`myshka.9` / `7009`** with **“Привет, мышка” at 0.50** and optional
**“Hey Jarvis”** with its independent five-evaluation mean **> 0.97**. The update
also attempts independent shutdown cleanup steps after a failure; listener
replacement and disabled-primary handling remain intact. The build passed
62 JVM tests; device checks covered six Android tests, configuration changes
without restarting the app, the None primary, three microphone mute/unmute
cycles and a normal restart. Settings were preserved. **Show 2 remains
unavailable, last verified on `.4`; physical speech acceptance remains pending.**
See the [mixed-wake guide](Mixed-wake-words.md) and [dated measurements](Validation.md#october-20-shutdown-checkpoint).

## Historical checkpoints

- [October 19 `.6` checkpoint](Validation.md#october-19-current-checkpoint): the preceding Show 1 update and separate voice-backend checks.
- [October 16 exact Myshka rollout](Wake-model-rollout.md): `.3` reference replay and lifecycle results on both Shows, followed by the `.4` inventory fix on Show 2.
- [October 15 display and dual-wake baseline](Process-and-results.md): the earlier microWakeWord pair, clock localization and startup recovery.

These dated records retain the original versions, measurements and acceptance
limits. They do not establish a new build or current availability of either device.

## Room endpoint expansion

[Room controls, timers, media and administration](Room-endpoint.md) documents the current expansion and its measured limits.

## Pick a task

- **Convert an untouched Show:** read [installation and recovery](Installation-and-recovery.md), then follow the complete [attended runbook](../runbook.md). Identify the model before using any image.
- **Update an existing Show:** use the same [installation page](Installation-and-recovery.md#update-an-existing-android-installation). App updates, static display releases and firmware conversions are different operations.
- **Choose a wake model or change the assistant:** [voice and wake words](Voice-and-wake-words.md) distinguishes exact Myshka, its optional Jarvis extension and the older two-model microWakeWord mode, and explains cloud recognition and reversible assistant selection.
- **Fix an unreadable screen or use cameras, music and calls:** [display, media and calls](Display-media-and-calls.md).
- **Understand where audio/video goes:** [architecture and data paths](Architecture.md), including the local/cloud voice diagram.
- **Diagnose a failure:** [troubleshooting](Troubleshooting.md), ordered by observable symptoms.
- **Decide whether a result is accepted:** [validation](Validation.md) separates software tests, transport checks and physical observation.
- **Choose a language or translate the project:** [localization](Localization.md).
- **Maintain patches, docs or releases:** [maintenance](Maintenance.md).

## Earlier installed baselines

The recorded October 14, 2026 deployment has two converted Shows with both the private **“Привет, мышка”** model and **“Hey Jarvis”** loaded in VACA, sharing a **0.35** threshold. They select **Local Russian Home**, which uses cloud recognition, local dialogue and local Irina synthesis. An application restart and service-level announcements passed; physical two-phrase acceptance and multi-day reliability remain pending. Consult the [validation page](Validation.md) before extending that claim to a different build, a power cycle or an acoustic test.

The October 15 update installed `dualwake.2` and display `20261015-r11` on both Shows. Each passed three software microphone mute/unmute cycles and a normal app restart with both models and capture restored. The clock supports four language families and a separate hour-format option; both devices retain English and 24-hour time. See [localization](Localization.md) for the exact configuration and scope.

## Terminology

- **Companion** is the official Home Assistant Android application. **VACA** is View Assist Companion App, used here for the continuous wake listener and authenticated display.
- **Wake word** means a locally detected activation phrase; it is separate from **STT** (speech-to-text recognition), **conversation** (intent/model response) and **TTS** (text-to-speech).
- **Satellite** is the device endpoint registered in HA. Changing its selected assistant does not require replacing the firmware.
- **Microphone handoff** temporarily gives a call application access while retaining enough state to restore the voice listener afterward.
- **Service-level success** means an API or protocol operation completed. It does not prove that a person heard a useful answer or saw smooth video.
- **Private evidence** includes serials, network addresses, tokens, recordings and household state. Public documentation contains sanitized conclusions and reproducible procedures.

The [sidebar](_Sidebar.md) contains all wiki pages. Diagrams are self-contained SVG source files in [`docs/assets/`](../assets/README.md), with accessible descriptions and no remote fonts or scripts.
