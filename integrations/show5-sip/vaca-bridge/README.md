# VACA local audio lease bridge

This additive overlay extends the exact `0.13.4+myshka.9` source with a
same-signer Android Messenger service. It builds as
`0.13.4+myshka.10-sip.1`, version code `7010`. It does not change the wake models,
their thresholds, camera settings, HA address or retained signing identity.

The bridge gives the SIP application exclusive ownership relative to VACA's
microphone capture. It is not an Android-wide lock and cannot prevent an unrelated
camera/call application from opening audio. Existing external Jitsi/intercom
launchers must be kept out of the SIP call window; a check followed by a separate
launch is not an atomic ownership protocol.

## Build

Reconstruct the exact `.9` source using the existing dual-wake builder in a fresh
ignored build directory. Before compiling that directory, apply this overlay:

```sh
python3 integrations/show5-sip/vaca-bridge/apply.py --source /absolute/private/vaca-source
```

The helper checks SHA-256 preconditions for all six files it patches and refuses
existing overlay files. It copies the three bridge Kotlin sources and JUnit tests
into the Android project. Run its normal `:app:testDebugUnitTest` and APK build
with the **retained VACA signer**. The SIP app must use the same signer. Never
replace the existing `.9` release receipt with the new build's identity; record a
separate receipt for version `7010`.

The source overlay has no device or PBX operations. Applying it twice is an error.

## IPC contract

- Component: `com.msp1974.vacompanion/.telephony.AudioLeaseService`.
- Explicit bind action: `com.msp1974.vacompanion.AUDIO_LEASE`.
- Signature permission: `com.msp1974.vacompanion.permission.AUDIO_LEASE`.
- The service additionally checks the sending UID's signer and exact permitted
  package `org.hahomelab.show5sip`; data-provided identity is never trusted.
- Requests: `STATUS=1`, `ACQUIRE=2`, `RENEW=3`, `RELEASE=4`.
- Results: `RESULT=100`, unsolicited `REVOKE=101`, protocol version `1`.
- Every request needs a `replyTo` Messenger and `request_id` (1–80 ASCII
  alphanumeric, dash or underscore). Lease operations need `lease_id` (16–80
  characters in the same alphabet). Persist a fresh random UUID before acquire.
- Acquire/renew accept a **Long** `ttl_ms`, 10,000–60,000, default 30,000. Renew
  every 10 seconds. The client must not use a timed-out acquire as permission to
  dial or answer.
- Results include `request_id`, `lease_id`, `ok`, `state`, `reason` and `protocol`.
  STATUS exposes the stored token only to its owning UID. States are `idle`,
  `acquiring`, `held`, `recovery`, `revoked`.

Only `ok=true,state=held` grants capture. Acquisition sets an inhibitor before
waiting for `.9`'s ordered wake-worker shutdown. It rejects an existing voice
pipeline, voice output, alarm or music service. The grant follows the awaited
`MicrophoneInput.close()` path, not a mute-switch update or fixed sleep.
The inhibitor also prevents settings reloads, manual wake actions, delayed engine
restarts and ordinary mute/unmute callbacks from opening VACA capture.
Playback checks run again inside the dispatched Main-thread actions and at the
music/alarm service playback entries, so an action queued before acquisition
cannot start sound after ownership has changed. Stop/pause remain available.

The bridge records the prior user mute state but **does not overwrite it**. Thus
normal release preserves that state, while an operator's newer mute choice made
during a call is also respected. It leaves the camera unchanged because this
integration is audio-only. It does not queue suppressed voice requests for later
playback or promise to resume interrupted media.

## Ending and recovery

The client must terminate its SIP call and wait for the native **Released** state,
or complete `Core.stop()`, before RELEASE. Remote hangup, local hangup, rejected
calls, failed dialing and abandoned answer attempts all follow that route.
Release is idempotent; a stale token cannot release a newer lease. A failed
teardown or restart retains the journal and blocks another acquisition.

Expiry sends REVOKE and keeps VACA inhibited until the client confirms release or
its Binder dies. **Expiry alone is not evidence that a living process stopped
recording.** The client must close media on REVOKE or VACA service disconnection.
Client process death releases its native resources and triggers local restoration;
neither path needs an HA network connection.

The journal uses AtomicFile under VACA's private files directory. After a VACA
process restart it remains in recovery: the SIP app first stops any old native
media, rebinds and releases its persisted token. A confirmed full-device reboot
invalidates old ownership because both applications and their audio handles were
terminated. An unreadable journal fails closed. Do not delete a recovery journal
while a client may still hold audio.

This does not make HA-dependent voice responses work through an HA outage. It
only makes audio ownership and release independent of HA. If VACA has no running
satellite after release, its normal HA reconnect lifecycle starts capture later.

## Validation scope

The 13 coordinator tests cover awaited teardown, busy rejection, preserved mute,
wrong UID and stale token rejection, persistent recovery, expiry without unsafe
unmute, renewal, idempotent release and teardown/restoration failures. To exercise
the actual patched dispatch methods with a queued Main dispatcher, run:

```sh
python3 integrations/show5-sip/vaca-bridge/verify_queued_dispatch.py \
  --source /absolute/private/vaca-source
```

This requires `kotlinc` and its coroutine runtime (or `--coroutines-jar`). It extracts
the production Kotlin methods and supplies explicit player/Android fakes. Six
checks cover queued music/alarm starts, unchanged operation without a lease, and
stop during a lease. It also checks the delayed service playback entry guards.
It does not install or contact anything. Android
Binder identity, service death, real microphone handoff and received SIP audio
still require separately recorded device acceptance. Keep those results separate
from unit-test and APK-build success.
