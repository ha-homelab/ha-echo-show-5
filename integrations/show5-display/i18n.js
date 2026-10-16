(function (root) {
  "use strict";

  // Static, same-origin resources only: choosing a language never fetches code,
  // sends device language information elsewhere, or changes camera/event IDs.
  var DEFAULT_LOCALES = Object.freeze({ en: "en-US", ru: "ru-RU", de: "de-DE", es: "es-ES" });
  var MESSAGES = Object.freeze({
    en: Object.freeze({
      title: "Clock", display: "Clock and camera", clock: "Clock", camera: "Camera",
      cameraImage: "Camera image", cameraVideo: "Camera video",
      loading: "Loading camera…", connecting: "Connecting to camera…",
      delayed: "Update delayed", unavailable: "Camera unavailable", front: "Front", porch: "Porch"
    }),
    ru: Object.freeze({
      title: "Часы", display: "Часы и камера", clock: "Часы", camera: "Камера",
      cameraImage: "Изображение с камеры", cameraVideo: "Видео с камеры",
      loading: "Загрузка камеры…", connecting: "Подключение к камере…",
      delayed: "Обновление задерживается", unavailable: "Камера недоступна", front: "Перед домом", porch: "Крыльцо"
    }),
    de: Object.freeze({
      title: "Uhr", display: "Uhr und Kamera", clock: "Uhr", camera: "Kamera",
      cameraImage: "Kamerabild", cameraVideo: "Kameravideo",
      loading: "Kamera wird geladen…", connecting: "Verbindung zur Kamera…",
      delayed: "Aktualisierung verzögert", unavailable: "Kamera nicht verfügbar", front: "Vor dem Haus", porch: "Veranda"
    }),
    es: Object.freeze({
      title: "Reloj", display: "Reloj y cámara", clock: "Reloj", camera: "Cámara",
      cameraImage: "Imagen de la cámara", cameraVideo: "Vídeo de la cámara",
      loading: "Cargando cámara…", connecting: "Conectando con la cámara…",
      delayed: "Actualización retrasada", unavailable: "Cámara no disponible", front: "Entrada", porch: "Porche"
    })
  });

  function resolveLocale(value) {
    // Accept only the documented language/region syntax. Do not coerce objects
    // or echo arbitrary input into page attributes, messages or resource URLs.
    var match = typeof value === "string" && /^([a-z]{2})(?:-([a-z]{2}))?$/i.exec(value);
    var language = match ? match[1].toLowerCase() : "en";
    if (!Object.prototype.hasOwnProperty.call(DEFAULT_LOCALES, language)) { language = "en"; match = null; }
    var locale = match && match[2] ? language + "-" + match[2].toUpperCase() : DEFAULT_LOCALES[language];
    return Object.freeze({ language: language, locale: locale });
  }

  function create(value) {
    var selected = resolveLocale(value);
    return Object.freeze({
      language: selected.language,
      locale: selected.locale,
      text: function (key) {
        return Object.prototype.hasOwnProperty.call(MESSAGES.en, key) ? MESSAGES[selected.language][key] : "";
      }
    });
  }

  function createFormatters(value, options) {
    options = options || {};
    var locale = resolveLocale(value).locale;
    // Reduced Android Intl builds can lack a locale. Keep a usable clock and
    // explicit formatter locale; UI translations do not depend on OS packs.
    if (Intl.DateTimeFormat.supportedLocalesOf([locale]).length === 0) { locale = "en-US"; }
    var time = new Intl.DateTimeFormat(locale, {
      timeZone: options.timeZone, hour: "2-digit", minute: "2-digit", hourCycle: options.hour12 ? "h12" : "h23"
    });
    var date = new Intl.DateTimeFormat(locale, {
      timeZone: options.timeZone, weekday: "long", day: "numeric", month: "long"
    });
    return Object.freeze({ locale: time.resolvedOptions().locale, time: time, date: date });
  }

  var exported = Object.freeze({ create: create, createFormatters: createFormatters,
    resolveLocale: resolveLocale, messages: MESSAGES });
  if (typeof module !== "undefined" && module.exports) { module.exports = exported; }
  else { root.Show5I18n = exported; }
})(typeof globalThis !== "undefined" ? globalThis : window);
