# Validation and evidence

[Wiki home](Home.md) · [Troubleshooting](Troubleshooting.md) · [Contributing](../../CONTRIBUTING.md)

Each result needs a dated target, exact artifact or revision, method and limitation. Avoid a single “everything works” claim that mixes an automated test with an earlier physical observation on another build.

## Evidence ladder

1. **Source checks:** syntax, unit tests, generated configuration validation and dependency checks. These establish expected code behavior under the exercised inputs.
2. **Installed-state checks:** correct package/version/signer, configuration, model hashes, permissions, service process and registered HA identity. These establish what is deployed.
3. **Transport checks:** authenticated connection, completed protocol exchange, downloaded TTS audio and advancing decoded video frames. These establish a working data path during the sample.
4. **Attended use:** a person deliberately says each phrase, hears the answer, sees remote video and checks intelligibility/echo. These establish the observed human experience.
5. **Recovery and duration:** app restart, Android reboot, loss of power, network interruption and a multi-day soak. Each is a distinct test; passing one does not imply the others.

## Recorded milestones

**Conversion — October 2 snapshot.** The guarded amonet/TWRP route, verified raw backup, LineageOS boot and Companion installation/login were observed. The [full record](../preparation-status.md) includes exact artifact and validation scope. Its threshold and initial voice settings are historical, not the current recommendation.

**Clock/cameras/media — October 4–5 records.** The [clock integration](../../integrations/show5-display/README.md) records live camera decoding, proportion-preserving video, motion handling, cleanup and later suppression of the native play placeholder. The [remote endpoint guide](../remote-endpoint.md) records individual app launches and selected playback checks. Neither is a current long-duration reliability certificate.

**Brightness/color — October 8 record.** The [Android guide](../android-and-home-assistant.md#fixed-display-brightness) records effective manual brightness, corrected idle dimming and neutral LiveDisplay settings. Physical panel color equality was not established.

**Voice — October 14 baseline.** Both Shows loaded the two activation models and recovered them after a normal app restart. Their existing satellite identities, selected assistant, threshold, screen settings and intended permissions were retained. Sequential announcements completed and satellites returned idle. See the [dual-wake record](../../integrations/vaca-dual-wake/README.md#historical-deployment-evidence--2026-10-14) and [Russian speech rollout](../fcc-voice-backup.md). **Physical two-phrase recognition, false-positive rate, power-cycle recovery and a multi-day soak remain unverified for that build.**

**Localization source — October 15.** The display now has a four-language source layer and locale/hour-format configuration. A source test establishes catalog and formatting behavior; the deployment record must separately identify which static revision and locales were actually inspected on hardware. Do not promote a prepared revision to a hardware milestone solely because files exist.

## October 15 installed-state and recovery checks

Both Shows received VACA **`0.13.4+dualwake.2` / code `7002`** and the complete
**`20261015-r11`** display. The APK signature matched the previous local build;
updates retained app data and did not uninstall or flash firmware. Private
backups were retained on two hosts and verified by hash.

On each device, three software microphone mute/unmute cycles and a normal app
restart restored both activation models and active microphone capture. Existing
HA identities, **Local Russian Home**, **Irina**, threshold **0.35**, English
24-hour display, manual **100%** brightness and intended permission grants/denials
were retained. Final HA checks reported both satellites idle, with mute and auto
brightness off. These results do not establish physical phrase recognition.

Fresh camera checks passed on **both Shows**: Porch at **1920×1080** and Front
at **854×480**, with advancing decoded frames and return to the English clock.
The check cleared the prior camera, required a newly resolved stream session,
then observed its frame count increase with the video visible. On Show 1, Porch
required an automatic second attempt after a startup timeout; an earlier sample
failed signaling. This establishes recovery and playback during the samples,
not immediate startup or sustained reliability. The earlier check could confuse
retained element counters with the next camera and was replaced.

HA experienced a separate server disk-pressure eviction during the rollout.
Removing unused build cache allowed startup to complete; persistent data and
backups were retained. The r11 fix covers the observed interval in which HTTP
and WebSocket authentication were available before MQTT subscription commands.
Long-term server storage capacity remains a separate operational issue.

## October 15 source and build checks

The installed display revision is **`20261015-r11`**, combining the r10 language
catalogs with recovery when MQTT is not ready during HA startup. The Android artifact is
**`0.13.4+dualwake.2` / `7002`**; its [build receipt](../../integrations/vaca-dual-wake/build-dualwake.2.json)
records the exact source, patch, APK and original signing-certificate hashes.

- Repository Python suite: 176 tests executed, including 15 optional HA-runtime
  skips; no failures. Skips do not establish compatibility with a live HA runtime.
- Display: 109 Node tests and 37 Python tests passed.
- Android builder: 31 host regression tests passed. The actual Gradle build
  passed nine JVM tests, including four detector resource-lifecycle cases.
- Workflow contracts: 16 checks passed. Six source-packaging tests also passed,
  including tests executed from the generated archive.
- Offline documentation validation passed for 62 Markdown/SVG files. It checks
  local targets, anchors and accessible SVG structure, not external availability.

Chrome 155 desktop visual checks covered **48 synthetic renders**: four
languages, 12/24-hour clocks, 960×480 and 480×240 viewports, and four camera
status messages. There was no clipping, clock wrapping, JavaScript error or
external resource request. The narrowest tested clock retained 33 px horizontal
margin. All six SVG diagrams were rendered and inspected. These are layout
checks; they do not certify every locale's font rendering on Android.

## Offline checks

From the repository root, use the suites relevant to the changed component:

```bash
python3 scripts/check_docs.py
python3 -m unittest discover -s tests -v
node --test integrations/show5-display/tests/*.cjs
python3 -m unittest discover -s integrations/show5-display/tests -p 'test_*.py' -v
python3 -m unittest discover -s integrations/show5-intercom/tests -v
```

The [contribution guide](../../CONTRIBUTING.md) and [CI workflow](../../.github/workflows/tests.yml) define additional isolated voice-runtime and container checks. VACA's patched Android source has its own [JVM/build procedure](../../integrations/vaca-dual-wake/README.md). Required runtimes must be present; a skipped test is not a pass. Do not unlock, flash, record ambient audio or publish just to validate documentation.

## Short device acceptance procedure

Use one identified device and a harmless read-only question. Preserve the previous configuration and keep recordings/transcripts private if any are deliberately collected.

- Confirm installed revision, assistant selection, loaded primary and secondary models, unsilenced capture and no onboarding prompt.
- Speak each wake phrase separately, wait for idle between trials, and record activation plus audible-answer outcome. Include negative phrases and background playback. Do not infer a rate from one successful utterance.
- Show each configured camera, verify actual moving video, then check natural expiry and Home cleanup. Confirm voice capture afterward.
- Play one permitted media item; confirm audible output and Stop. For a call, check both directions with a second participant and verify microphone restoration when ending.
- Restart the app and repeat the relevant checks. Schedule Android reboot, power-loss and network-interruption tests as separate attended recovery cases.

A useful private receipt records: timestamp/time zone; device identity; source/artifact hash; configuration revision; exact action; observable result; recovery state; and remaining tests. The public summary omits IPs, serials, tokens and household content while retaining enough version information to understand its scope.
