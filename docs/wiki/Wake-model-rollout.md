# Wake model rollout: process and results

[Wiki home](Home.md) · [Voice configuration](Voice-and-wake-words.md) · [Technical runbook](../openwakeword-myshka.md) · [Validation](Validation.md)

The October 16 work adds an exact ONNX feature pipeline for a privately trained **“Привет, Мышка” (Privet Myshka)** activation model. The intended configuration has one activation phrase. The bundled **Stop** command remains separate, consuming the same microphone samples. This page explains the change, the installation gates and what the evidence establishes.

**Build verified; device verification in progress.** VACA **`0.13.4+myshka.3` / `7003`** builds for ARMv7 with the retained signing certificate. Its **18 JVM tests pass without failures or skips**. This is a source/build result, not a claim that the model recognizes speech on the Shows. See the dated [build receipt](../../integrations/vaca-dual-wake/build-myshka.3.json).

## Why the audio path changed

A classifier depends on the feature extraction used during training. The earlier microWakeWord model and the new ONNX model have different input contracts. Matching only the model filename or the spoken phrase is insufficient. The new implementation binds the classifier and both frontend artifacts to verified hashes and reproduces the streaming feature alignment.

![Logical audio processing: one microphone, aligned PCM, exact mel features, embeddings and classifier; Stop reuses the same audio; HA owns subsequent speech processing.](../assets/exact-oww-pipeline.svg)

In text: mono PCM at 16 kHz is accumulated into 1280-sample chunks with 480-sample context. The frontend maintains 76 × 32 mel features and supplies 16 × 96 embedding values to the activation classifier. It waits for real embeddings rather than random warmup. The raw score is compared against **0.50**, displayed as **5.0** by the HA control.

The **80 ms** chunk size describes audio framing, not the time until an answer. Actual delay also depends on phrase duration, buffering, inference, recognition, conversation and speech synthesis. A lower numeric threshold on a different model does not establish greater acoustic sensitivity.

## The installation process

![Six rollout gates: identify and back up, verify the signed build, replay fixtures, activate one phrase, check runtime and lifecycle, then repeat and document; failure returns to the saved state.](../assets/wake-rollout.svg)

1. **Identify and preserve.** Confirm the exact device and save its app-private state, previous signed APK and HA settings. Keep verified backup copies on two hosts.
2. **Build and inspect.** Verify the pinned source, complete patch, package, version, architecture and retained certificate. A normal same-certificate update preserves app data.
3. **Replay before relying on the microphone.** Compare Android embeddings and scores with the reference using existing private audio fixtures. This test reads files; it does not record the room.
4. **Select the intended model with VACA stopped.** Save `openwakeword`, the manifest-bound model and HA threshold 5.0 in HA before relaunching the app. Separate live writes can expose an empty model list and terminate the upstream listener. Remove the saved secondary-model selection so Jarvis is no longer active. Use the option actually advertised by HA: this integration title-cases the model ID rather than using the manifest’s Russian label.
5. **Verify operation and preservation.** Observe advancing samples and classifier windows, measure processing time, exercise mute/unmute and app restart, and compare pipeline, permissions, screen and media settings.
6. **Repeat on the second device.** Treat each Show as its own result. Remove temporary fixture/test-app artifacts afterward and preserve private recovery material.

A failed gate requires diagnosis or restoration of the saved configuration. The [technical runbook](../openwakeword-myshka.md#rollback) covers rollback. Flashing firmware and uninstalling the working application are not routine steps in this upgrade.

## What the development evaluation says

![Development results: 23 of 24 owner clips and 798 of 800 synthetic clips detected; zero triggered negative clips out of 532; three events in 10.696 hours; independent hardware acceptance pending.](../assets/wake-validation.svg)

The candidate's recorded evaluation detected **23/24 owner development clips** and **798/800 synthetic positives**. It triggered **0/532 negative clips**, with **3 events in 10.696 hours** of longer background material and none in a separate **3601.99-second** control. Clip counts and elapsed-hour experiments have different denominators; they cannot be combined into one accuracy percentage.

These observations concern the supplied development material. The earlier eight far-field clips are now training data. They do not establish independent far-field success, and microphone equivalence between a Dot and a Show is unverified. **Fresh three-metre trials remain pending.** Model weights, examples, recordings and detailed household receipts stay private.

## Build results and device acceptance

The source build passed **18 JVM tests**: the previous nine selection/lifecycle cases plus nine new framing/state cases. The new cases cover fragmented reads, overlap, normalization, warmup, reset and buffer ownership. A prepared replay set contains **four fixtures, 234 classifier windows and 11 positive reference windows**. Those are reference expectations until a device replay independently matches them.

The separate Android instrumentation checks cover manifest integrity and full frontend/classifier replay. A numerical match proves compatibility for the exercised inputs. It does not prove deliberate wake recognition, intelligible answers, local Stop behavior during real playback, recovery from power loss or sustained reliability.

Per-device installation, replay timing and lifecycle results belong here only after the corresponding checks complete. For the preceding installed `dualwake.2`/display `r11` baseline, see the [October 15 record](Validation.md#october-15-installed-state-and-recovery-checks).

## Language and service boundaries

The screen's four UI language families and the five README entry languages remain independent of wake phrases and speech language. The selected Russian Assist path still uses cloud recognition. Updating the local activation model does not move recognition on-device or switch the conversation provider. See [localization](Localization.md) and [voice paths](Voice-and-wake-words.md#choose-and-switch-an-assistant).

The diagrams are editable, self-contained SVG source. Their labels use canonical English, with explanatory text available through the translated project entry points. They contain no household addresses, credentials or device identifiers.
