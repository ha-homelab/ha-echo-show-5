# Guarded VACA announcement services

This additive overlay gives VACA a correlated, asynchronous announcement API. It is intended for previously synthesized speech, independently of the conversational Assist pipeline. It never starts an Assist conversation, performs STT, enables a microphone, places a SIP call, or synthesizes a message.

The native Android overlay is required. Stock `assist_satellite.announce` is **not** a fallback. A missing or unsupported native protocol fails closed.

## Public contract

The `vaca` domain exposes four services. Every service requires a response (`SupportsResponse.ONLY`), an authenticated active HA user, and control permission for the selected VACA entity. REST callers use `/api/services/vaca/<service>?return_response` and read `service_response` from the HA envelope.

- `announcement_submit`: `entity_id`, `request_id`, `media_id`, `expires_at`, optional `preannounce: false`, optional `busy_policy: skip`.
- `announcement_status`: `entity_id`, `request_id`. Read-only with respect to device operation; never starts or retries playback.
- `announcement_stop`: `entity_id`, `request_id`. Only the original authenticated user can cancel that exact request. No generic player-stop operation is used.
- `announcement_capabilities`: `entity_id`. A read-only native protocol query, without reserving an audio session.

Request IDs have the form `announce-<32 lowercase hex characters>-<three-digit endpoint>`. The endpoint suffix is an identifier, not a request to create another SIP account. Each physical Show retains one ordinary SIP extension.

`expires_at` is an absolute Unix UTC timestamp, at most 300 seconds ahead when first submitted. Audio is limited to 120 seconds. The native wire timestamp is rounded down to whole seconds. A duplicate with the same owner, request ID, media and deadline returns its recorded receipt without replay. A conflicting reuse is rejected. A native claim marked `deduplicated: true` is polled without sending audio again; a claim without an explicit deduplication flag is treated as unknown. Receipts are retained for at least 24 hours after expiry, with a bounded store of 1,024 entries.

Native request/reply operations have a five-second total budget, including waiting for the per-device RPC lock. Cancellation or timeout removes only that operation's pending reply and releases its acquired lock.

Submit returns after durable queue insertion. It does not wait for download, decoding, native startup, or playback. `accepted` means queued, never “heard.” Results contain `request_id`, `status`, and a bounded machine-readable `reason`:

- `accepted`: durably queued or accepted by the native guard.
- `playing`: native playback has started.
- `completed`: the matching native session reports verified buffer drain.
- `skipped`: unavailable capability, busy endpoint, or insufficient time; no playback started.
- `failed`: a confirmed preparation/native failure.
- `stopped`: the owned operation was cancelled, either before dispatch or confirmed by the native session.
- `unknown`: completion or cancellation cannot be confirmed. Do not automatically resubmit with a fresh ID.

After an HA restart, interrupted records become `unknown`; playback is never resumed automatically. A native status query may resolve an uncertain receipt. Terminal receipts are immutable. A connection generation prevents late disconnect handling from cancelling a replacement connection's job.

Capability output includes `protocol: cisco-announcement-v1`, and Boolean `atomic_idle_guard`, `dedup`, `owned_cancel`, `honest_completion`, `deadline_enforced`. All must be true before use. Scope is explicitly `guard_scope: coordinated_vaca_sip`, `external_busy_policy: observe_and_abort`, `global_android_exclusion: false`. These flags do not assert exclusive control over arbitrary Android applications.

## Prepared Baya audio

Select the speech engine and voice in the producer, synthesize **once**, and reuse its prepared HA TTS URL for all targets. The HA API accepts the engine `tts.local_russian_speech` and voice `silero-ru-baya` when installed. `silero-ru-default` follows the speech service's current voice setting and is not a permanent alias for Baya.

This overlay accepts only `/api/tts_proxy/<filename>` or the equivalent URL on this HA instance's configured internal/external origin. It deliberately rejects arbitrary URLs, inline text, `media-source://` identifiers that could trigger synthesis, user-info URLs, query strings, redirects, filesystem paths and other protocols. The file is fetched through HA's loopback listener, capped at 8 MiB, then decoded through ffmpeg stdin with a `pipe` protocol allowlist. Plain HTTP listeners use HTTP loopback. Native-TLS listeners use HTTPS loopback with HA's certificate-verifying client session and SNI/hostname verification against the configured HTTPS internal URL (or HTTPS external URL when no HTTPS internal URL exists). The network destination stays loopback. No certificate or hostname verification is disabled. A missing configured HTTPS identity makes capabilities unsupported; an untrusted or mismatched certificate fails preparation before a native audio claim. Private CAs must already be trusted by HA's client SSL context. The decoded PCM is bounded to 22,050 Hz, mono, signed 16-bit, at most 120 seconds. No URL or credential is passed to ffmpeg.

## Required private guard mapping

Prefer a private `/config/vaca_guarded_announcement_guards.json` file, staged alongside the integration before the same coordinated HA restart. It is loaded once during setup; no live config-entry edit or premature reload is needed. The top level maps VACA satellite entity IDs to complete five-role mappings. Store real entity names in private deployment configuration, not in this repository:

```json
{
  "assist_satellite.example": {
    "room": "sensor.example_room_session",
    "intercom": "sensor.example_room_session",
    "dnd": "switch.example_voice_do_not_disturb",
    "media": "media_player.example_vaca",
    "sip": "sensor.example_sip_call"
  }
}
```

An absent file is allowed and leaves unconfigured satellites unsupported. The file is capped at 64 KiB and 256 satellites; duplicate JSON keys, partial role mappings and invalid entity IDs reject the entire file before services register. Validate the staged file before the restart. Each VACA config entry may instead define `options.guarded_announcement_guards`; an explicitly present option takes precedence over the file. An invalid explicit option fails closed rather than falling back.

Room, intercom and SIP states must be `idle`; DND must be `off`; media may be `idle`, `paused` or `off`. The room sensor must also report `owner: idle` and `busy: false`; the SIP sensor must report `lease_held: false` and a null `call_id`. Missing, unknown or unavailable guards reject admission. The room sensor may also serve as the intercom guard only when it tracks all managed room sessions.

If `show5_intercom` is loaded, its active lease, cleanup/recovery state and current call are additionally checked. This is intentionally conservative: an active shared intercom backend can block both endpoints. HA checks remain an observation layer; the Android shared guard is the admission authority for coordinated VACA/SIP work. External Android applications are observed and cause an owned announcement to abort, not subjected to a claimed global lock.

## Installation and rollback

Apply only to a **staging copy** of `custom_components/vaca`. The tool verifies exact source hashes and dependencies, checks all destinations before writing, and accepts an already applied identical overlay. Unknown, partially applied, linked or modified files fail closed. The pinned VACA `VAAsyncTcpClient` subclass supplies `can_write_event()`; this overlay does not assume that method exists on the upstream Wyoming base client.

```sh
python3 integrations/vaca-announce/home_assistant/apply.py --source /path/to/staging/vaca --check
python3 integrations/vaca-announce/home_assistant/apply.py --source /path/to/staging/vaca
python3 -m compileall -q /path/to/staging/vaca
```

Back up the installed integration before deploying the staged copy. Loading the changed Python modules requires a **coordinated HA process restart**; an ordinary config-entry reload is not sufficient. This repository does not automatically restart HA. Restore the original integration and coordinate another restart to roll back; retain the receipt store to avoid duplicate delivery.

The standard legacy announcement implementation also gets bounded subprocess cleanup and explicit errors for missing `played` acknowledgements, nonzero decoding exit, and empty audio. Its uncorrelated legacy `played` event remains weaker than this guarded API and must not be treated as the correlated completion contract.

## Quiet verification and acceptance limits

Run offline tests without contacting devices:

```sh
python3 -W error::ResourceWarning -m unittest discover -s integrations/vaca-announce/home_assistant/tests -v
```

Tests use fake HA services, fake transports, and fake decoder subprocesses. They cover no-replay deduplication, owned cancellation, connection generations, missing guards, permission rejection, bounded decoding, timeout cleanup, stale receipts and fail-closed source application.

During a workday only the capabilities and status services may be used for live verification. They must not be replaced by a “short” announcement test. Acoustic output, volume, long playback, real concurrent call/media transitions, and recovery after network loss still require a scheduled audible acceptance session. A compiled or installed beta does not establish those results.
