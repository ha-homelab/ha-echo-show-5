# Post-review announcement candidate — 2026-10-29

This candidate supersedes the [original quiet rollout](build-validation-2026-10-29.md).
The public service contract remains `cisco-announcement-v1`; ordinary calls retain
one SIP account per physical Show.

## Built and checked

VACA `0.13.4+myshka.13-announce.2`, version code **7013**:

- APK: `vaca-0.13.4-myshka.13-announce.2.apk`, **74,767,626 bytes**.
- SHA-256: `17e06d71e0ab5540c476a1c0ccc2f8977e60b089bba11af4af35121be6affa2b`.
- Composed source tree: `9e343e8d6b6be5807ff2532145db48625e07049e`.
- **201 JVM tests passed**, with no failures, errors or skips.
- The signer matches the previously installed application.

SIP **0.1.1 / 2** is unchanged from the original build, including its **19** passing
JVM tests and recorded APK checksum. The HA overlay passes **54** quiet tests.
Builds do not contact devices, transmit microphone data, or initiate playback.

## Review fixes

- SIP preemption waits for the ownership mutex and rereads its owner, including
  a claim that was still being recorded when the call arrived.
- A resumed, window-focused VACA activity supplies explicit foreground evidence
  during long kiosk sessions. Failed or oversized usage-event scans advance
  their cursor and fail closed; a foreground service alone is insufficient.
- Terminal journal entries are retained for at least 24 hours after expiry.
  Atomic pruning keeps a durable expiry fence; recent and active records remain.
  Full capacity makes new-work readiness false. Reusing an old ID with a new
  deadline after retention is prohibited by the caller contract.
- Election audio is tied to its actual pipeline. Aborted opens, later follow-ups
  and unrelated pipelines cannot consume stale microphone history.
- Wake-listener pauses retain discovery and authentication state while rejecting
  new elections. Changed configuration replaces the transport explicitly.
- Native HTTPS HA listeners use normal certificate and hostname verification
  with a configured HTTPS identity; no insecure TLS fallback is enabled.

## Quiet deployment and remaining acceptance

Both Shows have VACA **7013** installed. Installed APK checksums match the
artifact above; Usage Access remains enabled, device time matches the control
host, SIP registration is idle, and private configuration digests are unchanged.
Track final HA activation and live capability receipts in
[PR #119](https://github.com/ha-homelab/ha-echo-show-5/pull/119).

The HA HTTPS compatibility update is installed on disk with its prior version
backed up. A coordinated HA process restart activates the new module. The
HTTP route preserves the already verified service contract; the HTTPS addition
does not introduce a new audio path or weaken certificate validation.

No announcement, synthesis, music, test ringing, or call was initiated for these
checks. Audible quality, real call/media contention, room wake-word performance
and long-duration acceptance remain pending. These are candidate results, not
stable acoustic acceptance.

Journal schema 2 reads schema 1 and writes the new format on the next update.
Do not clear the journal to downgrade: old announcement APKs do not understand
schema 2. Use a compatible forward recovery build and preserve request history.
