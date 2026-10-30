"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { validateConfig, summarizeState, remainingTimer, readJournal, countdown } = require("../room.js");
const config = {
  actions: [{ id: "home", label: "Clock", script: "script.room_one_room_home" }],
  status: [{ entityId: "sensor.temperature", label: "Temperature" }, { entityId: "weather.home", label: "Outside", attribute: "temperature" }],
  timerEntity: "timer.room_one_room_timer", reminderEntity: "sensor.room_one_room_reminder",
  dismissScript: "script.room_one_room_dismiss", offline: true, photos: ["photos/garden.jpg"]
};

test("room is optional; configured actions bind exactly to this endpoint without arbitrary service data", () => {
  assert.equal(validateConfig(undefined), null);
  const result = validateConfig(config, "room_one");
  assert.ok(Object.isFrozen(result));
  assert.equal(result.actions[0].script, "script.room_one_room_home");
  assert.deepEqual(result.entities, ["sensor.temperature", "weather.home", "timer.room_one_room_timer", "sensor.room_one_room_reminder"]);
  for (const action of [
    { ...config.actions[0], script: "script.room_two_room_home" },
    { ...config.actions[0], data: { command: "anything" } },
    { ...config.actions[0], id: "dismiss" }, { ...config.actions[0], label: "" }
  ]) { assert.throws(() => validateConfig({ actions: [action] }, "room_one")); }
  assert.throws(() => validateConfig(config, ""));
  assert.throws(() => validateConfig({ actions: Array(7).fill(config.actions[0]) }, "room_one"));
  assert.throws(() => validateConfig({ dismissScript: "script.unrelated" }, "room_one"));
});

test("state and photo allowlists reject remote URLs, paths, duplicates and arbitrary attributes", () => {
  for (const photos of [["https://example.invalid/x.jpg"], ["photos/../config.js"], ["photos/a.jpg?token=secret"], ["photos/a.svg"], ["photos/a.jpg", "photos/a.jpg"], Array(13).fill("photos/a.jpg")]) {
    assert.throws(() => validateConfig({ photos }, "room_one"));
  }
  assert.throws(() => validateConfig({ status: [{ entityId: "script.a", label: "A" }] }, "room_one"));
  assert.throws(() => validateConfig({ status: [{ entityId: "sensor.a", label: "A", attribute: "access_token" }] }, "room_one"));
  for (const staleSeconds of [1, 3601, "120", NaN]) { assert.throws(() => validateConfig({ staleSeconds }, "room_one")); }
});

test("readings distinguish a stale transport, unknown state, valid zero and weather attributes", () => {
  const reading = config.status[0];
  const value = { entity_id: reading.entityId, state: "0", last_updated: "2025-01-01T00:00:00Z", attributes: { unit_of_measurement: "W" } };
  assert.deepEqual(summarizeState(value, reading, 1000, 2000, 30), { value: "0 W", stale: false, sourceUpdatedAt: value.last_updated });
  assert.equal(summarizeState(value, reading, 1000, 32000, 30).stale, true);
  assert.deepEqual(summarizeState({ ...value, state: "unavailable" }, reading, 1000, 2000, 30), { value: "—", stale: true });
  assert.deepEqual(summarizeState({ ...value, entity_id: "sensor.other" }, reading, 1000, 2000, 30), { value: "—", stale: true });
  assert.equal(summarizeState({ entity_id: "weather.home", state: "unknown", attributes: { temperature: 23, temperature_unit: "°C" } }, config.status[1], 1000, 2000, 30).value, "23 °C");
});

test("timer uses absolute deadlines, reconciles overdue state and never invents a paused countdown", () => {
  const value = { state: "active", attributes: { finishes_at: "2026-10-29T10:01:00Z" } };
  assert.equal(remainingTimer(value, Date.parse("2026-10-29T10:00:00Z")), 60);
  assert.equal(remainingTimer(value, Date.parse("2026-10-29T11:00:00Z")), 0);
  assert.equal(remainingTimer({ ...value, state: "paused" }, 0), null);
  assert.equal(remainingTimer({ state: "active", attributes: { finishes_at: "bad" } }, 0), null);
  assert.equal(countdown(125), "2:05");
  const now = Date.parse("2026-10-29T10:00:00Z"), journal = { version: 1, started: now - 600000, end: now - 300000 };
  assert.deepEqual(readJournal(JSON.stringify(journal), now), journal);
  for (const item of [
    { ...journal, started: now + 120000 }, { ...journal, end: now + 3600001 },
    { ...journal, version: 2 }, { ...journal, token: "must-not-persist" },
    { ...journal, started: now - 100000000, end: now - 90000000 }
  ]) { assert.equal(readJournal(JSON.stringify(item), now), null); }
  assert.equal(readJournal("not json", now), null);
});

function workerHarness() {
  const handlers = {}, stores = new Map(), requests = [], removed = [];
  let offline = false, failPath = null, rejectWrites = false, cacheUnavailable = false, liveContent = "synthetic static content";
  function cacheFor(name) {
    if (!stores.has(name)) stores.set(name, new Map());
    const stored = stores.get(name);
    return {
      async put(key, response) {
        if (rejectWrites) { throw new Error("Cache storage quota exceeded"); }
        stored.set(typeof key === "string" ? key : key.url, response.clone());
      },
      async match(key) { const value = stored.get(typeof key === "string" ? key : key.url); return value && value.clone(); },
      async keys() { return [...stored.keys()].map(url => ({ url })); },
      async delete(key) { removed.push(typeof key === "string" ? key : key.url); return stored.delete(typeof key === "string" ? key : key.url); }
    };
  }
  const context = {
    URL, Set, Response, Blob, AbortController, setTimeout, clearTimeout,
    self: { registration: { scope: "https://ha.example.invalid/local/room/" },
      location: { href: "https://ha.example.invalid/local/room/offline-worker.js?shell=index-r12.html" },
      addEventListener(type, callback) { handlers[type] = callback; }, async skipWaiting() {}, clients: { async claim() {} } },
    caches: { async open(name) { if (cacheUnavailable) { throw new Error("Cache storage unavailable"); } return cacheFor(name); },
      async keys() { return [...stores.keys()]; }, async delete(name) { return stores.delete(name); } },
    async fetch(input) {
      const url = typeof input === "string" ? input : input.url; requests.push(url);
      if (offline || failPath && url.endsWith(failPath)) { throw new Error("offline"); }
      return new Response(liveContent, { headers: { "Content-Type": url.endsWith(".jpg") ? "image/jpeg" : "text/javascript" } });
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../offline-worker.js"), "utf8"), context);
  async function event(type, value = {}) { let result; handlers[type]({ ...value, waitUntil(promise) { result = promise; }, respondWith(promise) { result = promise; } }); return result; }
  return { event, get stored() { return [...stores.entries()].find(([name]) => name.includes(":content:"))[1]; },
    stores, requests, removed, offline(value) { offline = value; }, fail(path) { failPath = path; },
    rejectWrites(value) { rejectWrites = value; }, failCacheOpen(value) { cacheUnavailable = value; },
    liveContent(value) { liveContent = value; } };
}

test("offline cache restores only its own shell and never intercepts API, media, auth or foreign paths", async () => {
  const h = workerHarness(); await h.event("install");
  assert.equal(h.stored.size, 9); h.offline(true);
  const response = await h.event("fetch", { request: new Request("https://ha.example.invalid/local/room/index-r12.html?camera=front") });
  assert.equal(await response.text(), "synthetic static content");
  for (const url of ["https://ha.example.invalid/api/states/sensor.a", "https://ha.example.invalid/api/camera_proxy/camera.front", "https://ha.example.invalid/local/other/index-r12.html", "https://foreign.invalid/local/room/index-r12.html"]) {
    assert.equal(await h.event("fetch", { request: new Request(url) }), undefined);
  }
  assert.equal(await h.event("fetch", { request: new Request("https://ha.example.invalid/local/room/config.js", { headers: { Authorization: "Bearer private" } }) }), undefined);
  assert.ok([...h.stored.keys()].every(url => url.startsWith("https://ha.example.invalid/local/room/")));
});

test("only configured photos enter offline cache and removed photos are purged", async () => {
  const h = workerHarness(); await h.event("install");
  await h.event("message", { data: { type: "CACHE_PHOTOS", photos: ["photos/garden.jpg", "photos/room.jpg"] } });
  assert.equal(h.stored.size, 11);
  await h.event("message", { data: { type: "CACHE_PHOTOS", photos: ["photos/room.jpg"] } });
  assert.equal(h.stored.size, 10); assert.ok(h.removed.includes("https://ha.example.invalid/local/room/photos/garden.jpg"));
  const before = h.requests.length;
  await h.event("message", { data: { type: "CACHE_PHOTOS", photos: ["https://foreign.invalid/private.jpg"] } });
  assert.equal(h.requests.length, before);
});

test("a cache write failure cannot replace a successful live response with stale content", async () => {
  const h = workerHarness(); await h.event("install");
  const url = "https://ha.example.invalid/local/room/config.js";
  h.liveContent("new live configuration"); h.rejectWrites(true);
  const response = await h.event("fetch", { request: new Request(url) });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "new live configuration");
  assert.equal(await h.stored.get(url).clone().text(), "synthetic static content");
});

test("a cache write failure still serves a successful live response when no cached entry exists", async () => {
  const h = workerHarness(); await h.event("install");
  const url = "https://ha.example.invalid/local/room/config.js";
  h.stored.delete(url); h.liveContent("live uncached configuration"); h.rejectWrites(true);
  const response = await h.event("fetch", { request: new Request(url) });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "live uncached configuration");
  assert.equal(h.stored.has(url), false);
});

test("unavailable active-cache storage does not block a successful live response or cache generic photos", async () => {
  const h = workerHarness(); await h.event("install");
  h.failCacheOpen(true); h.liveContent("fresh response without cache storage");
  const url = "https://ha.example.invalid/local/room/config.js";
  const response = await h.event("fetch", { request: new Request(url) });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "fresh response without cache storage");
  const photoURL = "https://ha.example.invalid/local/room/photos/uncached.jpg";
  const photo = await h.event("fetch", { request: new Request(photoURL) });
  assert.equal(photo.status, 200);
  assert.equal(await photo.text(), "fresh response without cache storage");
  assert.equal(h.stored.has(photoURL), false);
});

test("an evicted active-cache manifest still permits live static requests", async () => {
  const h = workerHarness(); await h.event("install");
  for (const name of h.stores.keys()) { if (name.endsWith(":manifest")) { h.stores.delete(name); } }
  h.liveContent("fresh response after cache eviction");
  const response = await h.event("fetch", { request: new Request("https://ha.example.invalid/local/room/config.js") });
  assert.equal(await response.text(), "fresh response after cache eviction");
});


test("failed offline upgrade preserves the complete previous generation", async () => {
  const h = workerHarness(); await h.event("install");
  const original = [...h.stores.keys()].find(name => name.includes(":content:"));
  h.fail("auth.js");
  await assert.rejects(h.event("install"), /offline/);
  assert.deepEqual([...h.stores.keys()].filter(name => name.includes(":content:")), [original]);
  h.offline(true);
  const response = await h.event("fetch", { request: new Request("https://ha.example.invalid/local/room/index-r12.html") });
  assert.equal(await response.text(), "synthetic static content");
});
