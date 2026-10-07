(function (root) {
  "use strict";

  var TIMEOUT_MS = 10000;
  var MAX_BYTES = 10 * 1024 * 1024;
  var ROLES = ["front", "porch"];

  function failure(code) {
    var error = new Error(code);
    error.code = code;
    return error;
  }

  function configuration(input) {
    if (!input || !input.cameras || typeof input.cameras !== "object") { throw failure("invalid_configuration"); }
    if (input.remoteTarget !== undefined && (typeof input.remoteTarget !== "string" || !/^[a-z0-9_]{1,48}$/.test(input.remoteTarget))) {
      throw failure("invalid_configuration");
    }
    var entities = new Set();
    var rules = [];
    Object.keys(input.cameras).forEach(function (role) {
      var camera = input.cameras[role];
      if (ROLES.indexOf(role) < 0 || !camera || typeof camera.entityId !== "string" || !/^camera\.[a-z0-9_]+$/.test(camera.entityId)) {
        throw failure("invalid_configuration");
      }
      entities.add(camera.entityId);
      if (camera.motion === undefined) { return; }
      var motion = camera.motion;
      if (!motion || typeof motion.topic !== "string" || !motion.topic || motion.topic.length > 256 ||
          /[+#\u0000-\u001f\u007f]/.test(motion.topic) || motion.topic.indexOf("$share/") === 0 ||
          (typeof motion.payload === "string") === (typeof motion.jsonName === "string")) {
        throw failure("invalid_configuration");
      }
      var value = motion.payload === undefined ? motion.jsonName : motion.payload;
      if (typeof value !== "string" || !value || value.length > 1024) { throw failure("invalid_configuration"); }
      rules.push(Object.freeze({ role: role, topic: motion.topic, payload: motion.payload, jsonName: motion.jsonName }));
    });
    return { entities: entities, rules: rules, roles: Object.keys(input.cameras), remoteTarget: input.remoteTarget,
      topics: Array.from(new Set(rules.map(function (rule) { return rule.topic; }))) };
  }

  function createAdapter(options) {
    var config = configuration(options.config);
    var origin = new URL(options.origin);
    if (!/^https?:$/.test(origin.protocol) || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash) {
      throw failure("invalid_origin");
    }
    var fetch = options.fetch;
    var WebSocket = options.WebSocket;
    var Abort = options.AbortController || root.AbortController;
    var BlobType = options.Blob || root.Blob;
    var now = options.now || function () { return root.performance.now(); };
    var wallNow = options.wallNow || function () { return Date.now() / 1000; };
    var setTimer = options.setTimeout || root.setTimeout.bind(root);
    var clearTimer = options.clearTimeout || root.clearTimeout.bind(root);
    var display = options.display || function () { return root.Show5Display; };
    var requestNative = options.requestNative;
    var token = null;
    var tokenExpires = 0;
    var pendingAuth = null;
    var refreshTimer = null;
    var started = false;
    var hidden = Boolean(options.hidden);
    var destroyed = false;
    var blocked = false;
    var state = "idle";
    var lastError = null;
    var socket = null;
    var epoch = 0;
    var reconnectTimer = null;
    var handshakeTimer = null;
    var heartbeatTimer = null;
    var pongTimer = null;
    var pingId = null;
    var nextId = 0;
    var retryMs = 1000;
    var subscriptions = new Map();
    var operations = new Set();
    var videoRefreshWaiters = new Set();
    var forceNextAuth = false;
    var manualUntil = 0;
    var recentCommands = new Map();
    var acknowledgements = new Set();

    function clock() {
      manualUntil = 0;
      var target = display();
      if (target && typeof target.showClock === "function") { target.showClock(); }
    }

    function validToken() { return token !== null && now() < tokenExpires; }
    function canConnect() { return started && !hidden && !destroyed && !blocked && (config.topics.length > 0 || Boolean(config.remoteTarget)); }

    function closeSocket() {
      epoch += 1;
      clearTimer(handshakeTimer); clearTimer(heartbeatTimer); clearTimer(pongTimer);
      handshakeTimer = null; heartbeatTimer = null; pongTimer = null; pingId = null;
      subscriptions.clear();
      acknowledgements.clear();
      var previous = socket;
      socket = null;
      if (previous) {
        previous.onopen = previous.onmessage = previous.onerror = previous.onclose = null;
        try { previous.close(); } catch (_) { /* Transport is already gone. */ }
      }
    }

    function reconnect(code) {
      if (code) { lastError = code; }
      closeSocket();
      // Event transport is separate from the bounded camera session. Keep its
      // current lease on a transient outage, but fail closed on auth/protocol errors.
      if (["websocket_closed", "websocket_failed", "websocket_stale", "websocket_timeout"].indexOf(code) < 0) { clock(); }
      if (!canConnect() || reconnectTimer !== null) { return; }
      state = "reconnecting";
      reconnectTimer = setTimer(function () { reconnectTimer = null; connect(); }, retryMs);
      retryMs = Math.min(retryMs * 2, 30000);
    }

    function scheduleRefresh() {
      clearTimer(refreshTimer); refreshTimer = null;
      if (!started || hidden || destroyed || !validToken()) { return; }
      var remaining = tokenExpires - now();
      refreshTimer = setTimer(function () {
        refreshTimer = null;
        getToken(true).then(function () {
          if (canConnect()) { closeSocket(); connect(); }
        }, function () { reconnect("native_auth_failed"); });
      }, Math.max(1, remaining - Math.min(60000, remaining * 0.1)));
    }

    function receiveToken(success, data) {
      // The native bridge has no request ID. Ignore unsolicited/late callbacks;
      // only one request is outstanding and all its consumers share the result.
      if (!pendingAuth || destroyed) { return; }
      var pending = pendingAuth;
      pendingAuth = null;
      clearTimer(pending.timer);
      if (success !== true || !data || typeof data.access_token !== "string" || !data.access_token ||
          data.access_token.length > 16384 || /[\r\n]/.test(data.access_token) ||
          typeof data.expires_in !== "number" || !Number.isFinite(data.expires_in) || data.expires_in < 1) {
        token = null; tokenExpires = 0; lastError = "native_auth_failed";
        pending.reject(failure(lastError)); return;
      }
      token = data.access_token;
      tokenExpires = now() + Math.min(data.expires_in, 86400) * 1000;
      scheduleRefresh();
      pending.resolve(token);
    }

    function getToken(force) {
      if (destroyed || hidden) { return Promise.reject(failure("inactive")); }
      if (pendingAuth) { return pendingAuth.promise; }
      if (!force && validToken()) { return Promise.resolve(token); }
      var resolve, reject;
      var promise = new Promise(function (yes, no) { resolve = yes; reject = no; });
      pendingAuth = { promise: promise, resolve: resolve, reject: reject, timer: null };
      pendingAuth.timer = setTimer(function () {
        if (!pendingAuth || pendingAuth.promise !== promise) { return; }
        pendingAuth = null; token = null; tokenExpires = 0; lastError = "native_auth_timeout";
        reject(failure(lastError));
      }, TIMEOUT_MS);
      try { requestNative(JSON.stringify({ force: Boolean(force) })); }
      catch (_) { receiveToken(false); }
      return promise;
    }

    async function readImage(response, signal) {
      var type = (response.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
      if (!/^image\/(jpeg|png|webp)$/.test(type)) { throw failure("invalid_image"); }
      var length = response.headers.get("content-length");
      if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BYTES)) { throw failure("image_too_large"); }
      if (!response.body || typeof response.body.getReader !== "function") { throw failure("invalid_image"); }
      var reader = response.body.getReader();
      var chunks = [], size = 0;
      try {
        while (true) {
          if (signal.aborted) { throw failure("snapshot_aborted"); }
          var part = await reader.read();
          if (signal.aborted) { throw failure("snapshot_aborted"); }
          if (part.done) { break; }
          size += part.value.byteLength;
          if (size > MAX_BYTES) { throw failure("image_too_large"); }
          chunks.push(part.value);
        }
        if (!size) { throw failure("invalid_image"); }
        var blob = new BlobType(chunks, { type: type });
        var prefix = new Uint8Array(await blob.slice(0, 12).arrayBuffer());
        var jpeg = prefix[0] === 255 && prefix[1] === 216 && prefix[2] === 255;
        var png = [137, 80, 78, 71, 13, 10, 26, 10].every(function (byte, index) { return prefix[index] === byte; });
        var webp = prefix[0] === 82 && prefix[1] === 73 && prefix[2] === 70 && prefix[3] === 70 &&
          prefix[8] === 87 && prefix[9] === 69 && prefix[10] === 66 && prefix[11] === 80;
        if (!(type === "image/jpeg" && jpeg || type === "image/png" && png || type === "image/webp" && webp)) {
          throw failure("invalid_image");
        }
        return blob;
      } finally {
        try { await reader.cancel(); } catch (_) { /* A cancelled fetch may reject cancel too. */ }
        reader.releaseLock();
      }
    }

    function fetchSnapshot(entityId, requestOptions) {
      if (!config.entities.has(entityId)) { return Promise.reject(failure("camera_not_allowed")); }
      if (hidden || destroyed) { return Promise.reject(failure("inactive")); }
      var external = requestOptions && requestOptions.signal;
      if (external && external.aborted) { return Promise.reject(failure("snapshot_aborted")); }
      var controller = new Abort();
      operations.add(controller);
      var timeout, abort;
      var stop = new Promise(function (_, reject) {
        abort = function () { controller.abort(); reject(failure("snapshot_aborted")); };
        if (external) { external.addEventListener("abort", abort, { once: true }); }
        controller.signal.addEventListener("abort", function () { reject(failure("snapshot_aborted")); }, { once: true });
        timeout = setTimer(function () { reject(failure("snapshot_timeout")); controller.abort(); }, TIMEOUT_MS);
      });
      var work = (async function () {
        var used = await getToken(false);
        for (var attempt = 0; attempt < 2; attempt += 1) {
          if (controller.signal.aborted) { throw failure("snapshot_aborted"); }
          var response = await fetch(new URL("/api/camera_proxy/" + encodeURIComponent(entityId), origin).href, {
            headers: { Authorization: "Bearer " + used }, signal: controller.signal,
            cache: "no-store", redirect: "error", credentials: "omit", referrerPolicy: "no-referrer"
          });
          try {
            if (response.status === 401 && attempt === 0) {
              if (response.body) { try { await response.body.cancel(); } catch (_) { /* No body required. */ } }
              if (controller.signal.aborted) { throw failure("snapshot_aborted"); }
              used = validToken() && token !== used ? token : await getToken(true);
              continue;
            }
            if (response.status === 403) { throw failure("snapshot_forbidden"); }
            if (response.status === 401) { throw failure("snapshot_unauthorized"); }
            if (!response.ok || response.redirected) { throw failure("snapshot_failed"); }
            var image = await readImage(response, controller.signal);
            if (controller.signal.aborted) { throw failure("snapshot_aborted"); }
            // A good frame resolves snapshot diagnostics, not independent
            // native-auth or MQTT subscription failures.
            if (lastError && lastError.indexOf("snapshot_") === 0) { lastError = null; }
            return image;
          } finally {
            // Rejecting headers/status must also stop the response body download.
            if (response.body && !response.body.locked) {
              try { await response.body.cancel(); } catch (_) { /* Fetch abort already closed it. */ }
            }
          }
        }
        throw failure("snapshot_unauthorized");
      })();
      return Promise.race([work, stop]).catch(function (error) {
        // Do not expose URLs, native errors, headers, or server response bodies.
        var allowed = ["inactive", "snapshot_aborted", "snapshot_timeout", "native_auth_failed", "native_auth_timeout",
          "snapshot_forbidden", "snapshot_unauthorized", "snapshot_failed", "invalid_image", "image_too_large"];
        var code = error && allowed.indexOf(error.code) >= 0 ? error.code : "snapshot_failed";
        // Switching camera/clock or hiding the page intentionally aborts work.
        if (code !== "snapshot_aborted" && code !== "inactive") { lastError = code; }
        throw failure(code);
      }).finally(function () {
        clearTimer(timeout);
        if (external) { external.removeEventListener("abort", abort); }
        operations.delete(controller);
      });
    }

    function startVideo(entityId, video, requestOptions) {
      if (!config.entities.has(entityId)) { return Promise.reject(failure("camera_not_allowed")); }
      if (hidden || destroyed) { return Promise.reject(failure("inactive")); }
      if (!root.Show5Stream || typeof root.Show5Stream.start !== "function") { return Promise.reject(failure("video_unavailable")); }
      requestOptions = requestOptions || {};
      var signal = requestOptions.signal;
      function inactive() { return hidden || destroyed || signal && signal.aborted; }
      function attempt() {
        if (inactive()) { return Promise.reject(failure("stream_aborted")); }
        return root.Show5Stream.start({ entityId: entityId, video: video,
          signal: signal, onError: requestOptions.onError,
          origin: origin.origin, getToken: getToken });
      }
      return Promise.resolve().then(attempt).catch(function (error) {
        // Only a rejected authentication challenge refreshes native credentials.
        // Permission/configuration failures must not produce a retry loop.
        if (!error || error.code !== "stream_unauthorized" || inactive()) { throw error; }
        return new Promise(function (resolve, reject) {
          var settled = false;
          function finish(error) {
            if (settled) { return; }
            settled = true;
            videoRefreshWaiters.delete(cancel);
            if (signal) { signal.removeEventListener("abort", cancel); }
            error ? reject(error) : resolve();
          }
          function cancel() { finish(failure("stream_aborted")); }
          videoRefreshWaiters.add(cancel);
          if (signal) { signal.addEventListener("abort", cancel, { once: true }); }
          if (inactive()) { cancel(); return; }
          // Native auth is shared with MQTT/snapshots: cancel this wait, not the
          // underlying native request needed by other consumers.
          getToken(true).then(function () { finish(); }, finish);
        }).then(attempt);
      });
    }

    function motionEvent(topic, message) {
      if (now() < manualUntil) { return; }
      if (!message || message.retain !== false || message.topic !== topic || typeof message.payload !== "string" || message.payload.length > 16384) { return; }
      config.rules.forEach(function (rule) {
        if (rule.topic !== topic) { return; }
        var matches = message.payload === rule.payload;
        if (rule.jsonName !== undefined) {
          try {
            var value = JSON.parse(message.payload);
            matches = value !== null && typeof value === "object" && !Array.isArray(value) && value.name === rule.jsonName;
          } catch (_) { matches = false; }
        }
        var target = display();
        // Motion is never queued while the renderer is absent or hidden.
        if (matches && !hidden && target && typeof target.showCamera === "function") { target.showCamera(rule.role); }
      });
    }

    function remoteEvent(event, send) {
      if (hidden || destroyed || !config.remoteTarget || !event || event.event_type !== "show5_remote_display") { return; }
      var command = event.data;
      if (!command || typeof command !== "object" || Array.isArray(command) ||
          Object.keys(command).some(function (key) { return ["target", "command_id", "command", "role", "seconds", "expires_at"].indexOf(key) < 0; }) ||
          command.target !== config.remoteTarget || typeof command.command_id !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(command.command_id) ||
          ["camera", "home"].indexOf(command.command) < 0 || typeof command.expires_at !== "number" || !Number.isFinite(command.expires_at)) { return; }
      var remaining = command.expires_at - wallNow();
      if (!(remaining > 0 && remaining <= 30)) { return; }
      if (command.command === "camera") {
        if (config.roles.indexOf(command.role) < 0 || typeof command.seconds !== "number" || !Number.isFinite(command.seconds) ||
            command.seconds < 5 || command.seconds > 120) { return; }
      } else if (command.role !== undefined || command.seconds !== undefined) { return; }
      var signature = JSON.stringify([command.command, command.role, command.seconds, command.expires_at]);
      var previous = recentCommands.get(command.command_id);
      if (previous && previous.signature !== signature) { return; }
      var status = previous ? previous.status : "error";
      if (!previous) {
        try {
          var target = display();
          if (command.command === "home" && target && typeof target.showClock === "function") {
            clock(); status = "ok";
          } else if (command.command === "camera" && target && typeof target.showCamera === "function" &&
              target.showCamera(command.role, command.seconds) === true) {
            manualUntil = now() + command.seconds * 1000; status = "ok";
          }
        } catch (_) { status = "error"; }
        recentCommands.set(command.command_id, { signature: signature, status: status });
        if (recentCommands.size > 32) { recentCommands.delete(recentCommands.keys().next().value); }
      }
      var id = ++nextId;
      acknowledgements.add(id);
      if (acknowledgements.size > 32) { acknowledgements.delete(acknowledgements.values().next().value); }
      // This confirms the renderer accepted the command, not decoded video or
      // camera availability. The existing renderer owns the bounded media lease.
      send({ id: id, type: "fire_event", event_type: "show5_remote_ack",
        event_data: { target: config.remoteTarget, command_id: command.command_id, status: status } });
    }

    function connect() {
      if (!canConnect()) { return; }
      clearTimer(reconnectTimer); reconnectTimer = null;
      closeSocket();
      var generation = epoch;
      state = "authenticating";
      var force = forceNextAuth; forceNextAuth = false;
      getToken(force).then(function (accessToken) {
        if (generation !== epoch || !canConnect()) { return; }
        var url = new URL("/api/websocket", origin);
        url.protocol = origin.protocol === "https:" ? "wss:" : "ws:";
        var current;
        try { current = new WebSocket(url.href); } catch (_) { reconnect("websocket_failed"); return; }
        socket = current; state = "connecting";
        var authenticated = false;
        function currentSocket() { return generation === epoch && current === socket && canConnect(); }
        function send(message) {
          try { current.send(JSON.stringify(message)); return true; }
          catch (_) { reconnect("websocket_failed"); return false; }
        }
        function heartbeat() {
          heartbeatTimer = setTimer(function () {
            if (!currentSocket()) { return; }
            pingId = ++nextId;
            if (!send({ id: pingId, type: "ping" })) { return; }
            pongTimer = setTimer(function () { reconnect("websocket_stale"); }, TIMEOUT_MS);
          }, 15000);
        }
        handshakeTimer = setTimer(function () { reconnect("websocket_timeout"); }, TIMEOUT_MS);
        current.onmessage = function (event) {
          if (!currentSocket()) { return; }
          var message;
          try {
            if (typeof event.data !== "string" || event.data.length > 65536) { throw failure("invalid_message"); }
            message = JSON.parse(event.data);
            if (!message || typeof message !== "object") { throw failure("invalid_message"); }
          } catch (_) { reconnect("websocket_protocol"); return; }
          if (message.type === "auth_required" && !authenticated) {
            state = "authenticating"; send({ type: "auth", access_token: accessToken });
          } else if (message.type === "auth_invalid") {
            token = null; tokenExpires = 0; forceNextAuth = true; reconnect("websocket_unauthorized");
          } else if (message.type === "auth_ok" && !authenticated) {
            authenticated = true; state = "subscribing";
            config.topics.forEach(function (topic) {
              if (!currentSocket()) { return; }
              var id = ++nextId;
              subscriptions.set(id, { kind: "motion", topic: topic, ready: false });
              send({ id: id, type: "mqtt/subscribe", topic: topic, qos: 0 });
            });
            if (config.remoteTarget && currentSocket()) {
              var id = ++nextId;
              subscriptions.set(id, { kind: "remote", ready: false });
              send({ id: id, type: "subscribe_events", event_type: "show5_remote_display" });
            }
          } else if (authenticated && message.type === "result" && subscriptions.has(message.id)) {
            if (message.success !== true) {
              // MQTT and custom HA event subscriptions are admin-only. Do not
              // partially activate controls when any subscription is rejected.
              blocked = true; lastError = "subscription_forbidden"; state = "forbidden";
              clearTimer(reconnectTimer); reconnectTimer = null; closeSocket(); clock(); return;
            }
            if (subscriptions.get(message.id).ready) { return; }
            subscriptions.get(message.id).ready = true;
            if (Array.from(subscriptions.values()).every(function (subscription) { return subscription.ready; })) {
              clearTimer(handshakeTimer); handshakeTimer = null; state = "ready"; lastError = null; retryMs = 1000;
              heartbeat();
            }
          } else if (state === "ready" && message.type === "event" && subscriptions.has(message.id)) {
            var subscription = subscriptions.get(message.id);
            if (subscription.kind === "remote") { remoteEvent(message.event, send); }
            else { motionEvent(subscription.topic, message.event); }
          } else if (authenticated && message.type === "result" && acknowledgements.has(message.id)) {
            acknowledgements.delete(message.id);
            if (message.success !== true) { lastError = "remote_ack_failed"; }
          } else if (message.type === "pong" && message.id === pingId && pingId !== null) {
            clearTimer(pongTimer); pongTimer = null; pingId = null; heartbeat();
          }
        };
        current.onerror = function () { if (currentSocket()) { reconnect("websocket_failed"); } };
        current.onclose = function () { if (currentSocket()) { reconnect("websocket_closed"); } };
      }, function () { if (generation === epoch && canConnect()) { reconnect("native_auth_failed"); } });
    }

    function start() {
      if (destroyed || started) { return; }
      started = true; scheduleRefresh();
      if (hidden) { state = "hidden"; } else { connect(); }
    }

    function setHidden(value) {
      hidden = Boolean(value);
      if (hidden) {
        clearTimer(reconnectTimer); reconnectTimer = null;
        clearTimer(refreshTimer); refreshTimer = null;
        closeSocket(); operations.forEach(function (operation) { operation.abort(); });
        videoRefreshWaiters.forEach(function (cancel) { cancel(); });
        state = "hidden"; clock();
      } else if (!destroyed) {
        scheduleRefresh();
        if (blocked) { state = "forbidden"; } else { connect(); }
      }
    }

    function destroy() {
      destroyed = true; setHidden(true); token = null; tokenExpires = 0;
      if (pendingAuth) {
        clearTimer(pendingAuth.timer); pendingAuth.reject(failure("inactive")); pendingAuth = null;
      }
      state = "stopped";
    }

    function status() {
      return Object.freeze({ connection: state, hidden: hidden, authenticated: validToken(),
        expiresInSeconds: validToken() ? Math.max(0, Math.floor((tokenExpires - now()) / 1000)) : 0,
        subscriptions: Array.from(subscriptions.values()).filter(function (item) { return item.ready; }).length,
        inFlightSnapshots: operations.size, lastError: lastError });
    }

    return Object.freeze({ start: start, setHidden: setHidden, destroy: destroy, receiveToken: receiveToken,
      fetchSnapshot: fetchSnapshot, startVideo: startVideo, status: status });
  }

  function bootstrap() {
    var adapter;
    try {
      adapter = createAdapter({ config: root.SHOW5_DISPLAY_CONFIG, origin: root.location.origin,
        fetch: root.fetch.bind(root), WebSocket: root.WebSocket, hidden: root.document.hidden,
        requestNative: function (options) { root.externalApp.getExternalAuth(options); } });
    } catch (_) {
      root.Show5Auth = Object.freeze({
        fetchSnapshot: function () { return Promise.reject(failure("invalid_configuration")); },
        status: function () { return Object.freeze({ connection: "disabled", lastError: "invalid_configuration" }); }
      });
      return;
    }
    root.externalAuthSetToken = adapter.receiveToken;
    root.Show5Auth = Object.freeze({ fetchSnapshot: adapter.fetchSnapshot, startVideo: adapter.startVideo, status: adapter.status });
    root.document.addEventListener("visibilitychange", function () { adapter.setHidden(root.document.hidden); });
    root.addEventListener("pagehide", function () { adapter.setHidden(true); });
    root.addEventListener("pageshow", function () { adapter.setHidden(root.document.hidden); });
    adapter.start();
  }

  if (typeof module !== "undefined" && module.exports) { module.exports = { createAdapter: createAdapter, configuration: configuration }; }
  else if (root.document) { bootstrap(); }
})(typeof globalThis !== "undefined" ? globalThis : window);
