# VACA / TECHO5 nearest-device overlay

This opt-in overlay extends the retained VACA private wake frontend and SIP audio
lease bridge with TECHO5-compatible voice arbitration. It targets the pinned
VACA source used by this repository, not arbitrary upstream versions.

Read the [operation and acceptance guide](../../docs/nearest-device-arbitration.md)
before enabling it on a mixed fleet.

## Build

The build needs the same Java 21 / Android SDK environment as the
[existing VACA build](../vaca-dual-wake/README.md) and the retained app signing key.
It reconstructs the pinned upstream source, applies the private-wake patch, then
the SIP bridge, then this overlay. It rejects a mismatched source tree, unexpected
ignored source files, a changed signer or overlay changes during compilation.

```sh
python3 integrations/vaca-nearest/build.py \
  --work-dir /absolute/private/nearest-build \
  --signing-dir /absolute/private/retained-vaca-signing \
  --expected-signer-sha256 YOUR_EXISTING_CERTIFICATE_SHA256
```

An optional `--source-cache /absolute/path/to/local/upstream/checkout` reuses Git
objects; the pinned commit and exact source checks still apply. The output is
`0.13.4+myshka.11-nearest.1` / version code `7011`, with an APK and JSON build
receipt in the private build directory. The builder runs the JVM suite and
verifies the final package, ARMv7 ABI and signing certificate. It never contacts a
device or Home Assistant and never creates a replacement signing identity.

## Updating an existing Show

1. Verify its model, Android version, installed VACA package/version and signer.
2. Retain the previous APK and a small private app configuration snapshot.
3. Check that there is no active SIP call, voice turn or media session.
4. Install as an in-place update with the same signer. Do not uninstall or clear
   app data. Restart the app and verify the assistant, model and SIP settings.
5. Configure the same House word and matching primary model ID as the Dots, plus
   a unique device name. Enable on one Show first and inspect its bounded,
   non-audio diagnostics before enabling the second.
6. Perform real, overlapping wake tests and verify both the winner and losing
   devices. Discovery is not proof of authentication or correct score selection.

Keep the existing Dot model weights and wake threshold unchanged during this
rollout. Do not tune several variables at once. The independent Home Assistant
fallback should use one exact advertised wake phrase across all four devices.

## Settings and diagnostics

The local VACA settings menu adds **Nearest voice device**. It controls
participation, a unique device name, the shared House word, election window
(100–500 ms) and microphone offset (−30 to +30 dB). A blank House word field
preserves the saved word; it is never redisplayed. Save reloads the election
configuration. Disabling participation restores independent voice operation.
Existing nonempty TECHO5 House words remain import-compatible. The UI requires
at least 16 characters for a newly entered word; leaving the field blank keeps
an existing value without rotating credentials on the other devices.

The private configuration file is `files/nearest-device.json` in VACA's app
directory. See [configuration.example.json](configuration.example.json) for
the schema; replace its placeholder privately and do not commit the result.
The protocol endpoint defaults to TCP 18127, advertises `_techo5._tcp`, and
accepts authenticated `/nearest` metadata only. It is not an intercom,
announcements, administration or file-serving endpoint. Some TECHO5 versions
may list these discovered peers in an intercom list even though they do not
provide that feature.

`files/nearest-status.json` contains bounded status metadata such as enabled
state, network readiness and discovered peer names. Discovery is not proof
that a peer authenticated or participated in a particular election. Protocol
and diagnostics do not contain audio, transcriptions or the House word.

The memory history is capped at three seconds. It is discarded on cancellation
or shutdown. Pending election and capture generations prevent an old timer,
network response or settings reload from resurrecting a cancelled voice turn.

## Provenance

TECHO5 protocol/score compatibility targets source
`2ae3c75776eb04f614295ceba7de3cfcf60e531f`. See the
[third-party notices](../../THIRD_PARTY_NOTICES.md) and
[TECHO5 MIT license](../../licenses/TECHO5-MIT.txt).
