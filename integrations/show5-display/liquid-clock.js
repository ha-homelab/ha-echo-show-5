(function (root) {
  "use strict";

  var WIDTH = 800, HEIGHT = 260, POINTS = 54;
  var BANDS = 10, VIEW_DISTANCE = 425;
  var REFLECTION = [20, 5, 16, 9, 24];
  var PROFILE = Array.from({ length: BANDS + 1 }, function (_, i) {
    var side = (2 * i / BANDS) - 1;
    return [side, Math.sqrt(1 - side * side)];
  });
  var FRAME_MS = 50, MORPH_MS = 1150;
  var STORAGE_KEY = "show5-clock-style";

  // Original glyph centre lines, drawn left to right across a 108 × 166 cell.
  // Uniform arc-length sampling pairs the bends even when different glyphs
  // have different numbers of curves. Closed loops share their endpoints.
  var PATHS = [
    "M54 3 C18 3 8 39 8 83 C8 127 18 163 54 163 C90 163 100 127 100 83 C100 39 90 3 54 3Z",
    "M23 35 C40 30 55 8 60 10 C66 12 62 111 62 161",
    "M9 38 C15 17 30 3 54 3 C92 3 107 33 94 60 C81 88 26 110 11 159 C42 161 74 161 102 161",
    "M13 20 C32 1 70 -5 90 13 C117 38 82 74 50 77 C92 68 112 113 91 142 C72 169 28 171 10 146",
    "M68 5 C52 30 22 68 8 103 C34 105 76 104 104 104 M80 40 C80 84 80 122 80 161",
    "M98 5 C71 5 47 5 20 6 C17 29 14 55 13 77 C33 59 69 60 86 75 C109 94 107 130 89 149 C69 170 29 169 10 145",
    "M93 15 C61 -12 25 11 14 49 C2 89 7 139 34 156 C62 174 96 157 101 128 C110 80 59 58 25 85 C18 91 12 99 11 111",
    "M9 6 C39 5 75 5 101 6 C88 35 76 49 60 79 C44 109 35 134 32 162",
    "M54 79 C18 69 9 50 13 33 C18 11 33 3 54 3 C90 3 107 32 90 56 C83 67 68 75 54 79 C23 87 4 104 9 130 C13 151 30 163 54 163 C80 163 100 151 100 128 C100 103 82 89 54 79Z",
    "M15 149 C47 177 83 154 94 116 C107 75 101 26 74 9 C46 -9 12 8 7 37 C-2 85 49 108 83 80 C90 74 96 65 97 54"
  ];

  function sample(document, d) {
    var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    var length = path.getTotalLength();
    return Array.from({ length: POINTS }, function (_, i) {
      var point = path.getPointAtLength(i * length / (POINTS - 1));
      return [point.x, point.y];
    });
  }

  function mix(a, b, t) { return a + (b - a) * t; }

  function blend(from, to, t) {
    if (from === to || t >= 1) { return to; }
    return to.map(function (point, i) {
      return [mix(from[i][0], point[0], t), mix(from[i][1], point[1], t)];
    });
  }

  function interpolate(from, to, t) {
    return from.map(function (line, i) { return blend(line, to[i], t); });
  }

  function progress(age) {
    var t = Math.max(0, Math.min(age / MORPH_MS, 1));
    return t * t * (3 - 2 * t);
  }

  function project(x, y, z) {
    var scale = VIEW_DISTANCE / (VIEW_DISTANCE - z);
    return [x * scale, y * scale];
  }

  function palette(ctx, hue, lighting, specular, flow) {
    var paint = ctx.createLinearGradient(-90, -100 + flow, 85, 95 - flow);
    for (var i = 0; i < 5; i++) {
      var colour = Math.min(96, lighting + (i % 2) * 9 + specular * REFLECTION[i]);
      paint.addColorStop(i / 4, "hsl(" + Math.round((hue + i * 47) % 360) + ", 93%, " + Math.round(colour) + "%)");
    }
    return paint;
  }

  function ringsFor(line, wave) {
    var yaw = 0.27 * Math.sin(wave * 0.59);
    var pitch = 0.18 * Math.cos(wave * 0.73);
    var cy = Math.cos(yaw), sy = Math.sin(yaw);
    var cp = Math.cos(pitch), sp = Math.sin(pitch);
    var centres = line.map(function (point) {
      var u = point[0], v = point[1];
      var x = u - 54 + 10 * Math.sin(v * 0.031 + wave);
      var y = v - 82 + 7 * Math.sin(u * 0.043 - wave);
      var z = 22 * Math.sin(v * 0.025 - wave) + 9 * Math.cos(u * 0.044 + wave);
      var turnedZ = cy * z - sy * x;
      return [cy * x + sy * z, cp * y - sp * turnedZ, sp * y + cp * turnedZ,
        21 + 3.6 * Math.sin(v * 0.042 + u * 0.022 - wave)];
    });
    var closed = Math.hypot(centres[0][0] - centres[centres.length - 1][0],
      centres[0][1] - centres[centres.length - 1][1]) < 1;
    var rings = [];

    centres.forEach(function (point, i) {
      var before = centres[i ? i - 1 : closed ? centres.length - 2 : 0];
      var after = centres[i === centres.length - 1 ? (closed ? 1 : i) : i + 1];
      var dx = after[0] - before[0], dy = after[1] - before[1], dz = after[2] - before[2];
      var flat = Math.hypot(dx, dy) || 1;
      var length = Math.hypot(flat, dz);
      // The tube's cross section uses two axes perpendicular to its tangent.
      var nx = -dy / flat, ny = dx / flat;
      var bx = -ny * dz / length, by = nx * dz / length, bz = flat / length;

      function ring(offset, radius) {
        var x = point[0] + dx * offset / length;
        var y = point[1] + dy * offset / length;
        var z = point[2] + dz * offset / length;
        return PROFILE.map(function (sample) {
          var side = sample[0] * radius, front = sample[1] * radius;
          return project(x + nx * side + bx * front, y + ny * side + by * front, z + bz * front);
        });
      }

      var radius = point[3];
      // Extend a hemisphere from each open end without rounding across a loop.
      if (i === 0 && !closed) {
        rings.push(ring(-radius, 0), ring(-0.87 * radius, 0.5 * radius), ring(-0.5 * radius, 0.87 * radius));
      }
      rings.push(ring(0, radius));
      if (i === centres.length - 1 && !closed) {
        rings.push(ring(0.5 * radius, 0.87 * radius), ring(0.87 * radius, 0.5 * radius), ring(radius, 0));
      }
    });
    return rings;
  }

  function ribbon(ctx, rings, left, right) {
    ctx.beginPath();
    ctx.moveTo(rings[0][left][0], rings[0][left][1]);
    for (var i = 1; i < rings.length; i++) { ctx.lineTo(rings[i][left][0], rings[i][left][1]); }
    for (var j = rings.length - 1; j >= 0; j--) { ctx.lineTo(rings[j][right][0], rings[j][right][1]); }
    ctx.closePath();
  }

  function tube(ctx, paths, x, hue, wave) {
    ctx.save();
    ctx.translate(x + 54, 124 + 6 * Math.sin(wave * 0.8));
    var light = 0.43 + 0.27 * Math.sin(wave * 0.75);
    var flow = 36 * Math.sin(wave * 0.85);
    var meshes = paths.map(function (line) { return ringsFor(line, wave); });

    // Cast shadows anchor the moving forms. Each coloured band is projected
    // from the curved surface at a different depth and lighting angle.
    ctx.save();
    ctx.translate(6, 11);
    ctx.fillStyle = "rgba(0, 0, 12, 0.60)";
    meshes.forEach(function (rings) { ribbon(ctx, rings, 0, BANDS); ctx.fill(); });
    ctx.restore();

    var paints = PROFILE.slice(0, BANDS).map(function (sample, band) {
      var near = (sample[1] + PROFILE[band + 1][1]) / 2;
      var half = (band + 0.5) / BANDS;
      var highlight = Math.exp(-70 * Math.pow(half - light, 2));
      var lightness = 27 + 37 * near + 17 * highlight + 9 * Math.pow(half, 4);
      return palette(ctx, hue + 17 * (1 - near), lightness, highlight, flow);
    });
    meshes.forEach(function (rings) {
      ribbon(ctx, rings, 0, BANDS);
      ctx.fillStyle = paints[0];
      ctx.fill();
      for (var band = 0; band < BANDS; band++) {
        ribbon(ctx, rings, band, band + 1);
        ctx.fillStyle = ctx.strokeStyle = paints[band];
        ctx.fill();
        // Cover subpixel gaps between neighbouring bands on low-DPI displays.
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }
    });
    ctx.restore();
  }

  function jewel(ctx, x, y, hue, radius) {
    var light = ctx.createRadialGradient(x - 4, y - 5, 1, x, y, radius);
    light.addColorStop(0, "#fff5ff");
    light.addColorStop(0.4, "hsl(" + Math.round(hue) + ", 100%, 74%)");
    light.addColorStop(1, "hsl(" + Math.round(hue + 35) + ", 90%, 25%)");
    ctx.fillStyle = light;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  function readStyle() {
    try { return root.localStorage.getItem(STORAGE_KEY); } catch (_) { return null; }
  }

  function create(document, config, language, formats) {
    var canvas = document.getElementById("liquid-clock");
    var clock = document.getElementById("clock-view");
    var button = document.getElementById("clock-style");
    var period = document.getElementById("clock-period");
    var seconds = document.getElementById("clock-seconds-number");
    var secondArc = document.getElementById("clock-seconds-arc");
    if (!canvas || !button || !period || !seconds || !secondArc || !formats.time.formatToParts ||
        !root.matchMedia || !root.MutationObserver) { return null; }
    var context;
    try { context = canvas.getContext("2d"); } catch (_) { return null; }
    if (!context) { return null; }

    // Four has a separate stem. Collapse a second path to one small point in
    // other glyphs so it can grow or melt without drawing a connecting slash.
    var paths;
    try {
      paths = PATHS.map(function (d) {
        var lines = d.split(/ (?=M)/).map(function (line) { return sample(document, line); });
        if (lines.length === 1) { lines.push(Array(POINTS).fill(lines[0][Math.floor(POINTS * 0.4)])); }
        return lines;
      });
    } catch (_) { return null; }

    var label = document.getElementById("clock-style-name");
    var calendarDay = document.getElementById("clock-calendar-day");
    var calendarWeekday = document.getElementById("clock-calendar-weekday");
    var calendarMonth = document.getElementById("clock-calendar-month");
    var calendarFormat = new Intl.DateTimeFormat(formats.locale, {
      timeZone: formats.date.resolvedOptions().timeZone, weekday: "long",
      day: "numeric", month: "long", year: "numeric"
    });
    var media = root.matchMedia("(prefers-reduced-motion: reduce)");
    var stored = readStyle();
    var style = stored === "classic" || stored === "liquid" ? stored : config && config.clockStyle === "classic" ? "classic" : "liquid";
    var lastSecond, digits = "", glyphs = [], hourLength = 0, start = 0, timer = null, pageHidden = false;

    function visible() {
      return style === "liquid" && glyphs.length > 0 && !document.hidden && !pageHidden &&
        !clock.hidden && !clock.classList.contains("room-open");
    }

    function render(time) {
      var phase = media.matches ? 0 : time / 2450;
      var hue = (phase * 53 + 207) % 360;
      var morph = media.matches ? 1 : progress(time - start);
      var spacing = 166, separator = 63;
      var x = (WIDTH - ((glyphs.length - 1) * spacing + 108 + separator)) / 2;
      context.clearRect(0, 0, WIDTH, HEIGHT);
      glyphs.forEach(function (glyph, i) {
        if (i === hourLength) {
          jewel(context, x - (spacing - 108 - separator) / 2, 100, (hue + 82) % 360, 12);
          jewel(context, x - (spacing - 108 - separator) / 2, 158, (hue + 118) % 360, 13);
          x += separator;
        }
        var wave = phase * 1.6 + i * 1.2;
        var shape = interpolate(glyph.from, glyph.to, morph);
        var stem = shape[1];
        if (stem[0] === stem[1]) { shape.pop(); }
        tube(context, shape, x, (hue + i * 78) % 360, wave);
        x += spacing;
      });
    }

    function updateSeconds(now) {
      var intoMinute = (now % 60000 + 60000) % 60000 / 1000;
      var whole = Math.floor(intoMinute);
      if (whole !== lastSecond) {
        seconds.textContent = (whole < 10 ? "0" : "") + whole;
        lastSecond = whole;
      }
      secondArc.setAttribute("stroke-dasharray", (media.matches ? whole : intoMinute.toFixed(2)) + " 60");
    }

    function refresh() {
      if (timer !== null) { root.clearTimeout(timer); timer = null; }
      if (!visible()) { return; }
      updateSeconds(Date.now());
      render(root.performance.now());
      if (!media.matches) { timer = root.setTimeout(refresh, FRAME_MS); }
    }

    function select() {
      label.textContent = language.text(style === "liquid" ? "clockLiquid" : "clockClassic");
      button.setAttribute("aria-label", language.text("clockStyle") + ": " + label.textContent);
      clock.classList.toggle("liquid-style", style === "liquid" && glyphs.length > 0);
      refresh();
    }

    button.addEventListener("click", function () {
      style = style === "liquid" ? "classic" : "liquid";
      try { root.localStorage.setItem(STORAGE_KEY, style); } catch (_) { /* Keep the session choice. */ }
      select();
    });
    button.hidden = false;
    new root.MutationObserver(refresh).observe(clock, { attributes: true, attributeFilter: ["hidden", "class"] });
    document.addEventListener("visibilitychange", refresh);
    root.addEventListener("pagehide", function () { pageHidden = true; refresh(); });
    root.addEventListener("pageshow", function () { pageHidden = false; refresh(); });
    if (typeof media.addEventListener === "function") { media.addEventListener("change", refresh); }
    else { media.addListener(refresh); }
    select();

    function updateTime(formatter, instant) {
      var parts = formatter.formatToParts(instant);
      var hour = parts.find(function (part) { return part.type === "hour"; });
      var minute = parts.find(function (part) { return part.type === "minute"; });
      var day = parts.find(function (part) { return part.type === "dayPeriod"; });
      var next = hour && minute ? hour.value + minute.value : "";
      period.textContent = day ? day.value : "";
      if (next === digits) { return; }
      var now = root.performance.now();
      if (!/^[0-9]{3,4}$/.test(next)) {
        glyphs = [];
      } else {
        var previous = glyphs.length === next.length ? glyphs : [];
        var t = media.matches || !visible() ? 1 : progress(now - start);
        glyphs = next.split("").map(function (digit, i) {
          var to = paths[Number(digit)];
          var from = previous[i] ? interpolate(previous[i].from, previous[i].to, t) : to;
          return { from: from, to: to };
        });
        hourLength = hour.value.length;
      }
      digits = next;
      start = now;
      select();
    }

    function updateDate(instant) {
      var date = {};
      calendarFormat.formatToParts(instant).forEach(function (part) { date[part.type] = part.value; });
      calendarDay.textContent = date.day;
      calendarWeekday.textContent = date.weekday;
      calendarMonth.textContent = date.month + " · " + date.year;
    }

    return {
      updateTime: updateTime,
      updateDate: updateDate,
      tick: function (instant) {
        if (media.matches && visible()) { updateSeconds(instant.getTime()); }
      }
    };
  }

  root.Show5LiquidClock = Object.freeze({ create: create });
})(typeof globalThis !== "undefined" ? globalThis : window);
