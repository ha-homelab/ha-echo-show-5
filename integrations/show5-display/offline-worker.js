/* Optional scoped static-page cache. Never intercept HA API or stream traffic. */
"use strict";
var scopeURL = new URL(self.registration.scope);
var shell = new URL(self.location.href).searchParams.get("shell");
if (!/^[A-Za-z0-9_.-]+\.html$/.test(shell || "")) { shell = "index.html"; }
var cacheName = "show5-room-r13:" + scopeURL.pathname;
var pointerKey = new URL(".offline-generation", scopeURL).href;
var staticNames = [shell, "display.css", "i18n.js", "room.js", "stream.js", "auth.js", "display.js", "blank-video.svg", "config.js"];
var photoUpdate = Promise.resolve();

async function activeCache() {
  var manifest = await caches.open(cacheName + ":manifest");
  var pointer = await manifest.match(pointerKey);
  var name = pointer && await pointer.text();
  if (!name || name.length > 512 || !name.startsWith(cacheName + ":content:")) { throw new Error("No complete offline shell"); }
  return caches.open(name);
}

function cachePath(url) {
  if (url.origin !== scopeURL.origin || !url.pathname.startsWith(scopeURL.pathname)) { return null; }
  var name = url.pathname.slice(scopeURL.pathname.length);
  if (staticNames.indexOf(name) < 0 && !/^photos\/[a-zA-Z0-9_-]{1,80}\.(jpg|jpeg|png|webp)$/.test(name)) { return null; }
  return name;
}

async function boundedResponse(response, limit, photo) {
  if (!response.ok || response.redirected || response.type === "opaque" || !response.body) { throw new Error("Static response unavailable"); }
  var type = (response.headers.get("content-type") || "").split(";")[0];
  if (photo && !/^image\/(jpeg|png|webp)$/.test(type)) { throw new Error("Invalid photo type"); }
  var reader = response.body.getReader(), size = 0, chunks = [];
  try {
    while (true) {
      var chunk = await reader.read();
      if (chunk.done) { break; }
      size += chunk.value.byteLength;
      if (size > limit) { throw new Error("Static resource too large"); }
      chunks.push(chunk.value);
    }
  } finally { try { await reader.cancel(); } catch (_) {} reader.releaseLock(); }
  return new Response(new Blob(chunks), { status: response.status, headers: response.headers });
}

async function network(name) {
  var controller = new AbortController();
  var deadline = setTimeout(function () { controller.abort(); }, 4000);
  try {
    var response = await fetch(new URL(name, scopeURL).href, {
      credentials: "omit", redirect: "error", cache: "no-store", signal: controller.signal
    });
    return await boundedResponse(response, name.startsWith("photos/") ? 2 * 1024 * 1024 : 512 * 1024, name.startsWith("photos/"));
  } finally { clearTimeout(deadline); }
}

self.addEventListener("install", function (event) {
  event.waitUntil((async function () {
    var generation = cacheName + ":content:" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
    var cache = await caches.open(generation);
    // Publish one pointer only after every resource is present. Failed installs
    // cannot overwrite the current complete offline generation.
    try {
      for (var name of staticNames) { await cache.put(new URL(name, scopeURL).href, await network(name)); }
      var manifest = await caches.open(cacheName + ":manifest");
      await manifest.put(pointerKey, new Response(generation));
    } catch (error) { await caches.delete(generation); throw error; }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", function (event) {
  event.waitUntil((async function () {
    var manifest = await caches.open(cacheName + ":manifest");
    var pointer = await manifest.match(pointerKey), active = pointer && await pointer.text();
    var names = await caches.keys();
    for (var name of names) {
      if (name.startsWith(cacheName + ":content:") && name !== active) { await caches.delete(name); }
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", function (event) {
  var request = event.request, url = new URL(request.url), name = cachePath(url);
  if (request.method !== "GET" || request.headers.has("Authorization") || !name) { return; }
  event.respondWith((async function () {
    var cache = await activeCache(), key = new URL(name, scopeURL).href;
    // Photos are cached only after explicit configuration, never on generic GET.
    if (name.startsWith("photos/")) { return (await cache.match(key)) || fetch(request); }
    try { var response = await network(name); await cache.put(key, response.clone()); return response; }
    catch (_) { var cached = await cache.match(key); if (cached) { return cached; } return Response.error(); }
  })());
});

self.addEventListener("message", function (event) {
  var data = event.data;
  if (!data || data.type !== "CACHE_PHOTOS" || !Array.isArray(data.photos) || data.photos.length > 12 ||
      data.photos.some(function (name) { return typeof name !== "string" || !/^photos\/[a-zA-Z0-9_-]{1,80}\.(jpg|jpeg|png|webp)$/.test(name); })) { return; }
  var photoNames = new Set(data.photos);
  photoUpdate = photoUpdate.catch(function () {}).then(async function () {
    var cache = await activeCache(), requests = await cache.keys();
    for (var request of requests) {
      var name = cachePath(new URL(request.url));
      if (name && name.startsWith("photos/") && !photoNames.has(name)) { await cache.delete(request); }
    }
    for (var name of photoNames) {
      try { await cache.put(new URL(name, scopeURL).href, await network(name)); } catch (_) { /* Existing cached photo remains useful offline. */ }
    }
  });
  event.waitUntil(photoUpdate);
});
