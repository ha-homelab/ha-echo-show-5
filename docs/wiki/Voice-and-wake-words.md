# Voice and two wake words

[Wiki home](Home.md) · [Architecture](Architecture.md) · [Dual-wake implementation](../../integrations/vaca-dual-wake/README.md)

The wake detector decides **when to start listening for a command**. Speech recognition, intent/model processing and speech synthesis are separate HA stages. Changing a page's language or its displayed clock does not change any of those stages.

## Recorded two-word configuration

The October 14, 2026 deployment loaded the private **“Привет, мышка”** model and built-in **“Hey Jarvis”** on both converted Shows, through VACA's local microWakeWord extension. They share one microphone, a feature extractor, a **0.35** threshold and a two-second cross-model cooldown. Either phrase starts the same assistant selected for that satellite.

HA's primary-model selector still chooses the first model. The optional second selection is stored in VACA's **app-private** `files/secondary-wake-word.json`:

```json
{"id": "hey_jarvis"}
```

The selected identifier must exist in the active engine's model inventory. Restart VACA after changing the file. Disabling the primary disables both; a duplicate or unsupported secondary is not a second detector. Other wake engines keep single-model behavior. Use the [implementation guide](../../integrations/vaca-dual-wake/README.md) for current selection validation and build details.

HA's threshold control uses a 0–10 scale: **3.5 in HA means 0.35 in the detector**. Lowering it can improve sensitivity and also increase accidental activations. It is not a measured confidence guarantee. Keep model files private, retain their hashes, and use deliberate positive/negative phrase tests before choosing a new threshold. The Russian model is not bundled with this repository; its spoken phrase does not let another operator reconstruct the trained model.

## Choose and switch an assistant

![Voice route choices and the explicit local/cloud boundaries.](../assets/voice-paths.svg)

The recorded device choice is **Local Russian Home**:

1. VACA detects the activation phrase locally.
2. HA sends command audio to **FCC Cloud Speech / NVIDIA Parakeet** for Russian recognition.
3. HA tries supported native intents first; unmatched dialogue uses the locally hosted `echomuse-home:4b` model through Ollama.
4. Local Piper generates **Irina** speech and HA returns it to the Show.

This is **not fully offline**. A cloud speech outage still affects recognition. There is no automatic cloud-language-model fallback for that local route. Supported home actions depend on HA exposure, intent handlers and the chosen conversation agent; a text-only general chatbot does not automatically gain household control.

Homeway and **FCC Russian Backup** can remain registered at the same time. HA chooses one pipeline per interaction. The independent FCC backup uses its cloud speech adapter and external text-model route; it does not need Homeway speech services. Read the [FCC guide](../fcc-voice-backup.md) for exact capability limits and [cloud audio](../fcc-cloud-audio.md) for transport and quota checks.

### During an outage or exhausted allowance

1. Record the affected Show's current **Assistant** selection. Inspect backend availability and run a harmless complete pipeline check, including fetching the answer audio. An entity marked available does not prove provider quota.
2. In that Show's HA device controls, select the already configured alternative. For Homeway exhaustion, choose the working FCC backup or local-dialogue route whose required speech service is healthy.
3. Re-read that satellite's selection, test a read-only question and a short announcement, and verify that the satellite returns to idle. Do not repeat a possibly executed household command merely because its response was lost.
4. When the original service recovers, verify it independently, restore the saved per-device selection, and repeat the bounded check. Retain the alternate integration for the next outage.

Do not change HA's global preferred pipeline to perform a single-device switch. A satellite's explicit selection can override that preference. Switching does not retrain wake words or require USB, APK replacement or new firmware.

The repository's [`voice_pipeline.py`](../../scripts/voice_pipeline.py) supports the named **homeway** and **fcc** backends with private mappings, dry-run previews and restore journals. Use the HA Assistant selector for **Local Russian Home**; do not relabel the third route as `fcc`. The [full switching runbook](../fcc-voice-backup.md#switch-one-or-several-satellites) contains exact commands and interrupted-operation behavior. There is no automatic failover.

## Acceptance and microphone coexistence

A model-load log and active unsilenced recorder establish deployment state. They do not prove that either phrase works from across the room. Record separate results for each phrase, near/far speech, negative phrases, background media and completion back to idle. Do not publish household audio or transcripts.

During a Jitsi call, follow the remote endpoint's microphone handoff. Home/Stop must restore the **previous** mute state, including an initially muted state. The display's camera viewer does not acquire a microphone. Avoid adding a second continuously listening application to solve a missing model; it can create capture contention without fixing the selected pipeline.

[Validation](Validation.md) lists the remaining physical tests. [Troubleshooting](Troubleshooting.md#voice-does-not-start-or-answer) separates failed activation from failed recognition or synthesis.
