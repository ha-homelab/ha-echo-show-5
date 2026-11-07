# Built-in microphone leveling for Echo Show 5

The `7016` overlay changes only the built-in microphone path on Android devices
whose device codename is `cronos`. It retains the calibrated Myshka ONNX model,
its exact frontend, the operator's wake threshold, and the existing SIP,
nearest-device and announcement admission guards. USB/Bluetooth microphones and
other Android devices retain the existing enhancement selection.

## Why this changes recognition

The working household Echo Dots now use TECHO5, not the older EchoMuse build.
Their microphone path applies software leveling before the wake frontend. The
old Android path instead follows a sample envelope and gates gain relative to a
noise estimate. On the retained owner validation clips, that path misses two
phrases that this frame leveler detects at the same threshold of 0.35.

`FrameMicrophoneLeveler` is an independent PCM16 implementation using TECHO5's
operating parameters: 20 ms frames, initial +20 dB gain, a -23 dBFS RMS target,
+27 dB maximum adaptive gain, and a -3 dBFS peak ceiling. Gain follows speech
with 500 ms downward and 5 s upward time constants; quiet intervals preserve
it. The noise floor falls over 200 ms and rises over 60 s. Gain adaptation
requires 12 dB above that floor. This condition does not drop or zero audio.
The fixed floor minimum is 16 raw PCM units, matching the reference Dot's
20 dB analog-gain operating point; the Android ADC is different, so this is
an explicit parameter choice rather than a claim of hardware equivalence.

The existing microphone-gain control shifts the target/start/maximum gain in
its bounded -10 to +10 dB range. It is not the Dot's analog gain control.
Arbitrary read sizes are assembled into 320-sample frames without duplication
or loss; the unfinished tail adds at most 19.94 ms of buffering. Reset clears
that tail. A peak ceiling takes effect immediately, including for -32768.
Hardware AGC is not attached to this path, avoiding double automatic gain.

## Build and verify

Use the [composed builder](../vaca-announce/README.md#build-without-devices).
`apply.py` requires exact source hashes after the `7015` overlay composition,
checks the patch before writing, and refuses existing or symlinked destinations.
The builder binds all overlay sources and tests into its source-tree receipt and
requires the frame-leveler unit suite. Preserve the existing signing identity.

The optional `FrameMicrophoneReplayTest` instrumentation test reads explicitly
staged files under the app-private `files/leveler-check/` directory. It opens no
microphone and plays no audio. Its manifest specifies model ID, threshold and
cases with numeric filenames (`.pcm`, `.leveled`), expected maximum classifier
score and positive/negative label. Input is mono 16 kHz signed little-endian
PCM16; expected output comes from the independent reference calculation. Each
case must contain a whole number of 320-sample frames. The test checks fragmented
read equivalence within one PCM unit, native ONNX score agreement within 0.002,
and the expected wake decision. Existing custom model assets are read without
modification. Remove the staged private clips and test application afterwards.
Never commit recordings, trained personal models, credentials or signing keys.

## Evidence and limits

See [November 6 qualification](../../docs/wake-audio-2026-11-06.md) for the exact
build, device rollout and validation limits. Saved clips exercise processing,
not the live microphone's acoustic response in a bathroom. This change does
not establish new room-distance, playback-overlap or camera-overlap acceptance.
A connected HA entity alone is not proof that AudioRecord is capturing: verify
its unsilenced source and advancing numeric sample counters separately.

The inspected Dot reference was TECHO5 `v1.0.49-beta.203_myshka2`, daemon source
`52f39926578b6b561e5556fec43f25c231f0eb5a`, specifically
`echod/internal/hardware/mic/level.go`. Classifier conversion parity does not
establish equivalence of the complete capture/frontend pipelines. No Dot
configuration is changed by this overlay.
