// Copy to ignored config.js and replace these local mappings before deployment.
// This file is served publicly by HA /local: never put credentials here.
window.SHOW5_DISPLAY_CONFIG = {
  timeZone: "America/Los_Angeles",
  cameraSeconds: 30,
  cameraMode: "webrtc",
  cameras: {
    front: {
      entityId: "camera.replace_me_front",
      label: "Перед домом",
      motion: { topic: "replace_me/front", payload: "motion" }
    },
    porch: {
      entityId: "camera.replace_me_porch",
      label: "Крыльцо",
      motion: { topic: "replace_me/porch", jsonName: "Porch" }
    }
  }
};
