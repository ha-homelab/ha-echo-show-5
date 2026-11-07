# Echo Show microphone leveling qualification — November 6, 2026

This follow-up addresses missed Myshka activation after the separate
[Assist admission recovery](wake-recovery-2026-10-31.md). The prior fix remains
in the composed build. The new built-in-microphone processing is documented in
[the overlay guide](../integrations/vaca-wake-audio/README.md).

## Reference and scope

The current working Dot reference is TECHO5 `v1.0.49-beta.203_myshka2`.
Read-only inspection confirmed Center mic, analog gain 20 dB, leveling and echo
cancellation enabled, one personal wake model, and threshold 0.50. Noise reduction
was enabled on one Dot and disabled on the other. These are reference settings,
not instructions to copy an analog-gain value into Android's different control.

The Show keeps threshold 0.35, its selected personal Myshka model and existing
pipeline. Only Cronos's built-in microphone uses the new 20 ms frame leveler.
Other microphone routes retain their previous selection. No HA restart, wake
model retraining, new recording or audible test is part of this rollout.

## Reproduced regression

An offline replay used 24 retained positive owner-validation clips and 32
retained negative owner-validation clips, with 1.6 seconds of silence on each
side and the exact streaming ONNX frontend. At threshold 0.35:

- Raw PCM detected 23 of 24 positive clips; 0 of 32 negatives activated.
- Existing Android sample-envelope AGC detected 22 of 24; 0 of 32 negatives activated.
- The proposed frame leveler detected 24 of 24; 0 of 32 negatives activated.

These clips come from the existing model-development dataset. They are not a
new independent acoustic trial. A proposed 532-negative replay could not run
to completion because 500 historical synthetic WAV paths no longer exist;
cached embeddings cannot substitute for waveform testing of a new leveler.
No 532-clip result is claimed.

Numeric live capture inspection on one Show found unsilenced built-in
VOICE_RECOGNITION mono input. Microphone source alternatives and a small bounded
read-stall probe did not establish a source-selection or buffer-overflow defect;
those settings were left intact. No live audio was retained.

## Native build and rollout

The composed APK is `0.13.4+myshka.16-audio.1` / `7016`:

- Composed source tree: `950ce0a06f28d685b81732d7500043e81c0cc549`.
- APK SHA-256: `9be66f85cb26558a76a17973937c2d5525545930258bd363cc8b832ae6a781cc`.
- Existing signing-certificate SHA-256: `2cebae957468fdb54ffaa473548e9b5f7946f84b8645e3947ff73d2af29b9850`.
- All 250 JVM tests passed, with no failures, errors or skips.

A silent instrumentation replay on Show One passed all 56 cases and 2,685
classifier windows per processing path. The real Android implementations
reproduced 24/24 positives for the frame leveler versus 22/24 for the previous
AGC, with 0/32 negative activations for either. Fragmented processing produced
exactly the reference PCM (maximum difference zero); maximum native/reference
classifier-score difference was 0.000002265. The test took 341.951 seconds and
opened no microphone or audio player. Staged recordings and the test package
were removed, and VACA was restored afterwards.

Both Shows received that exact signed APK with application data preserved.
The first used the already authorized administration connection; the second
used HA's existing trusted ADB integration. Version and installed-package SHA-256
were read back independently on each device. Their custom model/frontend
files were unchanged. The HA upload service rejects unapproved server paths;
the successful upload used an already allowed private configuration path and
removed it afterwards, without changing HA's allowlist or ADB trust.

The source-package checks passed all eight distribution tests, including an
extracted-source validation run. The build-provenance suite passed 35 tests;
the documentation validator checked 103 Markdown/SVG files. A distribution
guard also requires this new overlay's native sources to be packaged.

## Operational checks and recovery

Verify the device's immutable serial, idle SIP/Assist/announcement state and lack
of active media playback before replacing the app. Install the signed APK with
package replacement, preserving app data and operator settings. Restart VACA,
then verify version, selected model, threshold, numeric capture progress and HA
connectivity. The built-in path reports `VACA (20 ms frames)` as its AGC source.

An unauthorized ADB key on one computer need not imply loss of all management
access. An already trusted HA Android Debug Bridge integration can upload and
install the same verified APK. It does not require adding keys or disabling
Android authorization. Keep the package private and remove temporary copies.

Retain the prior signed `7015` APK and the new build receipt for recovery. An
ordinary update does not clear application data. Do not clear announcement
journals or reset HA pairing as a troubleshooting shortcut. Live acoustic
recognition remains a separate acceptance claim from silent fixture replay
and advancing capture counters.
