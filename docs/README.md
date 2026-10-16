# Documentation map — Echo Show 5 Gen2

[English overview](../README.md) · [Русский](../README.ru.md) · [Deutsch](../README.de.md) · [Español](../README.es.md) · [Français](../README.fr.md)

This route targets **Echo Show 5 Gen2 / 2021 / cronos**, using **LineageOS / Android**, Companion and optional voice/display integrations. It is distinct from [EchoLocal on Dot 2](https://github.com/ha-homelab/ha-echo-dot) and [EchoMuse on emOS](https://github.com/ha-homelab/ha-echomuse). Never reuse another model's firmware or unlock commands.

![Preparation and runtime responsibilities](assets/architecture.svg)

## First conversion

1. Read the [complete installation runbook](runbook.md): host preparation, exact USB selection, unlock, verified off-device backup, formatting and installation.
2. Review the [actual release audit](release-audit.md) and [upstream source audit](upstream-audit.md) before acquiring the pinned artifacts.
3. Configure [Android and Home Assistant](android-and-home-assistant.md), including permissions, language and Assist.
4. Check the [recorded validation results and outstanding acceptance](preparation-status.md). These are dated observations, not a live fleet report.

## Daily display and voice

- [Dashboard](show-dashboard.md) and [portable HA examples](../examples/home-assistant/README.md): provide your own private entity mapping.
- [Clock and camera display](../integrations/show5-display/README.md): runtime display behavior and bounded camera lifecycle.
- [VACA and private wake words](vaca-private-wakeword.md): permissions, deployment, thresholds and limitations. A deployed model is not evidence of reliable acoustic recognition.
- [Native voice controls](native-voice-controls.md): music routing, short play/stop phrases and origin selection.
- [Remote endpoint](remote-endpoint.md), [OTT command server](ott-command-server.md) and [stable addresses](stable-network-addresses.md).

## Speech services and diagnostics

- [FCC voice backup](fcc-voice-backup.md): separate speech paths and controlled switching.
- [Assist behavior](fcc-assist-behavior.md), [audio model capabilities](fcc-audio-models.md), [cloud audio](fcc-cloud-audio.md) and [local speech experiment](fcc-local-speech-experiment.md).
- Speech language, TTS voice, conversation-agent language and wake-word model are separate settings. Documentation translations do not alter any of them.
- [Script review](script-review.md) and [security design](security-design.md): failure boundaries and protected configuration.

## Optional camera and calls

- [Camera and intercom pilot](camera-and-intercom.md) and [HA intercom integration](../integrations/show5-intercom/README.md).
- [Native Jitsi pilot](jitsi-calls.md): attended call setup, resource ownership and restoration.
- Treat the acceptance limits in each guide independently. A fresh camera frame, successful signaling or one normal reboot does not prove audible calls or recovery after power loss.

## Maintain and publish

- [Contributing](../CONTRIBUTING.md), [translation policy](i18n.md), [security reporting](../SECURITY.md), [third-party notices](../THIRD_PARTY_NOTICES.md).
- [Release packaging](release-packaging.md), [workflow](release-workflow.md), [versioning](VERSIONING.md), [runner preflight](runner-preflight.md) and [fuzzing](fuzzing.md).
- [OpenSSF evidence](openssf-evidence.md).

The SVG is an architecture illustration, not a benchmark. Historical measurements keep their original conditions and dates; they do not predict another device's speed. Downloaded firmware, backups, household mappings and credentials stay outside Git.
