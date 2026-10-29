# Guarded announcement build validation — 2026-10-29

This record identifies the original compiled candidate for protocol
`cisco-announcement-v1`. It records software validation and quiet installation checks, not acoustic
acceptance. Artifact hashes and test totals were compared
with the candidate's retained private build receipts and validation summary.
No device identities, operator paths, credentials or speech recordings are
included here. Later source-layer changes require their own equivalence check;
they do not rewrite these original artifact results.

## Original candidate artifacts

**VACA:** `com.msp1974.vacompanion`, version
`0.13.4+myshka.12-announce.1`, version code **7012**.

- APK: `vaca-0.13.4-myshka.12-announce.1.apk`, **74,751,242 bytes**.
- SHA-256: `ecf70714a486667ce176ade132588c9c983831f322fecfbaeff3609ad194f223`.
- Pinned upstream commit: `65906aebffd2f39772773b44729b22fd022a1f3c`.
- Composed source tree: `ae422c6a74b6e8e74bcae7efc4d8293185d0c116`.
- Announcement patch SHA-256 used by this build: `f9a333cbf601d7b52a5de63b79238c1b17804a1029c46cf918dd471e9528fb67`.
- **163 JVM tests passed**, with zero failures, errors or skips.

**Show SIP:** `org.hahomelab.show5sip`, version **0.1.1**, version code **2**.

- APK: `show5-sip-0.1.1.apk`, **43,564,827 bytes**.
- SHA-256: `8765867ab31f6c1687fde894fea9ec629f3cb476fe32922a9505880b352d5464`.
- **19 JVM tests passed**, with zero failures, errors or skips.

**Home Assistant overlay:** **51 offline tests passed**. These use simulated
services, transport and decoding; they do not send speech to a device.

## Source-layer equivalence follow-up

The shared nearest-device recovery fix was subsequently moved into the lower
nearest overlay so its standalone build also receives the fix. The resulting
composed tree is `99ed955db94d9e38efc14178f902b82e777e25c0`.

Comparison with the original compiled tree above found **identical production
source, resources and build configuration**. The only changed file is
`app/src/test/java/com/msp1974/vacompanion/nearest/NearestAdapterTest.kt`, with
three additional regression tests. The APK hashes and original **163-test**
receipt remain unchanged. The recomposed source passed **166 JVM tests**, with zero failures, errors or
skips, including all three new regressions. This supplemental test run is
separate from the original artifact build.

## Validated scope and remaining limits

The candidate covers correlated requests, idempotent handling, bounded PCM,
owned cancellation, deadline enforcement, software playback-drain accounting,
and coordinated VACA/SIP admission. Incoming SIP takes priority over an owned
announcement. Each physical device still has one SIP account.

The native guard requires compatible SIP metadata and Usage Access. Its scope
is `coordinated_vaca_sip`; external applications use `observe_and_abort`.
`global_android_exclusion` remains **false**. Neither a passing test nor a
capability flag establishes exclusive control of every Android application.

**Acoustic acceptance is pending.** These results do not establish intelligible
sound, suitable volume, real-world audio latency, long-term stability, or actual
concurrent call/media behavior. No audible playback, test call or ringing is
part of this build-validation record.

## Installation and rollback checkpoint

Both endpoints have VACA **7012** and SIP **0.1.1** installed. Installed APK
checksums match the artifacts above, SIP registration is idle, configuration
digests are unchanged, and Usage Access is enabled. At **21:13 UTC**, all four
HA services were registered. Both endpoints returned HTTP 200 capabilities with
all five required flags true and reason `ready`; never-used request IDs returned
`unknown / request_not_found`. Both SIP entries were loaded and idle, room
guards were idle, and DND was off. Follow the
[operator guide](../../docs/guarded-announcements.md) for subsequent verified
rollout state; do not infer completion from the build results.

Install only on an idle endpoint after checking package identity and the
existing signer. Preserve the previous compatible application pair, private
settings, satellite identity, and receipt journals. Relaunch the SIP application
through its exported `MainActivity`; its `SipService` is not exported for direct
shell startup. Loading changed HA Python modules requires a coordinated HA
process restart; a config-entry reload is insufficient. Capabilities and
unknown-request status are suitable for quiet checks; submitting even a short
announcement is not.

For rollback, first disable the guarded dispatcher. Restore the retained HA
integration through a coordinated restart and use the documented compatible
application recovery procedure. Do not delete receipt journals or create fresh
request IDs to replay uncertain work. This record does **not** claim that an
APK downgrade or rollback was exercised.

## Home Assistant startup observation

After the coordinated HA restart, SIP entries initially entered `setup_retry`
because their AndroidTV status transport was not yet ready. This temporarily
made guarded capabilities unavailable. Correlated read-only status probes then
succeeded and automatic setup retries loaded both entries. No additional
restart, reload, code change or relaxed guard was needed.
