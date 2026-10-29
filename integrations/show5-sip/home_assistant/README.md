# Home Assistant controls for Show SIP

This optional custom integration controls the separately provisioned Show SIP
Android app through the existing authenticated **Android Debug Bridge** integration.
It adds SIP registration/call sensors, one **Call** button per allowed contact,
and **Answer**, **Decline** and **Hang up** buttons. It does not create Asterisk
accounts, install applications, open an additional network listener or retain
SIP passwords. All interface labels are English.

This source includes offline control and boundary tests. Those tests do not
establish live Home Assistant compatibility, device registration, audible media
or end-to-end hangup recovery. Record deployment and attended results separately.

## Configure

1. Provision the Android app and its compatible VACA lease service first. Record
   the exact Android serial, `cronos` identity and authenticated nonroot ADB
   connection. Use a distinct account and endpoint ID for each Show.
2. Copy `custom_components/show5_sip` into Home Assistant's private
   `config/custom_components/` directory.
3. As an administrator, open Settings → Devices & services → Add integration →
   **Show SIP**. Paste the reviewed endpoint JSON shown below. Use the exact
   `endpoint_id` already provisioned in that app. Set `adb_entity` to the existing
   AndroidTV entity for that same Show. The serial must be complete, not a suffix.
   Each contact contains only an app-provisioned `id` and English `label`.
   **Do not add SIP URIs, numbers, passwords or HA tokens to this mapping.**
4. If the new component is not discoverable after copying it, use the normal HA
   configuration check and a scheduled restart, then retry setup. Once discovered,
   adding endpoints through the standard admin setup flow needs no restart. An
   identical setup retry leaves the existing entry unchanged; conflicting endpoint
   IDs, serials and ADB entities are rejected. The setup API uses normal HA admin
   authentication and does not provide a separate credential or access bypass.
5. Inspect the actual generated entity IDs before adapting
   [dashboard.example.yaml](dashboard.example.yaml). Use an administrator-only
   dashboard. Services and buttons independently require an active administrator
   with control permission for the configured ADB entity; hiding buttons alone
   is not an authorization boundary.

Example reviewed setup JSON:

```json
{
  "endpoint_id": "show_one",
  "name": "Show one",
  "adb_entity": "media_player.show_one_adb",
  "serial": "REPLACE_WITH_FULL_SERIAL",
  "contacts": [{"id": "kitchen", "label": "Kitchen"}]
}
```

YAML import remains supported through
[configuration.example.yaml](configuration.example.yaml). Run the normal HA
configuration check before restarting to import YAML changes. Each endpoint
should be managed through one setup method.

Editing an existing YAML entry updates its imported config entry on the next
startup. Removing YAML alone does not remove an existing imported entry: remove
that entry from Settings → Devices & services after removing its YAML definition.
Unloading this integration does not hang up an existing call or change VACA mute.

## Call controls

For manual actions in Developer Tools → Actions:

```yaml
action: show5_sip.dial
data:
  endpoint_id: show_one
  contact_id: kitchen
```

The other services require the current `call_id` attribute from the SIP call
sensor, preventing a stale action from answering or ending a replacement call:

```yaml
action: show5_sip.hangup
data:
  endpoint_id: show_one
  expected_call_id: REPLACE_WITH_CURRENT_CALL_ID
```

`show5_sip.answer` and `show5_sip.decline` use the same fields and require a ringing
call. The entity buttons supply their observed call ID; a changed call is rejected
after a fresh device read. Call controls intentionally reject anonymous/system
contexts. They are for authenticated operator use, not unattended auto-answer or
scheduled dial-out. The Android app handles incoming calls locally when HA is down.

Each call action sends one request with a unique ID. It then requires the app's
matching `last_command_id` and `last_command_result`, rather than treating
`Broadcast completed: result=0` as successful telephony. A missing response never
causes an automatic second dial. Inspect current status before a manual retry.
Optional service response data reports acceptance and the observed state.

Dial and Answer first bring the fixed Show phone Activity to the foreground,
without any contact or answer extras, then send the guarded call command. This
keeps the operator's action visible and avoids relying only on background
foreground-service microphone eligibility on Android 11. Failed activity launch
prevents the call command. Decline and Hang up do not bring the UI forward.
Actual unsilenced microphone capture still requires device acceptance.

- `registered` means account registration succeeded, not that audio was tested.
- `preparing` means local microphone ownership is being acquired.
- `active` means the SIP app reports running media, not proven physical sound.
- `ending` or `lease_held: true` means restoration is still pending.
- Normal completion requires `state: idle`, no `call_id`, and `lease_held: false`.
  A failed call can finish in `error` with no call ID and no lease. If registration
  remains valid, Call buttons allow an explicit manual retry; nothing redials
  automatically. An error with an outstanding lease continues to block dialing.

Status refresh is every ten seconds while idle and five seconds during a call or
pending lease. A missing or mismatched response makes entities unavailable; it
does not synthesize an idle state. Outgoing commands always do a fresh status read.
Incoming calls appear immediately in the Android UI; HA's idle poll can take up to
ten seconds plus ADB response time to display ringing. This is polling, not an
instant ringing notification.

## Ownership and transport boundaries

The HA adapter never writes a VACA mute switch, starts a camera, kills an app or
uses `force-stop`. The Android SIP app and its same-signer VACA service own the
microphone transaction and restore it after local or remote hangup. An HA timeout
does not grant HA permission to release that lease or infer the call ended.

Every ADB query/control checks the configured full serial, product `cronos` and
shell UID `2000`. A fresh unpredictable begin/end marker rejects an old AndroidTV
`adb_response`. The Android provider/receiver require `android.permission.DUMP`,
so ordinary Android apps cannot invoke them. Network ADB must remain authenticated
and restricted to the existing trusted management path.

The only broadcast action is `org.hahomelab.show5sip.CONTROL`, scoped to package
`org.hahomelab.show5sip`. The adapter offers `dial`, `answer`, `decline`, `hangup`;
it does not expose arbitrary commands, SIP addresses, package names or app
provisioning. The provider `content://org.hahomelab.show5sip/status` returns one
`json` column. Schema 1 is an explicit allowlist, with string enums and nullable
IDs/error codes. Unexpected fields, credentials, duplicate JSON fields and
unmatched markers are rejected. No raw ADB output is logged by this integration.

Keep the old Jitsi controls separate from this endpoint. Their existing force-stop
and mute logic is not a substitute for the SIP lease service. Do not launch Jitsi
or another microphone owner during a SIP call; add shared ownership support to
those launchers before permitting automatic cross-application takeover.

## Offline checks

From this repository's root:

```bash
python3 -m unittest discover -s integrations/show5-sip/home_assistant/tests -v
```

The tests use no HA server, ADB endpoint or SIP account. They cover malformed and
stale responses, exact endpoint binding, shell/URI rejection, operator permission
checks, replaced-call protection, endpoint contention, explicit app rejection
and missing acknowledgement without duplicate dial-out. Live acceptance must
separately cover registration, attended calls in both directions, intelligible
audio, cancellation, remote hangup, pending cleanup, HA disconnection and restored
VACA capture. Never retain household recordings in the repository.
