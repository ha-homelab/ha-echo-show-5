(function (root) {
  "use strict";

  var ROLES = ["front", "porch"];
  var REQUEST_MS = 10000;
  var SNAPSHOT_MS = 1000;
  var FRAME_MAX_AGE_MS = 3000;
  var MAX_IMAGE_BYTES = 10 * 1024 * 1024;

  function duration(value) {
    var seconds = value === undefined ? 30 : value;
    if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 5 || seconds > 120) {
      throw new Error("Camera duration must be between 5 and 120 seconds");
    }
    return seconds;
  }

  function validateConfig(input) {
    if (!input || typeof input !== "object" || !input.cameras || typeof input.cameras !== "object") {
      throw new Error("Display configuration is missing");
    }
    if (typeof input.timeZone !== "string" || input.timeZone.length > 80) {
      throw new Error("Display time zone is invalid");
    }
    try { new Intl.DateTimeFormat("ru-RU", { timeZone: input.timeZone }); }
    catch (_) { throw new Error("Display time zone is invalid"); }
    var cameras = {};
    Object.keys(input.cameras).forEach(function (role) {
      if (ROLES.indexOf(role) < 0) { throw new Error("Camera role is not allowed"); }
      var camera = input.cameras[role];
      if (!camera || typeof camera.entityId !== "string" || !/^camera\.[a-z0-9_]+$/.test(camera.entityId)) {
        throw new Error("Camera entity is invalid");
      }
      var label = camera.label === undefined ? (role === "front" ? "Перед домом" : "Крыльцо") : camera.label;
      if (typeof label !== "string" || !label.trim() || label.length > 80) {
        throw new Error("Camera label is invalid");
      }
      // Auth owns motionEntityId and event subscription. Never interpret it here.
      cameras[role] = Object.freeze({ entityId: camera.entityId, label: label.trim() });
    });
    return Object.freeze({ timeZone: input.timeZone, cameraSeconds: duration(input.cameraSeconds), cameras: Object.freeze(cameras) });
  }

  function roleFromSearch(search) {
    var roles = new URLSearchParams(search).getAll("camera");
    return roles.length === 1 && ROLES.indexOf(roles[0]) >= 0 ? roles[0] : null;
  }

  function createController(options) {
    var config = validateConfig(options.config);
    var view = options.view;
    var fetchSnapshot = options.fetchSnapshot;
    var now = options.now || function () { return root.performance.now(); };
    var setTimer = options.setTimeout || root.setTimeout.bind(root);
    var clearTimer = options.clearTimeout || root.clearTimeout.bind(root);
    var createURL = options.createObjectURL || root.URL.createObjectURL.bind(root.URL);
    var revokeURL = options.revokeObjectURL || root.URL.revokeObjectURL.bind(root.URL);
    var Abort = options.AbortController || root.AbortController;
    var active = null;
    var sequence = 0;
    var expiresAt = 0;
    var hidden = false;
    var destroyed = false;
    var request = null;
    var pollTimer = null;
    var leaseTimer = null;
    var staleTimer = null;
    var imageURL = null;
    var failures = 0;

    function clearImage() {
      if (staleTimer !== null) { clearTimer(staleTimer); staleTimer = null; }
      view.clearSnapshot();
      if (imageURL !== null) { revokeURL(imageURL); imageURL = null; }
    }

    function live(token) {
      return !destroyed && !hidden && active !== null && token === sequence && now() < expiresAt;
    }

    function reset() {
      sequence += 1;
      active = null;
      expiresAt = 0;
      failures = 0;
      if (pollTimer !== null) { clearTimer(pollTimer); pollTimer = null; }
      if (leaseTimer !== null) { clearTimer(leaseTimer); leaseTimer = null; }
      if (request !== null) {
        clearTimer(request.timeout);
        request.controller.abort();
        // Keep the single request slot until settlement, including adapters
        // that ignore abort. Never overlap an old request with a new role.
      }
      clearImage();
    }

    function showClock() {
      reset();
      view.showClock();
    }

    function unavailable(token) {
      if (!live(token)) { return; }
      failures += 1;
      clearImage();
      view.showUnavailable();
    }

    async function pump() {
      pollTimer = null;
      if (!live(sequence) || request !== null) { return; }
      var token = sequence;
      var item = { controller: new Abort(), timeout: null, timedOut: false };
      request = item;
      item.timeout = setTimer(function () {
        item.timedOut = true;
        unavailable(token);
        item.controller.abort();
      }, Math.min(REQUEST_MS, expiresAt - now()));
      try {
        var blob = await fetchSnapshot(active.entityId, { signal: item.controller.signal });
        if (!live(token) || item.timedOut) { return; }
        if (!blob || !/^image\/(jpeg|png|webp)$/.test(blob.type) ||
            typeof blob.size !== "number" || blob.size <= 0 || blob.size > MAX_IMAGE_BYTES) {
          throw new Error("Snapshot is not a supported image");
        }
        clearImage();
        imageURL = createURL(blob);
        failures = 0;
        view.showSnapshot(imageURL);
        staleTimer = setTimer(function () {
          staleTimer = null;
          if (live(token)) { clearImage(); view.showUnavailable(); }
        }, FRAME_MAX_AGE_MS);
      } catch (_) {
        if (!item.timedOut) { unavailable(token); }
      } finally {
        clearTimer(item.timeout);
        if (request === item) { request = null; }
        if (live(sequence)) {
          // Successful snapshots are requested at most once per second.
          // Failed requests back off, but can never outlive the camera lease.
          var delay = token !== sequence ? 0 : Math.min(SNAPSHOT_MS * Math.pow(2, Math.max(0, failures - 1)), 5000);
          pollTimer = setTimer(pump, Math.min(delay || 0, expiresAt - now()));
        }
      }
    }

    function showCamera(role, seconds) {
      var camera = ROLES.indexOf(role) >= 0 ? config.cameras[role] : null;
      var lease;
      try { lease = duration(seconds === undefined ? config.cameraSeconds : seconds); }
      catch (_) { showClock(); return false; }
      if (camera && active === camera && live(sequence)) {
        expiresAt = now() + lease * 1000;
        clearTimer(leaseTimer);
        leaseTimer = setTimer(showClock, lease * 1000);
        return true;
      }
      reset();
      if (destroyed || hidden || !camera) { view.showClock(); return false; }
      active = camera;
      expiresAt = now() + lease * 1000;
      view.showCamera(camera.label);
      leaseTimer = setTimer(showClock, lease * 1000);
      pump();
      return true;
    }

    function setHidden(value) {
      hidden = Boolean(value);
      if (hidden) { showClock(); }
    }

    function snapshotFailed() {
      if (live(sequence)) { unavailable(sequence); }
    }

    function destroy() {
      destroyed = true;
      showClock();
    }

    view.showClock();
    return Object.freeze({ showCamera: showCamera, showClock: showClock, setHidden: setHidden,
      snapshotFailed: snapshotFailed, destroy: destroy });
  }

  function createView(document) {
    var clock = document.getElementById("clock-view");
    var camera = document.getElementById("camera-view");
    var image = document.getElementById("camera-image");
    var status = document.getElementById("camera-status");
    return {
      showClock: function () { camera.hidden = true; clock.hidden = false; },
      showCamera: function (label) {
        document.getElementById("camera-label").textContent = label;
        status.textContent = "Загрузка камеры…";
        status.hidden = false;
        clock.hidden = true;
        camera.hidden = false;
      },
      clearSnapshot: function () { image.hidden = true; image.removeAttribute("src"); },
      showSnapshot: function (url) { image.src = url; image.hidden = false; status.hidden = true; },
      showUnavailable: function () { status.textContent = "Камера недоступна"; status.hidden = false; }
    };
  }

  function bootstrap(document) {
    var view = createView(document);
    var config;
    try { config = validateConfig(root.SHOW5_DISPLAY_CONFIG); }
    catch (_) { document.documentElement.dataset.configuration = "invalid"; }
    var zone = config ? config.timeZone : undefined;
    var time = new Intl.DateTimeFormat("ru-RU", { timeZone: zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    var date = new Intl.DateTimeFormat("ru-RU", { timeZone: zone, weekday: "long", day: "numeric", month: "long" });
    function tick() {
      var instant = new Date();
      document.getElementById("clock-time").textContent = time.format(instant);
      document.getElementById("camera-time").textContent = time.format(instant);
      document.getElementById("clock-date").textContent = date.format(instant);
    }
    tick();
    var clockTimer = root.setInterval(tick, 1000);
    if (!config) { view.showClock(); return; }
    var controller = createController({ config: config, view: view, fetchSnapshot: function (entityId, options) {
      if (!root.Show5Auth || typeof root.Show5Auth.fetchSnapshot !== "function") {
        return Promise.reject(new Error("Camera authentication is unavailable"));
      }
      return root.Show5Auth.fetchSnapshot(entityId, options);
    } });
    root.Show5Display = Object.freeze({ showCamera: controller.showCamera, showClock: controller.showClock });
    document.getElementById("camera-image").addEventListener("error", controller.snapshotFailed);
    document.addEventListener("visibilitychange", function () { controller.setHidden(document.hidden); });
    root.addEventListener("pagehide", function () { controller.setHidden(true); root.clearInterval(clockTimer); });
    root.addEventListener("pageshow", function () {
      controller.setHidden(document.hidden);
      root.clearInterval(clockTimer);
      tick();
      clockTimer = root.setInterval(tick, 1000);
    });
    controller.setHidden(document.hidden);
    var initialRole = roleFromSearch(root.location.search);
    if (initialRole) { controller.showCamera(initialRole); }
    root.dispatchEvent(new Event("show5-display-ready"));
  }

  var exported = { validateConfig: validateConfig, roleFromSearch: roleFromSearch,
    createController: createController, createView: createView };
  if (typeof module !== "undefined" && module.exports) { module.exports = exported; }
  else if (root.document) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", function () { bootstrap(root.document); }, { once: true });
    } else { bootstrap(root.document); }
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
