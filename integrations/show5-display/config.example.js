// Copy to ignored config.js and replace these local mappings before deployment.
// This file is served publicly by HA /local: never put credentials here.
window.SHOW5_DISPLAY_CONFIG = {
  // Page language only; does not change Android, HA or the voice pipeline.
  // Supported: en/ru/de/es, optionally with a region (en-GB, ru-RU, etc.).
  // Unknown or malformed locales fall back to en-US; browser language is ignored.
  locale: "en-US",
  // Keep the compact 24-hour clock, or use true for a 12-hour clock.
  hour12: false,
  timeZone: "America/Los_Angeles",
  cameraSeconds: 30,
  // Optional: match the generated HA remote endpoint prefix. No credentials.
  // remoteTarget: "show5_two",
  cameraMode: "webrtc",
  cameras: {
    front: {
      entityId: "camera.replace_me_front",
      // Optional accessible label. Omit to translate the default with locale.
      // label: "Front",
      motion: { topic: "replace_me/front", payload: "motion" }
    },
    porch: {
      entityId: "camera.replace_me_porch",
      // label: "Porch",
      motion: { topic: "replace_me/porch", jsonName: "Porch" }
    }
  }
};
