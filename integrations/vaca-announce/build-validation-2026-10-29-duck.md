# Owned music ducking candidate — October 29, 2026

This follow-on candidate adds an explicit `duck_music` policy to guarded
announcements. The default remains `skip`. It is separate from the checked
[7013 baseline](build-validation-2026-10-29-r2.md).

## Built artifact

- Application: `com.msp1974.vacompanion`.
- Version: `0.13.4+myshka.14-announce.3`, code `7014`.
- APK SHA-256: `50ec1151e66d015efaa3d75235e4c01634b9668f4de3ae011caff97a0c423a74`.
- APK size: 74,784,010 bytes.
- Composed source tree: `bb4f41b9d7dacafb64984cba3ccec24135730f34`.
- Signing certificate SHA-256: `2cebae957468fdb54ffaa473548e9b5f7946f84b8645e3947ff73d2af29b9850`.

The retained signing identity matches the installed application. Build inputs
were frozen before compilation and compared with the reviewed source afterward.
The source-suite release distributes source and build instructions; APKs and
operator-specific receipts remain private.

## Automated checks

The complete Android JVM suite passed **238 tests**, with no failures, errors or
skips. It includes 37 ducking tests, 46 durable-ledger tests and 18 admission
tests. The HA overlay passed **75 tests**. Both versions of the guarded staging
script passed six isolated filesystem tests each.

Checks cover policy-bound deduplication and historical `skip` hashes, exact
native-player registry binding, current-volume changes, track transitions,
focus loss, cancellation, expiry, playback observation, and failed cleanup.
The final HA correction rejects terminal duck receipts that do not acknowledge
the requested policy. Cleanup tests cover cancellation while restoring gain and
watchdog completion without cancelling its own cleanup.

## Quiet installation

Both endpoints were updated sequentially with the same APK. Before each update,
the installer required an idle SIP session and no observed active playback.

- Show one finished at **21:50:40 UTC**.
- Show two finished at **21:51:50 UTC**.
- Installed APK hashes and version codes matched the build receipt.
- SIP configuration digests were unchanged; registration returned to idle.
- Usage access was allowed, DND was off and measured clock offset was zero.

The final three-file HA overlay was staged with checked before/after hashes and
private rollback copies. One coordinated HA restart was requested at **21:55:05
UTC**, after the separate Dot maintenance window had ended. At **21:58:00 UTC**,
the independent read-only check found HA running, both VACA entries and both SIP
entries loaded, and all four announcement services registered.

Both Shows reported the five required guarantees and `duck_music: true`,
`duck_music_player: vaca`, `duck_music_scope: owned_player`. Status queries for
never-used request IDs returned `unknown`. Assist, room and SIP sessions were
idle, DND was off, and the installed HA file hashes matched the final candidate.

## Scope and acceptance limits

Ducking uses a temporary **20% per-player gain** on an already owned VACA music
player. Removing that gain preserves the current user volume. Track changes on
the same owned service remain supported; a request admitted without music does
not acquire a subsequently started player. System-wide volume is never saved and
restored. Calls, Assist, alarms, timers and unrelated foreground activity retain
their guards.

Android playback observations can reject ambiguity but cannot provide global
exclusion against arbitrary applications. OTTPlay, Bluetooth and other external
players are not advertised as supported ducking sources.

No speech, music, ringing, announcement submission or acoustic test was performed
for this rollout. Readiness checks do not establish audible mix quality or
room-level acceptance. Keep this a candidate until attended playback, volume
changes, track transitions and call preemption have been checked.
