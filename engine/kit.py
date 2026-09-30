"""Download the launch-video sound kit from Mixkit into kit/audio, measure it, write kit/AUDIO.md and kit/beats.png.

Every file is a real Mixkit recording. Each event lists fallbacks in order; if a download fails the next one is used.
"""
import pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
import audiokit as A

KIT = pathlib.Path("kit")
OUT = KIT / "audio"
MUSIC_LICENSE = "[Mixkit Stock Music Free License](https://mixkit.co/license/#musicFree)"
SFX_LICENSE = "[Mixkit Sound Effects Free License](https://mixkit.co/license/#sfxFree)"

MUSIC = [  # (id, title, artist, listing page); 110-125 BPM with a clear drop, measured before choosing
    (474, "What About Action?", "Diego Nava", "https://mixkit.co/free-stock-music/tag/corporate/"),
    (473, "Talent in the Air", "", "https://mixkit.co/free-stock-music/tag/corporate/"),
]
SFX = {  # event: [(id, title, listing page), ...fallbacks]
    "click":   [(1113, "Mouse click close", "click"), (1117, "Classic click", "click")],
    "typing":  [(1396, "Soft typing on a digital keyboard", "typing"), (2532, "Slow typing on a keyboard", "typing")],
    "whoosh":  [(1490, "Fast whoosh transition", "whoosh"), (1489, "Air woosh", "whoosh")],
    "pop":     [(3005, "Explainer video pops whoosh light pop", "pop"), (2356, "Dry pop up notification alert", "pop")],
    "ding":    [(933, "Bell notification", "notification"), (2870, "Correct answer tone", "notification")],
    "success": [(2865, "Success software tone", "success"), (951, "Positive notification", "notification")],
    "paid":    [(1993, "Clinking coins", "coins"), (2003, "Coins sound", "coins")],
    "impact":  [(3049, "Quest game heavy stomp v", "thud"), (2182, "Wood hard hit", "thud")],
}


def fetch(url, dest):
    """Download over https only (redirects too), within 120 s, and keep it only if the server says it is audio."""
    tmp = dest.with_name(dest.name + ".part")          # never over the asset already there: replace it only when valid
    r = subprocess.run(["curl", "-sfL", "--proto", "=https", "--proto-redir", "=https", "--max-time", "120",
                        "-A", "Mozilla/5.0", "-o", str(tmp), "-w", "%{content_type}", url], capture_output=True, text=True)
    ok = r.returncode == 0 and r.stdout.startswith("audio/") and tmp.exists() and tmp.stat().st_size > 1000
    if ok:
        tmp.replace(dest)
    tmp.unlink(missing_ok=True)
    return ok


def first(options, url_of, dest_of):
    for opt in options:
        if fetch(url_of(opt), dest_of(opt)):
            return opt
        print(f"  download failed: {opt}, trying next")
    raise SystemExit(f"all downloads failed: {options}")


def draw_beats(x, bpm, beats, downbeats, drop, path):
    """Three strips: whole track, first 4 bars, 4 bars either side of the drop."""
    W, Hs = 2400, 300
    img = Image.new("RGB", (W, Hs * 3 + 40), "#F7F8F6")
    d = ImageDraw.Draw(img)
    bar = 4 * 60 / bpm
    strips = [(0, len(x) / A.SR, "whole track"), (0, min(beats[0] + 5 * bar, len(x) / A.SR), "start: first downbeat"),
              (drop - 4 * bar, drop + 4 * bar, "drop ±4 bars")]
    for k, (t0, t1, label) in enumerate(strips):
        y0, mid = k * Hs + 30 + k * 5, k * Hs + 30 + k * 5 + Hs // 2
        seg = x[int(max(t0, 0) * A.SR): int(t1 * A.SR)]
        cols = np.array_split(np.abs(seg), W)
        for px, c in enumerate(cols):  # peak level per pixel column, drawn symmetric
            a = (c.max() if len(c) else 0) * (Hs / 2 - 10)
            d.line([(px, mid - a), (px, mid + a)], fill="#9AA5A0")
        X = lambda t: (t - t0) / (t1 - t0) * W
        for b in beats:
            if t0 <= b <= t1:
                strong = np.isclose(downbeats, b).any()
                d.line([(X(b), y0), (X(b), y0 + (Hs if strong else Hs // 5))], fill="#0B8F63" if strong else "#15201B", width=2 if strong else 1)
        if t0 <= drop <= t1:
            d.line([(X(drop), y0), (X(drop), y0 + Hs)], fill="#C24A1B", width=4)
        d.text((8, y0 - 22), f"{label}  ({t0:.2f}s to {t1:.2f}s)   green = downbeat, black tick = beat, orange = drop {drop:.3f}s",
               fill="#15201B")
    img.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    mid, title, artist, page = first(MUSIC, lambda o: f"https://assets.mixkit.co/music/{o[0]}/{o[0]}.mp3",
                                     lambda o: OUT / f"music-{o[0]}.mp3")
    mpath = OUT / f"music-{mid}.mp3"
    x = A.load(mpath)
    bpm, beats = A.beat_grid(x)
    ph = A.downbeat_phase(x, beats)
    downbeats = beats[ph::4]
    drop, jump = A.find_drop(x, downbeats)
    if not 110 <= bpm <= 125:
        raise SystemExit(f"{title} measured {bpm:.2f} BPM, outside 110-125")
    rows.append((mpath.name, f"music: {title}" + (f" by {artist}" if artist else ""), page, MUSIC_LICENSE, len(x) / A.SR, A.peak_ms(x)))

    for event, opts in SFX.items():
        sid, stitle, cat = first(opts, lambda o: f"https://assets.mixkit.co/active_storage/sfx/{o[0]}/{o[0]}.wav",
                                 lambda o: OUT / f"sfx-{event}-{o[0]}.wav")
        p = OUT / f"sfx-{event}-{sid}.wav"
        s = A.load(p)
        rows.append((p.name, f"{event}: {stitle}", f"https://mixkit.co/free-sound-effects/{cat}/", SFX_LICENSE, len(s) / A.SR, A.peak_ms(s)))

    draw_beats(x, bpm, beats, downbeats, drop, KIT / "beats.png")

    period = 60 / bpm
    lines = ["# Audio kit", "",
             "Real recordings from Mixkit, downloaded and measured by `kit.py` (numpy, see `audiokit.py`).",
             "Peak = loudest sample, in ms from the start of the file. Put an effect at `event_time - peak` so its peak lands on the event.", "",
             "| File | Sound | Mixkit page | License | Length | Peak |", "|---|---|---|---|---|---|"]
    for name, what, page, lic, length, peak in rows:
        lines.append(f"| `audio/{name}` | {what} | {page} | {lic} | {length * 1000:.0f} ms | {peak:.1f} ms |")
    lines += ["", "## Music timing", "",
              f"- **BPM:** {bpm:.2f} (one beat = {period * 1000:.2f} ms, one bar = {4 * period * 1000:.1f} ms)",
              f"- **First downbeat:** {downbeats[0]:.3f} s",
              f"- **Drop:** {drop:.3f} s (dropBar {int(np.argmin(np.abs(downbeats - drop)))}, "
              f"loudness jumps {jump:+.1f} dB: mean of the next 4 bars vs the previous 4)",
              f"- **Beat grid:** beat n is at `{beats[0]:.4f} + n * {period:.6f}` s. The grid is one fixed tempo fitted to the whole track.",
              f"- **Downbeats:** every 4th beat from {downbeats[0]:.3f} s."
              + (f" The beats before it ({', '.join(f'{b:.3f}' for b in beats[:ph])} s) are a pickup." if ph else " The track starts on beat 1."),
              "", "Beat times in seconds, one bar per line (bar 0 starts at the first downbeat, as `dropBar` and `music.bars` "
              "count; `*` = drop):", "", "```"]
    if ph:
        lines.append("pickup  " + "  ".join(f"{b:8.3f}" for b in beats[:ph]))
    for i, dbt in enumerate(downbeats):
        bar = beats[ph + 4 * i: ph + 4 * i + 4]
        lines.append(f"bar {i:3d} " + "  ".join(f"{b:8.3f}" for b in bar) + ("  *" if np.isclose(dbt, drop) else ""))
    lines += ["```", "", "`beats.png`: the waveform with every beat (black), downbeat (green) and the drop (orange), "
              "plus close-ups of the first bars and the drop.", ""]
    (KIT / "AUDIO.md").write_text("\n".join(lines))
    print(f"{title}: {bpm:.2f} BPM, first downbeat {downbeats[0]:.3f}s, drop {drop:.3f}s ({jump:+.1f} dB)")
    for r in rows:
        print(f"  {r[0]:32s} {r[4] * 1000:7.0f} ms  peak {r[5]:7.1f} ms")


def self_test():
    """fetch() takes only https, gives up on a stalled server, and rejects a page that isn't audio (S9)."""
    global KIT, OUT, fetch
    import http.server, tempfile, threading
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<html>" + b"x" * 5000 + b"</html>")
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as t:
        dest = pathlib.Path(t) / "a.mp3"
        assert not fetch(f"http://127.0.0.1:{srv.server_address[1]}/a.mp3", dest), "fetched over plain http / accepted an html page"
        dest.write_bytes(b"GOOD" * 400)                  # a download that isn't audio never overwrites the asset already there (R7)
        real_run = subprocess.run
        def fake_curl(cmd, **kw):                         # curl succeeds but the server sent a page
            pathlib.Path(cmd[cmd.index("-o") + 1]).write_bytes(b"<html>" + b"x" * 5000)
            return subprocess.CompletedProcess(cmd, 0, "text/html", "")
        subprocess.run = fake_curl
        try:
            assert not fetch("https://example.test/a.mp3", dest)
        finally:
            subprocess.run = real_run
        assert dest.read_bytes() == b"GOOD" * 400, "an existing asset was overwritten by a download that isn't audio"
    srv.shutdown()
    # main(), offline (downloads copied from a built kit): no invented "Checked" line, the drop bar numbered the way
    # timeline.js counts it (dropBar, 0-based), an existing fallback file kept (a film may use it) (I19, X15, X14)
    src = pathlib.Path(__file__).resolve().parents[2] / "kit" / "audio"
    if not (src / "music-474.mp3").exists():
        print("kit self-check ok (main() skipped: no built kit to copy from)"); return
    import shutil
    saved = KIT, OUT, fetch
    with tempfile.TemporaryDirectory() as t:
        KIT = pathlib.Path(t) / "kit"; OUT = KIT / "audio"; OUT.mkdir(parents=True)
        (OUT / "sfx-click-1117.wav").write_bytes((src / "sfx-click-1113.wav").read_bytes())   # a fallback a film picked earlier
        fetch = lambda url, dest: (src / dest.name).exists() and bool(shutil.copy(src / dest.name, dest))
        try:
            main()
        finally:
            KIT, OUT, fetch = saved
        md = (pathlib.Path(t) / "kit" / "AUDIO.md").read_text()
        assert "Checked" not in md, "a hard-coded measurement line"
        assert "dropBar 32" in md and "bar  32" in md.split("```")[1], md[-2500:]
        assert (pathlib.Path(t) / "kit" / "audio" / "sfx-click-1117.wav").exists(), "a fallback file was deleted"
    print("kit self-check ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test(); sys.exit()
    main()
