"""capture.py: real product UI into a film, with provenance. The engine half of the motion-capture skill.

  capture.py <film dir> [capture.json]      default: <film dir>/capture.json
  capture.py import <film dir> <png> <source url> [x0,y0,x1,y1] [name]   a screenshot taken elsewhere, with provenance

capture.json:
  {"base": "https://app.example.com", "viewport": [1440, 900], "scale": 2,
   "storageState": "~/.config/motiontale/app.json",   # optional: a logged-in session, kept outside the film, mode 600
   "shots": [{"id": "home", "url": "/", "waitFor": "main", "patch": "document.querySelector('h1').textContent = 'Q3 plan'",
              "full": false,
              "elements": [{"id": "cta", "sel": "button.primary", "pad": 8, "transparent": true}]}]}
  optional: "cdp": "http://127.0.0.1:9222"   capture in your running, logged-in browser (local only, its own tab)
            "allowWrites": true            let POST/PUT/... out (demo accounts only)
            "allowOtherOrigins": true      capture shots, or follow redirects, off base's origin

Writes, inside the film folder:
  shots/<id>.png, shots/<id>--<element>.png     PNGs at `scale` (2 = sharp up to 2x camera zoom)
  crops.js       const CROPS = {...}: file, size, and each element's box on its page in CSS px
  provenance.json  per file: final URL, selector, patch, viewport, scale, time, sha256, page title
  facts.suggested.md  every number visible in the captured text, as facts.md rows to confirm (kind left blank)

Only GET/HEAD/OPTIONS requests leave the browser unless capture.json sets "allowWrites": true.
A patch is a state edit on the real page (fill a field, open a menu, seed a value) so a state the product
doesn't show on its own is still real pixels. Every patch is recorded in provenance.json.
"""
import hashlib, json, pathlib, re, sys, time
from urllib.parse import urljoin, urlsplit, urlunsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lint import NUM  # noqa: E402


def capture(d, cfg):
    from playwright.sync_api import sync_playwright
    d = pathlib.Path(d).resolve()
    (d / "shots").mkdir(exist_ok=True)
    vw, vh = cfg.get("viewport", [1440, 900])
    scale = cfg.get("scale", 2)
    for s in cfg["shots"]:                      # ids become file names under shots/: nothing else
        for i in [s["id"]] + [el["id"] for el in s.get("elements", [])]:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", i):
                sys.exit(f"capture id {i!r}: use letters, digits, - and _ only")
    state = None
    if cfg.get("storageState"):                 # a session file is a credential: never with the deliverables or readable by others
        state = pathlib.Path(cfg["storageState"]).expanduser()
        state = (state if state.is_absolute() else d / state).resolve()
        if state.is_relative_to(d):
            sys.exit(f"storageState {state} is inside the film folder; keep it outside, e.g. ~/.config/motiontale/")
        if state.stat().st_mode & 0o077:
            sys.exit(f"storageState {state} is readable by others: chmod 600 it")
    base_url = cfg.get("base", "")
    origin = lambda u: urlsplit(u)[:2]
    for s in cfg["shots"]:                      # the session belongs to base's origin: other sites need saying so
        u = urljoin(base_url, s.get("url", ""))
        if base_url and origin(u) != origin(base_url) and not cfg.get("allowOtherOrigins"):
            sys.exit(f"shot {s['id']}: {u} is not on base's origin {base_url}; set allowOtherOrigins to capture it")
    crops, prov, nums = {}, {}, {}
    if (d / "provenance.json").exists():        # a partial re-capture keeps the other shots' records and crops
        prov = json.loads((d / "provenance.json").read_text())
    if (d / "crops.js").exists():
        c = (d / "crops.js").read_text()
        crops = json.loads(c[c.index("=") + 1: c.rindex(";")])
    cdp = cfg.get("cdp")
    if cdp and urlsplit(cdp).hostname not in ("127.0.0.1", "localhost", "::1"):
        sys.exit(f"cdp {cdp}: only a local browser (127.0.0.1) is used; a remote one would hand over its sessions")
    with sync_playwright() as pw:
        if cdp:                                   # your running, logged-in browser: a tab of our own, closed after
            br = pw.chromium.connect_over_cdp(cdp)
            ctx = br.contexts[0]
            page = ctx.new_page()
            page.set_viewport_size({"width": vw, "height": vh})
        else:
            br = pw.chromium.launch(args=["--force-color-profile=srgb", "--font-render-hinting=none"])
            ctx = br.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=scale, service_workers="block",
                                 **({"storage_state": str(state)} if state else {}))   # a service worker would bypass the route
            page = ctx.new_page()
        if not cfg.get("allowWrites"):          # patches edit the page, never the product: block every write, popups too
            ctx.route("**/*", lambda r: r.continue_() if r.request.method in ("GET", "HEAD", "OPTIONS") else r.abort())
            ctx.route_web_socket("**/*", lambda ws: (ws.connect_to_server(), ws.on_message(lambda m: None)))   # server->page only
            if cdp:
                print("note: your browser's own service workers can't be blocked over cdp; capture a demo account")
        for s in cfg["shots"]:
            url = urljoin(base_url, s.get("url", ""))
            page.goto(url, wait_until="networkidle")
            if base_url and origin(page.url) != origin(base_url) and not cfg.get("allowOtherOrigins"):
                sys.exit(f"shot {s['id']}: {url} redirected to {page.url}, off base's origin; set allowOtherOrigins to capture it")
            if s.get("waitFor"):
                page.wait_for_selector(s["waitFor"])
            page.evaluate("document.fonts.ready")
            if s.get("patch"):
                page.evaluate(s["patch"])
                page.wait_for_timeout(300)
            page.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
            stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            base = {"url": urlunsplit(urlsplit(page.url)[:3] + ("", "")), **({"via": "cdp"} if cdp else {}), "patch": s.get("patch"), "viewport": [vw, vh],
                    "scale": page.evaluate("devicePixelRatio") if cdp else scale, "captured": stamp,
                    "title": page.title()}
            f = d / "shots" / f"{s['id']}.png"
            page.screenshot(path=str(f), full_page=bool(s.get("full")))
            crops[s["id"]] = {"file": f"shots/{f.name}", "w": vw, "h": page.evaluate("document.documentElement.scrollHeight") if s.get("full") else vh}
            prov[f"shots/{f.name}"] = {**base, "selector": None, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
            text = page.evaluate("document.body.innerText")
            for el in s.get("elements", []):
                loc = page.locator(el["sel"]).first
                loc.wait_for(state="visible")
                loc.evaluate("""async e => {           // scroll through it like a reader, so scroll-revealed content appears
                    const top = e.getBoundingClientRect().top + scrollY, h = e.offsetHeight;
                    for (let y = top - innerHeight / 2; y < top + h; y += innerHeight / 2) {
                        scrollTo(0, y); await new Promise(f => setTimeout(f, 150)); } }""")
                page.wait_for_timeout(300)
                loc.evaluate("""e => { window.__capHidden = [];      // fixed/sticky bars would be stamped into a page crop
                    for (const x of document.querySelectorAll('*')) {
                        const p = getComputedStyle(x).position;
                        if ((p === 'fixed' || p === 'sticky') && !x.contains(e) && !e.contains(x)) {
                            window.__capHidden.push([x, x.style.visibility]); x.style.visibility = 'hidden'; } } }""")
                box = loc.bounding_box()                # viewport coordinates: shift to the page, crop from the full page
                sx, sy = page.evaluate("[scrollX, scrollY]")
                box = {**box, "x": box["x"] + sx, "y": box["y"] + sy}
                pad = el.get("pad", 0)
                ef = d / "shots" / f"{s['id']}--{el['id']}.png"
                saved = None
                if el.get("transparent"):   # clear every ancestor's background for this shot only, then restore
                    saved = loc.evaluate("""e => { const out = []; for (let p = e.parentElement; p; p = p.parentElement) {
                        out.push([p, p.style.background, p.style.boxShadow, p.style.borderColor, p.style.outlineColor]);   // colours only: sizes keep the layout
                        p.style.background = 'transparent'; p.style.boxShadow = 'none'; p.style.borderColor = 'transparent'; p.style.outlineColor = 'transparent'; }
                        window.__capSaved = out;
                        for (const x of document.querySelectorAll('body *'))   // the pad shows page content beside it: hide that
                            if (!x.contains(e) && !e.contains(x) && x !== e) { window.__capHidden.push([x, x.style.visibility]); x.style.visibility = 'hidden'; }
                        return out.length; }""")
                x0, y0 = max(box["x"] - pad, 0), max(box["y"] - pad, 0)     # cut at the page edge: record what was cut
                clip = {"x": x0, "y": y0, "width": box["x"] + box["width"] + pad - x0, "height": box["y"] + box["height"] + pad - y0}
                page.screenshot(path=str(ef), omit_background=bool(el.get("transparent")), full_page=True, clip=clip)
                page.evaluate("() => { for (const [x, v] of window.__capHidden.reverse()) x.style.visibility = v; }")   # first saved = original
                if saved is not None:
                    page.evaluate("() => { for (const [p, bg, sh, bo, ou] of window.__capSaved) { p.style.background = bg; p.style.boxShadow = sh; p.style.borderColor = bo; p.style.outlineColor = ou; } }")
                crops[f"{s['id']}--{el['id']}"] = {"file": f"shots/{ef.name}", "of": s["id"], "x": round(clip["x"], 1),
                                                    "y": round(clip["y"], 1), "w": round(clip["width"], 1), "h": round(clip["height"], 1)}
                prov[f"shots/{ef.name}"] = {**base, "selector": el["sel"], "box": crops[f"{s['id']}--{el['id']}"],
                                            "sha256": hashlib.sha256(ef.read_bytes()).hexdigest(),
                                            "text": loc.inner_text()[:500]}
            for n in (n for n in NUM.findall(text) if len(n.strip()) > 1):    # lone digits: step numbers, noise
                nums.setdefault(n.strip(), (base["url"], stamp[:10]))   # without query or fragment
        if cdp:
            page.close()                          # never close the user's browser
        else:
            br.close()
    (d / "crops.js").write_text("const CROPS = " + json.dumps(crops, indent=1) + ";\n")
    (d / "provenance.json").write_text(json.dumps(prov, indent=1))
    rows = ["| claim as shown | source | date | kind |", "|---|---|---|---|"] + \
           [f"| {n} | {u} (captured UI) | {t} |  |" for n, (u, t) in sorted(nums.items())]
    (d / "facts.suggested.md").write_text("Numbers visible in the captured screens. Copy each one you show into facts.md\n"
                                          "and set kind: fact (true of the real product) or example (seeded demo data).\n\n"
                                          + "\n".join(rows) + "\n")
    return crops, prov, nums


def import_shot(d, src, source, box=None, name=None):
    """A screenshot taken elsewhere (a phone, the app's own export) into shots/, optionally cut to box
    (x0, y0, x1, y1 in its pixels), with provenance: where it came from, when, the box, the file's hash."""
    from PIL import Image
    d, src = pathlib.Path(d).resolve(), pathlib.Path(src)
    name = name or src.stem
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        sys.exit(f"import name {name!r}: use letters, digits, - and _ only")
    (d / "shots").mkdir(exist_ok=True)
    im = Image.open(src)
    if box:
        im = im.crop(box)
    f = d / "shots" / f"{name}.png"
    im.save(f)
    prov = json.loads((d / "provenance.json").read_text()) if (d / "provenance.json").exists() else {}
    prov[f"shots/{f.name}"] = {"source": urlunsplit(urlsplit(source)[:3] + ("", "")), "importedFrom": src.name, "box": list(box) if box else None,
                               "imported": time.strftime("%Y-%m-%dT%H:%M:%S"), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    (d / "provenance.json").write_text(json.dumps(prov, indent=1))
    crops = {}
    if (d / "crops.js").exists():
        c = (d / "crops.js").read_text(); crops = json.loads(c[c.index("=") + 1: c.rindex(";")])
    crops[name] = {"file": f"shots/{f.name}", "w": im.width, "h": im.height}
    (d / "crops.js").write_text("const CROPS = " + json.dumps(crops, indent=1) + ";\n")
    return f


def self_test():
    """A local page: page shot, transparent element crop, box, provenance, restored background, suggested facts."""
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "page.html").write_text('<body style="margin:0;background:#123"><div style="background:#456;padding:40px">'
                                     '<button id="b" style="background:#fff;width:120px;height:40px">Save 42%</button></div></body>')
        cfg = {"viewport": [400, 300], "scale": 2, "shots": [{"id": "p", "url": (d / "page.html").as_uri(),
               "elements": [{"id": "b", "sel": "#b", "pad": 6, "transparent": True}]}]}
        crops, prov, nums = capture(d, cfg)
        im = Image.open(d / "shots" / "p--b.png")
        assert im.size == (264, 104), im.size                                 # (box + 2 x pad) at 2x
        assert im.convert("RGBA").getpixel((1, 1))[3] == 0, "ancestor backgrounds must be cleared"
        assert crops["p--b"]["x"] == 34 and prov["shots/p--b.png"]["selector"] == "#b", crops
        assert "42%" in nums and "42%" in (d / "facts.suggested.md").read_text(), nums
    # an element below the fold, or taller than the viewport, is captured whole (N2)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "page.html").write_text('<body style="margin:0"><div style="height:1500px"></div>'
                                     '<section id="s" style="height:700px;background:#0a0">x</section></body>')
        capture(d, {"viewport": [400, 300], "scale": 1, "shots": [{"id": "p", "url": (d / "page.html").as_uri(),
                   "elements": [{"id": "s", "sel": "#s"}]}]})
        im = Image.open(d / "shots" / "p--s.png").convert("RGB")
        assert im.size == (400, 700) and im.getpixel((200, 650)) == (0, 170, 0), (im.size, im.getpixel((200, 650)))
    # content revealed on scroll (IntersectionObserver) is visible in an element capture (N3)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "page.html").write_text('<body style="margin:0"><div style="height:1500px"></div>'
            '<section id="s" style="height:200px;background:#fff"><p class="r" style="opacity:0;background:#0a0;height:100px">x</p></section>'
            '<script>new IntersectionObserver(es => es.forEach(e => e.isIntersecting && (e.target.style.opacity = 1)))'
            '.observe(document.querySelector(".r"))</script></body>')
        capture(d, {"viewport": [400, 300], "scale": 1, "shots": [{"id": "p", "url": (d / "page.html").as_uri(),
                   "elements": [{"id": "s", "sel": "#s"}]}]})
        px = Image.open(d / "shots" / "p--s.png").convert("RGB").getpixel((200, 50))
        assert px == (0, 170, 0), f"scroll-revealed content missing: {px}"
    # a fixed or sticky header is not stamped into an element capture (N4)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "page.html").write_text('<body style="margin:0"><header style="position:fixed;top:0;left:0;right:0;height:60px;'
            'background:#f00"></header><div style="height:1500px"></div><section id="s" style="height:900px;background:#0a0"></section></body>')
        capture(d, {"viewport": [400, 300], "scale": 1, "shots": [{"id": "p", "url": (d / "page.html").as_uri(),
                   "elements": [{"id": "s", "sel": "#s"}]}]})
        im = Image.open(d / "shots" / "p--s.png").convert("RGB")
        red = sum(1 for y in range(0, im.height, 10) if im.getpixel((200, y)) == (255, 0, 0))
        assert red == 0, f"fixed header stamped into the element capture ({red} rows)"
    # shot and element ids can't write outside shots/ (S4)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t) / "film"; d.mkdir(); (d / "page.html").write_text("<body><b id='b'>x</b></body>")
        for sid, eid in (("../../escape", None), ("/tmp/escape", None), ("ok", "../escape")):
            shot = {"id": sid, "url": (d / "page.html").as_uri()}
            if eid:
                shot["elements"] = [{"id": eid, "sel": "#b"}]
            try:
                capture(d, {"viewport": [200, 100], "scale": 1, "shots": [shot]})
                raise AssertionError(f"accepted id {sid!r}/{eid!r}")
            except SystemExit:
                pass
        assert not list(pathlib.Path(t).glob("*.png")) and not list(pathlib.Path(t).rglob("escape*")), "a file escaped"
    # a login session file is refused inside the film or when others can read it; a private one outside works (S2)
    with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as home:
        d = pathlib.Path(t); (d / "page.html").write_text("<body>x</body>")
        state = '{"cookies": [], "origins": []}'
        cfg = lambda st: {"viewport": [200, 100], "scale": 1, "storageState": st,
                          "shots": [{"id": "p", "url": (d / "page.html").as_uri()}]}
        (d / "auth.json").write_text(state)
        for bad in ("auth.json", str(d / "auth.json")):
            try:
                capture(d, cfg(bad)); raise AssertionError(f"accepted a session file inside the film: {bad}")
            except SystemExit:
                pass
        outside = pathlib.Path(home) / "site.json"; outside.write_text(state); outside.chmod(0o644)
        try:
            capture(d, cfg(str(outside))); raise AssertionError("accepted a session file others can read")
        except SystemExit:
            pass
        outside.chmod(0o600)
        capture(d, cfg(str(outside)))
    # a patch can't send writes to the product unless the config allows it (S1)
    import http.server, threading
    posts = []
    class H(http.server.SimpleHTTPRequestHandler):
        def do_POST(self):
            posts.append(self.path); self.send_response(204); self.end_headers()
        def log_message(self, *a): pass
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t); (d / "index.html").write_text("<body><p>hi</p></body>")
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: H(*a, directory=t))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        capture(d, {"base": base, "viewport": [200, 100], "scale": 1,
                    "shots": [{"id": "p", "url": "/", "patch": "fetch('/delete', {method: 'POST'}).catch(() => {})"}]})
        srv.shutdown()
        assert posts == [], f"a patch sent a write: {posts}"
    # a second capture of other shots keeps the first shots' crops; a crop cut at the page edge records the box it has (I12);
    # provenance drops query and fragment, where tokens live (S20)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "a.html").write_text('<body style="margin:0"><b id="e" style="position:absolute;left:2px;top:2px;width:50px;height:20px">A</b><p style="margin-top:60px">42%</p></body>')
        capture(d, {"viewport": [200, 100], "scale": 1, "shots": [{"id": "a", "url": (d / "a.html").as_uri() + "?token=s3cret#x",
                                                                    "elements": [{"id": "e", "sel": "#e", "pad": 6}]}]})
        assert "s3cret" not in (d / "facts.suggested.md").read_text(), (d / "facts.suggested.md").read_text()
        crops, prov, _ = capture(d, {"viewport": [200, 100], "scale": 1, "shots": [{"id": "b", "url": (d / "a.html").as_uri()}]})
        assert {"a", "a--e", "b"} <= set(crops), crops
        im = Image.open(d / "shots" / "a--e.png")
        assert (crops["a--e"]["x"], crops["a--e"]["y"], crops["a--e"]["w"], crops["a--e"]["h"]) == (0, 0, *im.size), (crops["a--e"], im.size)
        assert "s3cret" not in (d / "provenance.json").read_text() + (d / "facts.suggested.md").read_text()
    # a transparent crop's padding shows nothing but the element: page content beside it is hidden too (E4)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "n.html").write_text('<body style="margin:0"><nav style="height:40px"><b id="e" style="display:inline-block;margin:10px;'
                                  'width:60px;height:20px;background:#fff">Go</b></nav><div style="height:200px;background:#1b1438"></div></body>')
        capture(d, {"viewport": [200, 150], "scale": 1, "shots": [{"id": "n", "url": (d / "n.html").as_uri(),
                                                                    "elements": [{"id": "e", "sel": "#e", "pad": 12, "transparent": True}]}]})
        im = Image.open(d / "shots" / "n--e.png").convert("RGBA")
        assert im.getpixel((im.width // 2, im.height - 2))[3] == 0, im.getpixel((im.width // 2, im.height - 2))
    # an ancestor's border is cleared from the padding (R24)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "h.html").write_text('<body style="margin:0"><header style="position:fixed;top:0;left:0;width:200px;height:20px;background:#f00"></header>'
                                  '<div style="margin-top:60px;border:6px solid navy;display:inline-block"><b id="e" style="display:inline-block;'
                                  'width:40px;height:20px;background:#fff">Go</b></div></body>')
        capture(d, {"viewport": [200, 150], "scale": 1, "shots": [
            {"id": "h", "url": (d / "h.html").as_uri(), "elements": [{"id": "e", "sel": "#e", "pad": 8, "transparent": True}]}]})
        im = Image.open(d / "shots" / "h--e.png").convert("RGBA")
        assert im.getpixel((3, im.height // 2))[3] == 0, ("border kept", im.getpixel((3, im.height // 2)))
    # writes are blocked for the whole browser context: a popup's POST never reaches the server (R5)
    import http.server, threading
    seen = []
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/away":
                self.send_response(302); self.send_header("Location", f"http://localhost:{self.server.server_address[1]}/"); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<body><script>fetch('/w', {method: 'POST', body: 'x'})</script>ok 7</body>")
        def do_POST(self):
            seen.append(self.path); self.send_response(200); self.end_headers()
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    with tempfile.TemporaryDirectory() as t:
        capture(t, {"base": base, "viewport": [200, 100], "scale": 1,
                    "shots": [{"id": "w", "url": "/", "patch": f"window.open('{base}/pop')"}]})
        time.sleep(0.5)
    # a redirect that lands off base's origin is refused (R26)
    try:
        capture(tempfile.mkdtemp(), {"base": base, "shots": [{"id": "r", "url": "/away"}]}); raise AssertionError("redirect followed off origin")
    except SystemExit as e:
        assert "origin" in str(e), e
    srv.shutdown()
    assert seen == [], f"a write got out: {seen}"

    # cdp: capture through a running browser (your logged-in Chrome, started with --remote-debugging-port), in a tab
    # of its own that's closed after, leaving the browser running; only a local browser is accepted (G3)
    import socket, subprocess as sp
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        exe = pw.chromium.executable_path
    port = (lambda s_: (s_.bind(("127.0.0.1", 0)), s_.getsockname()[1], s_.close())[1])(socket.socket())
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        chrome = sp.Popen([exe, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={d / 'profile'}", "about:blank"],
                          stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        try:
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", port), 0.2).close(); break
                except OSError:
                    time.sleep(0.1)
            (d / "c.html").write_text('<body style="margin:0;background:#123"><b id="b" style="background:#fff">Hi</b></body>')
            crops, prov, _ = capture(d, {"cdp": f"http://127.0.0.1:{port}", "viewport": [200, 100], "scale": 1,
                                         "shots": [{"id": "c", "url": (d / "c.html").as_uri()}]})
            assert prov["shots/c.png"].get("via") == "cdp" and chrome.poll() is None, "not captured over cdp, or the browser was closed"
            assert prov["shots/c.png"]["scale"] == 1, prov["shots/c.png"]["scale"]           # the browser's own pixel ratio (R35)
            try:
                capture(d, {"cdp": "http://example.test:9222", "shots": []}); raise AssertionError("a remote browser was accepted")
            except SystemExit as e:
                assert "local" in str(e), e
        finally:
            chrome.terminate(); chrome.wait()

    # import: a screenshot taken elsewhere (or a box of it) enters shots/ with its source, box and hash recorded (G4)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        Image.new("RGB", (100, 50), "#abcdef").save(d / "phone.png")
        import_shot(d, d / "phone.png", "https://app.example.test/home?token=s3cret#x", box=(10, 5, 60, 45), name="home-card")
        prov = json.loads((d / "provenance.json").read_text())["shots/home-card.png"]
        assert Image.open(d / "shots" / "home-card.png").size == (50, 40), "box not applied"
        assert prov["source"] == "https://app.example.test/home" and prov["box"] == [10, 5, 60, 45] and len(prov["sha256"]) == 64, prov
        assert "home-card" in (d / "crops.js").read_text()
        try:
            import_shot(d, d / "phone.png", "https://x.test", name="../x"); raise AssertionError("an escaping name was accepted")
        except SystemExit:
            pass
    # with a base, a shot on another origin is refused before anything loads (S19)
    try:
        capture(tempfile.mkdtemp(), {"base": "https://app.example.test", "shots": [{"id": "x", "url": "https://other.test/"}]})
        raise AssertionError("another origin was captured")
    except SystemExit as e:
        assert "origin" in str(e), e
    print("capture self-check ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test(); sys.exit()
    if sys.argv[1] == "import":                   # capture.py import <film> <png> <source url> [x0,y0,x1,y1] [name]
        a = sys.argv[2:]
        box = tuple(map(int, a[3].split(","))) if len(a) > 3 and a[3] else None
        print(import_shot(a[0], a[1], a[2], box, a[4] if len(a) > 4 else None)); sys.exit()
    d = pathlib.Path(sys.argv[1])
    cfg = json.loads(pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else d / "capture.json").read_text())
    crops, prov, nums = capture(d, cfg)
    print(f"{len(crops)} captures, {len(prov)} provenance entries, {len(nums)} numbers suggested -> "
          f"{d}/shots, crops.js, provenance.json, facts.suggested.md")
