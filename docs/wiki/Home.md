# Echo Show 5 project wiki

[English README](../../README.md) · [Русский](../../README.ru.md) · [Deutsch](../../README.de.md) · [Español](../../README.es.md) · [Français](../../README.fr.md)

This wiki is versioned with the code under `docs/wiki/`. It describes the **Echo Show 5 Gen2 / 2021 / `cronos`** route. It is readable in a local checkout and on GitHub without enabling the separate GitHub Wiki feature. Detailed instructions and evidence remain linked at their source rather than copied into conflicting procedures.

## October 19: two activation phrases on Show 1

Show 1 runs **`myshka.7` / `7007`** with exact ONNX **“Привет, мышка” at 0.50**
and optional bundled **“Hey Jarvis”**, using a strict five-evaluation mean
**> 0.97**. One microphone supplies both paths; Jarvis shares the existing
MicroFrontend with Stop, which remains a separate playback command.

The retained-key build passed **42 JVM tests**. Show 1 passed **six Android
tests**, **three actual microphone mute/unmute cycles** and an **app restart**;
both activation models, Stop and HTTPS authentication recovered with settings
preserved. **Show 2 remains unavailable, last verified on `.4`.** Physical speech
acceptance remains pending. See the [opt-in and rollback guide](Mixed-wake-words.md)
and [measured results](Validation.md#october-19-mixed-wake-checkpoint).

## October 19: earlier myshka.6 checkpoint

Show 1 received the retained-key **`myshka.6` / `7006`** update, with **29 JVM
tests and three Android instrumentation tests passed**. HTTPS authentication,
the single Myshka model and microphone inference were observed. Show 2 is
currently unreachable and remains last verified on `.4`. The
[earlier .6 validation](Validation.md#october-19-current-checkpoint)
separates device checks, voice-backend checks and pending physical acceptance.

## October 16: new wake-model trial

**PR #69 follow-up: `myshka.4` / `7004` is installed and locally verified on Show 2.** The original signing certificate is retained and all 18 JVM tests pass. Show 2 passed the targeted Android inventory regression: one test covering five metadata cases in 0.624 seconds. Invalid optional metadata no longer aborts the model inventory; engine loading still rejects invalid assets. Show 2 also passed one actual microphone close/reopen cycle and a normal app restart, preserving settings, brightness, permissions and authenticated nonroot ADB. End-to-end voice acceptance remains pending. At that October 16 checkpoint, Show 1 was unreachable and remained last verified on `.3`. The `.3` fixture and lifecycle observations below remain a separate historical record.

### Verified myshka.3 baseline

**APK installed and reference replay passed on both Shows.** VACA `0.13.4+myshka.3` / `7003` passed 18 JVM tests. Each device also passed two Android instrumentation tests using four existing private fixtures: **294 embeddings, 234 classifier windows and 11 positive windows**, with all threshold decisions matching the reference. This is file-based inference evidence, not a room recording or acoustic acceptance.

At the October 16 checkpoint, both Shows were configured for only **“Привет, мышка”** at **0.50** (**5.0 in HA**) through the exact ONNX frontend, with “Hey Jarvis” removed from the active selection and the separate Stop command retained. **Both passed three microphone mute/unmute cycles with verified capture closure/reopening, plus a normal app restart.** HA settings, brightness, permissions and nonroot ADB were preserved. Spoken activation, audible answers, distance, Stop during playback, power-loss recovery and a multi-day soak remain pending.

![One capture stream feeds the exact ONNX activation pipeline and the separate Stop detector. Audio chunk size does not measure wake latency.](../assets/exact-oww-pipeline.svg)

[Wake-model rollout: process and results](Wake-model-rollout.md) tracks the new trial and its evidence gates. [Conversion process and results](Process-and-results.md) retains the earlier conversion, display and dual-wake milestones.

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
