# Documentation map — Echo Show 5 Gen2

[English overview](../README.md) · [Русский](../README.ru.md) · [Deutsch](../README.de.md) · [Español](../README.es.md) · [Français](../README.fr.md)

This route targets **Echo Show 5 Gen2 / 2021 / cronos**, using **LineageOS / Android**, Companion and optional voice/display integrations. It is distinct from [EchoLocal on Dot 2](https://github.com/ha-homelab/ha-echo-dot) and [EchoMuse on emOS](https://github.com/ha-homelab/ha-echomuse). Never reuse another model's firmware or unlock commands.

## Start with the wiki

- [Wiki home](wiki/Home.md): choose the installation, operation or maintenance path.
- [Wake-model rollout](wiki/Wake-model-rollout.md): the October 16 single-phrase ONNX trial, verified device replay and lifecycle checks, remaining physical acceptance and process/evidence diagrams.
- [Process and results](wiki/Process-and-results.md): conversion stages, current software changes, installed results and remaining acceptance work.
- [Architecture](wiki/Architecture.md): device, HA and service boundaries, including local versus cloud speech processing.
- [Validation and evidence](wiki/Validation.md): dated versions, automated checks, per-device observations and unverified behavior.
- [SVG diagram collection](assets/README.md): architecture, voice paths, installation paths, the conversion journey, startup recovery and recorded test counts.

## October 16 wake-model trial

**APK installed and reference replay passed on both Shows.** VACA `0.13.4+myshka.3` / `7003` passed 18 JVM tests. Each device also passed two Android instrumentation tests using four existing private fixtures: **294 embeddings, 234 classifier windows and 11 positive windows**, with all threshold decisions matching the reference. This is file-based inference evidence, not a room recording or acoustic acceptance.

Both Shows are configured for only **“Привет, мышка”** at **0.50** (**5.0 in HA**) through the exact ONNX frontend, with “Hey Jarvis” removed from the active selection and the separate Stop command retained. **Both passed three microphone mute/unmute cycles with verified capture closure/reopening, plus a normal app restart.** HA settings, brightness, permissions and nonroot ADB were preserved. Spoken activation, audible answers, distance, Stop during playback, power-loss recovery and a multi-day soak remain pending. See the [rollout process](wiki/Wake-model-rollout.md) and [technical guide](openwakeword-myshka.md).

![One microphone feeds the exact ONNX activation pipeline and a separate Stop detector; 80 ms denotes an audio chunk, not measured wake latency.](assets/exact-oww-pipeline.svg)

## Previous installed baseline

The October 15 record verified both Shows with **VACA `0.13.4+dualwake.2` / `7002`** and **display `20261015-r11`** installed. Three software mute/unmute cycles and a normal app restart on each restored both models and microphone capture. That microWakeWord configuration used **“Привет, мышка” + “Hey Jarvis”**, with a shared **0.35** threshold. Deliberately spoken activation and audible-response acceptance remain separate work; read the validation page for current camera and recovery results.

There are **five documentation entry languages** and **four implemented clock-UI languages**: English, Russian, German and Spanish. French is a documentation language only. English and 24-hour formatting remain selected on the two Shows. [Localization](wiki/Localization.md) explains the runtime settings; [translation policy](i18n.md) explains documentation coverage.

## First conversion or an existing Android device

1. Choose the correct route in [Installation, updates and recovery](wiki/Installation-and-recovery.md). An APK or static-page update does not require repeating firmware conversion.
2. For stock hardware, read the [complete installation runbook](runbook.md): host preparation, exact USB selection, unlock, verified off-device backup **before formatting**, then installation. The first backup is after unlock; it is not proof of a universal stock restore.
3. Review the [release audit](release-audit.md) and [upstream source audit](upstream-audit.md) before acquiring the pinned artifacts.
4. Configure [Android and Home Assistant](android-and-home-assistant.md), including permissions, language and Assist.
5. Compare the relevant [current validation](wiki/Validation.md) with the [historical conversion snapshot](preparation-status.md). These are dated observations, not an automatic live fleet report.

## Daily display and voice

- [Display, media and calls](wiki/Display-media-and-calls.md): the room endpoint's operating behavior and feature boundaries.
- [Clock and camera display](../integrations/show5-display/README.md): versioned deployment, four-language UI, startup recovery and camera lifecycle.
- [Voice and wake words](wiki/Voice-and-wake-words.md): the opt-in single-phrase ONNX path, two-model microWakeWord capability, independent language settings and per-satellite assistant selection.
- [Dual-wake extension](../integrations/vaca-dual-wake/README.md): source patch, reproducible build, versioned receipts, app-data preservation and rollback.
- [VACA and private wake words](vaca-private-wakeword.md): permissions, model deployment, thresholds and acoustic limitations.
- [Dashboard](show-dashboard.md) and [portable HA examples](../examples/home-assistant/README.md): provide your own private entity mapping.
- [Native voice controls](native-voice-controls.md): music routing, short play/stop phrases and origin selection.
- [Remote endpoint](remote-endpoint.md), [OTT command server](ott-command-server.md) and [stable addresses](stable-network-addresses.md).

## Speech services and diagnostics

- [FCC voice backup](fcc-voice-backup.md): separate speech paths and controlled switching; the selected Russian path still uses cloud speech recognition.
- [Assist behavior](fcc-assist-behavior.md), [audio model capabilities](fcc-audio-models.md), [cloud audio](fcc-cloud-audio.md) and [local speech experiment](fcc-local-speech-experiment.md).
- Speech recognition, TTS voice, conversation-agent language, display language and wake-word models are independent settings. Translating documentation changes none of them.
- [Troubleshooting](wiki/Troubleshooting.md): distinguish authentication, integration readiness, media transport, model loading and physical acceptance.
- [Script review](script-review.md) and [security design](security-design.md): failure boundaries and protected configuration.

## Optional camera and calls

- [Camera and intercom pilot](camera-and-intercom.md) and [HA intercom integration](../integrations/show5-intercom/README.md).
- [Native Jitsi pilot](jitsi-calls.md): attended call setup, resource ownership and restoration.
- Treat each guide's acceptance limits independently. A fresh camera frame, successful signaling or normal app restart does not prove an audible call or recovery after power loss.

## Maintain and publish

- [Maintenance](wiki/Maintenance.md): validation, release hygiene and repository-hosted wiki publication.
- [Contributing](../CONTRIBUTING.md), [translation policy](i18n.md), [security reporting](../SECURITY.md), [third-party notices](../THIRD_PARTY_NOTICES.md).
- [Release packaging](release-packaging.md), [workflow](release-workflow.md), [versioning](VERSIONING.md), [runner preflight](runner-preflight.md) and [fuzzing](fuzzing.md).
- [OpenSSF evidence](openssf-evidence.md).

Architecture and process SVGs describe logical relationships. The validation chart labels recorded test **counts**, not coverage percentages or a performance benchmark. Historical measurements keep their original conditions and dates. Downloaded firmware, backups, household mappings, raw receipts and credentials stay outside Git.
