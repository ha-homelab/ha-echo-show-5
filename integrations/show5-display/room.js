(function (root) {
  "use strict";

  var i18n = typeof module !== "undefined" && module.exports ? require("./i18n.js") : root.Show5I18n;
  var ENTITY = /^(sensor|binary_sensor|climate|weather|input_number|input_boolean)\.[a-z0-9_]{1,100}$/;
  var PHOTO = /^photos\/[a-zA-Z0-9_-]{1,80}\.(jpg|jpeg|png|webp)$/;
  var JOURNAL = "show5.local-timer.v1:";

  function text(value, max) {
    return typeof value === "string" && value.trim() && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
  }

  function validateConfig(input, prefix) {
    if (input === undefined) { return null; }
    if (!input || Array.isArray(input) || typeof input !== "object" || !/^[a-z][a-z0-9_]{0,47}$/.test(prefix || "")) {
      throw new Error("Room configuration requires a remote target");
    }
    var allowed = ["actions", "status", "timerEntity", "reminderEntity", "dismissScript", "sessionEntity", "staleSeconds", "offline", "photos"];
    if (Object.keys(input).some(function (key) { return allowed.indexOf(key) < 0; })) { throw new Error("Unknown room option"); }
    var actions = input.actions || [];
    var values = input.status || [];
    if (!Array.isArray(actions) || actions.length > 6 || !Array.isArray(values) || values.length > 4) { throw new Error("Room panel is limited to six actions and four readings"); }
    var ids = new Set();
    actions = actions.map(function (action) {
      if (!action || Object.keys(action).some(function (key) { return ["id", "label", "script"].indexOf(key) < 0; }) ||
          !/^[a-z][a-z0-9_]{0,39}$/.test(action.id || "") || action.id === "dismiss" || ids.has(action.id) || !text(action.label, 32) ||
          action.script !== "script." + prefix + "_room_" + action.id) { throw new Error("Invalid fixed room action"); }
      ids.add(action.id);
      return Object.freeze({ id: action.id, label: action.label.trim(), script: action.script });
    });
    var entities = new Set();
    values = values.map(function (value) {
      if (!value || Object.keys(value).some(function (key) { return ["entityId", "label", "attribute"].indexOf(key) < 0; }) ||
          !ENTITY.test(value.entityId || "") || !text(value.label, 32) ||
          value.attribute !== undefined && ["temperature", "current_temperature", "humidity", "wind_speed"].indexOf(value.attribute) < 0) { throw new Error("Invalid room reading"); }
      entities.add(value.entityId);
      return Object.freeze({ entityId: value.entityId, label: value.label.trim(), attribute: value.attribute });
    });
    [["timerEntity", "timer"], ["reminderEntity", "sensor"], ["sessionEntity", "sensor"]].forEach(function (item) {
      var value = input[item[0]];
      if (value !== undefined) {
        if (!new RegExp("^" + item[1] + "\\.[a-z0-9_]{1,100}$").test(value)) { throw new Error("Invalid room entity"); }
        entities.add(value);
      }
    });
    if (input.dismissScript !== undefined && input.dismissScript !== "script." + prefix + "_room_dismiss") { throw new Error("Invalid reminder action"); }
    var stale = input.staleSeconds === undefined ? 120 : input.staleSeconds;
    if (!Number.isInteger(stale) || stale < 30 || stale > 3600) { throw new Error("Invalid freshness interval"); }
    if (input.offline !== undefined && typeof input.offline !== "boolean") { throw new Error("Invalid offline option"); }
    var photos = input.photos || [];
    if (!Array.isArray(photos) || photos.length > 12 || photos.some(function (src) { return typeof src !== "string" || !PHOTO.test(src); }) || new Set(photos).size !== photos.length) {
      throw new Error("Use at most twelve unique local photos");
    }
    return Object.freeze({ prefix: prefix, actions: Object.freeze(actions), status: Object.freeze(values),
      entities: Object.freeze(Array.from(entities)), timerEntity: input.timerEntity, reminderEntity: input.reminderEntity,
      sessionEntity: input.sessionEntity, dismissScript: input.dismissScript, staleSeconds: stale,
      offline: input.offline === true, photos: Object.freeze(photos.slice()) });
  }

  function summarizeState(value, reading, receivedAt, now, staleSeconds) {
    if (!value || value.entity_id !== reading.entityId || typeof value.state !== "string") { return { value: "—", stale: true }; }
    var attributes = value.attributes && typeof value.attributes === "object" ? value.attributes : {};
    var raw = reading.attribute ? attributes[reading.attribute] : value.state;
    if (raw === undefined || raw === null || ["unavailable", "unknown", ""].indexOf(raw) >= 0 || typeof raw === "object") { return { value: "—", stale: true }; }
    var shown = String(raw).slice(0, 48);
    var unit = reading.attribute && reading.attribute.indexOf("temperature") >= 0 ? attributes.temperature_unit : attributes.unit_of_measurement;
    if (typeof unit === "string" && unit.length <= 12) { shown += " " + unit; }
    // last_changed can be old for a healthy steady sensor. Receipt age reports
    // transport freshness only; source timestamps are retained separately.
    return { value: shown, stale: !Number.isFinite(receivedAt) || now - receivedAt > staleSeconds * 1000,
      sourceUpdatedAt: typeof value.last_updated === "string" ? value.last_updated : null };
  }

  function remainingTimer(value, now) {
    if (!value || value.state !== "active" || !value.attributes) { return null; }
    var end = Date.parse(value.attributes.finishes_at);
    return Number.isFinite(end) ? Math.max(0, Math.ceil((end - now) / 1000)) : null;
  }

  function countdown(seconds) {
    return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
  }

  function readJournal(raw, now) {
    try {
      var value = JSON.parse(raw);
      if (value && Object.keys(value).sort().join(",") === "end,started,version" && value.version === 1 &&
          Number.isFinite(value.started) && Number.isFinite(value.end) && value.end > value.started &&
          value.end - value.started <= 3600000 && value.started <= now + 60000 && now - value.end < 86400000) { return value; }
    } catch (_) { /* Invalid or expired journals never create a new alarm. */ }
    return null;
  }

  function bootstrap(document) {
    var raw = root.SHOW5_DISPLAY_CONFIG || {}, config;
    try { config = validateConfig(raw.room, raw.remoteTarget); } catch (_) { return; }
    if (!config) { return; }
    var language = i18n.create(raw.locale), t = language.text;
    var clock = document.getElementById("clock-view");
    var panel = document.getElementById("room-panel");
    var toggle = document.getElementById("room-toggle");
    var network = document.getElementById("room-network");
    var timerLine = document.getElementById("room-timer");
    var reminder = document.getElementById("room-reminder");
    var actionNote = document.getElementById("room-action-status");
    var readings = document.getElementById("room-readings");
    var actionGrid = document.getElementById("room-actions");
    var timerControls = document.getElementById("room-local-timers");
    var photo = document.getElementById("room-photo");
    var entries = new Map(), busy = false, pollTimer = null, pollRunning = false, stopped = false, photoIndex = 0;
    var localTimer = null, alarmAttempted = false, toneContext = null;
    var journalKey = JOURNAL + config.prefix;
    var buttons = [];
    toggle.textContent = t("room"); toggle.hidden = false;
    panel.setAttribute("aria-label", t("room"));
    document.getElementById("room-title").textContent = t("room");
    document.getElementById("room-close").textContent = t("clock");
    document.getElementById("room-local-label").textContent = t("localTimer");
    document.getElementById("room-timer-note").textContent = t("localTimerNote");
    try { localTimer = readJournal(root.localStorage.getItem(journalKey), Date.now()); } catch (_) { /* Storage may be disabled. */ }

    function saveTimer() {
      try { if (localTimer) { root.localStorage.setItem(journalKey, JSON.stringify(localTimer)); } else { root.localStorage.removeItem(journalKey); } }
      catch (_) { actionNote.textContent = t("storageUnavailable"); }
    }
    function setOpen(open) {
      // A user opening controls wins over any still-preparing camera frame.
      if (open && root.Show5Display) { root.Show5Display.showClock(); }
      panel.hidden = !open; clock.classList.toggle("room-open", open); toggle.setAttribute("aria-expanded", String(open));
    }
    toggle.addEventListener("click", function () { setOpen(panel.hidden); });
    document.getElementById("room-close").addEventListener("click", function () { setOpen(false); });
    function button(label, callback, parent) {
      var node = document.createElement("button"); node.type = "button"; node.textContent = label;
      node.addEventListener("click", callback); parent.appendChild(node); return node;
    }
    async function invoke(id) {
      if (busy || !root.Show5Auth) { return; }
      busy = true; buttons.forEach(function (node) { node.disabled = true; }); actionNote.textContent = t("working");
      try { await root.Show5Auth.runRoomAction(id); actionNote.textContent = t("sent"); }
      catch (_) { actionNote.textContent = t("actionFailed"); }
      finally { busy = false; buttons.forEach(function (node) { node.disabled = false; }); }
    }
    config.actions.forEach(function (action) { buttons.push(button(action.label, function () { invoke(action.id); }, actionGrid)); });
    var dismiss = document.getElementById("room-dismiss");
    dismiss.textContent = t("dismiss");
    dismiss.addEventListener("click", function () { invoke("dismiss"); }); buttons.push(dismiss);
    var readingNodes = config.status.map(function (reading) {
      var node = document.createElement("p"), label = document.createElement("span"), value = document.createElement("strong");
      label.textContent = reading.label; value.textContent = "—"; node.appendChild(label); node.appendChild(value); readings.appendChild(node);
      return { node: node, value: value, reading: reading };
    });
    function unlockTone() {
      if (!toneContext) {
        try { var Audio = root.AudioContext || root.webkitAudioContext; if (Audio) { toneContext = new Audio(); } } catch (_) { /* Visual timer remains available. */ }
      }
      if (toneContext && toneContext.state === "suspended") { toneContext.resume().catch(function () {}); }
    }
    [5, 15, 30].forEach(function (minutes) {
      button(minutes + " " + t("minutes"), function () {
        unlockTone(); localTimer = { version: 1, started: Date.now(), end: Date.now() + minutes * 60000 };
        alarmAttempted = false; saveTimer(); update();
      }, timerControls);
    });
    button(t("clear"), function () { localTimer = null; alarmAttempted = false; saveTimer(); update(); }, timerControls);
    function chime() {
      if (alarmAttempted || document.hidden) { return; }
      var session = entries.get(config.sessionEntity);
      if (config.sessionEntity && (!session || Date.now() - session.at > config.staleSeconds * 1000 ||
          session.value.state !== "idle" || !session.value.attributes || session.value.attributes.busy !== false)) {
        // A visual overdue reminder survives. Do not surprise a later session
        // with delayed sound or interrupt call/media ownership.
        alarmAttempted = true; return;
      }
      alarmAttempted = true;
      if (!toneContext || toneContext.state !== "running") { return; }
      // Three soft local tones, never microphone capture or external audio.
      for (var n = 0; n < 3; n += 1) {
        var osc = toneContext.createOscillator(), gain = toneContext.createGain(), at = toneContext.currentTime + n * 0.4;
        osc.frequency.value = 660; gain.gain.setValueAtTime(0, at); gain.gain.linearRampToValueAtTime(0.12, at + 0.02);
        gain.gain.linearRampToValueAtTime(0, at + 0.22); osc.connect(gain); gain.connect(toneContext.destination);
        osc.start(at); osc.stop(at + 0.25);
      }
    }
    function update() {
      var now = Date.now(), status = root.Show5Auth && root.Show5Auth.status(), online = status && status.connection === "ready";
      network.textContent = online ? "" : t("offline"); network.hidden = online;
      readingNodes.forEach(function (item) {
        var entry = entries.get(item.reading.entityId);
        var result = summarizeState(entry && entry.value, item.reading, entry && entry.at, now, config.staleSeconds);
        item.value.textContent = result.value; item.node.classList.toggle("stale", result.stale);
        item.node.title = result.stale ? t("stale") : t("received") + " " + new Date(entry.at).toLocaleTimeString(language.locale);
      });
      var timerEntry = entries.get(config.timerEntity), remoteRemaining = timerEntry && remainingTimer(timerEntry.value, now);
      var localRemaining = localTimer && Math.max(0, Math.ceil((localTimer.end - now) / 1000));
      var lines = [];
      if (localTimer) { lines.push(t("localTimer") + " · " + (localRemaining ? countdown(localRemaining) : t("timerDone"))); if (!localRemaining) { chime(); } }
      document.getElementById("room-local-label").textContent = localTimer ? lines[0] : t("localTimer");
      if (remoteRemaining !== null && remoteRemaining !== undefined) {
        var stale = now - timerEntry.at > config.staleSeconds * 1000;
        lines.push(t("homeTimer") + " · " + countdown(remoteRemaining) + (stale ? " · " + t("stale") : ""));
      }
      timerLine.textContent = lines.join("  /  "); timerLine.hidden = lines.length === 0;
      timerLine.classList.toggle("due", localTimer !== null && localRemaining === 0);
      var message = entries.get(config.reminderEntity), attrs = message && message.value.attributes || {};
      var expires = typeof attrs.expires_at === "number" ? attrs.expires_at * 1000 : Date.parse(attrs.expires_at);
      var visible = message && ["unknown", "unavailable", "idle", "off", "none"].indexOf(message.value.state) < 0 &&
        text(attrs.message, 240) && Number.isFinite(expires) && expires > now;
      reminder.hidden = !visible;
      document.getElementById("room-reminder-text").textContent = visible ? attrs.message : "";
      dismiss.hidden = !config.dismissScript;
    }
    async function poll() {
      if (stopped || document.hidden || pollRunning || !root.Show5Auth || typeof root.Show5Auth.fetchRoomState !== "function") { return; }
      pollRunning = true;
      // Sequential bounded reads keep this low-memory endpoint inexpensive.
      for (var id of config.entities) {
        if (stopped || document.hidden) { break; }
        try { var value = await root.Show5Auth.fetchRoomState(id); entries.set(id, { value: value, at: Date.now() }); }
        catch (_) { /* Keep last good values with their original receipt age. */ }
      }
      pollRunning = false; update();
      if (!stopped && !document.hidden) { pollTimer = root.setTimeout(poll, 30000); }
    }
    function startPoll() { root.clearTimeout(pollTimer); poll(); }
    document.addEventListener("visibilitychange", function () { if (document.hidden) { root.clearTimeout(pollTimer); } else { startPoll(); update(); } });
    root.addEventListener("pagehide", function () { stopped = true; root.clearTimeout(pollTimer); });
    root.addEventListener("pageshow", function () { stopped = false; startPoll(); update(); });
    root.setInterval(function () {
      if (document.hidden || stopped) { return; } update();
      if (config.photos.length && !clock.hidden && panel.hidden) {
        var index = Math.floor(Date.now() / 30000) % config.photos.length;
        if (index !== photoIndex || !photo.getAttribute("src")) { photoIndex = index; photo.src = config.photos[index]; photo.hidden = false; }
      }
    }, 1000);
    if (config.offline && root.isSecureContext && root.navigator.serviceWorker) {
      var file = root.location.pathname.split("/").pop();
      if (/^[A-Za-z0-9_.-]+\.html$/.test(file)) {
        root.navigator.serviceWorker.register("offline-worker.js?shell=" + encodeURIComponent(file), { scope: "./" }).then(function () {
          return root.navigator.serviceWorker.ready;
        }).then(function (registration) {
          if (registration.active) { registration.active.postMessage({ type: "CACHE_PHOTOS", photos: config.photos }); }
        }).catch(function () { actionNote.textContent = t("offlineUnavailable"); });
      }
    } else if (config.offline) {
      actionNote.textContent = t("offlineUnavailable");
    }
    update(); startPoll();
  }

  var exported = Object.freeze({ validateConfig: validateConfig, summarizeState: summarizeState,
    remainingTimer: remainingTimer, readJournal: readJournal, countdown: countdown,
    isOpen: function () { var panel = root.document && root.document.getElementById("room-panel"); return Boolean(panel && !panel.hidden); } });
  if (typeof module !== "undefined" && module.exports) { module.exports = exported; }
  else {
    root.Show5Room = exported;
    if (root.document) { root.document.addEventListener("DOMContentLoaded", function () { bootstrap(root.document); }, { once: true }); }
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
