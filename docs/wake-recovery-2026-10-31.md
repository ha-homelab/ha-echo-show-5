# Echo Show wake recovery — October 31, 2026

## Observed failure

Both Show endpoints had the exact OpenWakeWord Myshka primary selected, with HA
threshold `5.0` (model probability `0.50`). Their classifier and both frontend
files matched the retained expected SHA-256 values. Android reported active,
unsilenced mono 16 kHz microphone capture. These checks establish configuration
and capture state, not recognition accuracy in the room.

Show two remained in HA Assist `processing` for several minutes while its media
and SIP sessions were idle. A quiet restart of VACA returned it to `idle`.
Review of the installed `7014` code found that enabled nearest-device arbitration
rejected every wake while a pipeline remained active. The local handler's stale
request recovery was downstream of that rejection and could never run.

## Change

The `7015` composition shares stale-request admission between arbitration and the
local handler. A fresh detection may replace an unchanged pre-response stage
after 16 seconds, or a TTS startup stage after 31 seconds. The policy uses
monotonic elapsed time, refuses unknown stages and does not time out actual
voice playback. Mute, SIP ownership and announcement guards remain in place.
This fixes an admission deadlock; it does not retry the previous spoken command.

Pipeline replacement also keeps an explicit current instance. Late state,
completion, output and continuation callbacks from the replaced instance cannot
clear or stop the replacement. The identity is installed before its coroutine
starts. A stopped pipeline may still release the voice player and streaming
state when there is no replacement.

Both endpoints were also changed to HA threshold `3.5` (model probability
`0.35`), with a successful readback after the restart. No model, microphone gain,
noise suppression setting or assistant backend was changed. The lower threshold
is a sensitivity trial and may admit more false detections.

## Validation and deployment

The signed Android build completed with **243 JVM tests passing** and no
failures, errors or skips. The 35 Python builder tests passed. A separate fresh
checkout passed all overlay source preconditions and produced matching pipeline
sources. Documentation links and the explicit 343-file source inventory passed.

- Application: `com.msp1974.vacompanion`.
- Version: `0.13.4+myshka.15-wake.1`, code `7015`.
- APK SHA-256: `ee0b73b95ff385de6f2dcce012c4b0e86b0ee4ac6e5e6c75b7ab3c9a297a1c54`.
- APK size: 74,784,006 bytes.
- Composed source tree: `480dfe5633d93de01cb7442061e3006abcf24bc0`.
- Signing certificate SHA-256: `2cebae957468fdb54ffaa473548e9b5f7946f84b8645e3947ff73d2af29b9850`.

Both endpoints were updated in place with the same signed APK, after checking
that Assist, SIP and media sessions were idle:

- Show two: installation verified at **17:02:48 UTC**.
- Show one: installation verified at **17:03:38 UTC**.
- Both installed APK hashes and version codes matched the build receipt.
- App preferences, nearest-device configuration and all wake-model files retained
  their exact before/after hashes. SIP configuration hashes also stayed unchanged.
- Native SIP returned to registered/idle; subsequent HA checks found both Assist,
  room and SIP sessions idle. No HA restart was required.
- Both startup logs reported the exact Myshka frontend loaded at threshold `0.35`,
  local Stop enabled and wake recording disabled. Android reported active,
  unsilenced mono 16 kHz capture on both endpoints after initialization.
- Usage access remained allowed, DND was off and measured device clock offsets
  were zero seconds.

The source inputs were compared with the build receipt again after installation.
The quiet checks above do not establish how often a spoken wake is recognized.

Five new JVM cases cover admission at both timeout boundaries, idle state,
negative elapsed time, playback/unknown-stage rejection and the enabled
arbitration path. The composed builder verifies source preconditions, the exact
source tree, all tests, package version, ABI and the existing signing identity.

Operator configuration, downloaded models, APKs, signing material and raw
diagnostic logs remain in ignored private storage. No microphone recording,
speech playback, music, ringing or announcement submission is part of this
verification.

## Background CPU finding

A bounded live counter capture revealed an additional problem on Show two:
processing 1,120,000 samples (70 seconds of 16 kHz audio) took approximately
97 seconds from engine startup. Cumulative inference work was 93.552 seconds;
Show one processed the same sample count in approximately 71 seconds, with
57.016 seconds of inference work. These are wall-time throughput observations,
not measured end-to-end wake latency; a slow reader may also lose buffered audio.

The paused SendspinDroid 2.0.0 process consumed approximately **245% CPU** in a
four-core `top` sample. A thread sample showed many active coroutine dispatcher
threads. All four CPU cores still reported 1.3 GHz. The client was stopped after
checking that no media session was playing. A subsequent sample showed about
67% total CPU idle instead of about 4.5% idle. No thermal safeguards or CPU limits
were disabled.

The package and saved pairing remain installed. Show two's Sendspin route is
currently **on demand**; use its existing endpoint action when needed and the
owned Stop/Home route afterwards. The NUC AirPlay configuration remains in place,
but audio cannot arrive through it while the Android Sendspin listener is stopped.
The two consecutive post-mitigation counters were 3,040,000 samples at
17:06:49.674 UTC and 4,000,000 at 17:07:49.804 UTC: **60 seconds of audio in
60.130 seconds of wall time**. Cumulative inference time increased by 46.602
seconds over that interval. This confirms restored real-time throughput during
that bounded interval; it is not a recognition-rate measurement.

This mitigation does not repair the third-party client's excessive idle CPU use. Recheck idle
CPU and concurrent wake throughput before enabling permanent background service.

## Attended acceptance

From a normal speaking position, try the configured Myshka phrase several times
with a pause between turns. Distinguish an absent wake from a wake followed by a
slow backend response. For overlapping devices, compare the winner and the
devices that yielded; one audible response alone does not prove correct
arbitration. Check false activations from normal room sounds before lowering the
threshold further. The operator subsequently reported that wake phrases were **still being missed**.
The specific endpoint, distance and correlated confidence scores were not yet
available. Acoustic acceptance therefore remains **failed/pending diagnosis**;
the software and throughput corrections must not be described as a complete
recognition fix.


For an attended score check, temporarily enable the endpoint's **On screen
diagnostics** switch in HA, wait for the overlay, and compare **Detection** with
`3.5`. The displayed detection value is probability multiplied by ten; it holds
a recent peak briefly. **Mic Level** is a display gauge, not a probability or
calibrated room sound-pressure reading. A zero during a quiet interval does
not alone prove a muted microphone. Leave **Record Audio** disabled and restore
diagnostics to their previous state after the check. Record the endpoint,
distance, number of attempts and observed peaks before changing another setting.
