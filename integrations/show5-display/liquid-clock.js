(function (root) {
  "use strict";

  var WIDTH = 800, HEIGHT = 260, POINTS = 54;
  var BANDS = 12, VIEW_DISTANCE = 425;
  var REFLECTION = [20, 5, 16, 9, 24];
  // Adjacent bands overlap slightly so antialiasing at a shared edge cannot
  // reveal a dark seam. The outer bands stop at the actual silhouette.
  var PROFILE = Array.from({ length: BANDS * 2 }, function (_, i) {
    var band = Math.floor(i / 2);
    var edge = i % 2 === 0 ? band - 0.12 : band + 1.12;
    var side = 2 * Math.max(0, Math.min(BANDS, edge)) / BANDS - 1;
    return [side, Math.sqrt(1 - side * side)];
  });
  var RING_STRIDE = PROFILE.length * 2;
  var CAP = [Math.PI / 10, Math.PI / 5, 3 * Math.PI / 10, 2 * Math.PI / 5, Math.PI / 2]
    .map(function (angle) { return [Math.sin(angle), Math.cos(angle)]; });
  var FRAME_MS = 50, MORPH_MS = 1150;
  var STORAGE_KEY = "show5-clock-style";

  // Original glyph centre lines, drawn left to right across a 108 × 166 cell.
  // Uniform arc-length sampling pairs the bends even when different glyphs
  // have different numbers of curves. Closed loops share their endpoints.
  var PATHS = [
    "M54 3 C18 3 8 39 8 83 C8 127 18 163 54 163 C90 163 100 127 100 83 C100 39 90 3 54 3Z",
    "M34 47 C46 38 54 24 63 15 C70 8 74 14 74 29 C74 54 67 108 66 158",
    "M11 38 C18 16 33 4 56 4 C94 4 104 38 96 56 C84 83 48 107 25 129 C7 146 15 160 37 160 C59 160 78 158 101 158",
    "M15 22 C36 0 73 -6 91 17 C109 42 86 61 66 67 C44 74 47 84 66 88 C92 93 109 119 89 145 C69 169 33 167 13 145",
    "M68 5 C51 27 31 60 15 83 C4 99 10 104 31 104 C56 104 80 104 104 104 M80 39 C80 80 80 121 80 161",
    "M99 5 C83 5 62 5 43 5 C23 5 18 13 16 32 C14 50 7 69 22 73 C38 77 59 66 79 73 C108 83 111 129 88 150 C68 170 34 168 12 145",
    "M93 15 C61 -12 25 11 14 49 C2 89 7 139 34 156 C62 174 96 157 101 128 C110 80 59 58 25 85 C18 91 12 99 11 111",
    "M10 6 C29 5 59 5 81 6 C103 7 106 17 94 34 C79 55 47 103 32 159",
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

  function palette(ctx, hue, lighting, specular, flow) {
    var paint = ctx.createLinearGradient(-90, -100 + flow, 85, 95 - flow);
    for (var i = 0; i < 5; i++) {
      var colour = Math.min(96, lighting + (i % 2) * 9 + specular * REFLECTION[i]);
      paint.addColorStop(i / 4, "hsl(" + Math.round((hue + i * 47) % 360) + ", 93%, " + Math.round(colour) + "%)");
    }
    return paint;
  }

  function distance(a, b) {
    return Math.hypot(a[0] - b[0], a[1] - b[1]);
  }

  function closedLoop(line) {
    return distance(line[0], line[line.length - 1]) < 0.001;
  }

  function rollLoop(line, offset) {
    if (!offset) { return line; }
    var shifted = line.slice(offset, -1).concat(line.slice(0, offset));
    return shifted.concat([shifted[0]]);
  }

  function alignLines(from, to) {
    if (from === to || from[0] === from[1] || to[0] === to[1]) { return [from, to]; }
    // Move a closed contour's arbitrary seam to the nearest matching point.
    // For open strokes, match the closer endpoint direction. This prevents
    // opposing samples from collapsing into a sharp knot during the morph.
    var toClosed = closedLoop(to);
    var rollFrom = !toClosed && closedLoop(from);
    var shifts = toClosed || rollFrom ? POINTS - 1 : 1;
    var best = Infinity, source = from, target = to;
    [to, to.slice().reverse()].forEach(function (direction) {
      for (var shift = 0; shift < shifts; shift++) {
        var a = rollFrom ? rollLoop(from, shift) : from;
        var b = toClosed ? rollLoop(direction, shift) : direction;
        var cost = 0;
        for (var p = 0; p < POINTS; p++) {
          var dx = a[p][0] - b[p][0], dy = a[p][1] - b[p][1];
          cost += dx * dx + dy * dy;
        }
        if (cost < best) { best = cost; source = a; target = b; }
      }
    });
    return [source, target];
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
    var last = centres.length - 1;
    var seam = distance(centres[0], centres[last]);
    var closed = seam < 0.001;
    var radii = centres.map(function (point, i) {
      var before = centres[i ? i - 1 : closed ? last - 1 : 0];
      var after = centres[i === last ? (closed ? 1 : last) : i + 1];
      var dx = point[0] - before[0], dy = point[1] - before[1];
      var ex = after[0] - point[0], ey = after[1] - point[1];
      var cross = Math.abs(dx * ey - dy * ex);
      if (cross < 0.001) { return point[3]; }
      // Inner offsets fold when the tube outgrows the local bend. Fit a
      // circumcircle through adjacent centres and leave room for perspective.
      var bend = distance(before, point) * distance(point, after) * distance(before, after) / (2 * cross);
      return Math.min(point[3], 0.86 * bend);
    });
    var total = 0;
    for (var i = 1; i <= last; i++) {
      var length = distance(centres[i - 1], centres[i]);
      total += length;
      radii[i] = Math.min(radii[i], radii[i - 1] + length * 0.42);
    }
    for (var j = last - 1; j >= 0; j--) {
      radii[j] = Math.min(radii[j], radii[j + 1] + distance(centres[j], centres[j + 1]) * 0.42);
    }
    if (closed) { radii[0] = radii[last] = Math.min(radii[0], radii[last]); }
    // One compact vertex buffer keeps the animation from allocating a
    // coordinate pair for every projected point on every frame.
    var rings = new Float32Array((centres.length + (closed ? 0 : 2 * CAP.length)) * RING_STRIDE);
    var cursor = 0;
    var growth = Math.min(1, total / 46);
    var endJoin = Math.max(0, 1 - seam / 20);

    centres.forEach(function (point, i) {
      var before = centres[i ? i - 1 : 0];
      var after = centres[i === last ? last : i + 1];
      var dx = after[0] - before[0], dy = after[1] - before[1], dz = after[2] - before[2];
      // Open ends ease into the shared closed-loop tangent during a morph.
      if (endJoin && (i === 0 || i === last)) {
        var wrapBefore = centres[last - 1], wrapAfter = centres[1];
        dx = mix(dx, wrapAfter[0] - wrapBefore[0], endJoin);
        dy = mix(dy, wrapAfter[1] - wrapBefore[1], endJoin);
        dz = mix(dz, wrapAfter[2] - wrapBefore[2], endJoin);
      }
      var flat = Math.hypot(dx, dy);
      if (flat < 0.001) {
        dx = after[0] - point[0];
        dy = after[1] - point[1];
        dz = after[2] - point[2];
        flat = Math.hypot(dx, dy);
      }
      if (flat < 0.001) { dx = 1; dy = dz = 0; flat = 1; }
      var length = Math.hypot(flat, dz);
      // The tube's cross section uses two axes perpendicular to its tangent.
      var nx = -dy / flat, ny = dx / flat;
      var bx = -ny * dz / length, by = nx * dz / length, bz = flat / length;

      function appendRing(offset, radius) {
        var x = point[0] + dx * offset / length;
        var y = point[1] + dy * offset / length;
        var z = point[2] + dz * offset / length;
        for (var index = 0; index < PROFILE.length; index++) {
          var sample = PROFILE[index];
          var side = sample[0] * radius, front = sample[1] * radius;
          var scale = VIEW_DISTANCE / (VIEW_DISTANCE - z - bz * front);
          rings[cursor++] = (x + nx * side + bx * front) * scale;
          rings[cursor++] = (y + ny * side + by * front) * scale;
        }
      }

      var radius = radii[i] * growth;
      var capLength = radius * (1 - endJoin);
      if (i === 0 && !closed) {
        for (var cap = CAP.length - 1; cap >= 0; cap--) {
          appendRing(-capLength * CAP[cap][0], radius * CAP[cap][1]);
        }
      }
      appendRing(0, radius);
      if (i === last && !closed) {
        CAP.forEach(function (step) { appendRing(capLength * step[0], radius * step[1]); });
      }
    });
    return rings;
  }

  function ribbon(ctx, rings, left, right) {
    ctx.beginPath();
    var start = left * 2;
    var opposite = right * 2;
    ctx.moveTo(rings[start], rings[start + 1]);
    for (var i = start + RING_STRIDE; i < rings.length; i += RING_STRIDE) {
      ctx.lineTo(rings[i], rings[i + 1]);
    }
    for (var j = rings.length - RING_STRIDE + opposite; j >= 0; j -= RING_STRIDE) {
      ctx.lineTo(rings[j], rings[j + 1]);
    }
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
    var edge = PROFILE.length - 1;
    meshes.forEach(function (rings) { ribbon(ctx, rings, 0, edge); ctx.fill(); });
    ctx.restore();

    var paints = [];
    for (var band = 0; band < BANDS; band++) {
      var half = (band + 0.5) / BANDS;
      var side = 2 * half - 1;
      var near = Math.sqrt(1 - side * side);
      var highlight = Math.exp(-55 * Math.pow(half - light, 2));
      var lightness = 27 + 37 * near + 17 * highlight + 9 * Math.pow(half, 4);
      paints.push(palette(ctx, hue + 17 * (1 - near), lightness, highlight, flow));
    }
    meshes.forEach(function (rings) {
      for (var band = 0; band < BANDS; band++) {
        ribbon(ctx, rings, band * 2, band * 2 + 1);
        ctx.fillStyle = paints[band];
        ctx.fill();
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
        !formats.calendar.formatToParts || !root.matchMedia || !root.MutationObserver) { return null; }
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
    var media = root.matchMedia("(prefers-reduced-motion: reduce)");
    var stored = readStyle();
    var style = stored === "classic" || stored === "liquid" ? stored : config && config.clockStyle === "classic" ? "classic" : "liquid";
    var lastSecond, lastArc, drawnStill = null, digits = "", glyphs = [], hourLength = 0, start = 0, timer = null, pageHidden = false;

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
      var arc = (media.matches ? whole : intoMinute.toFixed(2)) + " 60";
      if (arc !== lastArc) {
        secondArc.setAttribute("stroke-dasharray", arc);
        lastArc = arc;
      }
    }

    function paintFrame() {
      timer = null;
      if (!visible()) { return; }
      var frameStart = root.performance.now();
      updateSeconds(Date.now());
      if (!media.matches || drawnStill !== glyphs) {
        render(frameStart);
        drawnStill = media.matches ? glyphs : null;
      }
      if (!media.matches) {
        // Aim for the frame interval including render time. Keep a gap even
        // on a slow WebView so drawing cannot monopolize the event loop.
        var delay = Math.max(16, FRAME_MS - (root.performance.now() - frameStart));
        timer = root.setTimeout(paintFrame, delay);
      }
    }

    function refresh() {
      if (timer !== null && (!visible() || media.matches)) {
        root.clearTimeout(timer);
        timer = null;
      }
      if (timer === null && visible()) { paintFrame(); }
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
          var old = previous[i];
          if (!old) { return { digit: digit, from: to, to: to }; }
          if (old.digit === digit && t === 1) { return { digit: digit, from: old.to, to: old.to }; }
          var from = interpolate(old.from, old.to, t);
          var paired = [alignLines(from[0], to[0]), alignLines(from[1], to[1])];
          return { digit: digit, from: [paired[0][0], paired[1][0]], to: [paired[0][1], paired[1][1]] };
        });
        hourLength = hour.value.length;
      }
      digits = next;
      start = now;
      select();
    }

    function updateDate(instant) {
      var date = {};
      formats.calendar.formatToParts(instant).forEach(function (part) { date[part.type] = part.value; });
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
