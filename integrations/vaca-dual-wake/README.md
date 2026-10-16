# Local wake engines for VACA 0.13.4

[Project README](../../README.md) · [Private wake-word setup](../../docs/vaca-private-wakeword.md)

This Android patch extends [View Assist Companion App](https://github.com/msp1974/ViewAssistCompanionApp)
at the pinned commit `65906aebffd2f39772773b44729b22fd022a1f3c`.
The current source builds **`0.13.4+myshka.3` / version code `7003`** for ARMv7.
It retains the optional two-model microWakeWord extension and adds an opt-in
exact ONNX frontend for one privately trained activation model. These are
alternative configurations, not three simultaneously active wake phrases.

The new [Privet Myshka runbook](../../docs/openwakeword-myshka.md) and
[illustrated process and results](../../docs/wiki/Wake-model-rollout.md) describe
manifest binding, local Stop, numerical replay, installation gates and rollback.
The [myshka.3 build receipt](build-myshka.3.json) records 18 passing JVM tests;
device and acoustic acceptance are recorded separately.

![One microphone feeds exact ONNX activation features and the local Stop detector.](../../docs/assets/exact-oww-pipeline.svg)

The [validated build record](validated-build.json) and
[archived patch](history/dualwake.1.patch) describe the previously installed
`dualwake.1` build. They remain unchanged as historical evidence. A new build
produces its own private JSON evidence file; building an APK does not prove
installation or voice recognition.

The [dualwake.2 build record](build-dualwake.2.json) and
[archived patch](history/dualwake.2.patch) preserve the previous version. The record contains the checked APK,
patch, source-tree and certificate hashes from the October 15 build, with nine
passing JVM tests. Its build-only status is intentional; installed-device
results are recorded separately below when verified.

## Configure two microWakeWord phrases

Create `files/secondary-wake-word.json` inside VACA's **app-private data**:

```json
{"id": "hey_jarvis"}
```

Restart VACA after adding, changing or removing the file. The ID must match a
model available to the selected engine. Custom model files remain in
`files/custom/wakewords/microwakeword/`; they are not bundled with this patch or
published through Home Assistant's static file server.

- Both models share one microphone, feature extractor, assistant pipeline and
  threshold. The existing deployment uses **0.35**, shown as **3.5** on the HA
  control's 0–10 scale.
- A two-second cooldown applies across activation models, preventing two
  detections from the same utterance from immediately launching two requests.
- A duplicate or unknown secondary ID is ignored. An empty primary or the
  primary value `none` disables both. If a nonempty primary is unavailable, a
  valid secondary may still load; inspect both the selected and loaded models.
- Other wake engines retain their single-model behavior. The HA selector still
  shows only the primary model; it does not provide a second model selector.
- Diagnostics list selected IDs. Successful model-load logs provide separate
  evidence that each model was actually loaded. A selected ID alone is not a
  successful loading check.

The October 15 deployment used the custom Russian phrase **«Привет, мышка»** and the
built-in English phrase **“Hey Jarvis.”** The wake phrase, interface language,
HA recognition language and reply voice are independent settings. Adding an
English wake phrase does not switch a Russian assistant to English. Keep stable
model IDs untranslated in configuration.

## What changed in dualwake.2

The upstream microWakeWord engine created its detector in a local variable,
while its cleanup referenced a different, always-null field. Muting or
restarting the listener could therefore leave native model interpreters and the
feature extractor unclosed. This patch gives each collection one resource
owner: stopping closes the active detector; replacing it closes the previous
one; failures cannot close a retired detector twice. Microphone cleanup still
runs if detector cleanup throws.

Four JVM lifecycle tests cover shutdown, replacement, failed loading and failed
close. The five model-selection/cooldown tests remain. This fixes a concrete
resource lifetime defect; it does not establish an acoustic false-positive rate.

## Build and verify

Use Python 3.8+, Git, JDK 21, Android SDK 36, and the CMake/NDK components requested
by Gradle. SDK build-tools must provide `apksigner` and `aapt`. The builder has no
HA or device access. It builds a debuggable ARMv7 APK, preserving the private
backup/restore workflow used by the installed upstream debug APK. Keep ADB
authenticated and restricted to trusted hosts.

When building from a release source archive without Git metadata, keep work and
signing files under its `private/` directory or in an explicitly chosen external
directory. In a Git checkout, in-tree destinations must be Git-ignored.
Symlinked in-tree destinations and damaged Git metadata are rejected.

Run host regression tests without an Android toolchain:

```bash
python3 -m unittest discover -s integrations/vaca-dual-wake/tests -v
```

Set the toolchain, then choose **one** signing case below:

```bash
export JAVA_HOME=/path/to/jdk-21
export ANDROID_HOME=/path/to/android-sdk
```

### Update an existing local installation

Use the **original private signing directory**. On the first run of the hardened
builder, supply the SHA-256 certificate fingerprint from the installed APK or
its previous verified build record:

```bash
python3 integrations/vaca-dual-wake/build.py \
  --work-dir private/vaca-myshka-build-v3 \
  --signing-dir private/vaca-dual-wake-signing \
  --expected-signer-sha256 "$EXPECTED_SIGNER_SHA256"
```

The builder verifies and records that identity in the ignored signing directory.
Later builds reuse it and reject a changed certificate. `--create-signing-key`
is intentionally rejected when a key already exists. A lost or incomplete key
pair must be restored from backup; the builder never silently replaces it.

### First local installation only

A new operator who has never installed a locally signed build can explicitly
create a new identity:

```bash
python3 integrations/vaca-dual-wake/build.py \
  --work-dir private/vaca-myshka-build-v3 \
  --signing-dir private/vaca-dual-wake-signing \
  --create-signing-key
```

This certificate differs from upstream and from other operators' local builds.
It requires the first-migration procedure below, not a normal upstream update.
Back up the signing directory privately before relying on the new installation.

### Build safeguards and outputs

The helper checks out the exact upstream commit and accepts only the pristine
source tree or exactly that tree plus the current patch. It rejects unrelated
tracked edits, staged changes, added source files and unexpected ignored input
files. Symlinked build inputs/outputs are also rejected. Known build-cache/output directories and the regenerated
`local.properties` are allowed. It never resets operator edits. When upgrading
the patch, choose a new ignored work directory so the old build stays available.

The builder runs JVM tests, verifies APK signature/package/version/ABI, checks
source integrity again, and writes two private outputs:

- `vaca-0.13.4-myshka.3.apk`
- `vaca-0.13.4-myshka.3.json` — source and patch hashes, signing certificate,
  artifact hash/size, test results and an explicit “not deployed by build tool”
  status. It contains no password, token or device identity.

These checks establish source and artifact provenance, not byte-identical
reproducibility of the Android dependency/toolchain ecosystem. Keep generated
APKs, checkouts, signing material, models and device backups out of Git. The
upstream in-app updater cannot replace this differently signed APK.

## Install a same-certificate update

**An existing local installation with the original certificate can receive
`myshka.3` as an ordinary update. Do not uninstall it.** Select the intended
engine and private model using its runbook after verifying the new artifact.

1. Select one device by its exact serial and verify its current package/version.
   Save a fresh private data/settings backup and keep the known-working APK.
2. Compare the new APK certificate with the installed APK or verified build
   record. Confirm the package is `com.msp1974.vacompanion` and the new version
   code is greater. Stop if identities differ.
3. Use the trusted ADB host and explicit device selector:

   ```bash
   adb -s "$ANDROID_SERIAL" install -r "$APK"
   ```

4. Launch VACA. Confirm its existing HA satellite reconnects, the configured
   model or models load, and the microphone is active. Verify assistant, threshold,
   brightness, dashboard, permissions and special access remain as intended.
5. Restart the app once and recheck the expected loads before updating another device.
   Test each phrase physically when a listener is available.

For a same-certificate debuggable rollback, preserve a current backup and try
`adb -s "$ANDROID_SERIAL" install -r -d "$PREVIOUS_APK"`. Android may reject a
downgrade; if it does, stop and inspect the error. Do not turn a failed update
into an unplanned uninstall. Removing the secondary JSON and restarting VACA
returns a healthy local build to one wake model without reinstalling anything.

## First migration from upstream / return to upstream

Upstream and locally signed packages have different certificates. Android cannot
update one over the other. Never bypass signature verification or uninstall
before a verified backup exists. Migrate one device and verify it before the next:

1. Record the exact serial, original APK hash/certificate, HA satellite identity,
   assistant, threshold, screen settings, runtime permissions and special access.
2. Stop VACA briefly and back up its app-private files, preferences, databases
   and WebView state. Store the archive privately on two hosts and verify its
   hash and contents. Use **GNU tar format** for the migration archive; this
   Android image rejects some Python PAX headers. Restart the original app until
   ready to install.
3. Retain the verified original APK. Deactivate VACA's device administrator in
   Android Settings, then stop VACA, uninstall and install the new APK under the
   same package ID.
4. Restore data through the new app's own UID. Preserve the previous VACA UUID
   explicitly in preferences: fallback `ANDROID_ID` changes with the signing
   certificate. Restore only permissions and special access already granted.
   On this Android 11 image, `pm set-permission-flags` is unavailable. If camera
   and storage were denied, use their actual Android prompts to preserve those
   denials and verify `USER_FIXED` where intended.
5. Add the secondary configuration if needed, restore the Home-app selection,
   launch VACA and perform the same connection/model/settings checks as an update.
6. If migration fails, reinstall the original APK and restore its original private
   data with this same certificate-change procedure.

Returning to upstream also requires this migration. It removes the dual-wake
extension; an upstream in-app update is not a supported shortcut.

## Privacy and acceptance limits

The patch omits the Google Services and Crashlytics Gradle plugins and supplies
no Firebase project configuration. Upstream runtime code remains and skips
Firebase setup when no Firebase app exists. This is not a claim that the complete
assistant is offline: the selected HA pipeline owns recognition, conversation
and speech synthesis, which may involve external services.

Model selection, lifecycle tests and HA connection checks do not prove acoustic
accuracy. Test each phrase, negative phrases, background audio, playback
coexistence, full power-cycle recovery and a multi-day soak. Record these as
pending when nobody can listen near the device.

## Historical deployment evidence — 2026-10-14

The [validated build record](validated-build.json) identifies the installed
`dualwake.1` artifact and the exact [archived patch](history/dualwake.1.patch).
Five JVM tests passed for selection, duplicate elimination, absent/unknown
secondary models, primary disable behavior and the cross-model cooldown.

Both converted Echo Show 5 Gen2 devices loaded their existing custom primary
model plus `hey_jarvis` and recovered both after a normal app restart without an
operator prompt. Their existing HA identities and selected Russian assistant
were retained. The threshold stayed at 0.35; brightness at that deployment was
manual 80% and the long timeout was preserved. These are historical settings,
not assertions about the current brightness. Optional camera/storage permissions
remained denied, microphone permission granted, and ADB authenticated/nonroot.

Sequential HA announcements completed and both satellites returned to idle. This
confirms service-level playback completion, not attended listening. Physical
recognition, false-positive rate, power-cycle recovery and multi-day stability
remained unverified for that build.

## Installed update — 2026-10-15

Both converted Shows received `0.13.4+dualwake.2` / `7002` through an ordinary
same-certificate update. App-private backups were copied to two hosts and hash
checked first. No uninstall or firmware conversion was required.

Both retained their HA satellite identity, Local Russian Home assistant,
`privet_myshka_v1` primary and `hey_jarvis` secondary model, shared 0.35 threshold,
and intended permissions. At that checkpoint screen brightness was manual 100%; the older
80% value above is historical. On each Show, three software mute/unmute cycles
and one normal app restart restored both models and microphone capture without
an operator prompt. Display revision `20261015-r11` is installed on both.

Physical recognition of deliberately spoken phrases, audible response quality,
power-loss recovery and a multi-day soak remain unverified. See the
[validation record](../../docs/wiki/Validation.md) for scope and camera results.
