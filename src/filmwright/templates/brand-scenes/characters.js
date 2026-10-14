/* Flat cartoon characters for the animated scenes. A rig that is a pure function of time (see runtime.js).
 *
 *   const c = Characters.make("marketer", parentElement);      // or a custom look object
 *   c.pose({ t, x, y, face: 1, walk: 0..1, wave: 0..1, use: 0..1, look: {x:-1..1, y:-1..1}, surprise: 0..1,
 *            squash: 0..1, jump: px, scale: 1 });             // x,y = where the feet stand, in CSS px
 *
 * Looks (generic people only: no real person's likeness, nobody drawn as a villain):
 *   manager (tie)  lead (lapel pin)  consultant (briefcase)  you (magnifying glass)
 *   builder (hard hat)  marketer (megaphone)  reviewer (badge)  host (hand bell)
 *   analyst (clipboard)  reader (open book)
 * `use` activates the prop: the megaphone goes to the mouth, the bell rings, the lens lifts, the book opens.
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const mk = (tag, a, p) => { const e = document.createElementNS(NS, tag); for (const k in a || {}) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; };
  const LOOKS = {
    manager:  { skin: "#e8b890", hair: "#3a2a22", shirt: "#17335c", pants: "#101c30", prop: "tie" },
    lead:     { skin: "#c98f6b", hair: "#1e1a1a", shirt: "#4a5568", pants: "#262d3a", prop: "star" },
    consultant: { skin: "#f0c7a0", hair: "#7a4b2a", shirt: "#0f766e", pants: "#10303a", prop: "case" },
    you:      { skin: "#a9714f", hair: "#2a1b14", shirt: "#6d28d9", pants: "#241b3d", prop: "lens" },
    builder:  { skin: "#d9a37c", hair: "#2b2118", shirt: "#c2570c", pants: "#2c3a4d", prop: "hardhat" },
    marketer: { skin: "#f0c7a0", hair: "#5b3a24", shirt: "#7c2d5b", pants: "#2a2238", prop: "megaphone" },
    reviewer: { skin: "#b07a55", hair: "#1b1512", shirt: "#1e3a5f", pants: "#16243a", prop: "badge" },
    host:     { skin: "#e8b890", hair: "#8a5a2b", shirt: "#0e7490", pants: "#15303d", prop: "bell" },
    analyst:  { skin: "#c98f6b", hair: "#2a1b14", shirt: "#3f6212", pants: "#1f2a17", prop: "clipboard" },
    reader:   { skin: "#f0c7a0", hair: "#3a2a22", shirt: "#9a3412", pants: "#2b2018", prop: "book" },
  };
  const rot = (g, deg, px, py) => g.setAttribute("transform", "rotate(" + deg + " " + px + " " + py + ")");
  function blinkAmt(t, seed) { const ph = (t * 0.9 + seed * 1.7) % 3.4; return ph < 0.14 ? Math.sin((ph / 0.14) * Math.PI) : 0; }

  function make(look, parent, seed) {
    const c = typeof look === "string" ? LOOKS[look] : look;
    seed = seed || 1;
    const wrap = document.createElement("div");
    wrap.style.cssText = "position:absolute;width:120px;height:200px;transform-origin:50% 100%;will-change:transform";
    const sv = mk("svg", { width: 120, height: 200, viewBox: "0 0 120 200", style: "overflow:visible" }, wrap);
    mk("ellipse", { cx: 60, cy: 198, rx: 38, ry: 6, fill: "rgba(0,0,0,.35)" }, sv);
    const body = mk("g", {}, sv);
    const legL = mk("g", {}, body), legR = mk("g", {}, body);
    [[legL, 48], [legR, 72]].forEach(([g, x]) => { mk("rect", { x: x - 8, y: 118, width: 16, height: 66, rx: 7, fill: c.pants }, g); mk("ellipse", { cx: x + 2, cy: 186, rx: 13, ry: 6, fill: "#0a0f18" }, g); });
    const armL = mk("g", {}, body), armR = mk("g", {}, body);
    mk("rect", { x: 29, y: 74, width: 14, height: 52, rx: 7, fill: c.shirt }, armL); mk("circle", { cx: 36, cy: 128, r: 8, fill: c.skin }, armL);
    mk("rect", { x: 77, y: 74, width: 14, height: 52, rx: 7, fill: c.shirt }, armR); mk("circle", { cx: 84, cy: 128, r: 8, fill: c.skin }, armR);
    mk("rect", { x: 32, y: 64, width: 56, height: 66, rx: 20, fill: c.shirt }, body);
    // chest props
    if (c.prop === "tie") { mk("polygon", { points: "60,70 54,80 60,112 66,80", fill: "#c0392b" }, body); mk("rect", { x: 70, y: 92, width: 12, height: 16, rx: 2, fill: "#fff" }, body); }
    if (c.prop === "star") { mk("path", { d: "M72 84 l2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z", fill: "#7c5cff" }, body); mk("polygon", { points: "60,66 52,82 60,78 68,82", fill: "#fff" }, body); }
    if (c.prop === "badge") { mk("path", { d: "M60 84 l12 4 v10 c0 8-6 12-12 15 c-6-3-12-7-12-15 v-10z", fill: "#d4af37", stroke: "#8a6d12", "stroke-width": 2 }, body); mk("circle", { cx: 60, cy: 98, r: 4, fill: "#8a6d12" }, body); }
    // hand props live on the right arm so they move with it
    const hand = mk("g", {}, armR); const P = {};
    if (c.prop === "case") { P.g = mk("g", {}, hand); mk("rect", { x: 76, y: 128, width: 34, height: 26, rx: 4, fill: "#5b3a1e" }, P.g); mk("rect", { x: 86, y: 122, width: 14, height: 8, rx: 3, fill: "none", stroke: "#5b3a1e", "stroke-width": 3 }, P.g); }
    if (c.prop === "lens") { P.g = mk("g", {}, hand); mk("line", { x1: 88, y1: 128, x2: 104, y2: 108, stroke: "#9aa7b8", "stroke-width": 5, "stroke-linecap": "round" }, P.g); mk("circle", { cx: 110, cy: 100, r: 15, fill: "rgba(124,92,255,.15)", stroke: "#7c5cff", "stroke-width": 4 }, P.g); }
    if (c.prop === "megaphone") { P.g = mk("g", {}, hand); mk("polygon", { points: "78,128 112,112 112,146 78,134", fill: "#e5e7eb", stroke: "#9ca3af", "stroke-width": 2 }, P.g); mk("rect", { x: 70, y: 126, width: 12, height: 10, rx: 3, fill: "#6b7280" }, P.g); P.arcs = mk("g", { opacity: 0 }, P.g); [0, 1, 2].forEach((i) => mk("path", { d: "M" + (118 + i * 9) + " " + (122 - i * 3) + " q6 " + (10 + i * 3) + " 0 " + (22 + i * 6), fill: "none", stroke: "#7c5cff", "stroke-width": 3, "stroke-linecap": "round" }, P.arcs)); }
    if (c.prop === "bell") { P.g = mk("g", {}, hand); mk("path", { d: "M82 140 q2-22 14-22 q12 0 14 22 z", fill: "#e8b64a", stroke: "#a07416", "stroke-width": 2 }, P.g); mk("circle", { cx: 96, cy: 144, r: 4, fill: "#a07416" }, P.g); mk("rect", { x: 94, y: 112, width: 4, height: 8, fill: "#a07416" }, P.g); P.arcs = mk("g", { opacity: 0 }, P.g); [0, 1].forEach((i) => mk("path", { d: "M" + (114 + i * 8) + " " + (126 - i * 4) + " q5 8 0 16", fill: "none", stroke: "#7c5cff", "stroke-width": 3, "stroke-linecap": "round" }, P.arcs)); }
    if (c.prop === "clipboard") { P.g = mk("g", {}, hand); mk("rect", { x: 76, y: 108, width: 32, height: 42, rx: 4, fill: "#d6c7a1", stroke: "#8a7a52", "stroke-width": 2 }, P.g); [118, 126, 134].forEach((y) => mk("line", { x1: 82, y1: y, x2: 102, y2: y, stroke: "#6b5d3a", "stroke-width": 2.4 }, P.g)); mk("rect", { x: 87, y: 104, width: 12, height: 8, rx: 2, fill: "#6b5d3a" }, P.g); }
    if (c.prop === "book") { P.g = mk("g", {}, hand); P.left = mk("path", { d: "M76 138 l16 -6 v-24 l-16 6z", fill: "#fef3c7", stroke: "#a16207", "stroke-width": 2 }, P.g); P.right = mk("path", { d: "M92 132 l16 6 v-24 l-16 -6z", fill: "#fffbeb", stroke: "#a16207", "stroke-width": 2 }, P.g); }
    // head
    const head = mk("g", {}, body);
    mk("circle", { cx: 60, cy: 33, r: 29, fill: c.hair }, head);
    mk("circle", { cx: 60, cy: 41, r: 24, fill: c.skin }, head);
    mk("ellipse", { cx: 37, cy: 42, rx: 3.5, ry: 5, fill: c.skin }, head); mk("ellipse", { cx: 83, cy: 42, rx: 3.5, ry: 5, fill: c.skin }, head);
    const eyeL = mk("g", {}, head), eyeR = mk("g", {}, head);
    [[eyeL, 51], [eyeR, 69]].forEach(([g, x]) => { mk("circle", { cx: x, cy: 43, r: 4.6, fill: "#fff" }, g); g._p = mk("circle", { cx: x, cy: 43, r: 2.5, fill: "#1b1b1b" }, g); g._lid = mk("rect", { x: x - 5, y: 38, width: 10, height: 10, fill: c.skin, "transform-origin": x + " 38", transform: "scale(1,0)" }, g); });
    const browL = mk("line", { x1: 46, y1: 35, x2: 55, y2: 35, stroke: c.hair === "#2a1b14" ? "#2a1b14" : c.hair, "stroke-width": 2.4, "stroke-linecap": "round" }, head);
    const browR = mk("line", { x1: 65, y1: 35, x2: 74, y2: 35, stroke: c.hair, "stroke-width": 2.4, "stroke-linecap": "round" }, head);
    const smile = mk("path", { d: "M52 53 Q60 60 68 53", fill: "none", stroke: "#7a3b2a", "stroke-width": 2.6, "stroke-linecap": "round" }, head);
    const oh = mk("ellipse", { cx: 60, cy: 55, rx: 4.5, ry: 5, fill: "#7a3b2a", opacity: 0 }, head);
    if (c.prop === "hardhat") { mk("path", { d: "M33 34 C33 6 87 6 87 34 Z", fill: "#facc15", stroke: "#a16207", "stroke-width": 2 }, head); mk("rect", { x: 28, y: 32, width: 64, height: 7, rx: 3.5, fill: "#eab308", stroke: "#a16207", "stroke-width": 1.5 }, head); }
    parent.appendChild(wrap);

    function pose(p) {
      const t = p.t || 0, face = p.face || 1, sc = p.scale || 1, mv = p.moving == null ? (p.walk ? 1 : 0) : p.moving;
      const ph = (p.walk || 0) * 10, swing = Math.sin(ph) * 26 * mv;
      const bob = mv ? Math.abs(Math.sin(ph)) * 5 : Math.sin(t * 3 + seed) * 2.2;
      const sq = p.squash || 0, jump = p.jump || 0;
      wrap.style.left = (p.x - 60) + "px"; wrap.style.top = (p.y - 200 - bob * sc - jump * sc) + "px";   // scaled about the feet
      wrap.style.transform = "scale(" + (face * sc) + "," + sc + ")";
      body.setAttribute("transform", "translate(60 198) scale(" + (1 + 0.12 * sq) + " " + (1 - 0.12 * sq) + ") translate(-60 -198)");
      rot(legL, swing, 48, 118); rot(legR, -swing, 72, 118);
      rot(armL, mv ? -swing * 0.8 : Math.sin(t * 2 + seed) * 3, 36, 76);
      const wave = p.wave || 0, use = p.use || 0;
      let aR = mv ? swing * 0.8 : Math.sin(t * 2 + seed + 1) * 3;
      aR = aR * (1 - wave) + (-150 + Math.sin(t * 14) * 16) * wave;
      const usedAngle = { lens: -62 + Math.sin(t * 3) * 6, megaphone: -128, bell: -96 + Math.sin(t * 22) * 14 * use, book: -40, clipboard: -35, case: aR, badge: aR, tie: aR, star: aR, hardhat: aR }[c.prop];
      aR = aR * (1 - use) + (usedAngle == null ? aR : usedAngle) * use;
      rot(armR, aR, 84, 76);
      if (P.arcs) P.arcs.setAttribute("opacity", use * (0.4 + 0.6 * Math.abs(Math.sin(t * 9))));
      if (P.left) { const o = use; P.left.setAttribute("transform", "rotate(" + (-18 * o) + " 92 132)"); P.right.setAttribute("transform", "rotate(" + (18 * o) + " 92 132)"); }
      const lk = p.look || { x: 0, y: 0 }, sp = p.surprise || 0, bl = Math.max(blinkAmt(t, seed), p.blink || 0);
      [eyeL, eyeR].forEach((g) => { g._p.setAttribute("transform", "translate(" + lk.x * 1.9 + " " + lk.y * 1.4 + ")"); g._lid.setAttribute("transform", "scale(1," + (bl * (1 - sp * 0.8)) + ")"); });
      browL.setAttribute("transform", "translate(0 " + (-3.2 * sp) + ")"); browR.setAttribute("transform", "translate(0 " + (-3.2 * sp) + ")");
      smile.setAttribute("opacity", sp > 0.35 ? 0 : 1); oh.setAttribute("opacity", sp > 0.35 ? 1 : 0); oh.setAttribute("ry", 3 + 3 * sp);
      head.setAttribute("transform", "rotate(" + (Math.sin(t * 2.4 + seed) * 3 + lk.x * 3) + " 60 60)");
    }
    return { el: wrap, pose };
  }
  window.Characters = { make, LOOKS };
})();
