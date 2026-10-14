/*! motion.js | part of filmwright | MIT License | Copyright (c) 2026 the filmwright contributors
 *
 * A small, deterministic, seek-only animation timeline for rendering video frames from SVG/HTML pages.
 * It exposes the subset of the widely used `gsap` API that filmwright's templates need, under the global
 * name `motion` (also aliased as `gsap`, so templates written in that familiar style run unchanged):
 *
 *   motion.set(targets, vars)
 *   motion.to(targets, vars)                    (renders immediately to the end: a convenience, not used for video)
 *   motion.timeline({paused: true})  ->  tl
 *   tl.to(targets, vars, position) / tl.from(...) / tl.fromTo(targets, fromVars, toVars, position)
 *   tl.set(targets, vars, position) / tl.add(fnOrTimeline, position) / tl.call(fn, args, position)
 *   tl.seek(seconds) / tl.duration() / tl.progress(p) / tl.time()
 *
 * vars: duration (default 0.5), delay, ease (default "power1.out"), repeat, repeatDelay, yoyo, stagger,
 *   keyframes (array of vars, played one after another), onStart, onUpdate, onComplete, snap,
 *   attr: {...} (attributes), svgOrigin "x y", transformOrigin ("50% 50%", "center", "left top", "12px 40px"),
 *   transforms x, y, rotation (rotate), scale, scaleX, scaleY, skewX, skewY, and any CSS property
 *   (opacity, fill, strokeDashoffset, ...) or plain-object property. Values may be numbers, strings with units,
 *   colours, relative strings ("+=40", "-=10", "*=2") or functions (index, target, targets) => value.
 * Eases: none/linear, power0-4 (.in/.out/.inOut), quad, cubic, quart, quint, strong, sine, expo, circ,
 *   back(.in/.out/.inOut)(overshoot), bounce, elastic.out(amplitude, period), steps(n).
 *
 * Rendering model: there is no ticker. A paused timeline is driven only by seek(t). Seeking forward renders,
 * in start order, every tween whose local time changed; seeking backward resets every property the timeline
 * touched to its value when the timeline was first sought, then renders from scratch. Start values are read
 * when a tween first renders, so a tween continues from whatever earlier tweens left behind. The same seek
 * sequence always produces the same frame.
 */
(function (root) {
  "use strict";
  const DEG = Math.PI / 180, RAD = 180 / Math.PI;

  /* ------------------------------------------------------------------ eases */
  const _pow = n => ({in: p => Math.pow(p, n), out: p => 1 - Math.pow(1 - p, n),
    inOut: p => (p < .5 ? Math.pow(2 * p, n) / 2 : 1 - Math.pow(2 * (1 - p), n) / 2)});
  const _bounceOut = p => {
    const n1 = 7.5625, d1 = 2.75;
    if (p < 1 / d1) return n1 * p * p;
    if (p < 2 / d1) return n1 * (p -= 1.5 / d1) * p + .75;
    if (p < 2.5 / d1) return n1 * (p -= 2.25 / d1) * p + .9375;
    return n1 * (p -= 2.625 / d1) * p + .984375;
  };
  const _inOutFrom = fin => ({in: fin, out: p => 1 - fin(1 - p), inOut: p => (p < .5 ? fin(2 * p) / 2 : 1 - fin(2 * (1 - p)) / 2)});
  const EASES = {
    power0: () => ({in: p => p, out: p => p, inOut: p => p}),
    power1: () => _pow(2), quad: () => _pow(2),
    power2: () => _pow(3), cubic: () => _pow(3),
    power3: () => _pow(4), quart: () => _pow(4),
    power4: () => _pow(5), quint: () => _pow(5), strong: () => _pow(5),
    sine: () => _inOutFrom(p => 1 - Math.cos(p * Math.PI / 2)),
    expo: () => _inOutFrom(p => (p === 0 ? 0 : Math.pow(2, 10 * (p - 1)))),
    circ: () => _inOutFrom(p => 1 - Math.sqrt(1 - p * p)),
    back: (o = 1.70158) => _inOutFrom(p => p * p * ((o + 1) * p - o)),
    bounce: () => _inOutFrom(p => 1 - _bounceOut(1 - p)),
    elastic: (a = 1, per = .3) => {
      a = Math.max(1, a);
      const s = per / (2 * Math.PI) * Math.asin(1 / a);
      const out = p => (p === 0 || p === 1 ? p : a * Math.pow(2, -10 * p) * Math.sin((p - s) * (2 * Math.PI) / per) + 1);
      return {out, in: p => 1 - out(1 - p), inOut: p => (p < .5 ? (1 - out(1 - 2 * p)) / 2 : out(2 * p - 1) / 2 + .5)};
    },
  };
  const _easeCache = {};
  function parseEase(e) {
    if (typeof e === "function") return e;
    if (e == null) e = "power1.out";
    if (_easeCache[e]) return _easeCache[e];
    let f;
    const s = String(e).trim();
    if (s === "none" || s === "linear" || /^power0/.test(s)) f = p => p;
    else {
      const m = /^(\w+?)(?:\.(in|out|inOut))?(?:\(([^)]*)\))?$/.exec(s);
      if (m && m[1] === "steps") { const n = Math.max(1, parseInt(m[3], 10) || 1); f = p => (p >= 1 ? 1 : Math.floor(p * n) / n); }
      else if (m && EASES[m[1]]) {
        const args = m[3] ? m[3].split(",").map(Number) : [];
        f = EASES[m[1]](...args)[m[2] || "out"];
      } else { console.warn("motion.js: unknown ease", e, "- using power1.out"); f = _pow(2).out; }
    }
    return (_easeCache[e] = f);
  }

  /* --------------------------------------------------------------- colours */
  const NAMED = {white: [255, 255, 255, 1], black: [0, 0, 0, 1], red: [255, 0, 0, 1], transparent: [0, 0, 0, 0],
    none: null};
  function parseColor(v) {
    if (typeof v !== "string") return null;
    const s = v.trim().toLowerCase();
    if (s in NAMED) return NAMED[s] && NAMED[s].slice();
    let m = /^#([0-9a-f]{3,8})$/.exec(s);
    if (m) {
      let h = m[1];
      if (h.length === 3 || h.length === 4) h = h.split("").map(c => c + c).join("");
      if (h.length !== 6 && h.length !== 8) return null;
      const n = i => parseInt(h.slice(i, i + 2), 16);
      return [n(0), n(2), n(4), h.length === 8 ? n(6) / 255 : 1];
    }
    m = /^rgba?\(([^)]+)\)$/.exec(s);
    if (m) {
      const p = m[1].split(/[\s,/]+/).filter(Boolean).map(parseFloat);
      return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    }
    return null;
  }
  const fmtColor = c => `rgba(${Math.round(c[0])}, ${Math.round(c[1])}, ${Math.round(c[2])}, ${+c[3].toFixed(4)})`;

  /* ----------------------------------------------------------- interpolate */
  const NUM = /[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/gi;
  function splitNum(v) {
    if (typeof v === "number") return {n: v, unit: ""};
    if (typeof v !== "string") return null;
    const m = /^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)\s*([a-z%]*)\s*$/i.exec(v);
    return m ? {n: parseFloat(m[1]), unit: m[2]} : null;
  }
  // Returns a function p -> value for a start/end pair.
  function interpolator(a, b, snap) {
    const rnd = snap ? (x => Math.round(x / snap) * snap) : (x => x);
    const na = splitNum(a), nb = splitNum(b);
    if (na && nb) {
      const unit = nb.unit || na.unit, numeric = typeof b === "number" && !unit;
      return p => { const x = rnd(na.n + (nb.n - na.n) * p); return numeric ? x : x + unit; };
    }
    const ca = parseColor(a), cb = parseColor(b);
    if (ca && cb) return p => (p >= 1 && typeof b === "string" && !snap ? b : fmtColor(ca.map((x, i) => x + (cb[i] - x) * p)));
    if (typeof a === "string" && typeof b === "string") {
      const xa = a.match(NUM), xb = b.match(NUM);
      if (xa && xb && xa.length === xb.length) {
        const parts = b.split(NUM);
        return p => (p >= 1 ? b : parts.map((s, i) => s + (i < xb.length ? rnd(+xa[i] + (+xb[i] - +xa[i]) * p) : "")).join(""));
      }
    }
    return p => (p >= 1 ? b : a);
  }
  function relative(start, end) {
    if (typeof end !== "string") return end;
    const m = /^([-+*])=\s*(.+)$/.exec(end);
    if (!m) return end;
    const s = splitNum(start), e = splitNum(m[2]);
    if (!s || !e) return m[2];
    const unit = e.unit || s.unit;
    const v = m[1] === "+" ? s.n + e.n : m[1] === "-" ? s.n - e.n : s.n * e.n;
    return unit ? v + unit : v;
  }

  /* ---------------------------------------------------------------- targets */
  const isEl = t => t && typeof t === "object" && t.nodeType === 1;
  const isSVG = t => isEl(t) && typeof SVGElement !== "undefined" && t instanceof SVGElement && t.tagName.toLowerCase() !== "svg";
  function toArray(t) {
    if (t == null) return [];
    if (typeof t === "string") return Array.from(document.querySelectorAll(t));
    if (Array.isArray(t)) return t.flatMap(toArray);
    if (typeof NodeList !== "undefined" && (t instanceof NodeList || t instanceof HTMLCollection)) return Array.from(t);
    return [t];
  }
  const TRANSFORM = {x: 1, y: 1, rotation: 1, rotate: 1, scale: 1, scaleX: 1, scaleY: 1, skewX: 1, skewY: 1};
  const RESERVED = {duration: 1, delay: 1, ease: 1, repeat: 1, repeatDelay: 1, yoyo: 1, stagger: 1, keyframes: 1,
    onStart: 1, onUpdate: 1, onComplete: 1, onRepeat: 1, onUpdateParams: 1, onCompleteParams: 1, onStartParams: 1,
    paused: 1, immediateRender: 1, overwrite: 1, lazy: 1, snap: 1, id: 1, smoothOrigin: 1, callbackScope: 1,
    svgOrigin: 1, transformOrigin: 1, attr: 1, runBackwards: 1, data: 1};
  const kebab = s => s.replace(/[A-Z]/g, c => "-" + c.toLowerCase());

  // The engine's record of every element whose transforms it controls.
  function tcache(el) {
    if (el.__motion) return el.__motion;
    const c = {x: 0, y: 0, rotation: 0, skewX: 0, skewY: 0, scaleX: 1, scaleY: 1, ox: 0, oy: 0, xOffset: 0, yOffset: 0,
      svg: isSVG(el), originSet: false, smooth: true};
    if (c.svg) {
      let m = [1, 0, 0, 1, 0, 0];
      try {
        const bv = el.transform && el.transform.baseVal;
        const k = bv && bv.numberOfItems ? bv.consolidate().matrix : null;
        if (k) m = [k.a, k.b, k.c, k.d, k.e, k.f];
      } catch (e) { /* not transformable */ }
      // default origin: the top-left corner of the element's own bounding box
      let bb = {x: 0, y: 0};
      try { bb = el.getBBox(); } catch (e) { /* not rendered */ }
      c.ox = bb.x; c.oy = bb.y;
      const [a, b, cc, d, e, f] = m;
      c.scaleX = Math.sqrt(a * a + b * b);
      c.scaleY = Math.sqrt(d * d + cc * cc);
      c.rotation = (a || b) ? Math.atan2(b, a) * RAD : 0;
      c.skewX = (cc || d) ? Math.atan2(cc, d) * RAD + c.rotation : 0;
      if (c.skewX) c.scaleY *= Math.abs(Math.cos(c.skewX * DEG));
      const [A, B, C, D] = svgMatrix(c);
      c.x = e - (c.ox - (c.ox * A + c.oy * C));
      c.y = f - (c.oy - (c.ox * B + c.oy * D));
    } else if (isEl(el)) {
      const t = el.style.transform;
      if (t && t !== "none") console.warn("motion.js: existing inline transform on", el, "is replaced");
    }
    el.__motion = c;
    return c;
  }
  function svgMatrix(c) {
    let a, b, cc, d;
    const sx = c.scaleX, sy = c.scaleY;
    if (c.rotation || c.skewX || c.skewY) {
      const r = c.rotation * DEG, sk = c.skewX * DEG;
      a = Math.cos(r) * sx; b = Math.sin(r) * sx;
      cc = Math.sin(r - sk) * -sy; d = Math.cos(r - sk) * sy;
      if (sk) {
        const skY = c.skewY * DEG;
        let t = Math.tan(sk - skY); t = Math.sqrt(1 + t * t);
        cc *= t; d *= t;
        if (skY) { t = Math.tan(skY); t = Math.sqrt(1 + t * t); a *= t; b *= t; }
      } else if (c.skewY) {
        const skY = c.skewY * DEG;
        let t = Math.tan(skY); t = Math.sqrt(1 + t * t);
        b = Math.sin(r + skY) * sx; a = Math.cos(r + skY) * sx;
      }
    } else { a = sx; b = 0; cc = 0; d = sy; }
    return [a, b, cc, d];
  }
  const r6 = v => Math.round(v * 1e6) / 1e6;
  function writeTransform(el) {
    const c = el.__motion;
    if (c.svg) {
      const [a, b, cc, d] = svgMatrix(c);
      const tx = c.x + c.ox - (c.ox * a + c.oy * cc) + c.xOffset;
      const ty = c.y + c.oy - (c.ox * b + c.oy * d) + c.yOffset;
      el.setAttribute("transform", `matrix(${r6(a)},${r6(b)},${r6(cc)},${r6(d)},${r6(tx)},${r6(ty)})`);
    } else {
      el.style.transform = `translate(${c.x}px, ${c.y}px) rotate(${c.rotation}deg) skew(${c.skewX}deg, ${c.skewY}deg) scale(${c.scaleX}, ${c.scaleY})`;
    }
  }
  // Parses an origin string. Returns [x, y, absolute] in the element's local space for SVG, or a CSS string for HTML.
  const KW = {left: "0%", top: "0%", center: "50%", right: "100%", bottom: "100%"};
  function setOrigin(el, origin, absolute, smooth) {
    recordBase(el, "transform", "transform");
    const c = tcache(el);
    if (!c.svg) { el.style.transformOrigin = String(origin).split(/\s+/).map(v => KW[v] || v).join(" "); return; }
    let parts = String(origin).trim().split(/\s+/);
    if (!absolute) {
      if (parts.length === 1) parts = /^(top|bottom)$/.test(parts[0]) ? ["center", parts[0]] : [parts[0], parts[0] === "center" || KW[parts[0]] ? "center" : parts[0]];
      if (/^(top|bottom)$/.test(parts[0]) || /^(left|right)$/.test(parts[1])) parts = [parts[1], parts[0]];
      parts = parts.map(v => KW[v] || v);
    }
    let ox = parseFloat(parts[0]) || 0, oy = parseFloat(parts[1] != null ? parts[1] : parts[0]) || 0;
    const [a, b, cc, d] = svgMatrix(c);
    if (!absolute) {
      let bb = {x: 0, y: 0, width: 0, height: 0};
      try { bb = el.getBBox(); } catch (e) { /* not rendered */ }
      ox = bb.x + (/%$/.test(parts[0]) ? ox / 100 * bb.width : ox);
      oy = bb.y + (/%$/.test(parts[1] != null ? parts[1] : parts[0]) ? oy / 100 * bb.height : oy);
    } else {
      const tx = c.x + c.ox - (c.ox * a + c.oy * cc) + c.xOffset, ty = c.y + c.oy - (c.ox * b + c.oy * d) + c.yOffset;
      const det = a * d - b * cc;
      if (det && !(a === 1 && b === 0 && cc === 0 && d === 1 && tx === 0 && ty === 0)) {
        const x = ox * (d / det) + oy * (-cc / det) + ((cc * ty - d * tx) / det);
        const y = ox * (-b / det) + oy * (a / det) - ((a * ty - b * tx) / det);
        ox = x; oy = y;
      }
    }
    if (smooth !== false && c.smooth !== false) {
      const dx = ox - c.ox, dy = oy - c.oy;
      c.xOffset += (dx * a + dy * cc) - dx;
      c.yOffset += (dx * b + dy * d) - dy;
    } else { c.xOffset = c.yOffset = 0; }
    c.ox = ox; c.oy = oy; c.originSet = true;
    writeTransform(el);
  }

  // Property accessors -------------------------------------------------
  function getProp(t, name, kind) {
    if (kind === "attr") { const v = t.getAttribute(name); const n = splitNum(v); return n && !n.unit ? n.n : v; }
    if (kind === "transform") { const c = tcache(t); return name === "scale" ? c.scaleX : c[name === "rotate" ? "rotation" : name]; }
    if (kind === "css") {
      let v = t.style[name];
      if (v === "" || v == null) { try { v = getComputedStyle(t)[name]; } catch (e) { v = ""; } }
      const n = splitNum(v);
      if (n && (name === "opacity" || !n.unit || n.unit === "px")) return n.n;
      return v;
    }
    return t[name];
  }
  function setProp(t, name, kind, v) {
    recordBase(t, name, kind);
    if (kind === "attr") { t.setAttribute(name, typeof v === "number" ? r6(v) : v); return; }
    if (kind === "transform") {
      const c = tcache(t);
      if (name === "scale") { c.scaleX = c.scaleY = v; } else c[name === "rotate" ? "rotation" : name] = v;
      return; // written once per render by flushTransforms
    }
    if (kind === "css") { t.style[name] = typeof v === "number" ? String(r6(v)) : v; return; }
    t[name] = v;
  }
  function kindOf(t, name) {
    if (!isEl(t)) return "obj";
    if (TRANSFORM[name]) return "transform";
    return "css";
  }

  /* ------------------------------------------------- base state for resets */
  // Values each touched property had when its timeline was first sought, so a backward seek can restore them.
  let BASE = null;     // Map target -> {props: Map key->value, transform: snapshot|undefined}
  function recordBase(t, name, kind) {
    if (!BASE) return;
    let rec = BASE.get(t);
    if (!rec) { rec = {props: new Map(), transform: undefined}; BASE.set(t, rec); }
    if (kind === "transform") {
      if (rec.transform === undefined) {
        rec.transform = t.__motion ? {cache: Object.assign({}, t.__motion), attr: null}
          : {cache: null, attr: isSVG(t) ? t.getAttribute("transform") : t.style.transform};
      }
      return;
    }
    const key = kind + ":" + name;
    if (!rec.props.has(key)) rec.props.set(key, kind === "attr" ? t.getAttribute(name) : kind === "css" ? t.style[name] : t[name]);
  }
  function restoreBase() {
    if (!BASE) return;
    for (const [t, rec] of BASE) {
      for (const [key, v] of rec.props) {
        const i = key.indexOf(":"), kind = key.slice(0, i), name = key.slice(i + 1);
        if (kind === "attr") { if (v == null) t.removeAttribute(name); else t.setAttribute(name, v); }
        else if (kind === "css") t.style[name] = v;
        else t[name] = v;
      }
      if (rec.transform) {
        if (rec.transform.cache) { t.__motion = Object.assign({}, rec.transform.cache); writeTransform(t); }
        else {
          delete t.__motion;
          if (isSVG(t)) { if (rec.transform.attr == null) t.removeAttribute("transform"); else t.setAttribute("transform", rec.transform.attr); }
          else t.style.transform = rec.transform.attr || "";
        }
      }
    }
  }

  /* ----------------------------------------------------------------- tween */
  let _uid = 0;
  class Tween {
    constructor(targets, vars, fromVars, isSet) {
      this.id = ++_uid;
      this.targets = toArray(targets);
      this.vars = vars || {};
      this.fromVars = fromVars || null;
      this.isSet = !!isSet;
      this.dur = isSet ? 0 : (this.vars.duration != null ? +this.vars.duration : .5);
      this.delay = +this.vars.delay || 0;
      this.ease = parseEase(this.vars.ease);
      this.repeat = Math.max(0, this.vars.repeat | 0);
      this.rdelay = +this.vars.repeatDelay || 0;
      this.yoyo = !!this.vars.yoyo;
      this.start = 0;
      this.snap = this.vars.snap;
      this.reset();
    }
    get totalDur() { return this.dur * (this.repeat + 1) + this.rdelay * this.repeat; }
    reset() { this.inited = false; this.lastLocal = null; this.props = null; this.started = false; this.done = false; }
    // The value each property starts from is read the first time the tween renders.
    init() {
      this.props = [];
      const v = this.vars, f = this.fromVars;
      const snapFor = name => (typeof this.snap === "number" ? this.snap : this.snap && typeof this.snap === "object" ? this.snap[name] : undefined);
      this.targets.forEach((t, i) => {
        const resolve = x => (typeof x === "function" ? x(i, t, this.targets) : x);
        if (isEl(t) && v.svgOrigin != null) setOrigin(t, resolve(v.svgOrigin), true, v.smoothOrigin);
        else if (isEl(t) && v.transformOrigin != null) setOrigin(t, resolve(v.transformOrigin), false, v.smoothOrigin);
        const add = (name, kind, endRaw, fromRaw) => {
          let start = fromRaw !== undefined ? resolve(fromRaw) : getProp(t, name, kind);
          if (fromRaw !== undefined) start = relative(getProp(t, name, kind), start);
          const end = relative(start, resolve(endRaw));
          this.props.push({t, name, kind, fn: interpolator(start, end, snapFor(name)), end});
        };
        for (const k in v) {
          if (RESERVED[k]) continue;
          add(k, kindOf(t, k), v[k], f && k in f ? f[k] : undefined);
        }
        if (v.attr && isEl(t)) for (const k in v.attr) add(k, "attr", v.attr[k], f && f.attr && k in f.attr ? f.attr[k] : undefined);
      });
      this.inited = true;
    }
    // Local time (seconds since this tween's start) -> eased ratio
    ratioAt(local) {
      if (this.dur === 0) return local >= 0 ? 1 : 0;
      const cycle = this.dur + this.rdelay;
      let it, tt;
      if (local >= this.totalDur) { it = this.repeat; tt = this.dur; }
      else {
        it = Math.floor(local / cycle); tt = local - it * cycle;
        if (tt > this.dur) tt = this.dur;
      }
      let p = tt / this.dur;
      if (this.yoyo && (it & 1)) p = 1 - p;
      return this.ease(p);
    }
    render(local, suppress) {
      if (!this.inited) this.init();
      const r = this.ratioAt(local);
      if (!this.started && !suppress && this.vars.onStart) this.vars.onStart.apply(this, this.vars.onStartParams || []);
      this.started = true;
      const touched = new Set();
      for (const p of this.props) {
        setProp(p.t, p.name, p.kind, p.fn(r));
        if (p.kind === "transform") touched.add(p.t);
      }
      for (const t of touched) writeTransform(t);
      if (!suppress && this.vars.onUpdate) this.vars.onUpdate.apply(this, this.vars.onUpdateParams || []);
      if (local >= this.totalDur && !this.done) {
        this.done = true;
        if (!suppress && this.vars.onComplete) this.vars.onComplete.apply(this, this.vars.onCompleteParams || []);
      }
      this.lastLocal = local;
    }
    progress() { return this.lastLocal == null ? 0 : Math.min(1, this.lastLocal / (this.totalDur || 1)); }
  }

  // Applies vars to targets right now (no timeline), like a zero-length tween.
  function applyNow(targets, vars) {
    const tw = new Tween(targets, vars, null, true);
    tw.render(0, false);
    return tw;
  }

  /* -------------------------------------------------------------- timeline */
  class Timeline {
    constructor(vars) {
      this.vars = vars || {};
      this.children = [];   // {start, item: Tween|Timeline|fn, order}
      this._order = 0;
      this._end = 0;
      this._time = null;
      this._sorted = null;
      this._labels = {};
    }
    _pos(position) {
      if (position == null) return this._end;
      if (typeof position === "number") return position;
      const s = String(position).trim();
      let m = /^([+-])=\s*([\d.]+)$/.exec(s);
      if (m) return this._end + (m[1] === "+" ? 1 : -1) * parseFloat(m[2]);
      m = /^([<>])\s*([+-]=?\s*[\d.]+)?$/.exec(s);
      if (m) {
        const last = this.children[this.children.length - 1];
        const base = !last ? 0 : m[1] === "<" ? last.start : last.start + this._dur(last.item);
        return base + (m[2] ? parseFloat(m[2].replace("=", "")) : 0);
      }
      m = /^([A-Za-z_][\w-]*)\s*(?:([+-])=\s*([\d.]+))?$/.exec(s);
      if (m && m[1] in this._labels) return this._labels[m[1]] + (m[2] ? (m[2] === "+" ? 1 : -1) * parseFloat(m[3]) : 0);
      const n = parseFloat(s);
      return isNaN(n) ? this._end : n;
    }
    _dur(item) { return item instanceof Tween ? item.totalDur : item instanceof Timeline ? item.duration() : 0; }
    _push(item, start) {
      this.children.push({start, item, order: this._order++});
      this._end = Math.max(this._end, start + this._dur(item));
      this._sorted = null;
      return this;
    }
    _tween(targets, vars, fromVars, position, isSet) {
      if (vars && Array.isArray(vars.keyframes)) {
        let t = this._pos(position);
        for (const kf of vars.keyframes) {
          const v = Object.assign({ease: vars.ease}, kf);
          this._tween(targets, v, null, t, false);
          t += (kf.duration != null ? kf.duration : .5) + (kf.delay || 0);
        }
        return this;
      }
      const start = this._pos(position) + (+((vars || {}).delay) || 0);
      const stagger = vars && vars.stagger;
      if (stagger && !isSet) {
        const list = toArray(targets), each = typeof stagger === "number" ? stagger : (stagger.each || 0);
        const order = typeof stagger === "object" && stagger.from === "end" ? list.map((_, i) => list.length - 1 - i) : list.map((_, i) => i);
        list.forEach((t, i) => {
          const v = Object.assign({}, vars, {stagger: 0, delay: 0});
          for (const k in v) if (typeof vars[k] === "function" && !/^on/.test(k)) { const f = vars[k]; v[k] = () => f(i, t, list); }
          if (i !== list.length - 1) { delete v.onComplete; }
          if (i !== 0) { delete v.onStart; }
          this._push(new Tween([t], v, fromVars, false), start + order[i] * each);
        });
        return this;
      }
      const tw = new Tween(targets, Object.assign({}, vars, {delay: 0}), fromVars, isSet);
      if (fromVars && (vars.immediateRender !== false)) {
        // like a from() tween: the from-values show from the moment the tween is created
        applyNow(tw.targets, Object.assign({}, fromVars));
      }
      return this._push(tw, start);
    }
    to(targets, vars, position) { return this._tween(targets, vars, null, position, false); }
    from(targets, vars, position) {
      // from(): the given values are the start, the values the targets have now are the end
      const list = toArray(targets), fromV = {}, toV = {};
      for (const k in vars) {
        if (RESERVED[k] && k !== "attr" && k !== "svgOrigin" && k !== "transformOrigin") toV[k] = vars[k];
        else fromV[k] = vars[k];
      }
      const cur = list.map(t => {
        const o = {attr: {}};
        for (const k in fromV) {
          if (k === "attr") { for (const a in fromV.attr) o.attr[a] = getProp(t, a, "attr"); }
          else if (k !== "svgOrigin" && k !== "transformOrigin") o[k] = getProp(t, k, kindOf(t, k));
        }
        return o;
      });
      for (const k in fromV) {
        if (k === "svgOrigin" || k === "transformOrigin") toV[k] = fromV[k];
        else if (k === "attr") { toV.attr = {}; for (const a in fromV.attr) toV.attr[a] = i => cur[i].attr[a]; }
        else toV[k] = i => cur[i][k];
      }
      return this._tween(list, toV, fromV, position, false);
    }
    fromTo(targets, fromVars, toVars, position) { return this._tween(targets, toVars, fromVars || {}, position, false); }
    set(targets, vars, position) { return this._tween(targets, vars, null, position, true); }
    add(item, position) {
      if (typeof item === "string") { this._labels[item] = this._pos(position); return this; }
      if (typeof item === "function") return this.call(item, [], position);
      return this._push(item, this._pos(position));
    }
    addLabel(name, position) { this._labels[name] = this._pos(position); return this; }
    call(fn, args, position) {
      const tw = new Tween({}, {onComplete: fn, onCompleteParams: args || []}, null, true);
      return this._push(tw, this._pos(position));
    }
    duration() { return this._end; }
    totalDuration() { return this._end; }
    time() { return this._time || 0; }
    progress(p) { if (p == null) return this._end ? this.time() / this._end : 0; this.seek(p * this._end); return this; }
    pause() { return this; }
    play() { return this; }
    kill() { this.children = []; this._sorted = null; return this; }
    getChildren() { return this.children.map(c => c.item); }
    _sort() {
      if (!this._sorted) this._sorted = this.children.slice().sort((a, b) => a.start - b.start || a.order - b.order);
      return this._sorted;
    }
    _resetChildren() {
      for (const c of this.children) { if (c.item instanceof Timeline) c.item._resetAll(); else c.item.reset(); }
    }
    _resetAll() { this._resetChildren(); this._time = null; }
    _renderAt(t, suppress) {
      for (const c of this._sort()) {
        const local = t - c.start;
        if (c.item instanceof Timeline) { if (local >= 0 || c.item._time != null) c.item._renderAt(Math.max(0, Math.min(local, c.item.duration())), suppress); continue; }
        const tw = c.item;
        if (local < 0) continue;
        const clamped = Math.min(local, tw.totalDur);
        if (tw.lastLocal === clamped) continue;
        tw.render(clamped, suppress);
      }
      this._time = t;
    }
    seek(t, suppressEvents) {
      t = Math.max(0, +t || 0);
      if (!BASE) BASE = new Map();
      if (this._time != null && t < this._time) { restoreBase(); this._resetChildren(); }
      this._renderAt(t, suppressEvents === true);
      return this;
    }
    // A timeline added inside another renders as part of its parent; standalone, seek() drives it.
  }

  const motion = {
    version: "1.0.0",
    timeline: vars => new Timeline(vars),
    set: (targets, vars) => { applyNow(targets, vars); },
    to: (targets, vars) => { const tl = new Timeline(); tl.to(targets, vars, 0); tl.seek(tl.duration()); return tl; },
    fromTo: (targets, f, v) => { const tl = new Timeline(); tl.fromTo(targets, f, v, 0); tl.seek(tl.duration()); return tl; },
    parseEase,
    utils: {toArray, interpolate: (a, b, p) => interpolator(a, b)(p)},
    registerPlugin: () => {},
    _reset: () => { BASE = null; },
  };
  root.motion = motion;
  if (!root.gsap) root.gsap = motion;
})(typeof window !== "undefined" ? window : globalThis);
