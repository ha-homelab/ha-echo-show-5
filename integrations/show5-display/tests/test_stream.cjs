"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const { start, clientConfig, candidate } = require("../stream.js");
const flush = async () => { for (let i = 0; i < 20; i += 1) { await Promise.resolve(); } };
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }

class Timers {
  constructor() { this.time = 0; this.next = 0; this.tasks = new Map(); }
  set = (fn, ms) => { const id = ++this.next; this.tasks.set(id, { fn, at: this.time + ms }); return id; };
  clear = (id) => { this.tasks.delete(id); };
  async tick(ms) {
    const end = this.time + ms; let count = 0;
    while (true) {
      const next = [...this.tasks].sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
      if (!next || next[1].at > end) { break; }
      assert.ok(++count < 1000); this.tasks.delete(next[0]); this.time = next[1].at; next[1].fn(); await flush();
    }
    this.time = end; await flush();
  }
}

function track(kind = "video") { return { kind, stopped: false, stop() { this.stopped = true; } }; }
function harness(overrides = {}) {
  const timers = new Timers(), sockets = [], peers = [], errors = [], listeners = new Map();
  const controller = new AbortController();
  const token = deferred(), offer = overrides.offer || null, remote = overrides.remote || null;
  const video = { srcObject: null, muted: false, playsInline: false, autoplay: false, paused: false, currentTime: 0, videoWidth: 640, readyState: 2,
    play() { return overrides.play || Promise.resolve(); }, pause() { this.paused = true; },
    addEventListener(name, fn) { listeners.set(name, fn); }, removeEventListener(name, fn) { if (listeners.get(name) === fn) { listeners.delete(name); } } };
  if (overrides.frameCallback) {
    video.requestVideoFrameCallback = fn => { video.frame = fn; return 1; };
    video.cancelVideoFrameCallback = () => { video.frame = null; };
  }
  class Socket {
    constructor(url) { this.url = url; this.sent = []; this.readyState = 1; sockets.push(this); }
    send(raw) { this.sent.push(JSON.parse(raw)); }
    close() { this.readyState = 3; this.closed = true; }
    message(data) { if (this.onmessage) { this.onmessage({ data: JSON.stringify(data) }); } }
  }
  class PC {
    constructor(config) { this.config = config; this.transceivers = []; this.remoteCandidates = []; this.frames = 0; this.connectionState = "new"; this.iceConnectionState = "new"; this.receivers = []; peers.push(this); }
    createDataChannel(label) { this.channel = { label, closed: false, close() { this.closed = true; } }; return this.channel; }
    addTransceiver(kind, options) { this.transceivers.push({ kind, options }); }
    createOffer() { return offer ? offer.promise : Promise.resolve({ type: "offer", sdp: "v=0\r\nm=video synthetic" }); }
    setLocalDescription(value) { this.local = value; return Promise.resolve(); }
    setRemoteDescription(value) { this.remote = value; return remote ? remote.promise : Promise.resolve(); }
    addIceCandidate(value) { this.remoteCandidates.push(value); return Promise.resolve(); }
    getStats() { return Promise.resolve(new Map([["video", { type: "inbound-rtp", kind: "video", framesDecoded: this.frames }]])); }
    getReceivers() { return this.receivers; }
    close() { this.closed = true; }
    receive(trackValue = track()) { this.receivers.push({ track: trackValue }); this.ontrack({ track: trackValue }); return trackValue; }
  }
  class Stream { constructor(tracks) { this.tracks = tracks; } }
  const result = start({ entityId: "camera.front", origin: "https://ha.example.invalid", video, signal: controller.signal,
    getToken: () => token.promise, onError(error) { errors.push(error.code); },
    WebSocket: Socket, RTCPeerConnection: PC, MediaStream: Stream,
    now: () => timers.time, setTimeout: timers.set, clearTimeout: timers.clear });
  async function configured(data = { configuration: { iceServers: [] } }) {
    token.resolve("synthetic-memory-token"); await flush();
    const socket = sockets[0]; socket.message({ type: "auth_required" }); socket.message({ type: "auth_ok" });
    const command = socket.sent.find(item => item.type === "camera/webrtc/get_client_config");
    socket.message({ type: "result", id: command.id, success: true, result: data }); await flush();
    return socket;
  }
  function event(value) {
    const socket = sockets[0], command = socket.sent.find(item => item.type === "camera/webrtc/offer");
    socket.message({ type: "event", id: command.id, event: value });
  }
  async function playing() {
    await configured(); event({ type: "session", session_id: "synthetic-session" });
    event({ type: "answer", answer: "v=0\r\nm=video synthetic" }); await flush();
    const received = peers[0].receive(); peers[0].frames = 1; await timers.tick(250);
    const handle = await result;
    return { handle, received };
  }
  return { timers, sockets, peers, errors, video, listeners, controller, token, result, configured, event, playing };
}

test("client configuration validates bounded HA-provided ICE servers and data channel", () => {
  const valid = clientConfig({ configuration: { iceServers: [{ urls: ["stun:stun.example.invalid:3478", "turns:relay.example.invalid:5349?transport=tcp"], username: "example", credential: "synthetic" }], bundlePolicy: "max-bundle" }, dataChannel: "camera" });
  assert.equal(valid.configuration.iceServers[0].urls.length, 2);
  assert.equal(valid.dataChannel, "camera");
  for (const urls of ["https://example.invalid", "stun:user@host", "stun:host\n", [], Array(9).fill("stun:host")]) {
    assert.throws(() => clientConfig({ configuration: { iceServers: [{ urls }] } }), /stream_configuration/);
  }
  assert.throws(() => clientConfig({ configuration: { iceServers: Array(9).fill({ urls: "stun:host" }) } }));
  assert.throws(() => clientConfig({ configuration: { iceCandidatePoolSize: 999 } }));
  assert.throws(() => clientConfig({ configuration: {}, dataChannel: "x".repeat(129) }));
});

test("candidate validates bounds and preserves end-of-candidates and HA default m-line", () => {
  assert.deepEqual(candidate({ candidate: "" }), { candidate: "" });
  assert.deepEqual(candidate({ candidate: "candidate:synthetic" }), { candidate: "candidate:synthetic", sdpMLineIndex: 0 });
  assert.deepEqual(candidate({ candidate: "candidate:synthetic", sdpMid: "0", sdpMLineIndex: 1 }), { candidate: "candidate:synthetic", sdpMid: "0", sdpMLineIndex: 1 });
  for (const value of [null, { candidate: "x\n" }, { candidate: "x", sdpMLineIndex: -1 }, { candidate: "x".repeat(4097) }]) { assert.throws(() => candidate(value)); }
});

test("abort during token wait settles immediately and cannot create a late socket", async () => {
  const h = harness(); h.controller.abort(); await assert.rejects(h.result, /stream_aborted/);
  h.token.resolve("late-secret"); await flush(); assert.equal(h.sockets.length, 0);
  assert.equal(h.errors.length, 0); assert.equal(h.timers.tasks.size, 0);
});

test("startup deadline covers a native token request that never returns", async () => {
  const h = harness(); const rejected = assert.rejects(h.result, /stream_startup_timeout/);
  await h.timers.tick(14999); assert.equal(h.sockets.length, 0);
  await h.timers.tick(1); await rejected; assert.equal(h.timers.tasks.size, 0);
});

test("abort while waiting for HA authentication closes the socket without creating a peer", async () => {
  const h = harness(); h.token.resolve("synthetic"); await flush();
  const lateMessage = h.sockets[0].onmessage;
  h.controller.abort(); await assert.rejects(h.result, /stream_aborted/);
  lateMessage({ data: JSON.stringify({ type: "auth_required" }) });
  assert.equal(h.sockets[0].closed, true); assert.equal(h.sockets[0].sent.length, 0); assert.equal(h.peers.length, 0);
});

test("auth goes only to same-origin WebSocket and no camera request precedes auth_ok", async () => {
  const h = harness(); h.token.resolve("memory-only"); await flush();
  const socket = h.sockets[0]; assert.equal(socket.url, "wss://ha.example.invalid/api/websocket");
  assert.deepEqual(socket.sent, []); socket.message({ type: "auth_required" });
  assert.deepEqual(socket.sent, [{ type: "auth", access_token: "memory-only" }]);
  socket.message({ type: "auth_invalid", message: "private detail" });
  await assert.rejects(h.result, error => error.message === "stream_unauthorized");
  assert.equal(socket.closed, true);
});

test("recvonly video and optional data channel are configured without audio capture", async () => {
  const h = harness(); await h.configured({ configuration: { iceServers: [] }, dataChannel: "camera" });
  assert.deepEqual(h.peers[0].transceivers, [{ kind: "video", options: { direction: "recvonly" } }]);
  assert.equal(h.peers[0].channel.label, "camera");
  const offer = h.sockets[0].sent.find(item => item.type === "camera/webrtc/offer");
  assert.equal(offer.entity_id, "camera.front"); assert.equal(typeof offer.offer, "string");
  h.controller.abort(); await assert.rejects(h.result, /stream_aborted/);
  assert.equal(h.peers[0].channel.closed, true);
  const source = fs.readFileSync(path.join(__dirname, "../stream.js"), "utf8");
  assert.doesNotMatch(source, /getUserMedia|console\.|localStorage|sessionStorage/);
});

test("local candidates wait for session and remote candidates wait for answer application", async () => {
  const remote = deferred(); const h = harness({ remote }); await h.configured();
  h.peers[0].onicecandidate({ candidate: { candidate: "candidate:local", sdpMid: "0", sdpMLineIndex: 0 } });
  assert.equal(h.sockets[0].sent.filter(item => item.type === "camera/webrtc/candidate").length, 0);
  h.event({ type: "session", session_id: "synthetic-session" });
  const sent = h.sockets[0].sent.find(item => item.type === "camera/webrtc/candidate");
  assert.equal(sent.session_id, "synthetic-session"); assert.equal(sent.candidate.sdpMid, "0");
  h.event({ type: "candidate", candidate: { candidate: "candidate:remote", sdpMLineIndex: 0 } });
  h.event({ type: "answer", answer: "v=0\r\nm=video synthetic" }); await flush();
  assert.deepEqual(h.peers[0].remoteCandidates, []);
  remote.resolve(); await flush(); assert.equal(h.peers[0].remoteCandidates.length, 1);
  h.event({ type: "candidate", candidate: { candidate: "" } }); await flush();
  assert.deepEqual(h.peers[0].remoteCandidates[1], { candidate: "" });
  h.controller.abort(); await assert.rejects(h.result, /stream_aborted/);
});

test("ontrack and play success cannot resolve until decoder frames arrive", async () => {
  const h = harness(); await h.configured(); const received = h.peers[0].receive();
  let ready = false; h.result.then(() => { ready = true; }); await flush();
  await h.timers.tick(500); assert.equal(ready, false);
  h.peers[0].frames = 2; await h.timers.tick(250); const handle = await h.result;
  assert.equal(ready, true); assert.equal(h.video.muted, true); assert.equal(h.video.playsInline, true);
  handle.close(); assert.equal(received.stopped, true); assert.equal(h.video.srcObject, null);
});

test("a presented frame is valid evidence but play must also complete", async () => {
  const play = deferred(); const h = harness({ play: play.promise, frameCallback: true }); await h.configured(); h.peers[0].receive();
  let ready = false; h.result.then(() => { ready = true; }); h.video.frame(); await flush();
  assert.equal(ready, false); play.resolve(); await flush(); const handle = await h.result;
  assert.equal(ready, true); handle.close(); assert.equal(h.video.frame, null);
});

test("close unsubscribes the offer ID, stops tracks/peer, and is idempotent", async () => {
  const h = harness(); const { handle, received } = await h.playing();
  const socket = h.sockets[0], offer = socket.sent.find(item => item.type === "camera/webrtc/offer");
  handle.close(); handle.close();
  assert.equal(socket.sent.filter(item => item.type === "unsubscribe_events").length, 1);
  assert.equal(socket.sent.at(-1).subscription, offer.id);
  assert.equal(socket.closed, true); assert.equal(h.peers[0].closed, true); assert.equal(received.stopped, true);
  assert.equal(h.video.srcObject, null); assert.equal(h.errors.length, 0); assert.equal(h.timers.tasks.size, 0);
  assert.ok(!socket.sent.some(item => item.type === "camera/webrtc/end"));
});

test("close never detaches another session's video stream", async () => {
  const h = harness(); const { handle } = await h.playing(); const replacement = {};
  h.video.srcObject = replacement; handle.close(); assert.equal(h.video.srcObject, replacement);
});

test("cancellation during asynchronous offer and remote answer cannot resurrect session", async () => {
  const offer = deferred(); const h = harness({ offer }); await h.configured();
  h.controller.abort(); await assert.rejects(h.result, /stream_aborted/);
  offer.resolve({ type: "offer", sdp: "v=0\r\nm=video synthetic" }); await flush();
  assert.equal(h.sockets[0].sent.filter(item => item.type === "camera/webrtc/offer").length, 0);
  assert.equal(h.peers[0].closed, true);
  const remote = deferred(); const k = harness({ remote }); await k.configured();
  k.event({ type: "candidate", candidate: { candidate: "candidate:remote" } });
  k.event({ type: "answer", answer: "v=0\r\nm=video synthetic" }); await flush();
  k.controller.abort(); await assert.rejects(k.result, /stream_aborted/); remote.resolve(); await flush();
  assert.deepEqual(k.peers[0].remoteCandidates, []);
});

test("late ontrack after cancellation stops the new track without touching the element", async () => {
  const h = harness(); await h.configured(); const lateTrack = h.peers[0].ontrack;
  h.controller.abort(); await assert.rejects(h.result, /stream_aborted/);
  const received = track(); lateTrack({ track: received });
  assert.equal(received.stopped, true); assert.equal(h.video.srcObject, null);
});

test("playback denial rejects startup and releases the provider subscription", async () => {
  const play = deferred(); const h = harness({ play: play.promise }); await h.configured(); h.peers[0].receive();
  play.reject(new Error("private device diagnostic"));
  await assert.rejects(h.result, error => error.message === "stream_playback");
  assert.equal(h.video.srcObject, null); assert.ok(h.sockets[0].sent.some(item => item.type === "unsubscribe_events"));
  assert.deepEqual(h.errors, []);
});

test("malformed signaling and provider errors reject without exposing response details", async () => {
  for (const event of [{ type: "answer", answer: "private invalid SDP" }, { type: "candidate", candidate: null }, { type: "error", code: "private", message: "private error" }, { type: "session", session_id: "bad\nvalue" }]) {
    const h = harness(); await h.configured(); h.event(event);
    await assert.rejects(h.result, error => /^stream_/.test(error.message) && !error.message.includes("private"));
    assert.equal(h.sockets[0].closed, true); assert.equal(h.peers[0].closed, true); assert.equal(h.errors.length, 0);
  }
});

test("an unexpected audio track is immediately stopped and fails closed", async () => {
  const h = harness(); await h.configured(); const audio = track("audio"); h.peers[0].receive(audio);
  await assert.rejects(h.result, /stream_track/); assert.equal(audio.stopped, true); assert.equal(h.video.srcObject, null);
});

test("startup timeout releases established signaling when no decoded video arrives", async () => {
  const h = harness(); await h.configured(); h.peers[0].receive();
  const rejected = assert.rejects(h.result, /stream_startup_timeout/);
  await h.timers.tick(15000); await rejected;
  assert.equal(h.sockets[0].closed, true); assert.equal(h.peers[0].closed, true); assert.equal(h.video.srcObject, null);
});

test("ten seconds without decoder progress closes live video even when currentTime advances", async () => {
  const h = harness(); await h.playing();
  for (let i = 0; i < 9; i += 1) { h.video.currentTime += 1; await h.timers.tick(1000); }
  assert.deepEqual(h.errors, []); h.video.currentTime += 1; await h.timers.tick(1000);
  assert.deepEqual(h.errors, ["stream_stalled"]); assert.equal(h.video.srcObject, null);
  assert.equal(h.peers[0].closed, true);
});

test("transient peer and ICE disconnection can recover without replacing live video", async () => {
  const h = harness(); const { handle, received } = await h.playing();
  const peer = h.peers[0], stream = h.video.srcObject;
  peer.connectionState = "disconnected"; peer.onconnectionstatechange();
  peer.iceConnectionState = "disconnected"; peer.oniceconnectionstatechange();
  await h.timers.tick(5000);
  assert.deepEqual(h.errors, []); assert.equal(received.stopped, false);
  assert.equal(h.video.srcObject, stream); assert.equal(h.sockets[0].closed, undefined);
  peer.connectionState = "connected"; peer.onconnectionstatechange();
  peer.iceConnectionState = "completed"; peer.oniceconnectionstatechange();
  for (let i = 0; i < 8; i += 1) { peer.frames += 1; await h.timers.tick(1000); }
  assert.deepEqual(h.errors, []); assert.equal(h.peers.length, 1);
  assert.equal(h.video.srcObject, stream); assert.equal(received.stopped, false);
  handle.close(); assert.equal(h.timers.tasks.size, 0);
});

test("persistent ICE disconnection remains bounded by the decoded-frame deadline", async () => {
  const h = harness(); const { received } = await h.playing(); const peer = h.peers[0];
  peer.connectionState = "disconnected"; peer.onconnectionstatechange();
  peer.iceConnectionState = "disconnected"; peer.oniceconnectionstatechange();
  await h.timers.tick(9999); assert.deepEqual(h.errors, []);
  await h.timers.tick(1);
  assert.deepEqual(h.errors, ["stream_stalled"]); assert.equal(received.stopped, true);
  assert.equal(peer.closed, true); assert.equal(h.video.srcObject, null);
  assert.equal(h.timers.tasks.size, 0);
});

test("terminal peer or ICE state closes media immediately and reports failure once", async () => {
  for (const state of ["failed", "closed"]) {
    for (const [property, callback] of [["connectionState", "onconnectionstatechange"], ["iceConnectionState", "oniceconnectionstatechange"]]) {
      const h = harness(); const { received } = await h.playing(); const peer = h.peers[0];
      const changed = peer[callback]; peer[property] = state; changed(); changed();
      assert.deepEqual(h.errors, ["stream_disconnected"]); assert.equal(received.stopped, true);
      assert.equal(peer.closed, true); assert.equal(h.video.srcObject, null);
      assert.equal(h.timers.tasks.size, 0);
    }
  }
});

test("post-ready disconnection calls onError once while explicit abort stays quiet", async () => {
  const h = harness(); await h.playing(); const oldClose = h.sockets[0].onclose;
  oldClose(); oldClose(); assert.deepEqual(h.errors, ["stream_signaling_closed"]); assert.equal(h.video.srcObject, null);
  const k = harness(); await k.playing(); k.controller.abort(); assert.deepEqual(k.errors, []); assert.equal(k.video.srcObject, null);
});

test("candidate queue cannot grow without bound", async () => {
  const h = harness(); await h.configured();
  for (let i = 0; i < 129; i += 1) { h.event({ type: "candidate", candidate: { candidate: "candidate:synthetic" } }); }
  await assert.rejects(h.result, /stream_candidate/); assert.equal(h.peers[0].closed, true);
});
