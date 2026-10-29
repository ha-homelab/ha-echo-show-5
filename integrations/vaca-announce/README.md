# Guarded announcements for VACA

This additive candidate layers over the pinned dual-wake, SIP and nearest-device
sources. VACA identifies the build as `0.13.4+myshka.12-announce.1` / `7012`.
The companion SIP application is `0.1.1` / `2`. Each Show retains one SIP account.

See the [operator guide](../../docs/guarded-announcements.md) and the
[HA service contract and staging procedure](home_assistant/README.md).

[October 29 build validation](build-validation-2026-10-29.md) records the exact
original APK hashes, passed tests, and pending rollout/acoustic acceptance.

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

The native receipt ledger retains at most 2,048 request IDs without eviction.
When full, new requests fail with `ledger_full`; earlier IDs cannot replay.
Do not delete this journal as an automatic retry mechanism. The HA receipt store
has its own bounded retention described in its guide.

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
