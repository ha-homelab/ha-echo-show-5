# Documentation map — Echo Show 5 Gen2

[English overview](../README.md) · [Русский](../README.ru.md) · [Deutsch](../README.de.md) · [Español](../README.es.md) · [Français](../README.fr.md)

This route targets **Echo Show 5 Gen2 / 2021 / cronos**, using **LineageOS / Android**, Companion and optional voice/display integrations. It is distinct from [EchoLocal on Dot 2](https://github.com/ha-homelab/ha-echo-dot) and [EchoMuse on emOS](https://github.com/ha-homelab/ha-echomuse). Never reuse another model's firmware or unlock commands.

## October 29: installed capability audit

Both Shows are available and run VACA `0.13.4+myshka.10-sip.1` / 7010.
The audit confirms one real light sensor per device, existing HA lux entities,
bundled SSH binaries, an Android Bluetooth sink profile, and different installed
media players. It separates observed functions from untested expansion options.
The earlier SIP pilot verified HA-controlled pair calls and microphone return.

[Measured baseline, priorities and limitations](installed-capabilities.md) ·
[Remote access](android-remote-access.md) · [Permissions](android-permissions-and-limits.md).

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
See the [mixed-wake guide](wiki/Mixed-wake-words.md) and [dated measurements](wiki/Validation.md#october-20-shutdown-checkpoint).

## Start with the wiki

- [Wiki home](wiki/Home.md): choose the installation, operation or maintenance path.
- [Wake-model rollout](wiki/Wake-model-rollout.md): the October 16 single-phrase ONNX trial, verified device replay and lifecycle checks, remaining physical acceptance and process/evidence diagrams.
- [Process and results](wiki/Process-and-results.md): conversion stages, current software changes, installed results and remaining acceptance work.
- [Architecture](wiki/Architecture.md): device, HA and service boundaries, including local versus cloud speech processing.
- [Validation and evidence](wiki/Validation.md): dated versions, automated checks, per-device observations and unverified behavior.
- [SVG diagram collection](assets/README.md): architecture, voice paths, installation paths, the conversion journey, startup recovery and recorded test counts.

## Historical checkpoints

- [October 19 `.6` checkpoint](wiki/Validation.md#october-19-current-checkpoint): the preceding Show 1 update and separate voice-backend checks.
- [October 16 exact Myshka rollout](wiki/Wake-model-rollout.md): `.3` reference replay and lifecycle results on both Shows, followed by the `.4` inventory fix on Show 2.
- [October 15 display and dual-wake baseline](wiki/Process-and-results.md): the earlier microWakeWord pair, clock localization and startup recovery.

These dated records retain the original versions, measurements and acceptance
limits. They do not establish a new build or current availability of either device.

## First conversion or an existing Android device

1. Choose the correct route in [Installation, updates and recovery](wiki/Installation-and-recovery.md). An APK or static-page update does not require repeating firmware conversion.
2. For stock hardware, read the [complete installation runbook](runbook.md): host preparation, exact USB selection, unlock, verified off-device backup **before formatting**, then installation. The first backup is after unlock; it is not proof of a universal stock restore.
3. Review the [release audit](release-audit.md) and [upstream source audit](upstream-audit.md) before acquiring the pinned artifacts.
4. Configure [Android and Home Assistant](android-and-home-assistant.md), including permissions, language and Assist.
5. Compare the relevant [current validation](wiki/Validation.md) with the [historical conversion snapshot](preparation-status.md). These are dated observations, not an automatic live fleet report.

## Daily display and voice

- [Display, media and calls](wiki/Display-media-and-calls.md): the room endpoint's operating behavior and feature boundaries.
- [Clock and camera display](../integrations/show5-display/README.md): versioned deployment, four-language UI, startup recovery and camera lifecycle.
- [Voice and wake words](wiki/Voice-and-wake-words.md): exact Myshka with optional Jarvis, the older two-model microWakeWord mode, independent language settings and per-satellite assistant selection.
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
- [Native SIP audio pilot](../integrations/show5-sip/README.md): an existing PBX account, local VACA lease, incoming/outgoing calls and HA controls.
- Treat each guide's acceptance limits independently. A fresh camera frame, successful signaling or normal app restart does not prove an audible call or recovery after power loss.

## Maintain and publish

- [Maintenance](wiki/Maintenance.md): validation, release hygiene and repository-hosted wiki publication.
- [Contributing](../CONTRIBUTING.md), [translation policy](i18n.md), [security reporting](../SECURITY.md), [third-party notices](../THIRD_PARTY_NOTICES.md).
- [Release packaging](release-packaging.md), [workflow](release-workflow.md), [versioning](VERSIONING.md), [runner preflight](runner-preflight.md) and [fuzzing](fuzzing.md).
- [OpenSSF evidence](openssf-evidence.md).

Architecture and process SVGs describe logical relationships. The validation chart labels recorded test **counts**, not coverage percentages or a performance benchmark. Historical measurements keep their original conditions and dates. Downloaded firmware, backups, household mappings, raw receipts and credentials stay outside Git.
