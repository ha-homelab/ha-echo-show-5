# Validation and evidence

[Wiki home](Home.md) · [Troubleshooting](Troubleshooting.md) · [Contributing](../../CONTRIBUTING.md)

Each result needs a dated target, exact artifact or revision, method and limitation. Avoid a single “everything works” claim that mixes an automated test with an earlier physical observation on another build.

## October 19: mixed-wake checkpoint

This checkpoint uses America/Los_Angeles dates; its machine receipts are from
October 20 UTC.

The [mixed-wake implementation](Mixed-wake-words.md) adds optional Hey Jarvis
to the unchanged exact Myshka path. The retained-key **`0.13.4+myshka.7` / `7007`**
build passed **42 JVM tests**, with no failures, errors or skips. The builder's
**35 host regressions** and **six source-package checks** passed. Its
[build receipt](../../integrations/vaca-dual-wake/build-myshka.7.json)
records the artifact, source, patch and signing identity.

Before installation, VACA was stopped for a consistent private app-data backup;
copies on two hosts were verified by hash. The previous `.6` APK was retained.

**Show 1 received the same-signer `.7` update and passed all six Android
instrumentation tests in 19.668 seconds.** Its fresh process authenticated to
HA over HTTPS. Replay of the existing Myshka fixtures produced **294 embeddings,
234 classifier windows and 11 positive windows**, with every threshold decision
matching the reference. Maximum absolute differences were **0.00007439** for
embeddings and **0.0000068844** for classifier scores. Processing 23.520 seconds of fixture audio took
**14.544 seconds**, including initialization; this is not wake latency.

The shared Stop/Jarvis frontend matched independently constructed reference
detectors over **2,344 windows per model**, with **zero score difference**.
Three of four synthetic Jarvis voices produced accepted windows: **Samantha 8,
Karen 8 and Moira 8**. Daniel produced none; its maximum score was **0.9609375**,
below the calibrated 0.97 boundary. In total, **24 activation windows** passed
the temporal gate, and **24 high-score windows were correctly rejected** by that
gate. This checks routing and preservation of the model's decision. It is not
100% recognition, a room recording or acoustic acceptance of either phrase.

The enabled mixed configuration loaded exact Myshka at **0.50**, bundled Jarvis
with its **five-evaluation mean strictly greater than 0.97** gate, and the
separate Stop detector. **Three actual microphone mute/unmute cycles passed**:
each stopped capture and restored all three models. Mean processing after the
cycles was **53.664, 52.448 and 52.320 ms per 80 ms input chunk**. A normal app
restart restored the same configuration, completed fresh HTTPS token refresh
with certificate validation, and averaged **56.472 ms per 80 ms input**. These
are short local processing observations, not wake/response latency or a soak.

HA controls, the selected Local Russian Home pipeline, permissions, default
launcher, manual brightness 255 and authenticated nonroot ADB were preserved.
The final check found **exactly one unsilenced VACA microphone capture** and
both activation models selected. The instrumentation APK, temporary fixtures
and test caches were absent; all four private model/manifest files retained
their expected hashes. No new room audio was recorded or played, and no
shared speech-backend configuration was changed.

**Show 2 remains unavailable and last verified on `.4`.** Physical recognition,
audible replies, Stop during playback, distance, power-loss recovery and a
longer soak remain separate acceptance work. Historical `.3`/`.4`/`.6` results
below remain separate evidence.

<a id="october-19-current-checkpoint"></a>

## October 19: earlier myshka.6 checkpoint

Dates in this checkpoint use America/Los_Angeles; the machine receipts are from
October 20 UTC. The retained-key **`0.13.4+myshka.6` / `7006`** build passed
**29 JVM tests, with no failures, errors or skips**, including the TLS and malformed
input regressions. Its source tree, patch hash and test totals match the successful
hosted source build. The [build receipt](../../integrations/vaca-dual-wake/build-myshka.6.json)
identifies the locally signed artifact; the hosted test signer is a different
identity and was not used to update either device.

**Show 1 received `.6` as an in-place update from `.3`.** Its fresh private
application backup was copied to two hosts and hash-verified before installation.
Three Android instrumentation tests passed, including optional-metadata
enumeration and replay of four existing private fixtures: **294 embeddings,
234 classifier windows and 11 positive windows**, with every threshold decision
matching the reference. Maximum absolute differences were **0.00007439** for
embeddings and **0.000006885** for classifier scores. Replay of 23.520 seconds of
audio took **14.759 seconds**, including fixture initialization. This is file
inference evidence, not a new microphone recording or acoustic acceptance.

The fresh `.6` process authenticated to HA over HTTPS with certificate checks
enabled, loaded **Privet Myshka at 0.50** and the separate local Stop detector,
and resumed microphone inference. The current assistant selection and its
**Silero** voice were preserved; the older Irina records below remain historical.

One software mute/unmute cycle closed and restored actual microphone capture.
A normal application restart restored the listener and completed fresh HTTPS
authentication. Mean local processing was **51.224 ms per 80 ms input** after
the mute cycle and **56.608 ms per 80 ms** after restart; these short observations
are not wake or response latency. Current HA settings, manual brightness 255,
screen timeout, permissions, default launcher and authenticated nonroot ADB
were preserved. The secondary wake selection remained absent.

Final cleanup confirmed that temporary fixtures and the instrumentation APK
were absent, all four private model/manifest assets matched their expected
hashes, and the updated application remained running.

**Show 2 was unavailable during this check.** Its reserved network address did
not answer, no active DHCP lease or resolved ARP neighbor was found, and all
46 of its HA entities were unavailable. The existing static reservation was
retained. This does not distinguish power loss from a Wi-Fi problem. Its last
verified installation remains `.4`; no new installation, microphone or display
claim is made for it.

**The HA backend was checked without playing audio.** A Russian text request for
the first heater's power completed through a native HA intent and the current
Silero TTS provider; the response audio downloaded successfully in **4.481 seconds**
overall. A separate arithmetic request reached the conversation stage but ended
after **45.278 seconds without an intent result or TTS output**, under the probe's
explicit 45-second deadline. This is not evidence of a production timeout setting.
A `run-end` event alone is not a successful answer.

One repeat with the resident Ollama model and a 120-second probe budget
**succeeded**: the model answered “Четыре.” (“Four.”), the intent and TTS events
completed at **43.045 seconds**, and **8,876 bytes** of speech were downloaded by
**56.570 seconds**. The response came from the conversation model rather than a
native intent. HA-to-Ollama HTTP checks completed in about half a second; logs
showed slow CPU prompt processing: only 1,024 of 1,418 prompt tokens were cached,
leaving 394 to evaluate.

A subsequent **new arithmetic question**, after that completed request, reused
**1,407 of 1,419 prompt tokens**. It produced the first model output at **3.515
seconds**, completed the intent/TTS events at **8.479 seconds**, and downloaded
**22,484 bytes** of correct Russian speech by **12.495 seconds**. Configuration
and model selection were unchanged. This improvement reflects prompt-cache
state, not an applied optimization or a guaranteed response time. A resident
model alone does not establish a warm prompt cache; the first request and
requests with changed context can be substantially slower.

The installed HA default pipeline timeout was **300 seconds**, unchanged.
The native-intent timing must not be presented as model latency, and TTS URL
availability must not be presented as completed speech delivery. These checks
did not exercise speech recognition, the Show microphone or audible playback.
Pipeline definitions were unchanged.

Physical wake recognition, audible replies, Stop during playback, fresh
three-metre tests, power-loss recovery and a longer soak remain separate
acceptance work.

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

## PR #69 follow-up: myshka.4 build and Show 2 checks

At the October 16 checkpoint, VACA **`0.13.4+myshka.4` / `7004`** had a verified build with the original retained signing certificate and **18 JVM tests passed, zero failures, errors or skips**. The [build receipt](../../integrations/vaca-dual-wake/build-myshka.4.json) records its source, patch and APK hashes.

This patch isolates invalid optional label metadata from custom-model enumeration. The exact-engine loader continues to reject invalid assets. Show 2 received the same-certificate update and passed the targeted Android inventory regression: **one test, five metadata cases, 0.624 seconds**. Show 2 also passed **one actual microphone close/reopen cycle** and a **normal app restart**, with short local processing observations of **52.960 ms** and **55.184 ms per 80 ms input chunk**, respectively. These are processing times, not wake or response latency. The single model at 0.50, absent secondary selection, HA configuration, manual brightness 255, permissions and authenticated nonroot ADB were preserved. End-to-end HA/TTS health and physical speech acceptance were not tested. At that October 16 checkpoint, Show 1 was unreachable and remained last verified on `.3`; no installation was performed there.

Final cleanup confirmed that the temporary fixture directory and instrumentation APK are absent, all four private model/manifest assets still match their expected hashes, and VACA remains running.

The `.3` replay counts, numerical differences and lifecycle observations below remain the historical evidence for that artifact. A new build does not turn those observations into a full `.4` replay.

## October 16 exact ONNX source and publication checks

The [single-phrase rollout](Wake-model-rollout.md) adds a hash-bound exact ONNX
frontend in VACA **`0.13.4+myshka.3` / `7003`**. Its
[build receipt](../../integrations/vaca-dual-wake/build-myshka.3.json) preserves
source-tree, patch, certificate and APK hashes independently of deployment.

- Actual Android build: **18 JVM tests**, with no failures, errors or skips.
- Android builder host regressions: **31 passed**; the new APK version is
  accepted and the old version is rejected. The minimum JVM count is now 18.
- Repository Python suite: **182 tests**, no failures, **15 optional HA-runtime
  skips**. Those skips do not establish live HA compatibility.
- Source packaging: **six checks passed**, including isolated checks from the
  generated archive and exclusion of private runtime artifacts.
- Documentation: **72 Markdown/SVG files** passed local link/anchor and SVG
  accessibility checks. All **three new SVGs** were rendered in Chrome and
  visually inspected, with no observed clipping or external resource requests.

The [development-evaluation chart](../assets/wake-validation.svg) reports supplied
model-development observations. It is not an acoustic benchmark on the Shows.
Android replay and installed-state results are recorded separately below.
The earlier October 15 record remains historical.

## October 16 installed-state and replay checks

Both Shows received **`0.13.4+myshka.3` / `7003`**, matching the APK and retained
signing identity in the build receipt. Each passed both Android instrumentation
tests: private manifest validation and replay of four existing audio fixtures.
Each replay produced **294 embeddings and 234 classifier windows**, including
**11 positive windows**; all threshold decisions matched the reference. Maximum
absolute differences were **0.00007439** for embedding values and **0.000006885**
for classifier scores. No new room recording was made for these tests.

Each Show also passed **three software mute/unmute cycles and a normal app
restart**, restoring the same single classifier at **0.50** with no secondary
Jarvis selection. Actual microphone closure and recovery were checked; HA
identity, selected assistant, display/media settings and permissions were retained.
The [dated rollout record](Wake-model-rollout.md#october-16-device-observations)
records the individual timing observations. The final candidate corrects quiet-loop
coroutine starvation that had prevented a mute change from stopping capture.
HA switch state alone was not used as proof that microphone capture had stopped.

These checks do not establish physical wake recognition, audible replies, Stop
during playback, fresh three-metre performance, power-loss recovery or a
multi-day soak. The selected Assist pipeline is preserved; local wake detection
does not move its cloud recognition step onto the Show.

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

## Automated browser coverage

The [clock and authentication browser matrix](../browser-compatibility.md) checks
the real display files on desktop browser engines and operating systems. Its
release path uses the exact staged source archive. This does not substitute for
Android WebView or physical-device acceptance.

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

- Confirm installed revision, assistant selection, the intended active model or models, unsilenced capture and no onboarding prompt. For the single-phrase ONNX trial, confirm only the intended classifier is active and the secondary selection is absent.
- Speak each wake phrase separately, wait for idle between trials, and record activation plus audible-answer outcome. Include negative phrases and background playback. Do not infer a rate from one successful utterance.
- Show each configured camera, verify actual moving video, then check natural expiry and Home cleanup. Confirm voice capture afterward.
- Play one permitted media item; confirm audible output and Stop. For a call, check both directions with a second participant and verify microphone restoration when ending.
- Restart the app and repeat the relevant checks. Schedule Android reboot, power-loss and network-interruption tests as separate attended recovery cases.

A useful private receipt records: timestamp/time zone; device identity; source/artifact hash; configuration revision; exact action; observable result; recovery state; and remaining tests. The public summary omits IPs, serials, tokens and household content while retaining enough version information to understand its scope.
