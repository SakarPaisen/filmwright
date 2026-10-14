"""motion.js, the seek-only animation engine. Plain-object behaviour runs under Node; SVG behaviour runs in
headless Chromium. Each part is skipped when its runtime isn't installed."""
import json
import shutil
import subprocess

import pytest

from filmwright import paths

MOTION = paths.ASSETS / "motion.js"


def node(script: str):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    src = MOTION.read_text() + "\n;(function(){\n" + script + "\n})();"
    out = subprocess.run(["node", "-e", src], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_no_third_party_animation_code_bundled():
    text = MOTION.read_text()
    assert "MIT License" in text.splitlines()[0]
    for bad in ("GreenSock", "gsap.com", "Club GSAP"):
        assert bad not in text
    assert not list(paths.PKG.rglob("gsap*.js"))


def test_eases_match_their_definitions():
    r = node("""
      const e = n => motion.parseEase(n);
      console.log(JSON.stringify({
        p3out: e("power3.out")(.5), p1in: e("power1.in")(.5), sine: e("sine.inOut")(.25),
        back: e("back.out(3)")(.5), bounce: e("bounce.out")(.5), none: e("none")(.3),
        ends: ["power2.inOut", "back.out(2)", "bounce.out", "expo.out", "elastic.out(1, 0.3)"].map(n => [e(n)(0), e(n)(1)])}));
    """)
    assert r["p3out"] == pytest.approx(1 - .5 ** 4)
    assert r["p1in"] == pytest.approx(.25)
    assert r["sine"] == pytest.approx(0.1464466, abs=1e-6)
    assert r["back"] == pytest.approx((-.5) * (-.5) * (4 * -.5 + 3) + 1)
    assert r["bounce"] == pytest.approx(0.765625)
    assert r["none"] == pytest.approx(.3)
    for a, b in r["ends"]:
        assert a == pytest.approx(0, abs=1e-9) and b == pytest.approx(1, abs=1e-9)


def test_timeline_positions_relative_values_and_seeking_back():
    r = node("""
      const o = {v: 0, w: 10}, tl = motion.timeline({paused: true});
      tl.to(o, {v: 100, duration: 2, ease: "none"}, 1);
      tl.to(o, {w: "+=5", duration: 1, ease: "none"});              // appended at the end (t=3)
      tl.set(o, {v: -1}, 5);
      const at = t => { tl.seek(t); return [o.v, o.w]; };
      console.log(JSON.stringify({a: at(0.5), b: at(2), c: at(3.5), d: at(6), back: at(2), dur: tl.duration()}));
    """)
    assert r["a"] == [0, 10]
    assert r["b"] == [50, 10]
    assert r["c"] == [100, 12.5]
    assert r["d"] == [-1, 15]
    assert r["back"] == [50, 10]          # seeking backwards restores and replays
    assert r["dur"] == 5


def test_repeat_yoyo_and_stagger_and_callbacks():
    r = node("""
      const a = {x: 0}, b = {x: 0}, c = {x: 0}, o = {k: 0}, tl = motion.timeline({paused: true}); let calls = 0;
      tl.to(o, {k: 1, duration: 1, ease: "none", yoyo: true, repeat: 1, onUpdate() { calls++; }}, 0);
      tl.to([a, b, c], {x: 10, duration: 1, ease: "none", stagger: .5}, 0);
      const s = []; for (const t of [0.5, 1.5, 2.0]) { tl.seek(t); s.push([o.k, a.x, b.x, c.x]); }
      console.log(JSON.stringify({s, calls}));
    """)
    assert r["s"][0] == [0.5, 5, 0, 0]
    assert r["s"][1] == [0.5, 10, 10, 5]
    assert r["s"][2] == [0, 10, 10, 10]   # an even number of yoyo passes ends where it started
    assert r["calls"] == 3


def test_from_to_and_keyframes_and_function_values():
    r = node("""
      const o = {v: 3}, p = {x: 0}, q = [{y: 0}, {y: 0}], tl = motion.timeline({paused: true});
      tl.fromTo(o, {v: 10}, {v: 20, duration: 1, ease: "none"}, 1);
      const before = o.v;                                            // fromTo shows its start value at once
      tl.to(p, {keyframes: [{x: 5, duration: 1}, {x: -5, duration: 1}], ease: "none"}, 0);
      tl.to(q, {y: (i) => (i + 1) * 100, duration: 1, ease: "none"}, 0);
      tl.seek(1.5); const mid = [o.v, p.x, q[0].y, q[1].y];
      tl.seek(2); const end = [o.v, p.x];
      console.log(JSON.stringify({before, mid, end}));
    """)
    assert r["before"] == 10
    assert r["mid"] == [15, 0, 100, 200]
    assert r["end"] == [20, -5]


def test_svg_transforms_pivot_on_svg_origin():
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright
    html = f"""<html><body><svg width="400" height="400"><rect id="r" x="100" y="100" width="100" height="50"/>
      <g id="g" transform="translate(10,20) scale(2)"><rect width="10" height="10"/></g></svg>
      <script>{MOTION.read_text()}</script></body></html>"""
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            p = b.new_page()
            p.set_content(html)
            res = p.evaluate("""() => {
              const tl = motion.timeline({paused: true}), r = document.getElementById("r");
              tl.to(r, {rotation: 90, svgOrigin: "150 125", duration: 1, ease: "none"}, 0);
              tl.to("#g", {x: "+=30", duration: 1, ease: "none"}, 0);
              tl.seek(1);
              const bb = r.getBoundingClientRect(), g = document.getElementById("g").transform.baseVal.consolidate().matrix;
              return {cx: bb.x + bb.width / 2, cy: bb.y + bb.height / 2, w: bb.width, h: bb.height, ga: g.a, ge: g.e, gf: g.f};
            }""")
            b.close()
    except Error as e:
        pytest.skip(f"headless Chromium unavailable: {e}")
    assert res["w"] == pytest.approx(50, abs=.5) and res["h"] == pytest.approx(100, abs=.5)   # turned a quarter
    assert res["cx"] - res["w"] / 2 == pytest.approx(125 + 8, abs=1)                       # around its own centre (+ body margin)
    assert res["ga"] == pytest.approx(2) and res["ge"] == pytest.approx(40) and res["gf"] == pytest.approx(20)
