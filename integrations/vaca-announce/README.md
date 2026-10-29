# Guarded announcements for VACA

This additive candidate layers over the pinned dual-wake, SIP and nearest-device
sources. The checked baseline is `0.13.4+myshka.13-announce.2` / `7013`.
The companion SIP application is `0.1.1` / `2`. Each Show retains one SIP account.

See the [operator guide](../../docs/guarded-announcements.md) and the
[HA service contract and staging procedure](home_assistant/README.md).

[October 29 post-review validation](build-validation-2026-10-29-r2.md) records the exact
baseline APK hashes, passed tests, quiet rollout evidence and remaining acoustic acceptance.
The optional `duck_music` extension is a follow-on candidate; that baseline
record does not establish its build, deployment or audible behavior.

## Build without devices

Use the existing private signing identity that matches both installed apps.
Do not publish the signing directory, operator configuration or downloaded SDKs.

```sh
python3 integrations/vaca-announce/build.py \
  --work-dir /private/build/vaca \
  --signing-dir /private/signing \
  --expected-signer-sha256 YOUR_EXISTING_CERTIFICATE_SHA256
python3 integrations/show5-sip/build.py \
  --work-dir /private/build/sip \
  --signing-dir /private/signing \
  --expected-signer-sha256 YOUR_EXISTING_CERTIFICATE_SHA256 \
  --gradle /private/build/vaca/source/gradlew
```

Set `JAVA_HOME` to JDK 21 and `ANDROID_HOME` to the Android SDK first. The build
verifies the pinned source layers, tests, signer, APK package and independent
component versions. Neither builder connects to a device. An optional
`--source-cache` on the VACA builder reuses local Git objects while still requiring
the pinned upstream commit.

## Native guard prerequisites

Install both compatible applications and grant VACA Android Usage Access through
supported settings. Missing usage access, incompatible SIP metadata, an unhealthy
receipt journal, or uncertain external activity prevents guarded admission.
Do not modify volume or start playback to test capability registration.

The native receipt ledger retains at most 2,048 records. It retains terminal
receipts for at least 24 hours after their expiry and never prunes active
records. A full journal makes new-work capabilities unavailable until space can
be reclaimed. Cleanup commits the retained records and an expiry fence in one
atomic write; a clock rollback cannot make an original retired expiry valid.
Recent request IDs still reject altered content or deadlines. After retention,
status may be `unknown`; callers must never reuse an old ID with a new deadline.
Do not delete the journal as an automatic retry mechanism.

Journal schema 2 reads schema 1 and preserves its records. It writes the new
format on the next journal update. Older announcement APKs do not understand
schema 2 and will fail closed for announcements; retain the journal and use a
forward-compatible recovery build rather than downgrading and clearing data.
The HA receipt store has its own bounded retention described in its guide.

## Call priority and limits

An incoming SIP call preempts the matching active announcement before receiving
audio ownership. A late announcement-stop command cannot stop that call.
SIP now acquires its full audio lease before showing an incoming-call notification.
Consequently, active Assist or music that prevents a lease can cause rejection
before ringing. This is an explicit candidate behavior change.

Coordinated VACA/SIP operations share an admission boundary. External Android
applications are observed conservatively and cause owned playback to abort;
they do not participate in an Android-wide mutex. Unknown external state fails
closed. Offline tests and a successful build do not establish acoustic acceptance.

## Optional VACA music ducking

`busy_policy: "skip"` remains the default and preserves its stored request
fingerprints. `duck_music` requires explicit endpoint capability support and
permits only music owned by VACA's `MusicPlayerService`. A request ID cannot be
reused to switch between these policies.

The player keeps its current user-volume target and applies a temporary,
announcement-owned gain. Cleanup removes that gain instead of writing an old
volume snapshot. User-volume changes survive, tracks on the same owned player
inherit the gain, and replacement players cannot receive a stale restoration.
No system stream-volume change or generic media-stop is used for ducking.

Admission and continued playback still enforce SIP, Assist, alarms, DND,
foreground and observed-playback guards. Unknown or additional audio activity
fails closed. The Android focus system remains outside VACA's ownership;
`global_android_exclusion` stays false. See the operator guide for the scope and
the separate attended tests required before promoting music ducking.
