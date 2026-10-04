"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { createAdapter, configuration } = require("../auth.js");

const CONFIG = { cameras: {
  front: { entityId: "camera.front", motion: { topic: "test/front", payload: "motion" } },
  porch: { entityId: "camera.porch", motion: { topic: "test/porch", jsonName: "Porch" } }
} };
const flush = async () => { for (let i = 0; i < 24; i += 1) { await Promise.resolve(); } };

class Timers {
  constructor() { this.time = 0; this.next = 0; this.tasks = new Map(); }
  set = (fn, ms) => { const id = ++this.next; this.tasks.set(id, { fn, at: this.time + ms }); return id; };
  clear = (id) => { this.tasks.delete(id); };
  async tick(ms) {
    const end = this.time + ms;
    let steps = 0;
    while (true) {
      const next = [...this.tasks].sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
      if (!next || next[1].at > end) { break; }
      assert.ok(++steps < 1000, "timers must remain bounded");
      this.tasks.delete(next[0]); this.time = next[1].at; next[1].fn(); await flush();
    }
    this.time = end; await flush();
  }
}

function harness(config = CONFIG) {
  const timers = new Timers();
  const native = [], requests = [], sockets = [], displayed = [];
  let clocks = 0, displayAvailable = true;
  class Socket {
    constructor(url) { this.url = url; this.sent = []; this.closed = false; sockets.push(this); }
    send(raw) { this.sent.push(JSON.parse(raw)); }
    close() { this.closed = true; }
    message(data) { if (this.onmessage) { this.onmessage({ data: JSON.stringify(data) }); } }
    disconnect() { if (this.onclose) { this.onclose(); } }
  }
  const adapter = createAdapter({
    config, origin: "https://ha.example.invalid", WebSocket: Socket,
    now: () => timers.time, setTimeout: timers.set, clearTimeout: timers.clear,
    requestNative(raw) { native.push(JSON.parse(raw)); },
    display() { return displayAvailable ? { showCamera(role) { displayed.push(role); }, showClock() { clocks += 1; } } : undefined; },
    fetch(url, options) {
      const request = { url, options };
      requests.push(request);
      return new Promise((resolve, reject) => { request.resolve = resolve; request.reject = reject; });
    }
  });
  function token(value = "synthetic-token", expires = 3600) { adapter.receiveToken(true, { access_token: value, expires_in: expires }); }
  async function ready() {
    adapter.start(); token(); await flush();
    const socket = sockets.at(-1);
    socket.message({ type: "auth_required" }); socket.message({ type: "auth_ok" });
    socket.sent.filter(item => item.type === "mqtt/subscribe").forEach(item => socket.message({ type: "result", id: item.id, success: true }));
    return socket;
  }
  function event(socket, topic, payload, retain = false) {
    const sub = socket.sent.find(item => item.type === "mqtt/subscribe" && item.topic === topic);
    socket.message({ type: "event", id: sub.id, event: { topic, payload, retain } });
  }
  return { adapter, timers, native, requests, sockets, displayed, token, ready, event,
    clocks: () => clocks, setDisplay: value => { displayAvailable = value; } };
}

function image(bytes = Uint8Array.from([255, 216, 255, 224, 0, 1])) {
  return new Response(bytes, { status: 200, headers: { "content-type": "image/jpeg" } });
}

test("configuration limits camera entities and exact topics/matchers", () => {
  assert.deepEqual(configuration(CONFIG).topics, ["test/front", "test/porch"]);
  for (const topic of ["#", "test/+", "test/#", "$share/group/test", "", "a\n"]) {
    assert.throws(() => configuration({ cameras: { front: { entityId: "camera.front", motion: { topic, payload: "on" } } } }));
  }
  for (const motion of [{ topic: "a" }, { topic: "a", payload: "on", jsonName: "a" }, { topic: "a", payload: "" }]) {
    assert.throws(() => configuration({ cameras: { front: { entityId: "camera.front", motion } } }));
  }
  assert.throws(() => configuration({ cameras: { other: { entityId: "camera.front" } } }));
  assert.throws(() => configuration({ cameras: { front: { entityId: "https://foreign.invalid" } } }));
});

test("native authentication is coalesced, in memory and bounded; unsolicited callbacks ignored", async () => {
  const h = harness();
  h.token("unsolicited"); assert.equal(h.adapter.status().authenticated, false);
  const a = h.adapter.fetchSnapshot("camera.front");
  const b = h.adapter.fetchSnapshot("camera.porch");
  assert.deepEqual(h.native, [{ force: false }]);
  h.token(); await flush();
  assert.equal(h.requests.length, 2);
  h.requests.forEach(request => request.resolve(image()));
  assert.equal((await a).type, "image/jpeg"); await b;
  assert.equal(h.adapter.status().authenticated, true);
  assert.ok(!JSON.stringify(h.adapter.status()).includes("synthetic-token"));
  const source = fs.readFileSync(path.join(__dirname, "../auth.js"), "utf8");
  assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|document\.cookie|console\./);
});

test("missing native callback times out at ten seconds and late callback cannot seed token", async () => {
  const h = harness();
  const result = h.adapter.fetchSnapshot("camera.front");
  const rejection = assert.rejects(result, /snapshot_timeout|native_auth_timeout/);
  await h.timers.tick(9999); assert.equal(h.requests.length, 0);
  await h.timers.tick(1); await rejection;
  assert.equal(h.adapter.status().authenticated, false);
  h.token("late"); assert.equal(h.adapter.status().authenticated, false);
});

test("native failure and malformed success fail closed without exposing values", async () => {
  for (const data of [undefined, { access_token: "private\r\nvalue", expires_in: 60 }, { access_token: "private", expires_in: 0 }, { access_token: "private", expires_in: "3600" }]) {
    const h = harness();
    const result = h.adapter.fetchSnapshot("camera.front");
    h.adapter.receiveToken(true, data);
    await assert.rejects(result, error => error.message === "native_auth_failed" && !error.message.includes("private"));
    assert.equal(h.requests.length, 0);
  }
});

test("camera request uses only same-origin proxy and Bearer header, never query tokens", async () => {
  const h = harness();
  await assert.rejects(h.adapter.fetchSnapshot("camera.other"), /camera_not_allowed/);
  await assert.rejects(h.adapter.fetchSnapshot("https://foreign.invalid"), /camera_not_allowed/);
  assert.equal(h.native.length, 0);
  const result = h.adapter.fetchSnapshot("camera.front"); h.token(); await flush();
  const request = h.requests[0];
  assert.equal(request.url, "https://ha.example.invalid/api/camera_proxy/camera.front");
  assert.equal(request.options.headers.Authorization, "Bearer synthetic-token");
  assert.equal(request.options.redirect, "error"); assert.equal(request.options.cache, "no-store");
  assert.equal(request.options.credentials, "omit");
  request.resolve(image()); await result;
});

test("401 forces one native refresh and retries once; second 401 fails without loop", async () => {
  const h = harness();
  const result = h.adapter.fetchSnapshot("camera.front"); h.token("old"); await flush();
  h.requests[0].resolve(new Response(null, { status: 401 })); await flush();
  assert.deepEqual(h.native, [{ force: false }, { force: true }]);
  h.token("new"); await flush();
  assert.equal(h.requests[1].options.headers.Authorization, "Bearer new");
  h.requests[1].resolve(new Response(null, { status: 401 }));
  await assert.rejects(result, /snapshot_unauthorized/);
  assert.equal(h.native.length, 2); assert.equal(h.requests.length, 2);
});

test("simultaneous 401 responses share one forced refresh", async () => {
  const h = harness();
  const a = h.adapter.fetchSnapshot("camera.front"), b = h.adapter.fetchSnapshot("camera.porch");
  h.token(); await flush();
  h.requests.slice().forEach(request => request.resolve(new Response(null, { status: 401 })));
  await flush(); assert.equal(h.native.filter(item => item.force).length, 1);
  h.token("refreshed"); await flush();
  h.requests.slice(2).forEach(request => request.resolve(image())); await Promise.all([a, b]);
});

test("403 fails without refreshing and server/network errors are sanitized", async () => {
  const h = harness();
  const result = h.adapter.fetchSnapshot("camera.front"); h.token(); await flush();
  h.requests[0].resolve(new Response("private diagnostic", { status: 403 }));
  await assert.rejects(result, error => error.message === "snapshot_forbidden");
  assert.equal(h.native.length, 1);
  const next = h.adapter.fetchSnapshot("camera.front"); await flush();
  h.requests[1].reject(new Error("private URL and token"));
  await assert.rejects(next, error => error.message === "snapshot_failed");
  assert.ok(!JSON.stringify(h.adapter.status()).includes("private"));
});

test("expected aborts preserve diagnostics and a successful frame clears only snapshot errors", async () => {
  const h = harness();
  const abort = new AbortController();
  const cancelled = h.adapter.fetchSnapshot("camera.front", { signal: abort.signal });
  h.token(); await flush(); abort.abort();
  await assert.rejects(cancelled, /snapshot_aborted/);
  assert.equal(h.adapter.status().lastError, null);

  const failed = h.adapter.fetchSnapshot("camera.front"); await flush();
  h.requests[1].reject(new Error("synthetic failure"));
  await assert.rejects(failed, /snapshot_failed/);
  assert.equal(h.adapter.status().lastError, "snapshot_failed");

  const hidden = h.adapter.fetchSnapshot("camera.front"); await flush();
  h.adapter.setHidden(true); await assert.rejects(hidden, /snapshot_aborted/);
  await assert.rejects(h.adapter.fetchSnapshot("camera.front"), /inactive/);
  assert.equal(h.adapter.status().lastError, "snapshot_failed");
  h.adapter.setHidden(false);
  const recovered = h.adapter.fetchSnapshot("camera.porch"); await flush();
  h.requests[3].resolve(image()); await recovered;
  assert.equal(h.adapter.status().lastError, null);
});

test("successful snapshots preserve independent native-auth and subscription errors", async () => {
  const auth = harness();
  const denied = auth.adapter.fetchSnapshot("camera.front");
  auth.adapter.receiveToken(false); await assert.rejects(denied, /native_auth_failed/);
  const recovered = auth.adapter.fetchSnapshot("camera.front"); auth.token(); await flush();
  auth.requests[0].resolve(image()); await recovered;
  assert.equal(auth.adapter.status().lastError, "native_auth_failed");

  const mqtt = harness(); mqtt.adapter.start(); mqtt.token(); await flush();
  const socket = mqtt.sockets[0]; socket.message({ type: "auth_ok" });
  const sub = socket.sent.find(item => item.type === "mqtt/subscribe");
  socket.message({ type: "result", id: sub.id, success: false });
  const frame = mqtt.adapter.fetchSnapshot("camera.front"); await flush();
  mqtt.requests[0].resolve(image()); await frame;
  assert.equal(mqtt.adapter.status().lastError, "subscription_forbidden");
  assert.equal(mqtt.adapter.status().connection, "forbidden");
});

test("caller abort, ten-second transport deadline and hidden page abort outstanding snapshots", async () => {
  const h = harness();
  const external = new AbortController();
  const result = h.adapter.fetchSnapshot("camera.front", { signal: external.signal }); h.token(); await flush();
  external.abort(); await assert.rejects(result, /snapshot_aborted/);
  assert.equal(h.requests[0].options.signal.aborted, true);
  const timed = h.adapter.fetchSnapshot("camera.front"); await flush();
  const rejected = assert.rejects(timed, /snapshot_timeout/);
  await h.timers.tick(10000); await rejected;
  assert.equal(h.requests[1].options.signal.aborted, true);
  const hidden = h.adapter.fetchSnapshot("camera.front"); await flush(); h.adapter.setHidden(true);
  await assert.rejects(hidden, /snapshot_aborted/);
  assert.equal(h.requests[2].options.signal.aborted, true);
  await assert.rejects(h.adapter.fetchSnapshot("camera.front"), /inactive/);
});

test("aborting during native auth never sends a later camera request", async () => {
  const h = harness(); const controller = new AbortController();
  const result = h.adapter.fetchSnapshot("camera.front", { signal: controller.signal });
  controller.abort(); await assert.rejects(result, /snapshot_aborted/);
  h.token(); await flush(); assert.equal(h.requests.length, 0);
});

test("images reject unsafe content types and oversized declared or streamed bodies", async () => {
  for (const response of [
    new Response("svg", { headers: { "content-type": "image/svg+xml" } }),
    new Response("not actually a JPEG", { headers: { "content-type": "image/jpeg" } }),
    new Response(null, { headers: { "content-type": "image/png" } }),
    new Response("small", { headers: { "content-type": "image/png", "content-length": "10485761" } }),
    new Response(new Uint8Array(10485761), { headers: { "content-type": "image/webp" } })
  ]) {
    const h = harness(); const result = h.adapter.fetchSnapshot("camera.front"); h.token(); await flush();
    h.requests[0].resolve(response); await assert.rejects(result, /invalid_image|image_too_large/);
  }
});

test("JPEG, PNG and WebP signatures must agree with the response content type", async () => {
  for (const [type, bytes] of [
    ["image/png", [137, 80, 78, 71, 13, 10, 26, 10]],
    ["image/webp", [82, 73, 70, 70, 4, 0, 0, 0, 87, 69, 66, 80]]
  ]) {
    const h = harness(); const result = h.adapter.fetchSnapshot("camera.front"); h.token(); await flush();
    h.requests[0].resolve(new Response(Uint8Array.from(bytes), { headers: { "content-type": type } }));
    assert.equal((await result).type, type);
  }
});

test("rejecting response headers cancels an unread body", async () => {
  const h = harness(); let cancelled = false;
  const response = new Response(new ReadableStream({ cancel() { cancelled = true; } }), { headers: { "content-type": "text/html" } });
  const result = h.adapter.fetchSnapshot("camera.front"); h.token(); await flush(); h.requests[0].resolve(response);
  await assert.rejects(result, /invalid_image/); assert.equal(cancelled, true);
});

test("WebSocket authenticates then subscribes exact topics with qos zero", async () => {
  const h = harness(); h.adapter.start(); h.token(); await flush();
  const socket = h.sockets[0];
  assert.equal(socket.url, "wss://ha.example.invalid/api/websocket"); assert.equal(socket.sent.length, 0);
  socket.message({ type: "auth_required" });
  assert.deepEqual(socket.sent[0], { type: "auth", access_token: "synthetic-token" });
  assert.equal(socket.sent.filter(item => item.type === "mqtt/subscribe").length, 0);
  socket.message({ type: "auth_ok" });
  assert.deepEqual(socket.sent.slice(1).map(({ type, topic, qos }) => ({ type, topic, qos })), [
    { type: "mqtt/subscribe", topic: "test/front", qos: 0 }, { type: "mqtt/subscribe", topic: "test/porch", qos: 0 }
  ]);
});

test("motion rejects retained, unacknowledged, wrong topic/payload and malformed JSON events", async () => {
  const h = harness(); const socket = await h.ready();
  h.event(socket, "test/front", "motion", true);
  h.event(socket, "test/front", "Motion");
  h.event(socket, "test/porch", "not JSON");
  h.event(socket, "test/porch", JSON.stringify({ name: "Other" }));
  h.event(socket, "test/porch", JSON.stringify([{ name: "Porch" }]));
  const id = socket.sent.find(item => item.topic === "test/front").id;
  socket.message({ type: "event", id, event: { topic: "wrong", payload: "motion", retain: false } });
  socket.message({ type: "event", id, event: { topic: "test/front", payload: "motion" } });
  socket.message({ type: "event", id: 99999, event: { topic: "test/front", payload: "motion", retain: false } });
  assert.deepEqual(h.displayed, []);
  h.event(socket, "test/front", "motion"); h.event(socket, "test/front", "motion");
  h.event(socket, "test/porch", JSON.stringify({ name: "Porch" }));
  assert.deepEqual(h.displayed, ["front", "front", "porch"]);
});

test("events before all subscriptions ready or renderer exists are discarded, never replayed", async () => {
  const h = harness(); h.adapter.start(); h.token(); await flush();
  const socket = h.sockets[0]; socket.message({ type: "auth_ok" });
  const subs = socket.sent.filter(item => item.type === "mqtt/subscribe");
  socket.message({ type: "result", id: subs[0].id, success: true });
  h.event(socket, "test/front", "motion"); assert.deepEqual(h.displayed, []);
  socket.message({ type: "result", id: subs[1].id, success: true });
  h.setDisplay(false); h.event(socket, "test/front", "motion"); h.setDisplay(true);
  assert.deepEqual(h.displayed, []);
  h.event(socket, "test/front", "motion"); assert.deepEqual(h.displayed, ["front"]);
});

test("subscription permission failure closes all subscriptions and blocks reconnect or motion", async () => {
  const h = harness(); h.adapter.start(); h.token(); await flush();
  const socket = h.sockets[0]; socket.message({ type: "auth_ok" });
  const sub = socket.sent.find(item => item.type === "mqtt/subscribe");
  socket.message({ type: "result", id: sub.id, success: false, error: { code: "unauthorized", message: "private error" } });
  assert.equal(h.adapter.status().connection, "forbidden");
  assert.equal(h.adapter.status().lastError, "subscription_forbidden");
  assert.equal(socket.closed, true); assert.equal(h.adapter.status().subscriptions, 0);
  await h.timers.tick(60000); assert.equal(h.sockets.length, 1);
  h.adapter.setHidden(true); h.adapter.setHidden(false); await flush(); assert.equal(h.sockets.length, 1);
  assert.ok(!JSON.stringify(h.adapter.status()).includes("private"));
});

test("disconnect reconnects with exponential delay and ignores obsolete socket callbacks", async () => {
  const h = harness(); const first = await h.ready(); const oldMessage = first.onmessage;
  first.disconnect(); assert.equal(h.adapter.status().connection, "reconnecting");
  await h.timers.tick(999); assert.equal(h.sockets.length, 1);
  await h.timers.tick(1); assert.equal(h.sockets.length, 2);
  h.sockets[1].disconnect(); await h.timers.tick(1999); assert.equal(h.sockets.length, 2);
  await h.timers.tick(1); assert.equal(h.sockets.length, 3);
  const id = first.sent.find(item => item.topic === "test/front").id;
  oldMessage({ data: JSON.stringify({ type: "event", id, event: { topic: "test/front", payload: "motion", retain: false } }) });
  assert.deepEqual(h.displayed, []);
});

test("reconnect exponential backoff stops growing at thirty seconds", async () => {
  const h = harness(); h.adapter.start(); h.token(); await flush();
  for (const delay of [1000, 2000, 4000, 8000, 16000, 30000, 30000]) {
    const count = h.sockets.length; h.sockets.at(-1).disconnect();
    await h.timers.tick(delay - 1); assert.equal(h.sockets.length, count);
    await h.timers.tick(1); assert.equal(h.sockets.length, count + 1);
  }
});

test("handshake and missing heartbeat pong are bounded and reconnect", async () => {
  const h = harness(); h.adapter.start(); h.token(); await flush();
  await h.timers.tick(10000); assert.equal(h.sockets[0].closed, true);
  assert.equal(h.adapter.status().lastError, "websocket_timeout");
  const k = harness(); const socket = await k.ready();
  await k.timers.tick(15000);
  const ping = socket.sent.find(item => item.type === "ping"); assert.ok(ping);
  socket.message({ type: "pong", id: ping.id + 1 });
  await k.timers.tick(10000); assert.equal(socket.closed, true);
  assert.equal(k.adapter.status().lastError, "websocket_stale");
});

test("matching pongs keep connection healthy and schedule the next ping", async () => {
  const h = harness(); const socket = await h.ready();
  await h.timers.tick(15000); const ping = socket.sent.find(item => item.type === "ping");
  socket.message({ type: "pong", id: ping.id });
  await h.timers.tick(14999); assert.equal(socket.closed, false);
  await h.timers.tick(1); assert.equal(socket.sent.filter(item => item.type === "ping").length, 2);
});

test("native token refresh happens before expiry and reconnects with the fresh token", async () => {
  const h = harness(); h.adapter.start(); h.token("old", 10); await flush();
  await h.timers.tick(8999); assert.equal(h.native.length, 1);
  await h.timers.tick(1); assert.deepEqual(h.native[1], { force: true });
  h.token("new", 3600); await flush();
  assert.equal(h.sockets[0].closed, true);
  h.sockets[1].message({ type: "auth_required" });
  assert.equal(h.sockets[1].sent[0].access_token, "new");
});

test("hidden closes socket and clock, visible reconnects without replay; destroy forgets token", async () => {
  const h = harness(); const socket = await h.ready(); h.event(socket, "test/front", "motion");
  h.adapter.setHidden(true); assert.equal(socket.closed, true); assert.ok(h.clocks() > 0);
  await h.timers.tick(60000); assert.equal(h.sockets.length, 1);
  h.event(socket, "test/front", "motion"); assert.deepEqual(h.displayed, ["front"]);
  h.adapter.setHidden(false); await flush(); assert.equal(h.sockets.length, 2);
  assert.deepEqual(h.displayed, ["front"]);
  h.adapter.destroy(); assert.equal(h.adapter.status().authenticated, false);
  assert.equal(h.adapter.status().connection, "stopped"); await h.timers.tick(60000);
  assert.equal(h.sockets.length, 2);
});

test("browser entrypoint installs the exact native callback and exposes only fetch/status", async () => {
  const events = new Map(), docEvents = new Map(), native = [];
  const timers = new Timers();
  const context = { SHOW5_DISPLAY_CONFIG: { cameras: { front: { entityId: "camera.front" } } },
    location: { origin: "https://ha.example.invalid" }, document: { hidden: false, addEventListener(name, fn) { docEvents.set(name, fn); } },
    externalApp: { getExternalAuth(raw) { native.push(JSON.parse(raw)); } },
    addEventListener(name, fn) { events.set(name, fn); },
    fetch() { return Promise.resolve(image()); }, WebSocket: class {}, URL, Set, Map, Blob, AbortController,
    performance: { now: () => timers.time }, setTimeout: timers.set, clearTimeout: timers.clear };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../auth.js"), "utf8"), context);
  assert.deepEqual(Object.keys(context.Show5Auth).sort(), ["fetchSnapshot", "status"]);
  assert.equal(typeof context.externalAuthSetToken, "function");
  const result = context.Show5Auth.fetchSnapshot("camera.front");
  assert.deepEqual(native, [{ force: false }]);
  context.externalAuthSetToken(true, { access_token: "memory-only", expires_in: 3600 });
  await result;
  events.get("pagehide")(); assert.equal(context.Show5Auth.status().hidden, true);
  events.get("pageshow")(); assert.equal(context.Show5Auth.status().hidden, false);
  context.document.hidden = true; docEvents.get("visibilitychange")(); assert.equal(context.Show5Auth.status().hidden, true);
});
