"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { createController, createView, validateConfig, roleFromSearch } = require("../display.js");

const CONFIG = {
  timeZone: "America/Los_Angeles",
  cameras: {
    front: { entityId: "camera.front", label: "Front", motionEntityId: "binary_sensor.front_motion" },
    porch: { entityId: "camera.porch", label: "Porch" }
  },
  cameraSeconds: 30
};
const goodImage = () => new Blob(["synthetic-test-image"], { type: "image/jpeg" });
const flush = async () => { for (let i = 0; i < 8; i += 1) { await Promise.resolve(); } };

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
      assert.ok(++steps < 2000, "timer loop must remain bounded");
      this.tasks.delete(next[0]);
      this.time = next[1].at;
      next[1].fn();
      await flush();
    }
    this.time = end;
    await flush();
  }
}

function harness(config = CONFIG, prepareSnapshot, startVideo) {
  const timers = new Timers();
  const calls = [];
  const created = [];
  const revoked = [];
  const clears = [];
  const state = { mode: "clock", image: null, status: null, label: null };
  const view = {
    video: {},
    clearVideo() { state.video = false; },
    showVideoLoading() { state.status = "video-loading"; },
    showVideo() { state.video = true; state.status = null; },
    showClock() { state.mode = "clock"; },
    showCamera(label) { state.mode = "camera"; state.label = label; state.status = "loading"; },
    clearSnapshot() { clears.push(timers.time); state.image = null; },
    showSnapshot(url) { state.image = url; state.status = null; },
    showDelayed() { state.status = "delayed"; },
    showUnavailable() { state.status = "unavailable"; }
  };
  if (prepareSnapshot) { view.prepareSnapshot = prepareSnapshot; }
  const controller = createController({
    config, view, startVideo, now: () => timers.time, setTimeout: timers.set, clearTimeout: timers.clear,
    createObjectURL(blob) { const url = "blob:test-" + (created.length + 1); created.push({ url, blob }); return url; },
    revokeObjectURL(url) { revoked.push(url); },
    fetchSnapshot(entityId, { signal }) {
      const call = { entityId, signal };
      const pending = new Promise((resolve, reject) => { call.resolve = resolve; call.reject = reject; });
      calls.push(call);
      return pending;
    }
  });
  return { controller, timers, calls, created, revoked, clears, state };
}

test("configuration accepts only named camera entities and ignores auth-owned motion fields", () => {
  const config = validateConfig(CONFIG);
  assert.deepEqual(config.cameras.front, { entityId: "camera.front", label: "Front" });
  assert.equal(config.cameraSeconds, 30);
  assert.ok(Object.isFrozen(config.cameras.front));
  assert.equal(CONFIG.cameras.front.motionEntityId, "binary_sensor.front_motion");
  const omitted = { ...CONFIG }; delete omitted.cameraSeconds;
  assert.equal(validateConfig(omitted).cameraSeconds, 30);
});

test("URLs, foreign entities, roles, time zones and unsafe durations fail closed", () => {
  for (const entityId of ["https://example.invalid/snapshot", "camera.front/../../secret", "sensor.front", "camera.Front", {}, ""]) {
    assert.throws(() => validateConfig({ ...CONFIG, cameras: { front: { entityId } } }));
  }
  assert.throws(() => validateConfig({ ...CONFIG, cameras: { backyard: { entityId: "camera.other" } } }));
  assert.throws(() => validateConfig({ ...CONFIG, timeZone: "not/a-zone" }));
  assert.throws(() => validateConfig(undefined));
  assert.throws(() => validateConfig({ ...CONFIG, cameraMode: "arbitrary-url" }));
  for (const cameraSeconds of [0, 4.9, 120.1, Infinity, NaN, "30", null]) {
    assert.throws(() => validateConfig({ ...CONFIG, cameraSeconds }));
  }
  assert.equal(validateConfig({ ...CONFIG, cameraSeconds: 5 }).cameraSeconds, 5);
  assert.equal(validateConfig({ ...CONFIG, cameraSeconds: 120 }).cameraSeconds, 120);
});

test("URL selection allows only one front or porch role, never a URL", () => {
  assert.equal(roleFromSearch("?external_auth=1&camera=front"), "front");
  assert.equal(roleFromSearch("?camera=porch"), "porch");
  for (const query of ["", "?camera=back", "?camera=Front", "?camera=https://example.invalid", "?camera=front&camera=porch", "?camera=front&camera=front"]) {
    assert.equal(roleFromSearch(query), null);
  }
});

test("clock-only idle does not fetch or allocate image URLs", async () => {
  const h = harness();
  await h.timers.tick(120000);
  assert.equal(h.state.mode, "clock");
  assert.equal(h.calls.length, 0);
  assert.equal(h.created.length, 0);
  assert.equal(h.timers.tasks.size, 0);
});

test("camera fetch passes only configured entity and AbortSignal with no overlapping poll", async () => {
  const h = harness();
  assert.equal(h.controller.showCamera("front"), true);
  assert.equal(h.calls[0].entityId, "camera.front");
  assert.ok(h.calls[0].signal instanceof AbortSignal);
  await h.timers.tick(9000);
  assert.equal(h.calls.length, 1);
  h.calls[0].resolve(goodImage()); await flush();
  assert.equal(h.state.image, "blob:test-1");
  await h.timers.tick(999); assert.equal(h.calls.length, 1);
  await h.timers.tick(1); assert.equal(h.calls.length, 2);
});

test("lease expires at 30 seconds even with an unresolved request and rejects its late blob", async () => {
  const h = harness();
  h.controller.showCamera("front");
  await h.timers.tick(30000);
  assert.equal(h.state.mode, "clock");
  assert.equal(h.calls[0].signal.aborted, true);
  h.calls[0].resolve(goodImage()); await flush();
  assert.equal(h.created.length, 0);
  assert.equal(h.timers.tasks.size, 0);
  await h.timers.tick(60000); assert.equal(h.calls.length, 1);
});

test("showClock aborts the next request, clears the displayed frame and revokes its Blob URL", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  await h.timers.tick(1000);
  h.controller.showClock();
  assert.equal(h.state.mode, "clock");
  assert.equal(h.state.image, null);
  assert.deepEqual(h.revoked, ["blob:test-1"]);
  assert.equal(h.calls[1].signal.aborted, true);
  h.calls[1].resolve(goodImage()); await flush();
  assert.equal(h.created.length, 1);
  assert.equal(h.timers.tasks.size, 0);
});

test("hiding discards the lease; showing again does not silently resume the camera", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.controller.setHidden(true);
  assert.equal(h.calls[0].signal.aborted, true);
  assert.equal(h.controller.showCamera("porch"), false);
  h.calls[0].resolve(goodImage()); await flush();
  h.controller.setHidden(false);
  await h.timers.tick(60000);
  assert.equal(h.state.mode, "clock");
  assert.equal(h.calls.length, 1);
  assert.equal(h.created.length, 0);
});

test("a held frame gets a delay badge at five seconds and expires at fifteen despite repeated motion", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  await h.timers.tick(4999);
  assert.equal(h.state.image, "blob:test-1");
  assert.equal(h.calls.length, 2);
  await h.timers.tick(1);
  assert.equal(h.state.image, "blob:test-1");
  assert.equal(h.state.status, "delayed");
  h.controller.showCamera("front");
  await h.timers.tick(9999);
  assert.equal(h.state.image, "blob:test-1");
  await h.timers.tick(1);
  assert.equal(h.state.image, null);
  assert.equal(h.state.status, "unavailable");
  assert.deepEqual(h.revoked, ["blob:test-1"]);
});

test("the ten-second request deadline aborts, clears state and retries only after settlement", async () => {
  const h = harness();
  h.controller.showCamera("front");
  await h.timers.tick(10000);
  assert.equal(h.calls[0].signal.aborted, true);
  assert.equal(h.state.status, "unavailable");
  await h.timers.tick(2000);
  assert.equal(h.calls.length, 1, "an abort-ignoring request must not overlap a retry");
  h.calls[0].reject(new Error("aborted")); await flush();
  await h.timers.tick(1000);
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve(goodImage()); await flush();
  assert.equal(h.state.image, "blob:test-1");
});

test("transient refresh failures retain the previous frame and retry with bounded backoff", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  await h.timers.tick(1000);
  h.calls[1].reject(new Error("private network diagnostics")); await flush();
  assert.equal(h.state.image, "blob:test-1");
  assert.equal(h.state.status, "delayed");
  assert.deepEqual(h.revoked, []);
  await h.timers.tick(1000);
  h.calls[2].reject(new Error("second failure")); await flush();
  await h.timers.tick(1999); assert.equal(h.calls.length, 3);
  await h.timers.tick(1); assert.equal(h.calls.length, 4);
  h.calls[3].resolve(goodImage()); await flush();
  assert.equal(h.state.status, null);
  assert.equal(h.state.image, "blob:test-2");
  assert.deepEqual(h.revoked, ["blob:test-1"]);
});

test("three-second downloads with a one-second poll gap never blank a healthy camera", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  const initialClears = h.clears.length;
  for (let i = 1; i <= 4; i++) {
    await h.timers.tick(1000);
    await h.timers.tick(3000);
    assert.equal(h.state.image, "blob:test-" + i);
    assert.equal(h.state.status, null);
    h.calls[i].resolve(goodImage()); await flush();
    assert.equal(h.state.image, "blob:test-" + (i + 1));
    assert.equal(h.clears.length, initialClears, "valid replacements must not clear the visible frame");
  }
});

test("old frame remains until replacement decode completes and bad replacements do not erase it", async () => {
  const prepared = [];
  const h = harness(CONFIG, (url, signal) => new Promise((resolve, reject) => prepared.push({url, signal, resolve, reject})));
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  assert.equal(h.state.image, null);
  prepared[0].resolve(); await flush();
  assert.equal(h.state.image, "blob:test-1");
  await h.timers.tick(1000);
  h.calls[1].resolve(goodImage()); await flush();
  assert.equal(h.state.image, "blob:test-1");
  assert.deepEqual(h.revoked, []);
  prepared[1].reject(new Error("decode failed")); await flush();
  assert.equal(h.state.image, "blob:test-1");
  assert.equal(h.state.status, "delayed");
  assert.deepEqual(h.revoked, ["blob:test-2"]);
  await h.timers.tick(1000);
  h.calls[2].resolve(goodImage()); await flush();
  prepared[2].resolve(); await flush();
  assert.equal(h.state.image, "blob:test-3");
  assert.deepEqual(h.revoked, ["blob:test-2", "blob:test-1"]);
});

test("role change during decode cannot display or leak the old pending frame", async () => {
  let finish;
  const h = harness(CONFIG, () => new Promise(resolve => { finish = resolve; }));
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  h.controller.showCamera("porch");
  assert.equal(h.calls[0].signal.aborted, true);
  finish(); await flush();
  assert.equal(h.state.image, null);
  assert.deepEqual(h.revoked, ["blob:test-1"]);
  await h.timers.tick(0);
  assert.equal(h.calls[1].entityId, "camera.porch");
});

test("newest role wins and an abort-ignoring older response cannot render or overlap", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.controller.showCamera("porch");
  assert.equal(h.state.label, "Porch");
  assert.equal(h.calls[0].signal.aborted, true);
  assert.equal(h.calls.length, 1);
  h.calls[0].resolve(goodImage()); await flush();
  assert.equal(h.created.length, 0);
  await h.timers.tick(0);
  assert.equal(h.calls[1].entityId, "camera.porch");
  h.calls[1].resolve(goodImage()); await flush();
  assert.equal(h.state.image, "blob:test-1");
  assert.equal(h.state.label, "Porch");
});

test("repeat motion renews the bounded lease without aborting an in-flight same-camera request", async () => {
  const h = harness({ ...CONFIG, cameraSeconds: 5 });
  h.controller.showCamera("front");
  await h.timers.tick(4000);
  assert.equal(h.controller.showCamera("front"), true);
  assert.equal(h.calls[0].signal.aborted, false);
  assert.equal(h.calls.length, 1);
  await h.timers.tick(1000);
  assert.equal(h.state.mode, "camera", "original lease must not return to clock");
  await h.timers.tick(3999); assert.equal(h.state.mode, "camera");
  await h.timers.tick(1); assert.equal(h.state.mode, "clock");
});

test("unknown roles and out-of-range overrides stop camera without arbitrary fetches", async () => {
  const h = harness();
  assert.equal(h.controller.showCamera("https://example.invalid"), false);
  assert.equal(h.calls.length, 0);
  assert.equal(h.controller.showCamera("front", 5), true);
  await h.timers.tick(5000);
  assert.equal(h.state.mode, "clock");
  for (const seconds of [4, 121, "30", NaN]) {
    assert.equal(h.controller.showCamera("porch", seconds), false);
  }
  assert.equal(h.calls.length, 1);
});

test("non-image, empty and oversized responses never become displayed blobs", async () => {
  for (const blob of [new Blob(["<html>"], { type: "text/html" }), new Blob([], { type: "image/jpeg" }),
    { type: "image/jpeg", size: 10485761 }, new Blob(["<svg/>"], { type: "image/svg+xml" })]) {
    const h = harness();
    h.controller.showCamera("front"); h.calls[0].resolve(blob); await flush();
    assert.equal(h.state.image, null);
    assert.equal(h.state.status, "unavailable");
    assert.equal(h.created.length, 0);
  }
});

test("decode failure clears a frame and destroy prevents any future activation", async () => {
  const h = harness();
  h.controller.showCamera("front"); h.calls[0].resolve(goodImage()); await flush();
  h.controller.snapshotFailed();
  assert.equal(h.state.image, null);
  assert.equal(h.state.status, "unavailable");
  h.controller.destroy();
  assert.equal(h.controller.showCamera("porch"), false);
  await h.timers.tick(120000);
  assert.equal(h.calls.length, 1);
  assert.equal(h.timers.tasks.size, 0);
});

function fakeDocument() {
  const elements = {};
  for (const id of ["clock-view", "camera-view", "camera-image", "camera-video", "camera-status", "clock-time", "clock-date"]) {
    elements[id] = { hidden: false, textContent: "", listeners: {},
      pause() {},
      classList: { values: new Set(), add(v) { this.values.add(v); }, remove(v) { this.values.delete(v); }, contains(v) { return this.values.has(v); } },
      setAttribute(name, value) { this[name] = value; },
      removeAttribute(name) { delete this[name]; },
      addEventListener(name, fn) { this.listeners[name] = fn; } };
  }
  return { elements, hidden: false, readyState: "complete", documentElement: { dataset: {} }, listeners: {},
    getElementById(id) { return elements[id]; }, addEventListener(name, fn) { this.listeners[name] = fn; } };
}

test("DOM view keeps camera labels accessible and clears the image source on removal", () => {
  const doc = fakeDocument(); const view = createView(doc);
  view.showCamera('<img src="https://example.invalid">');
  assert.equal(doc.elements["camera-view"]["aria-label"], '<img src="https://example.invalid">');
  assert.equal(doc.elements["camera-view"].innerHTML, undefined);
  view.showSnapshot("blob:test");
  view.clearSnapshot();
  assert.equal(doc.elements["camera-image"].src, undefined);
  assert.equal(doc.elements["camera-image"].hidden, true);
  view.showUnavailable();
  assert.equal(doc.elements["camera-status"].textContent, "Camera unavailable");
});

test("camera startup and retry never reveal a poster, and teardown masks before abort", async () => {
  const doc = fakeDocument();
  const view = createView(doc);
  const video = view.video;
  const timers = new Timers();
  const streams = [];
  const controller = createController({
    config: { ...CONFIG, cameraMode: "webrtc" }, view,
    now: () => timers.time, setTimeout: timers.set, clearTimeout: timers.clear,
    createObjectURL() {}, revokeObjectURL() {},
    startVideo(entity, element, options) {
      assert.equal(element, video);
      assert.equal(video.hidden, false, "the decoder can run during startup");
      assert.equal(video.classList.contains("has-frame"), false);
      options.signal.addEventListener("abort", () => {
        assert.equal(video.hidden, true, "mask before adapter clears its stream");
        assert.equal(video.classList.contains("has-frame"), false);
      });
      return new Promise(resolve => streams.push({ entity, resolve, options }));
    }
  });
  controller.showCamera("front"); await flush();
  assert.equal(video.classList.contains("has-frame"), false);
  assert.equal(doc.elements["camera-status"].hidden, false);
  streams[0].resolve({ close() {} }); await flush();
  assert.equal(video.classList.contains("has-frame"), true);
  assert.equal(doc.elements["camera-status"].hidden, true);
  controller.showCamera("front"); await flush();
  assert.equal(streams.length, 1, "repeated motion keeps playing video");
  streams[0].options.onError();
  assert.equal(video.hidden, true);
  await timers.tick(5000);
  assert.equal(streams.length, 2);
  assert.equal(video.classList.contains("has-frame"), false);
  controller.showClock();
  streams[1].resolve({ close() {} }); await flush();
  assert.equal(video.hidden, true, "a stale frame cannot reveal the poster");
  assert.equal(video.classList.contains("has-frame"), false);
});

test("offscreen decode is abortable and never mutates the visible image", async () => {
  const doc = fakeDocument();
  let finish, next;
  doc.createElement = () => next = { decode() { return new Promise(resolve => { finish = resolve; }); }, removeAttribute(k) { delete this[k]; } };
  const view = createView(doc);
  view.showSnapshot("blob:old");
  const abort = new AbortController();
  const preparation = view.prepareSnapshot("blob:new", abort.signal);
  assert.equal(doc.elements["camera-image"].src, "blob:old");
  abort.abort();
  await assert.rejects(preparation, /aborted/);
  assert.equal(next.src, undefined);
  finish(); await flush();
  assert.equal(doc.elements["camera-image"].src, "blob:old");
});

test("browser bootstrap exposes only the display controls and delegates authenticated snapshots", async () => {
  const document = fakeDocument(); const timers = new Timers();
  const calls = []; const events = []; const listeners = {}; const intervals = new Map();
  let intervalId = 0;
  const sandbox = { document, SHOW5_DISPLAY_CONFIG: CONFIG, location: { search: "?external_auth=1" },
    Show5Auth: { fetchSnapshot(entityId, options) { calls.push({ entityId, options }); return new Promise(() => {}); } },
    URL: { createObjectURL() { return "blob:browser"; }, revokeObjectURL() {} }, URLSearchParams, AbortController,
    performance: { now: () => timers.time }, setTimeout: timers.set, clearTimeout: timers.clear,
    setInterval(fn) { const id = ++intervalId; intervals.set(id, fn); return id; }, clearInterval(id) { intervals.delete(id); },
    addEventListener(name, fn) { listeners[name] = fn; }, dispatchEvent(event) { events.push(event.type); },
    Event: class { constructor(type) { this.type = type; } }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../display.js"), "utf8"), sandbox);
  assert.deepEqual(Object.keys(sandbox.Show5Display).sort(), ["showCamera", "showClock"]);
  assert.ok(events.includes("show5-display-ready"));
  assert.match(document.elements["clock-time"].textContent, /^\d{2}:\d{2}$/);
  assert.equal(calls.length, 0);
  sandbox.Show5Display.showCamera("porch");
  assert.equal(calls[0].entityId, "camera.porch");
  document.hidden = true; document.listeners.visibilitychange();
  assert.equal(calls[0].options.signal.aborted, true);
  listeners.pagehide(); assert.equal(intervals.size, 0);
  document.hidden = false; listeners.pageshow();
  assert.equal(intervals.size, 1);
  assert.equal(document.elements["camera-view"].hidden, true);
});

test("page assets are local, CSP disallows external scripts and camera CSS preserves aspect", () => {
  const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
  assert.deepEqual([...html.matchAll(/<script src="([^"]+)" defer>/g)].map(x => x[1]), ["config.js?v=20261005-r9", "stream.js?v=20261005-r9", "auth.js?v=20261005-r9", "display.js?v=20261005-r9"]);
  assert.match(html, /href="display.css\?v=20261005-r9"/);
  assert.match(html, /default-src 'none'/);
  assert.match(html, /script-src 'self'/);
  assert.match(html, /connect-src 'self'/);
  assert.match(html, /img-src 'self' blob:/);
  assert.doesNotMatch(html, /https?:\/\/|unsafe-inline|unsafe-eval|<iframe|<audio/);
  assert.match(html, /media-src 'self' blob:/);
  assert.match(html, /<video id="camera-video" autoplay muted playsinline poster="blank-video.svg\?v=20261005-r9" disableremoteplayback hidden>/);
  const css = fs.readFileSync(path.join(__dirname, "../display.css"), "utf8");
  assert.match(css, /object-fit:\s*cover/);
  assert.doesNotMatch(css, /@import|https?:\/\//);
});

test("WebRTC mode starts video instead of snapshots, renews without restarting and stops on expiry", async () => {
  const streams = []; let closed = 0;
  const h = harness({...CONFIG, cameraMode: "webrtc", cameraSeconds: 5}, null,
    (entity, video, opts) => { streams.push({entity, video, opts}); return Promise.resolve({close(){closed++;}}); });
  h.controller.showCamera("front"); await flush();
  assert.equal(streams.length, 1); assert.equal(streams[0].entity, "camera.front");
  assert.equal(h.calls.length, 0); assert.equal(h.state.video, true);
  await h.timers.tick(4000); h.controller.showCamera("front"); await flush();
  assert.equal(streams.length, 1);
  await h.timers.tick(5000);
  assert.equal(streams[0].opts.signal.aborted, true); assert.equal(closed, 1);
  assert.equal(h.state.video, false); assert.equal(h.state.mode, "clock");
});

test("switching or hiding during WebRTC startup rejects stale handles without displaying old camera", async () => {
  const streams = []; let closed = 0;
  const h = harness({...CONFIG, cameraMode: "webrtc"}, null,
    (entity, video, opts) => new Promise(resolve => streams.push({entity, opts, resolve})));
  h.controller.showCamera("front"); await flush();
  h.controller.showCamera("porch"); await flush();
  assert.equal(streams[0].opts.signal.aborted, true);
  streams[0].resolve({close(){closed++;}}); await flush();
  assert.equal(closed, 1); assert.equal(h.state.video, false);
  h.controller.setHidden(true);
  streams[1].resolve({close(){closed++;}}); await flush();
  assert.equal(closed, 2); assert.equal(h.state.mode, "clock");
  assert.equal(h.calls.length, 0);
});

test("WebRTC startup can take twelve seconds without the JPEG deadline aborting it", async () => {
  const streams = []; let closed = 0;
  const h = harness({...CONFIG, cameraMode: "webrtc"}, null,
    (entity, video, opts) => new Promise(resolve => streams.push({opts, resolve})));
  h.controller.showCamera("front"); await flush();
  await h.timers.tick(12000);
  assert.equal(streams[0].opts.signal.aborted, false);
  assert.equal(h.state.status, "video-loading");
  streams[0].resolve({close(){closed++;}}); await flush();
  assert.equal(h.state.video, true);
  await h.timers.tick(4001);
  assert.equal(streams[0].opts.signal.aborted, false, "success clears the outer startup deadline");
  assert.equal(streams.length, 1);
  h.controller.showClock();
  assert.equal(closed, 1);
});

test("a short camera lease caps the longer WebRTC startup deadline", async () => {
  const streams = []; let closed = 0;
  const h = harness({...CONFIG, cameraMode: "webrtc", cameraSeconds: 5}, null,
    (entity, video, opts) => new Promise(resolve => streams.push({opts, resolve})));
  h.controller.showCamera("front"); await flush();
  await h.timers.tick(5000);
  assert.equal(streams[0].opts.signal.aborted, true);
  assert.equal(h.state.mode, "clock");
  streams[0].resolve({close(){closed++;}}); await flush();
  assert.equal(closed, 1, "a handle resolved after lease expiry is released");
  await h.timers.tick(16000);
  assert.equal(streams.length, 1);
  assert.equal(h.timers.tasks.size, 0);
});

test("WebRTC failure retries only within the active lease and startup cannot hang indefinitely", async () => {
  const streams = []; let closed = 0;
  const h = harness({...CONFIG, cameraMode: "webrtc"}, null,
    (entity, video, opts) => new Promise(resolve => streams.push({opts, resolve})));
  h.controller.showCamera("front"); await flush();
  await h.timers.tick(15999);
  assert.equal(streams[0].opts.signal.aborted, false);
  await h.timers.tick(1);
  assert.equal(streams[0].opts.signal.aborted, true); assert.equal(h.state.status, "unavailable");
  await h.timers.tick(5000); assert.equal(streams.length, 2);
  streams[1].resolve({close(){closed++;}}); await flush();
  streams[1].opts.onError();
  assert.equal(closed, 1); assert.equal(h.state.video, false);
  h.controller.showClock(); await h.timers.tick(120000);
  assert.equal(streams.length, 2); assert.equal(h.timers.tasks.size, 0);
});
