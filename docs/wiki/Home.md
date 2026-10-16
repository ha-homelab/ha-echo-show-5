# Echo Show 5 project wiki

[English README](../../README.md) · [Русский](../../README.ru.md) · [Deutsch](../../README.de.md) · [Español](../../README.es.md) · [Français](../../README.fr.md)

This wiki is versioned with the code under `docs/wiki/`. It describes the **Echo Show 5 Gen2 / 2021 / `cronos`** route. It is readable in a local checkout and on GitHub without enabling the separate GitHub Wiki feature. Detailed instructions and evidence remain linked at their source rather than copied into conflicting procedures.

![Conversion stages and installed results](../assets/process-and-results.svg)

[Process and results](Process-and-results.md) explains the conversion stages, installed versions, recovery behavior and remaining acceptance work.

## Pick a task

- **Convert an untouched Show:** read [installation and recovery](Installation-and-recovery.md), then follow the complete [attended runbook](../runbook.md). Identify the model before using any image.
- **Update an existing Show:** use the same [installation page](Installation-and-recovery.md#update-an-existing-android-installation). App updates, static display releases and firmware conversions are different operations.
- **Enable two wake words or change the assistant:** [voice and wake words](Voice-and-wake-words.md) explains local detection, cloud recognition and reversible selection.
- **Fix an unreadable screen or use cameras, music and calls:** [display, media and calls](Display-media-and-calls.md).
- **Understand where audio/video goes:** [architecture and data paths](Architecture.md), including the local/cloud voice diagram.
- **Diagnose a failure:** [troubleshooting](Troubleshooting.md), ordered by observable symptoms.
- **Decide whether a result is accepted:** [validation](Validation.md) separates software tests, transport checks and physical observation.
- **Choose a language or translate the project:** [localization](Localization.md).
- **Maintain patches, docs or releases:** [maintenance](Maintenance.md).

## Current baseline

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
