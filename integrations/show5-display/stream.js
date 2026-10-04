(function (root) {
  "use strict";

  var STARTUP_MS = 15000;
  var STALL_MS = 10000;
  var MAX_CANDIDATES = 128;

  function failure(code) { var error = new Error(code); error.code = code; return error; }

  function clientConfig(input) {
    if (!input || typeof input !== "object" || !input.configuration || typeof input.configuration !== "object") {
      throw failure("stream_configuration");
    }
    var source = input.configuration, result = {};
    if (source.iceServers !== undefined) {
      if (!Array.isArray(source.iceServers) || source.iceServers.length > 8) { throw failure("stream_configuration"); }
      result.iceServers = source.iceServers.map(function (server) {
        if (!server || typeof server !== "object") { throw failure("stream_configuration"); }
        var urls = typeof server.urls === "string" ? [server.urls] : server.urls;
        if (!Array.isArray(urls) || !urls.length || urls.length > 8 || urls.some(function (url) {
          return typeof url !== "string" || url.length > 512 ||
            !/^(stun|stuns|turn|turns):(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9.-]+)(?::[0-9]{1,5})?(?:\?transport=(udp|tcp))?$/.test(url);
        })) { throw failure("stream_configuration"); }
        var clean = { urls: urls.slice() };
        ["username", "credential"].forEach(function (key) {
          if (server[key] !== undefined) {
            if (typeof server[key] !== "string" || server[key].length > 4096) { throw failure("stream_configuration"); }
            clean[key] = server[key];
          }
        });
        if (server.credentialType !== undefined && server.credentialType !== "password") { throw failure("stream_configuration"); }
        return clean;
      });
    }
    var enums = { iceTransportPolicy: ["all", "relay"], bundlePolicy: ["balanced", "max-compat", "max-bundle"], rtcpMuxPolicy: ["require"] };
    Object.keys(enums).forEach(function (key) {
      if (source[key] !== undefined) {
        if (enums[key].indexOf(source[key]) < 0) { throw failure("stream_configuration"); }
        result[key] = source[key];
      }
    });
    if (source.iceCandidatePoolSize !== undefined) {
      if (!Number.isInteger(source.iceCandidatePoolSize) || source.iceCandidatePoolSize < 0 || source.iceCandidatePoolSize > 4) {
        throw failure("stream_configuration");
      }
      result.iceCandidatePoolSize = source.iceCandidatePoolSize;
    }
    if (input.dataChannel !== undefined && (typeof input.dataChannel !== "string" || !input.dataChannel ||
        input.dataChannel.length > 128 || /[\u0000-\u001f\u007f]/.test(input.dataChannel))) { throw failure("stream_configuration"); }
    return { configuration: result, dataChannel: input.dataChannel };
  }

  function candidate(input) {
    if (!input || typeof input !== "object" || typeof input.candidate !== "string" || input.candidate.length > 4096 ||
        /[\r\n]/.test(input.candidate)) { throw failure("stream_candidate"); }
    var result = { candidate: input.candidate };
    if (input.sdpMid !== undefined && input.sdpMid !== null) {
      if (typeof input.sdpMid !== "string" || input.sdpMid.length > 256) { throw failure("stream_candidate"); }
      result.sdpMid = input.sdpMid;
    }
    if (input.sdpMLineIndex !== undefined && input.sdpMLineIndex !== null) {
      if (!Number.isInteger(input.sdpMLineIndex) || input.sdpMLineIndex < 0 || input.sdpMLineIndex > 32) { throw failure("stream_candidate"); }
      result.sdpMLineIndex = input.sdpMLineIndex;
    }
    if (input.usernameFragment !== undefined && input.usernameFragment !== null) {
      if (typeof input.usernameFragment !== "string" || input.usernameFragment.length > 256) { throw failure("stream_candidate"); }
      result.usernameFragment = input.usernameFragment;
    }
    if (result.candidate && result.sdpMid === undefined && result.sdpMLineIndex === undefined) { result.sdpMLineIndex = 0; }
    return result;
  }

  function start(options) {
    var origin;
    try {
      origin = new URL(options.origin);
      if (!/^https?:$/.test(origin.protocol) || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash ||
          typeof options.entityId !== "string" || !/^camera\.[a-z0-9_]+$/.test(options.entityId) ||
          !options.video || typeof options.video.play !== "function" || typeof options.video.addEventListener !== "function" ||
          typeof options.video.removeEventListener !== "function" || typeof options.getToken !== "function") {
        throw failure("stream_configuration");
      }
    } catch (_) { return Promise.reject(failure("stream_configuration")); }
    var video = options.video, signal = options.signal;
    var WebSocket = options.WebSocket || root.WebSocket;
    var PeerConnection = options.RTCPeerConnection || root.RTCPeerConnection;
    var MediaStream = options.MediaStream || root.MediaStream;
    var setTimer = options.setTimeout || root.setTimeout.bind(root);
    var clearTimer = options.clearTimeout || root.clearTimeout.bind(root);
    var now = options.now || function () { return root.performance.now(); };
    var socket = null, pc = null, channel = null, stream = null;
    var done = false, resolved = false, authenticated = false, authSent = false;
    var offerId = null, configId = null, sessionId = null, nextId = 0;
    var localCandidates = [], remoteCandidates = [], candidateRequests = new Set();
    var localCount = 0, remoteCount = 0;
    var answerStarted = false, remoteReady = false;
    var candidateChain = Promise.resolve();
    var startupTimer = null, healthTimer = null, heartbeatTimer = null, pongTimer = null, stallTimer = null, frameCallback = null;
    var pingId = null, playStarted = false, receivedFrame = false, statsBusy = false;
    var lastFrames = 0, lastFrameAt = now();
    var tracks = new Set();
    var resolveStart, rejectStart;
    var result = new Promise(function (resolve, reject) { resolveStart = resolve; rejectStart = reject; });

    function cleanup() {
      if (done) { return; }
      done = true;
      [startupTimer, healthTimer, heartbeatTimer, pongTimer, stallTimer].forEach(clearTimer);
      if (signal) { signal.removeEventListener("abort", aborted); }
      video.removeEventListener("error", videoError);
      if (frameCallback !== null && typeof video.cancelVideoFrameCallback === "function") {
        try { video.cancelVideoFrameCallback(frameCallback); } catch (_) { /* Already delivered. */ }
      }
      tracks.forEach(function (track) { track.onended = null; try { track.stop(); } catch (_) { /* Already ended. */ } });
      if (pc) {
        pc.ontrack = pc.onicecandidate = pc.onconnectionstatechange = pc.oniceconnectionstatechange = null;
        try { pc.getReceivers().forEach(function (receiver) { if (receiver.track) { receiver.track.stop(); } }); } catch (_) { /* Closing peer. */ }
        try { pc.close(); } catch (_) { /* Already closed. */ }
      }
      if (channel) { try { channel.close(); } catch (_) { /* Already closed. */ } }
      // An obsolete stream must never clear a replacement session's element.
      if (stream && video.srcObject === stream) {
        try { video.pause(); } catch (_) { /* Detached element. */ }
        video.srcObject = null;
      }
      if (socket) {
        if (authenticated && offerId !== null && socket.readyState === 1) {
          try { socket.send(JSON.stringify({ id: ++nextId, type: "unsubscribe_events", subscription: offerId })); } catch (_) { /* Disconnect also releases subscriptions. */ }
        }
        socket.onmessage = socket.onclose = socket.onerror = null;
        try { socket.close(); } catch (_) { /* Already closed. */ }
      }
      localCandidates.length = 0; remoteCandidates.length = 0; candidateRequests.clear();
    }

    function fail(code) {
      if (done) { return; }
      cleanup();
      var error = failure(code);
      if (!resolved) { rejectStart(error); }
      else if (typeof options.onError === "function") {
        try { options.onError(error); } catch (_) { /* Consumer errors cannot leak resources. */ }
      }
    }
    function aborted() { if (!done) { cleanup(); if (!resolved) { rejectStart(failure("stream_aborted")); } } }
    function close() { if (!done) { cleanup(); if (!resolved) { rejectStart(failure("stream_closed")); } } }
    function videoError() { fail("stream_playback"); }
    function send(message) {
      if (done) { return false; }
      try { socket.send(JSON.stringify(message)); return true; }
      catch (_) { fail("stream_signaling"); return false; }
    }

    function checkStarted() {
      if (!done && !resolved && playStarted && receivedFrame && tracks.size > 0) {
        if (now() - lastFrameAt >= STALL_MS) { fail("stream_stalled"); return; }
        resolved = true; clearTimer(startupTimer);
        stallTimer = setTimer(function () { fail("stream_stalled"); }, STALL_MS - (now() - lastFrameAt));
        resolveStart(Object.freeze({ close: close }));
      }
    }
    function frameReceived() {
      if (done) { return; }
      receivedFrame = true; lastFrameAt = now();
      if (resolved) {
        clearTimer(stallTimer);
        stallTimer = setTimer(function () { fail("stream_stalled"); }, STALL_MS);
      }
      checkStarted();
    }
    function presentedFrame() {
      if (done || !stream || video.srcObject !== stream) { return; }
      frameReceived();
      frameCallback = video.requestVideoFrameCallback(presentedFrame);
    }
    function health() {
      if (done) { return; }
      if (resolved && now() - lastFrameAt >= STALL_MS) { fail("stream_stalled"); return; }
      // A WebRTC media clock can advance while its last image is frozen. Only
      // presented frames or inbound decoder counters establish live video.
      if (pc && !statsBusy) {
        statsBusy = true;
        Promise.resolve().then(function () { if (!done) { return pc.getStats(); } }).then(function (stats) {
          if (done) { return; }
          var frames = 0;
          stats.forEach(function (report) {
            if (report.type === "inbound-rtp" && (report.kind === "video" || report.mediaType === "video") &&
                typeof report.framesDecoded === "number" && Number.isFinite(report.framesDecoded)) { frames += report.framesDecoded; }
          });
          if (frames > lastFrames) { frameReceived(); }
          lastFrames = frames;
        }, function () { /* Presented frame callbacks remain valid evidence. */ }).finally(function () { statsBusy = false; });
      }
      healthTimer = setTimer(health, resolved ? 1000 : 250);
    }

    function sendCandidate(value) {
      if (!sessionId || done) { localCandidates.push(value); return; }
      var id = ++nextId;
      candidateRequests.add(id);
      send({ id: id, type: "camera/webrtc/candidate", entity_id: options.entityId, session_id: sessionId, candidate: value });
    }
    function addRemote(value) {
      candidateChain = candidateChain.then(function () {
        if (!done) { return pc.addIceCandidate(value); }
      }).catch(function () { fail("stream_candidate"); });
    }
    async function configure(data) {
      var clean;
      try {
        clean = clientConfig(data);
        pc = new PeerConnection(clean.configuration);
        if (clean.dataChannel !== undefined) { channel = pc.createDataChannel(clean.dataChannel); }
        pc.addTransceiver("video", { direction: "recvonly" });
        pc.onicecandidate = function (event) {
          if (done || !event.candidate) { return; }
          try {
            if (++localCount > MAX_CANDIDATES) { throw failure("stream_candidate"); }
            sendCandidate(candidate(typeof event.candidate.toJSON === "function" ? event.candidate.toJSON() : event.candidate));
          } catch (_) { fail("stream_candidate"); }
        };
        function connectionChanged() {
          if (done) { return; }
          if (["failed", "closed", "disconnected"].indexOf(pc.connectionState) >= 0 ||
              ["failed", "closed", "disconnected"].indexOf(pc.iceConnectionState) >= 0) { fail("stream_disconnected"); }
        }
        pc.onconnectionstatechange = pc.oniceconnectionstatechange = connectionChanged;
        pc.ontrack = function (event) {
          if (done) { if (event.track) { event.track.stop(); } return; }
          if (!event.track || event.track.kind !== "video" || tracks.size > 0) {
            if (event.track) { event.track.stop(); }
            fail("stream_track"); return;
          }
          tracks.add(event.track);
          event.track.onended = function () { fail("stream_ended"); };
          stream = new MediaStream([event.track]);
          video.muted = true; video.playsInline = true; video.autoplay = true;
          video.srcObject = stream;
          if (typeof video.requestVideoFrameCallback === "function") { frameCallback = video.requestVideoFrameCallback(presentedFrame); }
          try {
            Promise.resolve(video.play()).then(function () { if (!done) { playStarted = true; checkStarted(); } }, function () { fail("stream_playback"); });
          } catch (_) { fail("stream_playback"); }
        };
        var offer = await pc.createOffer();
        if (done) { return; }
        if (!offer || typeof offer.sdp !== "string" || offer.sdp.length > 524288 || offer.type !== "offer") { throw failure("stream_offer"); }
        await pc.setLocalDescription(offer);
        if (done) { return; }
        offerId = ++nextId;
        send({ id: offerId, type: "camera/webrtc/offer", entity_id: options.entityId, offer: offer.sdp });
        health();
      } catch (_) { fail("stream_configuration"); }
    }

    function signalingEvent(event) {
      if (!event || typeof event !== "object") { fail("stream_protocol"); return; }
      if (event.type === "session") {
        if (typeof event.session_id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(event.session_id) ||
            sessionId !== null && event.session_id !== sessionId) { fail("stream_protocol"); return; }
        sessionId = event.session_id;
        var queued = localCandidates; localCandidates = [];
        queued.forEach(sendCandidate);
      } else if (event.type === "answer") {
        if (answerStarted || typeof event.answer !== "string" || event.answer.length > 524288 || !/^v=0(?:\r?\n)/.test(event.answer)) {
          fail("stream_protocol"); return;
        }
        answerStarted = true;
        Promise.resolve().then(function () { if (!done) { return pc.setRemoteDescription({ type: "answer", sdp: event.answer }); } }).then(function () {
          if (done) { return; }
          remoteReady = true;
          var queued = remoteCandidates; remoteCandidates = [];
          queued.forEach(addRemote);
        }, function () { fail("stream_answer"); });
      } else if (event.type === "candidate") {
        try {
          if (++remoteCount > MAX_CANDIDATES) { throw failure("stream_candidate"); }
          var value = candidate(event.candidate);
          if (remoteReady) { addRemote(value); } else { remoteCandidates.push(value); }
        } catch (_) { fail("stream_candidate"); }
      } else if (event.type === "error") { fail("stream_signaling"); }
      else { fail("stream_protocol"); }
    }

    function heartbeat() {
      heartbeatTimer = setTimer(function () {
        if (done) { return; }
        pingId = ++nextId;
        if (send({ id: pingId, type: "ping" })) { pongTimer = setTimer(function () { fail("stream_signaling_timeout"); }, 10000); }
      }, 15000);
    }

    function message(event) {
      if (done) { return; }
      var data;
      try {
        if (typeof event.data !== "string" || event.data.length > 1048576) { throw failure("stream_protocol"); }
        data = JSON.parse(event.data);
        if (!data || typeof data !== "object") { throw failure("stream_protocol"); }
      } catch (_) { fail("stream_protocol"); return; }
      if (data.type === "auth_ok" && authSent && !authenticated) {
        authenticated = true;
        configId = ++nextId;
        send({ id: configId, type: "camera/webrtc/get_client_config", entity_id: options.entityId });
        heartbeat();
      } else if (data.type === "auth_invalid") { fail("stream_unauthorized"); }
      else if (authenticated && data.type === "result") {
        if (data.id === configId) {
          configId = null;
          if (data.success !== true) { fail("stream_configuration"); } else { configure(data.result); }
        } else if (data.id === offerId || candidateRequests.has(data.id)) {
          candidateRequests.delete(data.id);
          if (data.success !== true) { fail("stream_signaling"); }
        }
      } else if (authenticated && data.type === "event" && data.id === offerId && offerId !== null) { signalingEvent(data.event); }
      else if (data.type === "pong" && data.id === pingId && pingId !== null) {
        clearTimer(pongTimer); pongTimer = null; pingId = null; heartbeat();
      }
    }

    if (signal && signal.aborted) { aborted(); return result; }
    if (signal) { signal.addEventListener("abort", aborted, { once: true }); }
    video.addEventListener("error", videoError);
    startupTimer = setTimer(function () { fail("stream_startup_timeout"); }, STARTUP_MS);
    Promise.resolve().then(function () { if (!done) { return options.getToken(false); } }).then(function (token) {
      if (done) { return; }
      if (typeof token !== "string" || !token || token.length > 16384 || /[\r\n]/.test(token)) { fail("stream_unauthorized"); return; }
      var url = new URL("/api/websocket", origin); url.protocol = origin.protocol === "https:" ? "wss:" : "ws:";
      try { socket = new WebSocket(url.href); } catch (_) { fail("stream_signaling"); return; }
      socket.onmessage = function (event) {
        if (done) { return; }
        // Authenticate only after HA's challenge. The token remains solely in
        // this connection's closure and never enters the URL or diagnostics.
        var data;
        try { data = typeof event.data === "string" && event.data.length <= 1048576 ? JSON.parse(event.data) : null; }
        catch (_) { fail("stream_protocol"); return; }
        if (data && data.type === "auth_required" && !authSent) {
          authSent = true; send({ type: "auth", access_token: token });
        } else { message(event); }
      };
      socket.onclose = function () { fail("stream_signaling_closed"); };
      socket.onerror = function () { fail("stream_signaling"); };
    }).catch(function () { fail("stream_unauthorized"); });
    return result;
  }

  if (typeof module !== "undefined" && module.exports) { module.exports = { start: start, clientConfig: clientConfig, candidate: candidate }; }
  else { root.Show5Stream = Object.freeze({ start: start }); }
})(typeof globalThis !== "undefined" ? globalThis : window);
