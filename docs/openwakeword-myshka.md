# Privet Myshka: one openWakeWord activation phrase on Echo Show

[Project overview](../README.md) · [Wake-model rollout](wiki/Wake-model-rollout.md) · [Voice and wake words](wiki/Voice-and-wake-words.md) · [Validation](wiki/Validation.md) · [Previous dual-wake build](../integrations/vaca-dual-wake/README.md)

**Status — October 16, 2026: build verified.** VACA `0.13.4+myshka.3` / version code `7003` has been built, and **18 JVM tests passed with zero failures, errors or skips**. Android deployment, comparison with the reference output and physical Echo Show acceptance remain pending. This document records the verified build and the remaining rollout gates; it is not an installation receipt.

The authorized trial will replace the previous two-phrase configuration on both converted Shows with the updated **“Привет, мышка” / “Privet Myshka” as the only activation phrase**. “Hey Jarvis” must no longer be an active wake model. The selected HA assistant pipeline, clock/display configuration and media behavior are to be preserved.

## Process and current outcome

The [rollout guide](wiki/Wake-model-rollout.md) tracks the same stages with their evidence. Each stage answers a different question:

1. **Bind the model and preprocessing artifacts.** Identify the exact classifier and matching ONNX frontend files through the private manifest and checksums. This fixes the inputs to the trial; it does not establish recognition on Show hardware.
2. **Build and test the Android implementation — verified.** The `7003` candidate is built and all 18 JVM tests pass. These checks cover exercised code behavior; they do not run the complete model through an Android microphone.
3. **Compare Android inference with the reference — pending.** The prepared reference contains **four fixtures, 234 windows and 11 positive reference results**. Those are fixture/reference counts, not passed Android tests. Compare aligned output windows and classifier results before claiming parity.
4. **Deploy and check lifecycle — pending.** Verify each device's APK, private artifacts, one-model selection, effective threshold, microphone capture and recovery after mute/unmute and app restart. Preserve its HA identity, pipeline and display/media settings.
5. **Check attended use and duration — pending.** Deliberately test the intended phrase, the now-inactive alternative, Stop, a harmless request and the audible reply. A fresh three-metre test and longer observation remain separate acceptance work.

![Validation stages distinguish the verified JVM build, prepared reference material, pending Android comparison and pending physical acceptance.](assets/wake-validation.svg)

## Model identity and available evidence

The classifier is the privately supplied openWakeWord **ONNX** model evaluated in the EchoMuse work. Its recorded SHA-256 is:

```text
778acee4c4d4d612da7d39020e75887fc0fb18f821dab8dba9d4279130c3da9c
```

The trial uses a classifier threshold of **0.50**, represented as **5.0** by the VACA HA control's 0–10 scale. This is a new model/frontend combination; comparing 0.50 with the previous microWakeWord threshold of 0.35 does not establish a relative acoustic sensitivity.

The supplied development results are:

- Owner/development positive recordings: **23 of 24** detected.
- Synthetic positive examples: **798 of 800** detected.
- Negative test clips: **0 of 532** triggered.
- Longer negative material: **3 events over 10.696 hours**.
- A separate **3601.99-second** control: **no events**.

These are results from the supplied evaluation material, not success rates measured on either Show. They must not be combined into an overall accuracy figure. The earlier eight far-field recordings are now training material and therefore are not an independent test set. A **fresh three-metre test remains pending**.

No microphone equivalence between EchoMuse and Echo Show has been established. Different capture hardware, placement, room acoustics and playback conditions can change the result. This trial does not collect new recordings automatically.

## Why this needs a new APK

The previous private activation model used the microWakeWord path and its TFLite model contract. The new classifier uses the openWakeWord feature pipeline and an ONNX graph. Renaming an `.onnx` file to `.tflite` changes neither the graph format nor its required inputs. Merely loading an ONNX classifier with a different feature extractor also fails to establish equivalence to its training pipeline.

The verified build candidate is **VACA `0.13.4+myshka.3`, version code `7003`**, package **`com.msp1974.vacompanion`**. It must be signed with the **same retained private certificate** as the installed local builds. Successful signing and package checks are required before an in-place update; the version string alone is insufficient.

The new opt-in path uses `ExactOnnxFrontend` with the ONNX frontend artifacts whose hashes match those used for training:

![One microphone capture feeds the exact ONNX activation pipeline and the separate existing Stop detector; feature windows and model hashes are bound to the private artifacts.](assets/exact-oww-pipeline.svg)

1. Accumulate **1280 samples / 80 ms** of 16 kHz PCM, independently of individual microphone read sizes.
2. Retain **480 samples** of context between chunks.
3. Maintain the matching **76-frame, 32-bin mel window**, including the expected mel normalization.
4. Produce **96-value embeddings** and supply the classifier with the most recent **16 embeddings** in order.
5. Run the frontend on the CPU using the verified ONNX artifacts, validate tensor shapes and retain the classifier score without the legacy two-decimal rounding path.

The **80 ms value is a processing chunk size**, not a measured wake-detection or end-to-end response latency. These dimensions define feature alignment. Each running collection owns its native sessions and microphone cleanup. The verified JVM build does not replace the pending Android inference comparison, lifecycle checks or physical acceptance.

The existing microWakeWord implementation remains available independently, including its optional two-model support. Keeping that capability in the APK does **not** mean a second activation model is active in this trial.

## Private artifact layout and binding

The classifier, matching frontend models and manifest remain in VACA's app-private storage beneath:

```text
files/custom/wakewords/openwakeword/
```

The private `exact-frontend.json` manifest binds the selected model to its artifacts. It specifies:

- `schema_version: 1` and `frontend: "openwakeword-80ms-v1"`;
- the exact `model_id` and a display `label`;
- the classifier filename and SHA-256, with the filename matching `<model_id>.onnx`;
- the mel and embedding filenames and SHA-256 values, stored in the private `frontend/` subdirectory.

The loader requires exactly one selected model for this path. It checks the manifest, file locations, size bounds and checksums. A matching manifest with invalid assets must fail rather than silently loading unverified substitutes. The manifest is opt-in: a different engine or model selection is not proof that this exact frontend is running.

Do not place model weights, frontend artifacts, app backups, recordings, credentials or signing material in Git or in HA's public `/local` or `/vaca` static directories. Keep the manifest and its verified inputs together in private recovery storage. Do not use Custom Files Sync for an intentionally private-only model deployment; the existing sync behavior can remove local custom files.

## Preserve Stop without a second activation phrase

`LocalStopDetector` preserves the existing bundled **Stop command** using the **same PCM samples** read by the activation engine. It does not open another microphone and does not load “Hey Jarvis” or another activation model. Its stop-only microWakeWord processing is separate from the openWakeWord feature pipeline.

“Privet Myshka” starts an assistant interaction; the existing Stop path controls interruption. These are distinct roles. One active wake phrase does not require removing the Stop command. The new code adds no automatic recording or audio-upload destination; existing Assist streaming and any explicitly configured diagnostic recording still follow the application's settings.

## Rollout sequence and required settings

Work on one explicitly identified Show first. Do not infer success on the second from the first.

1. **Record and back up the current state.** Save the installed APK and certificate identity, a verified app-private backup, satellite identity, engine/model selection, HA threshold, optional secondary-model JSON, pipeline, dashboard path, permissions and media settings. Keep the backups private and verify their hashes.
2. **Verify the new build.** Check package name, version `7003`, architecture and certificate against the installed app. Record the new APK hash and relevant build/test results. A same-certificate update should preserve app data; do not uninstall the working app as a routine update step.
3. **Install the private artifact set.** Place the classifier, matching ONNX frontend files and `exact-frontend.json` in app-private storage. Verify their bytes, ownership and access. Remove any temporary staging copies and return debugging to the intended nonroot state.
4. **Stop VACA before changing the engine.** Use the trusted ADB host and the already verified device selector to force-stop only `com.msp1974.vacompanion`. Do not restart Home Assistant. The observed upstream engine-selection path can construct a legacy openWakeWord engine with an empty model list between separate HA control writes and terminate the app. Muting alone does not prevent that constructor failure.
5. **Save the complete selection while VACA is stopped.** Remove `files/secondary-wake-word.json` after preserving its backup. Set the HA engine to **`openwakeword`**, not `openwakeword_rt`, select only the manifest-bound model, and set the HA threshold to **5.0** (effective **0.50**). The observed selector displays **`Privet Myshka Dab4A660248F Cal`**, derived from ID `privet_myshka_dab4a660248f_cal`, rather than the manifest's Russian phrase label. Confirm all three saved HA values before launching the app; do not treat an unavailable or rejected write as success.
6. **Launch and verify preserved behavior.** Confirm the exact model ID in the load log, advancing samples, one active wake classifier, the existing HA satellite and selected pipeline, saved display page, and retained media settings. Changing activation does not require switching STT, conversation or TTS providers.
7. **Exercise lifecycle recovery.** Check mute/unmute and a normal app restart. Confirm the same ONNX path reloads, microphone capture resumes, and native resources release on stop. Only then repeat the controlled update on the second Show.

If the verified build is unavailable or an identity/checksum check fails, the rollout is not ready. Keep the known-working installation and record the specific failure instead of reporting deployment from source preparation alone.

## Acceptance and deployment record

The current public record is **build verified; Android comparison and deployment pending**. The prepared four-fixture reference must not be reported as successful runtime parity. Update device outcomes only from per-device observations, with artifact versions and the test method:

- **Installed state:** expected APK/certificate; exact manifest and artifact checksums; `openwakeword`; one selected activation model; effective threshold 0.50; no secondary “Hey Jarvis” selection.
- **Running state:** exact frontend loaded; microphone samples and classifier windows advancing; no fallback to a different engine; existing HA identity and pipeline connected.
- **Lifecycle:** mute/unmute and app restart recover capture and the same model. Android reboot and loss of AC power are separate tests.
- **Attended activation:** deliberately say “Привет, мышка,” issue a harmless request, observe the response and hear the answer. Test the inactive “Hey Jarvis” phrase separately and include non-wake speech and normal playback. Keep trials and observations distinct from training material.
- **Stop and media:** verify the existing Stop action, then return to normal capture after assistant speech or media playback. A loaded stop model is not evidence that interruption was heard and acted upon.
- **Distance and duration:** collect the fresh three-metre acceptance result and a suitable duration sample before making far-field or false-activation claims. Do not create recordings without an explicit reason and authorization.

No installed-device result, acoustic acceptance, measured wake latency or power-cycle result is claimed by this build record. The central [validation page](wiki/Validation.md) should link the eventual per-device receipt without publishing private recordings or device identifiers.

## Rollback

Keep the verified previous APK, saved settings and app-private backup available until the trial is accepted. Prefer a normal same-certificate restoration compatible with the installed Android build; use the established [signed update and rollback procedure](../integrations/vaca-dual-wake/README.md#install-a-same-certificate-update). If Android rejects a downgrade, inspect the failure and stop rather than turning it into an unplanned uninstall or data loss.

Stop VACA before restoring separate HA engine/model controls, save the complete previous selection, then launch and verify it. Restoring only the old APK is insufficient: the previous microWakeWord build cannot be assumed to consume this exact ONNX manifest. Restore the saved engine, primary model, threshold and matching private assets, then verify the existing HA identity and microphone lifecycle. Restore the secondary-model JSON only if deliberately returning to the prior two-phrase configuration; otherwise retain one supported primary activation phrase. Preserve the saved pipeline, display and media configuration throughout.

After rollback, record the restored version and effective settings and repeat the relevant acceptance checks. Retained training/evaluation scores do not validate a different restored runtime.
