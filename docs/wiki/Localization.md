# Localization and language settings

[Wiki home](Home.md) · [English](../../README.md) · [Русский](../../README.ru.md) · [Deutsch](../../README.de.md) · [Español](../../README.es.md)

The repository has four substantive README entry points and a localized clock interface. It does **not** claim that every technical document, Android application or HA integration is translated. English is the canonical technical documentation language; translated README pages guide readers to the same maintained procedures.

## Display configuration

The clock interface accepts these independent options in its private `config.js`:

```javascript
window.SHOW5_DISPLAY_CONFIG = {
  // Keep the remaining camera/event mappings from config.example.js.
  locale: "de-DE",
  hour12: false,
  timeZone: "Europe/Berlin"
};
```

This is a fragment showing the language options, not a complete camera configuration. Start from [`config.example.js`](../../integrations/show5-display/config.example.js), preserve required mappings, and change the fields you need.

Supported language families are **`en`, `ru`, `de`, `es`**, with region forms such as `en-US`, `en-GB`, `ru-RU`, `de-DE` and `es-ES`. Unsupported or malformed locale input falls back to **`en-US`**. The default is English and **24-hour** time (`hour12: false`); `hour12: true` explicitly selects localized 12-hour formatting. The configured time zone is separate from language.

The catalog covers interface status text, page title, accessibility labels and default camera labels. Date/time formatting uses the selected locale. An operator-provided camera `label` remains literal text and is not machine-translated. Camera roles, MQTT payloads/topics, entity IDs and remote command names remain stable protocol identifiers regardless of language.

The new source revision includes **`i18n.js`**. Deploy it together with the HTML, other scripts, style, blank poster and filled configuration under a fresh asset version and entry filename. See the [display installation procedure](../../integrations/show5-display/README.md#installation). Changing an old cached config URL alone may leave an earlier language visible.

## Four different language choices

1. **README language** chooses an introductory document. It does not change the device.
2. **Display locale** controls the local clock/status interface and formatting.
3. **Android/application language** is managed by Android or the upstream app. This project does not replace all VACA, Jitsi, OTT or Companion translations.
4. **Assist language and wake model** belong to the selected HA pipeline and on-device model configuration. Switching the clock to German does not create German speech recognition or a German wake word.

A Russian assistant can therefore use an English clock and respond to either the Russian private phrase or “Hey Jarvis.” Each speech language still needs appropriate recognition/synthesis support and an evaluated activation model.

## Documentation coverage

- `README.md`: English, canonical project entry point.
- `README.ru.md`: Russian entry point, including capabilities, compatibility, validation limits and maintenance links.
- `README.de.md`: German entry point with the same operational boundaries.
- `README.es.md`: Spanish entry point with the same operational boundaries.
- `docs/wiki/`, detailed runbooks, SVG labels, contribution and release documentation: English.
- Product names, package names, command names and model IDs: retain their exact spelling in every language.

This explicit coverage avoids suggesting that a short translated landing page is a translated installation manual. Follow the linked English runbook for every write operation.

## Adding or changing a translation

Add a complete catalog following the display's existing keys, retain the English fallback, and add the locale to the supported selection. Exercise missing/invalid locale values, placeholder handling, 12/24-hour output, date formatting and document/accessibility labels. Inspect long translations on a five-inch layout; do not add permanent camera headers to make text fit.

For README updates, preserve compatibility warnings, local/cloud boundaries and the difference between tested and pending work in every language. Add reciprocal language links and update this coverage page. Keep command blocks, paths and identifiers exact. Use natural technical language; do not translate `cronos`, package IDs, action modes or credential field names.

Detailed translation expansion should be reviewed as its own maintained document set. Do not create empty translated copies or silently leave outdated installation instructions that diverge from the canonical source.
