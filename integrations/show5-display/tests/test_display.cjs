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

function harness(config = CONFIG) {
  const timers = new Timers();
  const calls = [];
  const created = [];
  const revoked = [];
  const state = { mode: "clock", image: null, status: null, label: null };
  const view = {
    showClock() { state.mode = "clock"; },
    showCamera(label) { state.mode = "camera"; state.label = label; state.status = "loading"; },
    clearSnapshot() { state.image = null; },
    showSnapshot(url) { state.image = url; state.status = null; },
    showUnavailable() { state.status = "unavailable"; }
  };
  const controller = createController({
    config, view, now: () => timers.time, setTimeout: timers.set, clearTimeout: timers.clear,
    createObjectURL(blob) { const url = "blob:test-" + (created.length + 1); created.push({ url, blob }); return url; },
    revokeObjectURL(url) { revoked.push(url); },
    fetchSnapshot(entityId, { signal }) {
      const call = { entityId, signal };
      const pending = new Promise((resolve, reject) => { call.resolve = resolve; call.reject = reject; });
      calls.push(call);
      return pending;
    }
  });
  return { controller, timers, calls, created, revoked, state };
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

test("a displayed frame expires after three seconds while a subsequent fetch hangs", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  await h.timers.tick(2999);
  assert.equal(h.state.image, "blob:test-1");
  assert.equal(h.calls.length, 2);
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

test("a failed refresh removes the previous frame immediately and retries with bounded backoff", async () => {
  const h = harness();
  h.controller.showCamera("front");
  h.calls[0].resolve(goodImage()); await flush();
  await h.timers.tick(1000);
  h.calls[1].reject(new Error("private network diagnostics")); await flush();
  assert.equal(h.state.image, null);
  assert.equal(h.state.status, "unavailable");
  await h.timers.tick(1000);
  h.calls[2].reject(new Error("second failure")); await flush();
  await h.timers.tick(1999); assert.equal(h.calls.length, 3);
  await h.timers.tick(1); assert.equal(h.calls.length, 4);
  h.calls[3].resolve(goodImage()); await flush();
  assert.equal(h.state.status, null);
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
  for (const id of ["clock-view", "camera-view", "camera-image", "camera-status", "camera-label", "clock-time", "clock-date", "camera-time"]) {
    elements[id] = { hidden: false, textContent: "", listeners: {},
      removeAttribute(name) { delete this[name]; },
      addEventListener(name, fn) { this.listeners[name] = fn; } };
  }
  return { elements, hidden: false, readyState: "complete", documentElement: { dataset: {} }, listeners: {},
    getElementById(id) { return elements[id]; }, addEventListener(name, fn) { this.listeners[name] = fn; } };
}

test("DOM view treats labels as text and clears the image source on removal", () => {
  const doc = fakeDocument(); const view = createView(doc);
  view.showCamera('<img src="https://example.invalid">');
  assert.equal(doc.elements["camera-label"].textContent, '<img src="https://example.invalid">');
  assert.equal(doc.elements["camera-label"].innerHTML, undefined);
  view.showSnapshot("blob:test");
  view.clearSnapshot();
  assert.equal(doc.elements["camera-image"].src, undefined);
  assert.equal(doc.elements["camera-image"].hidden, true);
  view.showUnavailable();
  assert.equal(doc.elements["camera-status"].textContent, "Камера недоступна");
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
  assert.deepEqual([...html.matchAll(/<script src="([^"]+)" defer>/g)].map(x => x[1]), ["config.js?v=20261004-r2", "auth.js?v=20261004-r2", "display.js?v=20261004-r2"]);
  assert.match(html, /href="display.css\?v=20261004-r2"/);
  assert.match(html, /default-src 'none'/);
  assert.match(html, /script-src 'self'/);
  assert.match(html, /connect-src 'self'/);
  assert.match(html, /img-src 'self' blob:/);
  assert.doesNotMatch(html, /https?:\/\/|unsafe-inline|unsafe-eval|<iframe|<audio|<video/);
  const css = fs.readFileSync(path.join(__dirname, "../display.css"), "utf8");
  assert.match(css, /object-fit:\s*contain/);
  assert.doesNotMatch(css, /@import|https?:\/\//);
});
