"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { create, createFormatters, resolveLocale, messages } = require("../i18n.js");

test("every supported language has a complete immutable plain-text catalog", () => {
  const keys = Object.keys(messages.en).sort();
  assert.deepEqual(Object.keys(messages).sort(), ["de", "en", "es", "ru"]);
  assert.equal(keys.length, 12);
  for (const [language, catalog] of Object.entries(messages)) {
    assert.deepEqual(Object.keys(catalog).sort(), keys, language);
    assert.ok(Object.isFrozen(catalog));
    for (const text of Object.values(catalog)) {
      assert.equal(typeof text, "string");
      assert.ok(text.trim());
      assert.doesNotMatch(text, /<|>|https?:\/\//);
    }
    assert.equal(create(language).text("unavailable"), catalog.unavailable);
    assert.equal(create(language).text("unknown-secret-or-diagnostic"), "");
    assert.equal(create(language).text("constructor"), "");
  }
});

test("language and regional variants are explicit and canonicalized", () => {
  for (const [value, language, locale] of [
    ["en", "en", "en-US"], ["ru", "ru", "ru-RU"], ["de", "de", "de-DE"], ["es", "es", "es-ES"],
    ["en-gb", "en", "en-GB"], ["DE-at", "de", "de-AT"], ["es-MX", "es", "es-MX"], ["ru-RU", "ru", "ru-RU"]
  ]) {
    assert.deepEqual(resolveLocale(value), { language, locale });
  }
});

test("unsupported and hostile locales fall back without coercion or echoing input", () => {
  for (const value of [undefined, null, "", "fr-FR", "zh-Hans", "../../private", "en-US?token=secret",
    "<script>", "ru_RU", "ru-RU-u-ca-buddhist", "de".repeat(5000), [],
    { toString() { throw new Error("must not call"); } }]) {
    assert.deepEqual(resolveLocale(value), { language: "en", locale: "en-US" });
    assert.equal(create(value).text("title"), "Clock");
  }
});

test("date and clock use the requested language with the configured time zone", () => {
  const instant = new Date("2026-10-15T07:05:00Z");
  const expected = {
    en: "Thursday, October 15", ru: "четверг, 15 октября",
    de: "Donnerstag, 15. Oktober", es: "jueves, 15 de octubre"
  };
  for (const [locale, date] of Object.entries(expected)) {
    const formats = createFormatters(locale, { timeZone: "America/Los_Angeles" });
    assert.equal(formats.time.format(instant), "00:05", locale);
    assert.equal(formats.date.format(instant), date, locale);
  }
  assert.equal(createFormatters("en", { timeZone: "Pacific/Honolulu" }).date.format(instant), "Wednesday, October 14");
});

test("12-hour format includes a localized day period and daylight saving follows the time zone", () => {
  const noon = new Date("2026-10-15T20:05:00Z");
  for (const locale of Object.keys(messages)) {
    const parts = createFormatters(locale, { timeZone: "America/Los_Angeles", hour12: true }).time.formatToParts(noon);
    assert.equal(parts.find(part => part.type === "hour").value, "01");
    assert.ok(parts.find(part => part.type === "dayPeriod").value);
  }
  const clock = createFormatters("en", { timeZone: "America/Los_Angeles" }).time;
  assert.equal(clock.format(new Date("2026-11-01T08:30:00Z")), "01:30");
  assert.equal(clock.format(new Date("2026-11-01T09:30:00Z")), "01:30");
});

test("a reduced Intl locale set falls back for dates while retaining translated interface text", () => {
  function DateTimeFormat(locale, options) { return new Intl.DateTimeFormat(locale, options); }
  DateTimeFormat.supportedLocalesOf = locales => locales.filter(locale => locale === "en-US");
  const sandbox = { Intl: { DateTimeFormat } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../i18n.js"), "utf8"), sandbox);
  assert.equal(sandbox.Show5I18n.createFormatters("ru").locale, "en-US");
  assert.equal(sandbox.Show5I18n.create("ru").text("title"), "Часы");
  assert.equal(sandbox.Show5I18n.createFormatters("ru", { timeZone: "UTC" }).time.format(new Date("2026-10-15T00:05:00Z")), "00:05");
});
