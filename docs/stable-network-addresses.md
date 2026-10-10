# Stable network addresses for multiple Shows

Keep each converted Show on DHCP and reserve its address in the LAN router.
VACA and Android Debug Bridge store the device address separately in Home
Assistant. A working HA page on the Show does not prove that either inbound
connection still uses the correct address.

## Identify before changing

1. Read the complete serial, product (`cronos`), Wi-Fi MAC and current IPv4
   address through an already authorized USB or network ADB connection.
2. Match the MAC against the router's active leases and static reservations.
   Do not infer identity from the Android hostname: converted Shows can share it.
3. Inspect the LAN netmask, dynamic pool and existing reservations before
   choosing a free address in the site's media-device range. An address grouping
   within a larger LAN is not a separate routed subnet.
4. Preserve an existing correct reservation. Check both configured reservations
   and active leases for collisions before adding another one.

## Reserve and renew

For OpenWrt, back up `/etc/config/dhcp`, check `uci changes dhcp`, and add only
the intended `host` section. Include the verified MAC, chosen IP and a unique
DNS name. Generate and syntax-check the candidate dnsmasq configuration before
activating it; use the validation procedure supported by the installed OpenWrt
version. Do not reload an unvalidated candidate. After validation, commit the
intended DHCP changes, reload dnsmasq, and verify service health and the resulting
leases. Check that unrelated reservations remain unchanged. If validation or
activation fails, restore only this operation's changes from the backup and
verify the previous configuration before continuing.

A reservation does not immediately replace an active lease. With USB recovery
available, reconnect Wi-Fi on the selected Show, then verify the new address
both on Android and in the router's lease table. Check ADB identity again at
the new address and test VACA's TCP 10800 listener from the HA host.

## Rebind Home Assistant

Update both the existing VACA and Android Debug Bridge entries. Retain their
entry IDs, entity IDs, authentication and unrelated options. Preserve the
VACA `ha_url` and per-device `ha_dashboard` separately.

Use an integration's supported reconfiguration flow when available. If the
installed integrations do not expose host reconfiguration, an administrator
can migrate the stored host fields during a controlled HA shutdown: stop HA,
verify it is fully stopped, back up `core.config_entries`, change only the
identified entries' `data.host` values, validate the complete JSON, write it
atomically with its original permissions, and restart HA. Never edit the
storage file while HA is running. Keep a restart/recovery path independent of
HA before stopping it.

Refresh the selected VACA page after its integration reconnects. Verify the
actual page on the device, its authenticated connection and camera playback.
Also verify the assistant, wake word and threshold after the reload; server
configuration alone does not establish physical wake-word recognition.

## Multiple display profiles

Each Show needs its own display configuration and remote target. Reuse the
tested clock/camera assets, but never copy another device's remote target
unchanged. Use a new entry-point filename and asset version when deploying,
because the HA static-file cache can retain old assets for a long time.

Keep serials, MACs, addresses, configuration backups, screenshots and deployment
receipts in ignored private storage. Rollback consists of restoring the affected
HA host fields while HA is stopped, and restoring/removing only the reservation
changed by this operation, followed by lease renewal and verification.

## Recorded recovery in October 2026

The source notes record this recovery in October 2026 without an exact day.
These are historical observations, not a check of current device state.

USB inspection showed the first Show on a new dynamic address while both HA
integrations retained its previous address. The second Show already had a
correct static reservation. The first received a new reservation in the same
media-device range; both physical identities and the renewed lease were checked.
The actual inventory and before/after receipts are private.

After the migration, both Shows loaded the same English clock design with
separate remote targets and authenticated motion subscriptions. On the first
Show, bounded playback checks confirmed growing decoded-frame counts for
Front (854×480) and Porch (1920×1080), followed by a clean return to the clock.
Both retained FCC Russian Backup, Privet Myshka V1 and the configured 0.35
threshold; Android reported one active, unsilenced VACA recorder per device.
These checks do not substitute for an attended spoken wake-word test.
