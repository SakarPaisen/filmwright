/* Scene runtime for animated explainer scenes (intro, outro, feature explainers).
 *
 * A scene is a PURE FUNCTION OF TIME: render(t) sets every style, position and opacity for second t, and
 * nothing else drives it. No CSS animations, no CSS transitions, no setTimeout, no performance.now.
 * That is what makes a frame-stepped capture exact: the recorder calls window.__seek(t) for t = 0, 1/30, 2/30 ...
 * and screenshots each one, so the take is identical on every run whatever the CPU is doing.
 *
 *   Scene.define({ setup(S) { ...build DOM into S.stage... }, render(t, S) { ...style everything from t... } })
 *
 * Live preview (open the HTML in a browser) runs the same render(t) from a requestAnimationFrame clock.
 * Query string: ?d=<seconds> scene length, ?capture=1 frame-stepped capture mode (set by the recorder).
 * Parameters: window.PARAMS (the generator injects it) with theme, themeColor, brand {wordmark, logo_radius, fonts, wordmark_css}, episode, of,
 * and the scene's own fields. Brand colours are applied by the generator (brandkit), not here.
 *
 * Layout: Scene.W / Scene.H are the viewport in CSS px (1440x810 landscape, 430x764 vertical). Scene.U scales
 * lengths (1 at design size). Scene.vertical is true for 9:16. Use fractions of W/H, not fixed coordinates.
 * Guardrails for content: no real people's likenesses, nobody drawn as a villain, and sample data that is
 * clearly sample data.
 */
(function () {
  const q = new URLSearchParams(location.search);
  const W = innerWidth, H = innerHeight, vertical = H > W;
  const U = vertical ? W / 430 : W / 1440;
  const P = window.PARAMS || {};
  const THEMES = { main: "#7c5cff", alt: "#22c55e", warm: "#ff8a4c" };
  const accent = P.themeColor || THEMES[P.theme] || THEMES.main;       // PARAMS.themeColor: the brand's accent for this episode's theme
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = {
    out: (x) => 1 - Math.pow(1 - x, 3), out5: (x) => 1 - Math.pow(1 - x, 5),
    io: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    back: (x) => { const c = 1.9; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
    lin: (x) => x,
  };
  const seg = (t, s, d) => clamp((t - s) / d);
  const lerp = (a, b, k) => a + (b - a) * k;
  const rnd = (seed) => { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); };
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, parent, ns) {
    const e = ns ? document.createElementNS(NS, tag) : document.createElement(tag);
    for (const k in attrs || {}) { if (k === "text") e.textContent = attrs[k]; else if (k === "style") e.style.cssText = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (parent) parent.appendChild(e);
    return e;
  }
  const svg = (tag, attrs, parent) => el(tag, attrs, parent, true);
  // drifting dot field + faint links, drawn on a canvas; deterministic in t
  function field(ctx, t, o) {
    o = Object.assign({ n: 130, link: 8500, glow: 7, alpha: 1, seed: 11 }, o || {});
    if (!field.cache || field.cache.seed !== o.seed || field.cache.n !== o.n) {
      const r = rnd(o.seed), ds = [];
      for (let i = 0; i < o.n; i++) ds.push({ x: r() * W, y: r() * H, vx: (r() - 0.5) * 22 * U, vy: (r() - 0.5) * 22 * U, r: 1.3 + r() * 1.8, ph: r() * 6.28, glow: i < o.glow });
      field.cache = { seed: o.seed, n: o.n, ds };
    }
    const ds = field.cache.ds, link = o.link * U * U, pos = ds.map((p) => [((p.x + p.vx * t + Math.sin(t * 0.6 + p.ph) * 12 * U) % W + W) % W, ((p.y + p.vy * t + Math.cos(t * 0.5 + p.ph) * 12 * U) % H + H) % H]);
    ctx.clearRect(0, 0, W, H); ctx.lineWidth = 1;
    for (let i = 0; i < ds.length; i++) for (let j = i + 1; j < ds.length; j++) {
      const dx = pos[i][0] - pos[j][0], dy = pos[i][1] - pos[j][1], dd = dx * dx + dy * dy;
      if (dd < link) { ctx.strokeStyle = "rgba(155,160,198," + ((1 - dd / link) * 0.14 * o.alpha) + ")"; ctx.beginPath(); ctx.moveTo(pos[i][0], pos[i][1]); ctx.lineTo(pos[j][0], pos[j][1]); ctx.stroke(); }
    }
    ds.forEach((p, i) => {
      const tw = 0.6 + 0.4 * Math.sin(t * 2 + p.ph); ctx.beginPath();
      if (p.glow) { ctx.fillStyle = "rgba(124,92,255," + o.alpha * tw + ")"; ctx.shadowColor = "rgba(124,92,255,.9)"; ctx.shadowBlur = 16; }
      else { ctx.fillStyle = "rgba(161,166,204," + o.alpha * tw * 0.75 + ")"; ctx.shadowBlur = 0; }
      ctx.arc(pos[i][0], pos[i][1], (p.glow ? 3.4 : p.r) * U, 0, 6.283); ctx.fill(); ctx.shadowBlur = 0;
    });
  }
  // series strip: one dot per episode, the current one lit in the theme accent
  function strip(parent, n, cur) {
    const box = el("div", { style: "position:absolute;display:flex;gap:" + 7 * U + "px;align-items:center" }, parent);
    for (let i = 1; i <= n; i++) el("i", { style: "display:block;border-radius:50%;width:" + (i === cur ? 11 : 6) * U + "px;height:" + (i === cur ? 11 : 6) * U + "px;background:" + (i === cur ? accent : (i < cur ? "#54597b" : "#2c2f48")) }, box);
    return box;
  }
  function countUp(from, to, k, fmt) { const v = lerp(from, to, ease.out(clamp(k))); return fmt ? fmt(v) : Math.round(v).toLocaleString("en-US"); }
  const style = el("style", { text: `*{box-sizing:border-box;margin:0}html,body{width:100vw;height:100vh;overflow:hidden;background:#0f1222;color:#f4f5fb;font-family:"IBM Plex Sans",system-ui,sans-serif}
    #stage{position:absolute;inset:0;overflow:hidden;background:radial-gradient(${1100 * U}px ${700 * U}px at 50% 45%,#181b35 0%,#0f1222 62%)}
    .abs{position:absolute}.serif{font-family:${(P.brand && P.brand.fonts && P.brand.fonts.headline) || '"IBM Plex Sans",system-ui,sans-serif'}}canvas{position:absolute;inset:0}` }, document.head);
  const API = { W, H, U, vertical, P, accent, ease, seg, lerp, clamp, rnd, el, svg, field, strip, countUp, D: parseFloat(q.get("d") || "10") };
  API.S = (x) => x * U;
  API.define = function (def) {
    const stage = el("div", { id: "stage" }, document.body); API.stage = stage; API.canvas = null;
    def.setup && def.setup(API);
    const draw = (t) => { def.render(t, API); };
    if (q.get("capture") === "1") { window.__seek = (t) => { draw(t); return true; }; draw(0); window.__ready = true; return; }
    const t0 = performance.now();
    const loop = (now) => { draw(Math.min(API.D, (now - t0) / 1000)); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  };
  window.Scene = API;
})();
