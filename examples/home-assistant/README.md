# Echo Show Home Assistant scripts

This package adds a message field and twelve scripts for a converted Echo Show with VACA and Home Assistant Companion. It contains generic entity IDs, no device addresses or credentials.

Before installing, replace these entity IDs with your own:

- `assist_satellite.echo_show`: VACA Assist satellite.
- `button.echo_show_wake`: VACA Wake button.
- `switch.echo_show_mute`: VACA microphone mute.
- `media_player.echo_show_media_player`: VACA audio player.
- `media_player.echo_show_android`: the Android Debug Bridge integration for this specific Show. Verify its identity before enabling screen or navigation commands.

If your configuration already loads packages, place `echo-show-package.yaml` in that package directory. Otherwise merge the `script` section into your existing script configuration and create the `input_text.echo_show_message` helper separately. Do not replace an existing configuration file. Use either the YAML helper or a UI-created helper with this ID, not both.

Validate the configuration before loading it. The package creates scripts; it does not execute them. Changes to the script section can use a script reload. A new YAML helper must be loaded through the normal helper/configuration workflow.

## Voice and media

- `script.echo_show_announce`: required `message` field; speaks through the selected Assist pipeline, without a chime. A nonempty message is required. An active conversation causes this script to skip playback.
- `script.echo_show_listen`: presses VACA Wake when the satellite is idle and the microphone is not muted. This bypasses wake-word recognition without changing mute or wake-word settings.
- `script.echo_show_play_media`: required `media_id`, optional `media_type` (default `music`). Choose an audio item from HA Media Browser or provide an approved audio URL. The Show must be able to reach the resolved URL.
- `script.echo_show_stop_media`: stops VACA audio playback.
- `script.echo_show_say_message`: reads the nonempty `input_text.echo_show_message` field aloud. The helper is limited to 255 characters.

VACA 0.13.4 accepts the media player's `announce` parameter but does not send it to Android. These scripts use `assist_satellite.announce` for speech instead. VACA does not provide a music queue or next-track control, and its media search returns no results. Playback URLs are logged by the integration; avoid embedding long-lived credentials in them.

## Screen and navigation

- `script.echo_show_screen_wake` and `script.echo_show_screen_sleep` send fixed Android key events 224 and 223.
- `script.echo_show_show_home`, `script.echo_show_show_camera`, `script.echo_show_show_voice`, `script.echo_show_show_music`, and `script.echo_show_show_calls` wake the screen and open the corresponding Companion view.

The tested ROM enabled Always-on Display by default, so sleep initially left the display ON in Dozing. With `doze_always_on=0`, the unchanged sleep script produced Display Power OFF; wake restored Awake/ON. Verify actual display state on your device. The package does not change Android settings automatically; see [the targeted change and null-aware rollback](../../docs/android-and-home-assistant.md#screen-sleep-and-always-on-display). Switching to VACA's Screen control does not itself bypass ambient-display policy.

Navigation expects an `echo-show` dashboard with `home`, `camera`, `voice`, `music`, and `receive` view paths. `script.echo_show_show_calls` opens `/echo-show/receive` on the physical Show, where the video-call card has the receiving `show` role. A phone or desktop places calls from the separate `/echo-show/calls` controller view. Opening the receiving view does not automatically answer a call.

The five remote navigation commands use `NEW_TASK | CLEAR_TASK` (`-f 0x10008000`) before opening the supported Companion deep link. This clears Companion’s UI history so repeated commands do not retain additional dashboard activities and WebViews. One device trial reduced three instances to one; it did not establish fast loading. Prefer ordinary dashboard navigation while Companion is open, and allow cold loads to finish before sending another remote command. Slow frontend loading and connection stalls remain separate limitations.

Change those fixed paths if your dashboard differs. The command targets the minimal Companion package, `io.homeassistant.companion.android.minimal`; a full Companion installation uses a different package ID. These wrappers use the authenticated HA Android Debug Bridge integration, not notification delivery, and never accept arbitrary commands from script callers.

Camera and intercom lifecycle is deliberately outside this package. A session controller must coordinate microphone ownership and app cleanup before camera/audio transitions; these navigation scripts only change the displayed view.

The script schemas were checked against HA Core 2026.9.1. Audio quality, wake-word reliability and physical playback still require a device test. A successful action response alone is not proof that sound played or a screen changed.
