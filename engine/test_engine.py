"""Engine self-check: make the template film, mix, render, run every measured check, and prove determinism.
Fails if the engine breaks. About 5 minutes. Run: .venv/bin/python engine/test_engine.py"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile

ENGINE = pathlib.Path(__file__).resolve().parent
PY, FILM = sys.executable, str(ENGINE / "film.py")

def main():
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp) / "film"
        run = lambda *a, **kw: subprocess.run([PY, FILM, *a, str(d)], check=True, capture_output=True, text=True, **kw)
        run("new")
        run("mix")
        out = run("render", "--workers", "4").stdout
        assert all(f"{q}%" in out for q in (25, 50, 75)), out          # a long render says how far it is (E8)
        r = subprocess.run([PY, FILM, "check", str(d)], capture_output=True, text=True)
        res = json.loads((d / "checks.json").read_text())
        assert r.returncode == 0, r.stdout[-600:]
        assert not res["pops"]["found"], res["pops"]
        assert res["loop"]["firstVsLast"] < 1.0, res["loop"]
        assert all(abs(p["errorMs"]) <= 5 for p in res["peaks"]), res["peaks"]
        assert abs(res["lufs"]["integrated"] + 14) <= 1 and res["lufs"]["truePeak"] <= -1 and res["lufs"]["lra"] <= 15, res["lufs"]
        assert not res["layout"]["found"] and not res["determinism"]["differingBeats"], (res["layout"], res["determinism"])
        assert res["avsync"]["effects"] and all(e["ok"] is True for e in res["avsync"]["effects"]), res["avsync"]   # measured, not waved through (T2)
        # the final file's audio slipped 40 ms against the picture: avsync must catch it (E6 rework)
        good = (d / "film.mp4").read_bytes()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "build/video.mp4"), "-i", str(d / "audio/mix.wav"),
                        "-map", "0:v", "-map", "1:a", "-af", "adelay=40:all=1", "-shortest", "-c:v", "copy", "-c:a", "aac",
                        str(d / "film.mp4")], check=True)
        subprocess.run([PY, FILM, "check", str(d), "avsync"], capture_output=True, text=True)
        late = json.loads((d / "checks.json").read_text())["avsync"]["effects"]
        assert late and all(e["ok"] is False for e in late), late
        (d / "film.mp4").write_bytes(good)
        # what ships matches what the checks inspect: a settled film frame vs a lossless page shot (I3; JPEG capture measured 1.18)
        import numpy as np, os as _os
        sys.path.insert(0, str(ENGINE)); _os.environ["SIZE"] = "1920x1080"
        from render import Renderer
        t = 9.5 * 0.49586776859504134
        shot = Renderer(d / "index.html"); ref = shot.shot(t)
        # a new film draws in the house fonts, bundled with the template, not a system fallback (A1)
        assert shot.page.evaluate("document.fonts.check('800 40px Manrope') && document.fonts.check('italic 40px \"Instrument Serif\"')"
                                  " && [...document.fonts].some(f => f.family.includes('Manrope') && f.status === 'loaded')"), "fonts not loaded"
        # place() with a width or height of 0 sets 0, not the previous size (X9)
        assert shot.page.evaluate("(() => { const e = h('div', '', document.body); place(e, 0, 0, 50, 50); place(e, 0, 0, 0, 0);"
                                  " return e.style.width + ' ' + e.style.height; })()") == "0px 0px"
        # motion(): a one-step swap isn't motion (it would cost 64 blur samples for nothing); 30 px a frame is 30 (E9)
        mo = pathlib.Path(tmp) / "mo"
        shutil.copytree(d, mo)
        html = (mo / "index.html").read_text()
        i = html.index("function draw(b) {") + len("function draw(b) {")
        html = html[:i] + ("\n  if (window.__mode) { const T = 4 * TLB + 0.02, f = 1 / TL.fps, t = b * TLB;"
            "\n    const x = window.__mode === 'step' ? (b < 4 ? 0 : 500) : window.__mode === 'stop' ? Math.min(t, T) * TL.fps * 30"
            "\n      : window.__mode === 'two' ? (t < T - f / 4 ? 0 : 500) : b * TLB * TL.fps * 30;"
            "\n    place(dot, x, 0, 64, 64); dot.style.opacity = 1;"
            "\n    l1.style.transform = window.__mode === 'two' && t > T + f / 4 ? 'translateX(300px)' : ''; return; }") + html[i:]
        (mo / "index.html").write_text(html)
        rm = shot; rm.page.goto((mo / "index.html").as_uri())                  # one browser per thread: reuse it
        step = rm.page.evaluate(f"(async () => {{ window.__mode = 'step'; return await window.motion({4 * 0.49586776859504134 - 0.004}); }})()")
        move = rm.page.evaluate(f"(async () => {{ window.__mode = 'move'; return await window.motion({2 * 0.49586776859504134}); }})()")
        two = rm.page.evaluate(f"(async () => {{ window.__mode = 'two'; return await window.motion({4 * 0.49586776859504134 + 0.02}); }})()")
        stop = rm.page.evaluate(f"(async () => {{ window.__mode = 'stop'; return await window.motion({4 * 0.49586776859504134 + 0.02}); }})()")
        assert step < 15 and 25 < move < 35 and two < 15 and 25 < stop < 35, (step, move, two, stop)   # R23: per element, per quarter
        # track() keys in any order give the same value as sorted keys (E11)
        assert shot.page.evaluate("[6, 20].every(b => track(b, [[0, 0], [8, 100], [4, 50]]) === track(b, [[0, 0], [4, 50], [8, 100]]))")
        shot.close()
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", str(d / "film.mp4"), "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        err = np.abs(np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3).astype(float) - ref).mean()
        assert err < 0.8, f"film frame differs from the page by {err:.2f} (lossy capture?)"
        # a partial render or an animatic never replaces the full film or the video mux reuses (I4)
        keep = {p: (d / p).read_bytes() for p in ("film.mp4", "build/video.mp4")}
        run("render", "--from", "0", "--to", "30", "--workers", "2")
        run("render", "--animatic", "--workers", "2")
        assert all((d / p).read_bytes() == b for p, b in keep.items()), "a partial render or animatic overwrote the full film"
        assert (d / "part_0-30.mp4").exists() and (d / "animatic.mp4").exists()
        # a full render at another size, or to another name, is a variant: it never becomes the film mux and replay use (review)
        keep["recipe.json"] = (d / "recipe.json").read_bytes()
        subprocess.run([PY, FILM, "render", str(d), "--out", "film_9x16.mp4", "--workers", "4"], check=True, capture_output=True,
                       env={**os.environ, "SIZE": "1080x1920"})
        assert all((d / p).read_bytes() == b for p, b in keep.items()) and (d / "film_9x16.mp4").exists(), "a variant replaced the film"
        # a film with no music, effects or voice is refused by mix with a reason, not an ffmpeg traceback (found while checking I8)
        quiet = pathlib.Path(tmp) / "quiet"
        subprocess.run([PY, FILM, "new", str(quiet)], check=True, capture_output=True)
        q = json.loads((quiet / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        q["sfx"] = []; q.pop("music")
        (quiet / "timeline.js").write_text("const TL = " + json.dumps(q) + ";")
        r = subprocess.run([PY, FILM, "mix", str(quiet)], capture_output=True, text=True)
        assert r.returncode != 0 and "Traceback" not in r.stderr and "nothing to mix" in r.stderr, r.stderr[-300:]
        # sound paths stay inside the kit and voice paths inside the film; playlists are refused (S5)
        esc = pathlib.Path(tmp) / "escape"
        subprocess.run([PY, FILM, "new", str(esc)], check=True, capture_output=True)
        tlj = json.loads((esc / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        outside = pathlib.Path(tmp) / "outside.wav"                 # real audio, so only confinement can reject it
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=0.3", str(outside)], check=True)
        import os.path as op
        rel = op.relpath(outside, pathlib.Path(__file__).resolve().parent.parent.parent / "kit" / "audio")
        for bad in (str(outside), rel, "list.m3u8"):
            tlj["sfx"][0]["file"] = bad
            (esc / "timeline.js").write_text("const TL = " + json.dumps(tlj) + ";")
            r = subprocess.run([PY, FILM, "mix", str(esc)], capture_output=True, text=True)
            assert r.returncode != 0 and bad in r.stderr + r.stdout, f"mix accepted {bad}"
        # render refuses a film with a blocking lint finding (I6)
        bad = pathlib.Path(tmp) / "unsourced"
        subprocess.run([PY, FILM, "new", str(bad)], check=True, capture_output=True)
        html = (bad / "index.html").read_text().replace("function draw(b) {", "h('div', '', cam, 'Save 42%');\nfunction draw(b) {")
        (bad / "index.html").write_text(html)
        r = subprocess.run([PY, FILM, "render", str(bad), "--workers", "1"], capture_output=True, text=True)
        assert r.returncode != 0 and "invent" in r.stdout + r.stderr and not (bad / "film.mp4").exists(), r.stdout[-300:]
        # `new` works after motion-brief has written its files, and never overwrites a film (X3)
        b = pathlib.Path(tmp) / "briefed"; b.mkdir()
        for n in ("BRIEF.md", "facts.md", "shotlist.md"):
            (b / n).write_text(n)
        subprocess.run([PY, FILM, "new", str(b)], check=True, capture_output=True)
        assert (b / "index.html").exists() and (b / "BRIEF.md").read_text() == "BRIEF.md"
        r = subprocess.run([PY, FILM, "new", str(b)], capture_output=True, text=True)
        assert r.returncode != 0 and "index.html" in r.stderr + r.stdout, "new overwrote an existing film"
        # an unknown check name is an error, not a silent pass (I5)
        r = subprocess.run([PY, FILM, "check", str(d), "lufz"], capture_output=True, text=True)
        assert r.returncode != 0 and "lufz" in r.stderr + r.stdout and "pass" not in r.stdout, r.stdout[-200:]
        # a transient-heavy mix still meets -14 LUFS and -1 dBTP after AAC encoding (smoke-test finding L1)
        loud = pathlib.Path(tmp) / "loud"
        shutil.copytree(d, loud)
        lt = json.loads((loud / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        lt["sfx"] = [{**e, "gainDb": 6} for e in lt["sfx"]] + [{"file": "sfx-impact-3049.wav", "beat": b, "gainDb": 6} for b in (2, 4, 12)]
        (loud / "timeline.js").write_text("const TL = " + json.dumps(lt) + ";")
        subprocess.run([PY, FILM, "mix", str(loud)], check=True, capture_output=True)
        subprocess.run([PY, FILM, "mux", str(loud)], check=True, capture_output=True)
        r = subprocess.run([PY, FILM, "check", str(loud), "lufs"], capture_output=True, text=True)
        assert r.returncode == 0, json.loads((loud / "checks.json").read_text())["lufs"]
        # a film with no audio fails the loudness check instead of passing it (I2)
        mute = pathlib.Path(tmp) / "mute"
        shutil.copytree(d, mute)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "film.mp4"), "-an", "-c", "copy", str(mute / "film.mp4")], check=True)
        r = subprocess.run([PY, FILM, "check", str(mute), "lufs"], capture_output=True, text=True)
        assert r.returncode == 1 and json.loads((mute / "checks.json").read_text())["failed"], r.stdout[-300:]
        # a silent audio track (peak -inf) fails the check cleanly instead of crashing it (S15)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "film.mp4"), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "copy", "-c:a", "aac", str(mute / "film.mp4")], check=True)
        r = subprocess.run([PY, FILM, "check", str(mute), "lufs"], capture_output=True, text=True)
        assert r.returncode == 1 and "Traceback" not in r.stderr and json.loads((mute / "checks.json").read_text())["failed"], r.stderr[-300:]
        # a number the page draws with no facts.md row fails, however it got there: static HTML, an array (E2, X4)
        num = pathlib.Path(tmp) / "num"
        shutil.copytree(d, num)
        html = (num / "index.html").read_text().replace("<body>", "<body><h1 style='position:fixed'>Save $999</h1>", 1)
        i = html.rindex("</script>")
        (num / "index.html").write_text(html[:i] + "h('p', '', document.body, ['in', 12, 'days'].join(' '));" + html[i:])
        r = subprocess.run([PY, FILM, "check", str(num), "facts"], capture_output=True, text=True)
        found = {f["text"] for f in json.loads((num / "checks.json").read_text())["facts"]["found"]}
        assert r.returncode == 1 and found == {"$999", "12"}, (found, r.stdout[-300:], r.stderr[-300:])
        (num / "facts.md").write_text("| claim as shown | source | date | kind |\n|---|---|---|---|\n"
                                      "| Save $999 | https://x.test | 2026-09 | fact |\n| in 12 days | https://x.test | 2026-09 | fact |\n")
        r = subprocess.run([PY, FILM, "check", str(num), "facts"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-300:]
        # facts also reads input values, needs the Example label in the number's own card, ignores text a clip-path
        # hides, and catches a number shown for only a third of a second between beat centres (R13, R14)
        html = (num / "index.html").read_text().replace("<body>", "<body><input style='position:fixed;left:10px;top:900px' value='Only 4,999'>"
            "<div style='position:fixed;left:10px;top:960px'><p>77 seats</p></div><footer style='position:fixed;left:900px;top:960px'>Example</footer>"
            "<b style='position:fixed;left:10px;top:200px;clip-path:inset(100%)'>555 hidden</b>"
            "<b id='flash' style='position:fixed;left:10px;top:260px;display:none'>123 quick</b>", 1)
        i = html.index("function draw(b) {") + len("function draw(b) {")
        html = html[:i] + "\n  document.getElementById('flash').style.display = b > 2.6 && b < 3.3 ? 'block' : 'none';" + html[i:]
        (num / "index.html").write_text(html)
        (num / "facts.md").write_text((num / "facts.md").read_text() + "| 77 seats | seeded demo | | example |\n")
        subprocess.run([PY, FILM, "check", str(num), "facts"], capture_output=True, text=True)
        got = {f["text"]: f["why"] for f in json.loads((num / "checks.json").read_text())["facts"]["found"]}
        assert set(got) == {"4,999", "77", "123"} and "Example" in got["77"], got
        # an assert on a missing element, or on one wholly off the frame, fails; a true one passes (X10)
        html = (num / "index.html").read_text()
        (num / "index.html").write_text(html.replace("<body>", "<body><i id='off' style='position:fixed;left:3000px;width:9px;height:9px'></i>"
            "<div style='position:fixed;left:100px;top:300px;width:300px;height:40px;overflow:hidden'><b id='sunk' style='display:block;"
            "height:40px;transform:translateY(115%)'>Sunk</b></div><i id='sliver' style='position:fixed;left:1915px;top:0;width:100px;height:9px'></i>", 1))
        tl = json.loads((num / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["asserts"] = [{"sel": ".dot", "appearsBy": "payoff"}, {"sel": ".dot", "staysInFrame": ["s01.dot", "s01.fold"]},
                         {"sel": "#nope", "staysInFrame": [0, 4]}, {"sel": "#off", "appearsBy": 2},
                         {"sel": "#sunk", "appearsBy": 2}, {"sel": "#sliver", "appearsBy": 2}]
        (num / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "check", str(num), "asserts"], capture_output=True, text=True)
        fails = json.loads((num / "checks.json").read_text())["asserts"]
        assert len(fails) == 4 and [f.split()[0] for f in fails] == ["#nope", "#off", "#sunk", "#sliver"], fails   # half must show
        # layout measures what shows: a word half sunk into its mask doesn't overlap the line below, a word popping out
        # isn't "small"; text that stays 20 px is (E5)
        lay = pathlib.Path(tmp) / "lay"
        shutil.copytree(d, lay)
        html = (lay / "index.html").read_text().replace("<body>", "<body><div style='position:fixed;left:100px;top:100px;"
            "width:700px;height:60px;overflow:hidden'><b id='sink' style='display:block;font-size:48px;transform:translateY(40px)'>"
            "Sinking words</b></div><b style='position:fixed;left:100px;top:170px;font-size:48px'>Line below</b>"
            "<b id='pop' style='position:fixed;left:900px;top:100px;font-size:40px'>Popping</b>"
            "<i style='position:fixed;left:1500px;top:40px;font-size:20px'>Tiny label</i>"
            "<div style='position:fixed;inset:0;overflow:hidden'><b style='position:absolute;left:-300px;top:600px;font-size:48px'>"
            "Off the left edge</b><b style='position:absolute;left:-900px;top:700px;font-size:48px'>Out of shot</b></div>"
            "<b style='position:fixed;left:600px;top:40px;font-size:12px;clip-path:inset(100%)'>Clipped tiny</b>"
            "<b id='count' style='position:fixed;left:600px;top:120px;font-size:14px'>0</b>", 1)
        i = html.index("function draw(b) {") + len("function draw(b) {")
        html = (html[:i] + "\n  document.getElementById('pop').style.transform = `scale(${clamp(9 - b)})`;"
                + "\n  document.getElementById('count').textContent = String(Math.floor(b * 7));"   # small digits that change stay small (R15)
                + html[i:])
        (lay / "index.html").write_text(html)
        subprocess.run([PY, FILM, "check", str(lay), "layout"], capture_output=True, text=True)
        found = {(f["kind"], f["text"]) for f in json.loads((lay / "checks.json").read_text())["layout"]["found"]}
        assert {k for k, t in found} == {"small", "off"} and ("small", "Tiny label") in found and ("off", "Off the left edge") in found \
            and any(k == "small" and t.isdigit() for k, t in found) and not any("Clipped" in t or "Out of" in t for _, t in found), found
        # a looping film's music runs into its own first bar at the seam: the last 8 ms are the track's 8 ms before it (E10)
        from audiokit import load as decode
        import film
        tl = json.loads((d / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        src = decode(ENGINE.parents[1] / "kit" / "audio" / tl["music"]["file"], 48000, 1)
        bar = 4 * 60 / tl["music"]["bpm"]
        start = round((tl["music"]["firstDownbeat"] + film.music_bars(tl, bar, len(src) / 48000)[0] * bar) * 48000)
        m, xf = decode(d / "audio" / "music.wav", 48000, 1), int(0.008 * 48000)
        assert np.corrcoef(m[-xf:], src[start - xf: start])[0, 1] > 0.99, np.corrcoef(m[-xf:], src[start - xf: start])[0, 1]
        # a looping film whose music starts at the track's very first bar has no lead-in to end on: refused (R20)
        lp = pathlib.Path(tmp) / "lp"
        shutil.copytree(d, lp)
        tl = json.loads((lp / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["music"]["bars"] = [0, 1, 2, 3]
        (lp / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        r = subprocess.run([PY, FILM, "mix", str(lp)], capture_output=True, text=True)
        assert r.returncode != 0 and "lead-in" in r.stderr, r.stderr[-300:]
        # music ducks under the voice: normalising after the ducking must not undo it (X7)
        duck = pathlib.Path(tmp) / "duck"
        shutil.copytree(d, duck)
        (duck / "vo").mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=8", "-ar", "48000", "-ac", "1",
                        str(duck / "vo" / "take_01.wav")], check=True)
        tl = json.loads((duck / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["lines"] = [{"file": "vo/take_01.wav", "beat": 0, "len": 16, "text": "test tone"}]
        tl["music"].pop("payoffCue"); tl["music"]["bars"] = [1, 2, 3, 4]      # talk throughout, no lift on a payoff
        (duck / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "mix", str(duck)], check=True, capture_output=True)
        from audiokit import load as decode
        rms = lambda f: 10 * np.log10(np.mean(decode(duck / "audio" / f, 48000, 1)[24000:144000] ** 2))   # 0.5-3 s
        assert rms("voice.wav") - rms("music.wav") >= 12, (rms("voice.wav"), rms("music.wav"))
        # a film without a voice exports its on-screen captions: each from its cue (or beat) until the next (E13)
        cap = pathlib.Path(tmp) / "cap"
        shutil.copytree(d, cap)
        tl = json.loads((cap / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["captions"] = [{"at": 0, "text": "First line."}, {"at": "payoff", "text": "Second line."}]
        (cap / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "export", str(cap)], check=True, capture_output=True)
        assert (cap / "captions.srt").read_text() == ("1\n00:00:00,000 --> 00:00:03,967\nFirst line.\n\n"
                                                      "2\n00:00:03,967 --> 00:00:07,934\nSecond line.\n\n"), (cap / "captions.srt").read_text()
        # caption text is one line per cue, and VTT gets its markup characters escaped (S26)
        tl["captions"] = [{"at": 0, "text": "Fix it\nnow & <then>"}]
        (cap / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "export", str(cap)], check=True, capture_output=True)
        assert (cap / "captions.srt").read_text().splitlines()[2] == "Fix it now & <then>", (cap / "captions.srt").read_text()
        assert (cap / "captions.vtt").read_text().splitlines()[3] == "Fix it now &amp; &lt;then&gt;", (cap / "captions.vtt").read_text()
        # export removes captions and chapters whose inputs are gone (R30)
        tl.pop("captions"); (cap / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "export", str(cap)], check=True, capture_output=True)
        assert not (cap / "captions.srt").exists() and not (cap / "captions.vtt").exists(), "stale captions kept"
        # chapters YouTube would ignore (under 3, or one under 10 s) aren't written; the reason is printed (E14)
        tl["shots"] = [{"id": "a", "start": 0, "end": 30, "title": "One"}, {"id": "b", "start": 30, "end": 60, "title": "Two"},
                       {"id": "c", "start": 60, "end": 64, "title": "Three"}]
        tl["totalBeats"] = 64
        (cap / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        r = subprocess.run([PY, FILM, "export", str(cap)], check=True, capture_output=True, text=True)
        assert not (cap / "chapters.txt").exists() and "Three" in r.stdout and "10 s" in r.stdout, r.stdout
        tl["shots"][2]["end"] = tl["totalBeats"] = 90
        (cap / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "export", str(cap)], check=True, capture_output=True)
        assert (cap / "chapters.txt").read_text() == "0:00 One\n0:14 Two\n0:29 Three\n", (cap / "chapters.txt").read_text()
        # checks that need the film say so on an unrendered one; peaks with no effects stem fails instead of vanishing (I23, I7)
        bare = pathlib.Path(tmp) / "bare"
        shutil.copytree(d, bare, ignore=shutil.ignore_patterns("film.mp4", "audio"))
        for name in ("seams", "avsync", "peaks"):
            r = subprocess.run([PY, FILM, "check", str(bare), name], capture_output=True, text=True)
            assert r.returncode == 1 and "Traceback" not in r.stderr and ("render first" in r.stderr or "mix first" in r.stderr), (name, r.stderr[-300:])
        # render refuses ranges it can't make, with a reason (L17)
        for args in (["--workers", "0"], ["--from", "10", "--to", "5"], ["--to", "0"]):
            r = subprocess.run([PY, FILM, "render", str(bare), *args], capture_output=True, text=True)
            assert r.returncode != 0 and "Traceback" not in r.stderr, (args, r.stderr[-300:])
        # mux says when it attached no sound (L19); check reads the film it's told to (L18)
        r = subprocess.run([PY, FILM, "mux", str(bare), "--out", "silent.mp4"], capture_output=True, text=True)
        assert "no audio/mix.wav" in r.stdout, r.stdout
        r = subprocess.run([PY, FILM, "check", str(bare), "first", "--film", "silent.mp4"], capture_output=True, text=True)
        assert r.returncode == 0 and (bare / "first.png").exists(), r.stderr[-300:]
        # new: --size sets the format; the rules template becomes the film's CLAUDE.md, never over an existing one (A3)
        v = pathlib.Path(tmp) / "v"; v.mkdir(); (v / "CLAUDE.md").write_text("mine")
        subprocess.run([PY, FILM, "new", str(v), "--size", "1080x1920"], check=True, capture_output=True)
        tlv = json.loads((v / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        assert (tlv["width"], tlv["height"]) == (1080, 1920) and (v / "CLAUDE.md").read_text() == "mine", tlv
        w = pathlib.Path(tmp) / "w"
        subprocess.run([PY, FILM, "new", str(w)], check=True, capture_output=True)
        assert (w / "CLAUDE.md").read_text().startswith("# "), "no CLAUDE.md from the template"
        # a worker whose encoder fails fails the render, even when the part file got written (I14)
        shim = pathlib.Path(tmp) / "shim"; shim.mkdir()
        real = shutil.which("ffmpeg")
        (shim / "ffmpeg").write_text(f'#!/bin/sh\n"{real}" "$@"; s=$?\ncase "$*" in *libx264*) exit 1;; esac\nexit $s\n')
        (shim / "ffmpeg").chmod(0o755)
        r = subprocess.run([PY, FILM, "render", str(bare), "--from", "0", "--to", "12", "--workers", "1"], capture_output=True, text=True,
                           env={**os.environ, "PATH": f"{shim}:{os.environ['PATH']}"})
        assert r.returncode != 0 and not (bare / "part_0-12.mp4").exists(), (r.returncode, r.stdout[-200:], r.stderr[-300:])
        # typing: sound between its beats and silence after; a span longer than the recording is refused (T6, I21)
        ty = pathlib.Path(tmp) / "typing"
        shutil.copytree(d, ty)
        tl = json.loads((ty / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["sfx"], tl["typing"] = [], {"file": "sfx-typing-1396.wav", "from": 2, "to": 6}
        (ty / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "mix", str(ty)], check=True, capture_output=True)
        x = np.abs(np.fromfile(ty / "audio" / "sfx_stem.f32", np.float32).reshape(-1, 2).mean(1))
        at = lambda b: int(b * tl["beat"] * 48000)
        assert x[at(2.5):at(5.5)].max() > 0.01 and x[at(6.2):].max() == 0, (x[at(2.5):at(5.5)].max(), x[at(6.2):].max())
        tl["typing"]["to"], tl["totalBeats"], tl["music"] = 120, 128, None
        (ty / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        r = subprocess.run([PY, FILM, "mix", str(ty)], capture_output=True, text=True)
        assert r.returncode != 0 and "typing" in r.stderr and "Traceback" not in r.stderr, r.stderr[-300:]
        # planted faults: state kept between frames fails determinism (T1); seams, strip, frames and doctor run (T6)
        st = pathlib.Path(tmp) / "state"
        shutil.copytree(d, st)
        html = (st / "index.html").read_text()
        i = html.index("function draw(b) {") + len("function draw(b) {")
        (st / "index.html").write_text(html[:i] + "\n  window.__n = (window.__n || 0) + 1; l1.style.marginLeft = (window.__n % 7) * 9 + 'px';" + html[i:])
        subprocess.run([PY, FILM, "check", str(st), "determinism"], capture_output=True, text=True)
        assert json.loads((st / "checks.json").read_text())["determinism"]["differingBeats"], "kept state not caught"
        tl = json.loads((st / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["shots"] = [{"id": "a", "start": 0, "end": 8}, {"id": "b", "start": 8, "end": 16}]
        (st / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        subprocess.run([PY, FILM, "check", str(st), "seams"], check=True, capture_output=True)
        subprocess.run([PY, FILM, "strip", str(st), "2"], check=True, capture_output=True)
        assert (st / "seams" / "seam_b.png").exists() and (st / "strip_2.png").exists()
        r = subprocess.run([PY, FILM, "doctor", str(st)], capture_output=True, text=True)
        assert r.returncode == 0 and "kit" in r.stdout and "sk-" not in r.stdout, r.stdout
        # the pop scan finds a hard cut (one big change, calm either side) unless the timeline plans it (X11)
        import numpy as np
        from film import pops
        v = np.zeros((40, 108, 192)); v[20:] = 255
        assert [f[0] for f in pops(v)[1]] == [20], pops(v)[1]          # the first frame of the new picture
        assert not pops(v, planned={20})[1]
        # the recipe rebuilds every frame, and the delivery bundle exports
        subprocess.run([PY, FILM, "check", str(d), "contact", "phone", "first", "poster"], check=True, capture_output=True)
        run("render", "--workers", "4")                                     # check outputs existed when the recipe was written
        outputs = [k for k in json.loads((d / "recipe.json").read_text())["inputs"] if re.match(r"(contact|first|poster|phone_\d+)\.png$", k)]
        assert not outputs, f"check outputs recorded as inputs: {outputs}"
        video = (d / "build" / "video.mp4").read_bytes()
        rec = json.loads((d / "recipe.json").read_text())
        rec["engine"]["motion.js"] = "0" * 16; (d / "recipe.json").write_text(json.dumps(rec))
        r = subprocess.run([PY, FILM, "replay", str(d)], capture_output=True, text=True)
        assert r.returncode == 0 and "IDENTICAL" in r.stdout, r.stdout[-300:] + r.stderr[-300:]
        # replay names what changed outside the film too, and leaves the render mux reuses alone (I15)
        assert "motion.js" in r.stdout and (d / "build" / "video.mp4").read_bytes() == video, r.stdout[-300:]
        assert not any(x in r.stdout for x in ("contact.png", "poster.png", "phone_", "first.png")), r.stdout[-300:]   # outputs aren't inputs
        subprocess.run([PY, FILM, "export", str(d)], check=True, capture_output=True)
        assert (d / "poster.png").exists() and (d / "preview.gif").exists()
        # determinism: the same beat rendered in two fresh browsers is byte-identical
        shots = []
        for _ in range(2):
            subprocess.run([PY, FILM, "frames", str(d), "7.5"], check=True, capture_output=True)
            shots.append((d / "frames" / "b7.5.png").read_bytes())
        assert shots[0] == shots[1], "frame differs between renders"
        # reframing: a vertical frame renders at the vertical size
        subprocess.run([PY, FILM, "frames", str(d), "8.5"], check=True, capture_output=True, env={**os.environ, "SIZE": "1080x1920"})
        from PIL import Image
        assert Image.open(d / "frames" / "b8.5.png").size == (1080, 1920)
        for tool in ("voice.py", "capture.py", "kit.py"):
            subprocess.run([PY, str(ENGINE / tool), "--self-test"], check=True, capture_output=True)
        subprocess.run([PY, str(ENGINE / "test_units.py")], check=True, capture_output=True)   # the fast checks too (R36)
        print("engine self-check ok:", res["lufs"], "loop", res["loop"]["firstVsLast"], "peaks",
              [p["errorMs"] for p in res["peaks"]])


if __name__ == "__main__":
    main()
