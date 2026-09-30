"""film.py: one command for every film, whatever the style. A film is a folder with index.html (window.seek,
window.motion), timeline.js (const TL = {...}) and motion.js.

  film.py new <dir> [--size 1080x1920]    copy the template film (index.html, timeline.js, motion.js, fonts, CLAUDE.md)
  film.py mix <dir>                       music bars + effects on measured peaks + voice -> audio/mix.wav (-14 LUFS)
                                          and stems (music.wav, sfx.wav, voice.wav)
  film.py render <dir> [--workers 6] [--from F --to F] [--animatic] [--max-samples 64] [--shutter 360] [--out film.mp4]
                                          partial renders write part_F-T.mp4, animatics animatic.mp4; only a full render writes film.mp4
                                          motion blur: 4 samples a frame, doubling with motion up to --max-samples;
                                          a full render writes recipe.json
  film.py mux <dir>                       re-attach a new mix to the last render, no frames rendered
  film.py replay <dir>                    re-render from recipe.json and prove every frame matches
  film.py check <dir> [name ...] [--film f.mp4]  contact layout determinism asserts facts phone first poster pops seams loop
                                          peaks avsync lufs loopcheck (default: all that apply)
  film.py export <dir>                    captions.srt/.vtt, chapters.txt, poster.png, preview.gif
  film.py doctor [dir]                    which login and keys this workspace uses (Claude Code/Codex login first)
  film.py strip <dir> <seconds>           12 frames in a row around a fast moment
  film.py frames <dir> <beat> [...]       single unblurred frames at beats, for close looks

SIZE=1080x1920 (or 1080x1080) before any command reframes the film: the page reads innerWidth/innerHeight.
"""
import argparse, json, math, os, pathlib, re, shutil, subprocess, sys, time
from multiprocessing import Process

ENGINE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
from lint import tl_of as timeline, kit_dir, load_env, local_login, lint, fmt, inside, Refused, facts, unsourced, NUM  # noqa: E402
SR = 48000


def kit(d):
    return kit_dir(d) or sys.exit("no kit/AUDIO.md found above the film: build one with engine/kit.py or set MOTION_KIT")


def size(tl):
    if os.environ.get("SIZE"):
        return tuple(map(int, os.environ["SIZE"].split("x")))
    os.environ["SIZE"] = f"{tl['width']}x{tl['height']}"    # render.py reads SIZE at import
    return tl["width"], tl["height"]


def renderer(d):
    from render import Renderer
    return Renderer(d / "index.html")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# ---------------------------------------------------------------- new
def cmd_new(a):
    d = pathlib.Path(a.dir)
    clash = [n for n in [p.name for p in (ENGINE / "template").iterdir()] + ["motion.js"] if (d / n).exists()]
    if clash:                                   # brief files may already be here; film files never get overwritten
        raise SystemExit(f"{d} already has {', '.join(clash)}")
    shutil.copytree(ENGINE / "template", d, dirs_exist_ok=True)
    shutil.copy(ENGINE / "motion.js", d / "motion.js")
    if not (d / "CLAUDE.md").exists():          # the film's rules: paste the style card under "# Look"
        shutil.copy(ENGINE.parent / "skills" / "motion-video" / "CLAUDE.template.md", d / "CLAUDE.md")
    if a.size:
        w, h = map(int, a.size.split("x"))
        t = (d / "timeline.js").read_text()
        (d / "timeline.js").write_text(re.sub(r'"width": \d+, "height": \d+', f'"width": {w}, "height": {h}', t, count=1))
    print(f"new film in {d}: paste the style card into CLAUDE.md, edit timeline.js and index.html, then mix, render, check")


# ---------------------------------------------------------------- mix
def load(path, ch=2):
    from audiokit import load as decode
    return decode(path, SR, ch)


def music_bars(tl, bar_s, track_s):
    """Explicit bars win. Otherwise play the track straight through, started so its drop lands on the payoff."""
    m = tl["music"]
    n = math.ceil(tl["totalBeats"] / 4)
    if "bars" in m:
        if len(m["bars"]) != n:                  # more crash the mix, fewer leave the end silent
            raise SystemExit(f"music.bars lists {len(m['bars'])} bars; the film is {n} bars long")
        last = int((track_s - m["firstDownbeat"]) / bar_s) - 1
        bad = [b for b in m["bars"] if not isinstance(b, int) or not 0 <= b <= last]
        if bad:
            raise SystemExit(f"music.bars {bad}: the track has whole bars 0 to {last}")
        return m["bars"]
    if m.get("payoffCue") not in tl["cues"]:
        raise SystemExit("music needs a payoffCue that is in cues (to land the drop), or explicit music.bars")
    payoff_bar = tl["cues"][m["payoffCue"]] / 4
    if payoff_bar != int(payoff_bar):
        raise SystemExit(f"payoff cue {m['payoffCue']} is not on a downbeat (beat {payoff_bar * 4})")
    start = m["dropBar"] - int(payoff_bar)
    last = (track_s - m["firstDownbeat"]) / bar_s
    if start < 0 or start + n > last:
        raise SystemExit(f"the track cannot put its drop (bar {m['dropBar']}) on film bar {int(payoff_bar)} "
                         f"for {n} bars: write music.bars by hand (loop bars measured as close)")
    return list(range(start, start + n))


def cmd_mix(a):
    import numpy as np
    d = pathlib.Path(a.dir)
    tl = timeline(d)
    KIT = kit(d)
    beat, n = tl["beat"], round(tl["totalBeats"] * tl["beat"] * SR)
    db = lambda x: 10 ** (x / 20)

    def place(buf, clip, start, gain=1.0):
        i = round(start * SR)
        lo, hi = max(i, 0), min(i + len(clip), len(buf))
        if hi > lo:
            buf[lo:hi] += clip[lo - i: hi - i] * gain

    def rms_db(x):
        live = x[np.abs(x).max(1) > 1e-4]
        return 10 * np.log10(np.mean(live ** 2)) if len(live) else None   # silence has no level: skip it

    sfx = np.zeros((n, 2), np.float32)
    for e in tl.get("sfx", []):
        clip = load(inside(KIT, e["file"]))
        peak = np.argmax(np.abs(clip.mean(1))) / SR   # measured here, at the mix rate (see kit/AUDIO.md note)
        if e.get("peakFirst"):                         # clicks: press and release peaks are near-equal
            env = np.abs(clip.mean(1))
            peak = np.argmax(env > 0.7 * env.max()) / SR
        place(sfx, clip, e["beat"] * beat - peak, db(e.get("gainDb", 0)))
    ty = tl.get("typing")
    if ty:
        want = round((ty["to"] - ty["from"]) * beat * SR)
        clip = load(inside(KIT, ty["file"]))[SR: SR + want]           # skip the first second (the recording's run-up)
        if len(clip) < want:
            raise SystemExit(f"typing from beat {ty['from']} to {ty['to']} needs {want / SR:.1f} s; {ty['file']} has "
                             f"{len(clip) / SR:.1f} s after its first second: shorten it or type in two runs")
        f = min(len(clip) // 4, int(0.05 * SR))
        clip[:f] *= np.linspace(0, 1, f)[:, None]; clip[-f:] *= np.linspace(1, 0, f)[:, None]
        place(sfx, clip, ty["from"] * beat, db(ty.get("gainDb", -14)))

    voice = np.zeros((n, 2), np.float32)
    for ln in tl.get("lines", []):
        place(voice, load(inside(d, ln["file"])), ln["beat"] * beat)

    music = np.zeros((n, 2), np.float32)
    m, bars = tl.get("music"), []
    if m:
        src = load(inside(KIT, m["file"]))
        bar = 4 * 60 / m["bpm"]
        bars = music_bars(tl, bar, len(src) / SR)
        xf, prev = int(0.008 * SR), None
        for i, b in enumerate(bars):
            d0, d1 = round(i * bar * SR), round((i + 1) * bar * SR)
            seg = src[round((m["firstDownbeat"] + b * bar) * SR):][: d1 - d0].copy()
            if prev is not None and b != prev + 1:        # a jump: 8 ms equal-power join
                cont = src[round((m["firstDownbeat"] + (prev + 1) * bar) * SR):][:xf]
                r = np.sin(np.linspace(0, np.pi / 2, xf))[:, None].astype(np.float32)
                seg[:xf] = seg[:xf] * r + cont[: len(seg[:xf])] * r[::-1]
            music[d0: d0 + len(seg)] += seg[: n - d0]
            prev = b
        if tl.get("loop"):                                 # the seam plays the film's end into its start: end on the
            s0 = round((m["firstDownbeat"] + bars[0] * bar) * SR)     # track's own lead-in to the first bar, so it's continuous
            if s0 < 2 * xf:
                raise SystemExit("a looping film needs the track's lead-in before its first bar: start music.bars at bar 1 or later")
            pre = src[s0 - 2 * xf: s0]
            r = np.sin(np.linspace(0, np.pi / 2, xf))[:, None].astype(np.float32)
            music[n - 2 * xf: n - xf] = music[n - 2 * xf: n - xf] * r[::-1] + pre[:xf] * r
            music[n - xf:] = pre[xf:]
    r = rms_db(music)
    if r is not None:                                  # level first, so the gain and ducking below survive
        music *= db(-18 - r)
    gain = np.zeros(n, np.float32)
    if tl.get("lines"):                                # duck under the voice, full on the payoff
        talk = np.zeros(n, np.float32)
        for ln in tl["lines"]:
            talk[max(round((ln["beat"] * beat - .15) * SR), 0): round(((ln["beat"] + ln["len"]) * beat + .2) * SR)] = 1
        k = np.convolve(talk, np.ones(int(.25 * SR)) / int(.25 * SR), "same")   # 250 ms ramps
        gain = -6 - 9 * np.clip(k, 0, 1)
        if m.get("payoffCue"):
            t = np.arange(n) / SR - (tl["cues"][m["payoffCue"]] * beat + .4)
            gain[np.abs(t) < .9] = 0
    music *= db(gain)[:, None]

    r = rms_db(voice)
    if r is not None:
        voice *= db(-18 - r)
    mix = voice + music + sfx
    if not np.abs(mix).max() > 1e-4:          # loudnorm can't raise silence to -14 LUFS
        sys.exit("nothing to mix: the timeline has no music, effects or voice lines")
    out = d / "audio"
    out.mkdir(exist_ok=True)
    raw = out / "mix_raw.f32"
    mix.astype(np.float32).tofile(raw)
    master(raw, out / "mix.wav")
    raw.unlink()
    sfx.astype(np.float32).tofile(out / "sfx_stem.f32")    # read by `check peaks`
    for name, stem in (("music", music), ("sfx", sfx), ("voice", voice)):   # levelled stems, before the master
        if np.abs(stem).max() > 1e-4:
            run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_s24le",
                 str(out / f"{name}.wav")], input=stem.astype(np.float32).tobytes())
    print("wrote", out / "mix.wav", f"music bars {bars[0]}-{bars[-1]}" if bars else "(no music)")


AAC = ["-c:a", "aac", "-b:a", "320k"]           # at 192k the encoder overshot peaks by up to 3.3 dB in the smoke test


def true_peak(p):
    o = subprocess.run(["ffmpeg", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(re.search(r"Peak:\s+(-?(?:[\d.]+|inf)) dBFS", o[o.rindex("Summary"):])[1])


def riding(raw, dst):
    """dB by which some stretch of the master gets more gain than the typical stretch: 0 for plain gain (a limiter
    only ever takes gain away), more when loudnorm rides the gain. Compared in 0.4 s windows."""
    import numpy as np
    x = np.fromfile(raw, np.float32).reshape(-1, 2).mean(1)
    y = load(dst, 1)
    w, n = int(.4 * SR), min(len(x), len(y))
    g = [20 * np.log10(np.sqrt(np.mean(y[i:i + w] ** 2)) / np.sqrt(np.mean(x[i:i + w] ** 2)))
         for i in range(0, n - w, w) if np.mean(x[i:i + w] ** 2) > 1e-8]
    return float(np.percentile(g, 95) - np.median(g)) if g else 0.0


def master(raw, dst, tp=-1.5):
    """-14 LUFS with true peak <= -1 dBTP in the delivered AAC, not just the WAV. A short limiter first holds the few
    effect peaks down just enough for plain gain to reach -14 LUFS (loudnorm's own fallback compresses the whole mix);
    its look-ahead is compensated, so no sound moves. Then encode, measure how far AAC overshoots, and go again with
    that much more headroom."""
    src = ["-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(raw)]
    lim = None
    limiter = lambda: f"alimiter=limit={lim:.5f}:attack=5:release=50:level=false:latency=true," if lim else ""
    measure = lambda: (lambda e: json.loads(e[e.rindex("{"): e.rindex("}") + 1]))(run(
        ["ffmpeg", "-v", "info", "-y", *src, "-af", limiter() + f"loudnorm=I=-14:TP={tp}:LRA=11:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr)
    floor = None                                 # the limiter takes at most 12 dB off the input's peaks
    for _ in range(2):
        for _ in range(4):                       # limiting lowers the loudness a little: settle the threshold
            q = measure()
            floor = floor or 10 ** ((float(q["input_tp"]) - 12) / 20)
            allowed = tp - 0.5 - (-14 - float(q["input_i"]))       # peak before the gain; 0.5 dB for true-peak overshoot
            if float(q["input_tp"]) <= allowed:
                break
            new = min(max(10 ** (allowed / 20), floor, 0.0625), 1.0)
            settled = lim is not None and abs(math.log10(new / lim) * 20) < 0.1
            lim = new
            if settled:
                q = measure(); break
        else:
            q = measure()                        # the loop ran out: measure with the limiter actually used
        ln = (f"loudnorm=I=-14:TP={tp}:LRA=11:measured_I={q['input_i']}:measured_TP={q['input_tp']}:measured_LRA={q['input_lra']}:"
              f"measured_thresh={q['input_thresh']}:offset={q['target_offset']}:linear=true:print_format=json")
        done = run(["ffmpeg", "-v", "info", "-y", *src, "-af", limiter() + ln + f",aresample={SR}", "-c:a", "pcm_s24le", str(dst)],
                   capture_output=True, text=True).stderr
        enc = dst.with_suffix(".check.m4a")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), *AAC, str(enc)])
        over = true_peak(enc) - true_peak(dst)
        enc.unlink()
        if true_peak(dst) + over <= -1.2:
            break
        tp = round(-1.2 - max(over, 0), 1)       # second pass: exactly the headroom this mix needs
    if riding(raw, dst) > 0.5:   # measured, not loudnorm's own report ("dynamic" even for plain gain)
        print("note: the gain rides through the mix: the loudest peaks stand more than 12 dB over what -14 LUFS allows;"
              " lower the loudest effects or raise the quiet stems")
    if lim:
        print(f"limiter: peaks held at {20 * math.log10(lim):.1f} dBFS before the gain")


# ---------------------------------------------------------------- mux
def mux(d, video, out, start, dur):
    """Picture + audio/mix.wav -> out. The audio is cut or padded to exactly the picture's length (never -shortest,
    which can drop the last frames' sound)."""
    mix = d / "audio" / "mix.wav"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video)]
    if mix.exists():
        cmd += ["-ss", f"{start:.6f}", "-i", str(mix), "-map", "0:v", "-map", "1:a", "-af", f"apad=whole_dur={dur:.6f}",
                "-t", f"{dur:.6f}", *AAC]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", str(out)]
    run(cmd)


def cmd_mux(a):
    """Re-attach a new mix to the last render without rendering a frame (after `mix`, for sound-only notes)."""
    d = pathlib.Path(a.dir).resolve()
    tl = timeline(d)
    video = d / "build" / "video.mp4"
    if not video.exists():
        raise SystemExit("no build/video.mp4: render first")
    mux(d, video, d / (a.out or "film.mp4"), 0, tl["totalBeats"] * tl["beat"])
    print("re-muxed", a.out or "film.mp4", "with audio/mix.wav" if (d / "audio" / "mix.wav").exists() else "with no audio/mix.wav: silent")


# ---------------------------------------------------------------- doctor
def cmd_doctor(a):
    """Which login and which keys this workspace will use. Never prints a key."""
    env = load_env(a.dir or ".")
    print(".env:", env.pop("_file", "none found (copy .env.example to your workspace as .env)"))
    for cli, key in (("claude", "ANTHROPIC_API_KEY"), ("codex", "OPENAI_API_KEY")):
        li = local_login(cli)
        print(f"{cli:7s} {'logged in via ' + li if li else 'no local login: sign in, or export ' + key + ' in the shell that runs it'}")
        if li and os.environ.get(key):
            print(f"        note: {key} is exported in your shell; {cli} may bill it instead of the login")
    prov = os.environ.get("VOICE_PROVIDER", "google")
    need = {"google": ["GEMINI_API_KEY"], "microsoft": ["AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"],
            "elevenlabs": ["ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"]}.get(prov, [])
    print(f"voice   provider {prov} (only used by voice.py --tts):",
          ", ".join(f"{k} {'set' if os.environ.get(k) else 'missing'}" for k in need) or "unknown provider")
    k = kit_dir(pathlib.Path(a.dir or "."))
    print("kit    ", k or "missing (engine/kit.py builds it)")


# ---------------------------------------------------------------- export
def poster_time(tl):
    """Seconds: the "poster" cue if the film sets one (a payoff that lands by morph is mid-change just after it),
    else 0.3 s after the payoff cue."""
    if "poster" in tl["cues"]:
        return tl["cues"]["poster"] * tl["beat"]
    return tl["cues"].get((tl.get("music") or {}).get("payoffCue", "payoff"), tl["totalBeats"] / 2) * tl["beat"] + .3


def srt_time(t, sep):
    """Seconds as HH:MM:SS,mmm (sep "," for SRT, "." for VTT), from whole milliseconds so 1.9996 s is 2.000, not 1.000."""
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"


def cmd_export(a):
    """The delivery bundle next to film.mp4: captions.srt/.vtt (from voice lines, else the on-screen "captions":
    [{"at": cue or beat, "text"}], each until the next or the end), chapters.txt (YouTube, from shots
    with a "title"), poster.png (poster_time), preview.gif (8 s, 480 px)."""
    d = pathlib.Path(a.dir).resolve()
    tl = timeline(d)
    film, beat = d / (a.film or "film.mp4"), tl["beat"]
    out = []
    at = lambda v: tl["cues"][v] if isinstance(v, str) else float(v)
    shown = [at(c["at"]) for c in tl.get("captions", [])] + [tl["totalBeats"]]
    cues = ([(ln["beat"] * beat, (ln["beat"] + ln["len"]) * beat, ln["text"]) for ln in tl["lines"]] if tl.get("lines") else
            [(b0 * beat, b1 * beat, c["text"]) for b0, b1, c in zip(shown, shown[1:], tl.get("captions", []))])
    cues = [(a0, a1, " ".join(t.split())) for a0, a1, t in cues]          # one line per cue: a blank line ends it
    vtt = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for f in ("captions.srt", "captions.vtt", "chapters.txt"):
        (d / f).unlink(missing_ok=True)              # written fresh below, or gone with their inputs
    if cues:
        (d / "captions.srt").write_text("".join(f"{i}\n{srt_time(a0, ',')} --> {srt_time(a1, ',')}\n{t}\n\n" for i, (a0, a1, t) in enumerate(cues, 1)))
        (d / "captions.vtt").write_text("WEBVTT\n\n" + "".join(f"{srt_time(a0, '.')} --> {srt_time(a1, '.')}\n{vtt(t)}\n\n" for a0, a1, t in cues))
        out += ["captions.srt", "captions.vtt"]
    titled = [s_ for s_ in tl.get("shots", []) if s_.get("title")]
    if titled:
        if titled[0]["start"] != 0:
            titled.insert(0, {"start": 0, "title": "Intro"})
        ends = [s_["start"] for s_ in titled[1:]] + [tl["totalBeats"]]
        short = [f"{s_['title']} ({(e - s_['start']) * beat:.1f} s)" for s_, e in zip(titled, ends) if (e - s_["start"]) * beat < 10]
        if len(titled) < 3 or short:              # YouTube ignores the whole list: 3+ chapters, each 10 s or more
            print("no chapters.txt: YouTube needs 3 or more chapters, each 10 s or more;",
                  f"{len(titled)} chapters" if len(titled) < 3 else "under 10 s: " + ", ".join(short))
        else:
            (d / "chapters.txt").write_text("".join(f"{int(s_['start'] * beat // 60)}:{int(s_['start'] * beat % 60):02d} {s_['title']}\n" for s_ in titled))
            out.append("chapters.txt")
    if film.exists():
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{poster_time(tl):.3f}", "-i", str(film), "-frames:v", "1", str(d / "poster.png")])
        run(["ffmpeg", "-v", "error", "-y", "-t", "8", "-i", str(film), "-vf",
             "fps=15,scale=480:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer",
             str(d / "preview.gif")])
        out += ["poster.png", "preview.gif"]
    print("exported:", ", ".join(out) or "nothing (no lines, titled shots or film.mp4)")


# ---------------------------------------------------------------- recipe
def sha(path):
    import hashlib
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:16]


def frames_hash(video):
    """Hash of every decoded frame (framemd5), so container metadata can't make equal films look different."""
    import hashlib
    out = run(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True).stdout
    return hashlib.sha256("\n".join(l.split(",")[-1] for l in out.splitlines() if l and not l.startswith("#")).encode()).hexdigest()[:16]


def write_recipe(d, tl, args, video):
    """recipe.json: everything that decides the film, hashed. Same recipe + same engine -> same frames (film.py replay)."""
    inputs = {str(p.relative_to(d)): sha(p) for p in sorted(d.rglob("*")) if p.is_file() and p.suffix in
              (".html", ".js", ".md", ".json", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ttf", ".otf", ".woff2", ".wav")
              and not any(x in p.parts for x in ("build", "frames", "audio", "seams")) and p.name not in ("recipe.json", "checks.json")
              and not re.fullmatch(r"(contact|first|poster|phone_\d+|strip_[\d.]+)\.png", p.name)}   # check outputs aren't inputs
    kitd = kit(d)
    sounds = {e["file"] for e in tl.get("sfx", [])} | {x["file"] for x in (tl.get("music"), tl.get("typing")) if x}
    rec = {"engine": {"film.py": sha(__file__), "motion.js": sha(ENGINE / "motion.js"), "render.py": sha(ENGINE / "render.py")},
           "size": os.environ["SIZE"], "args": args, "inputs": inputs,
           "kit": {f: sha(kitd / f) for f in sorted(sounds) if (kitd / f).exists()},
           "mix": sha(d / "audio" / "mix.wav") if (d / "audio" / "mix.wav").exists() else None,
           "frames": frames_hash(video), "rendered": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (d / "recipe.json").write_text(json.dumps(rec, indent=1))
    return rec


def cmd_replay(a):
    """Re-render from the recipe's settings and compare every frame with the recorded film."""
    d = pathlib.Path(a.dir).resolve()
    rec = json.loads((d / "recipe.json").read_text())
    os.environ["SIZE"] = rec["size"]
    changed = [k for k, v in rec["inputs"].items() if not (d / k).exists() or sha(d / k) != v]
    kitd, mix = kit(d), d / "audio" / "mix.wav"
    changed += [f"engine {k}" for k, v in rec["engine"].items() if sha(ENGINE / k) != v]
    changed += [f"kit {k}" for k, v in rec["kit"].items() if not (kitd / k).exists() or sha(kitd / k) != v]
    changed += ["audio/mix.wav"] if rec["mix"] != (sha(mix) if mix.exists() else None) else []
    ns = argparse.Namespace(dir=str(d), out="replay.mp4", f0=0, f1=None, animatic=False, **rec["args"])
    cmd_render(ns, record=False)
    same = frames_hash(d / "replay.mp4") == rec["frames"]
    print(("IDENTICAL: every frame matches the recipe" if same else "DIFFERENT frames")
          + (f"; inputs changed since: {', '.join(changed)}" if changed else ""))
    sys.exit(0 if same else 1)


# ---------------------------------------------------------------- render
def samples(mv, cap):
    """Motion-blur samples for a frame that moves mv px: double from 4 while a sample steps more than 3.75 px
    (over 15 px/frame -> 8, over 30 -> 16, over 60 -> 32, over 120 -> 64), never more than cap."""
    n = 4
    while n < cap and mv / n > 3.75:
        n = min(n * 2, cap)
    return n


def sample_times(f, n, fps, shutter=360):
    """The n blur samples of frame f, in seconds: spread evenly over the shutter, centred on the frame's time.
    Each rounds back to f (round(t * fps) == f), which is how a page holds one value across a frame."""
    return [(f + ((j + .5) / n - .5) * shutter / 360) / fps for j in range(n)]


def worker(d, k, f0, f1, fps, animatic, outdir, cap=64, shutter=360):
    import numpy as np
    r = renderer(d)
    W, H = map(int, os.environ["SIZE"].split("x"))
    vf = ("scale=960:-2," if animatic else "") + "format=yuv420p"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(fps), "-i", "-", "-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                           str(outdir / f"part_{k:03d}.mp4")], stdin=subprocess.PIPE)
    used = []
    for f in range(f0, f1):         # r.shot: the same lossless capture every check inspects
        if animatic:
            ff.stdin.write(r.shot(f / fps).astype(np.uint8).tobytes()); used.append(1)
        else:
            n = samples(r.page.evaluate(f"window.motion({f / fps!r})"), cap)
            acc = sum(r.shot(t) for t in sample_times(f, n, fps, shutter))
            ff.stdin.write(np.rint(acc / n).astype(np.uint8).tobytes())
            used.append(n)
        if len(used) % 10 == 0:                   # progress for the parent, which prints it
            (outdir / f"part_{k:03d}.done").write_text(str(len(used)))
    (outdir / f"part_{k:03d}.done").write_text(str(len(used)))
    ff.stdin.close(); r.close()
    if ff.wait():                                 # a failed encode can still leave a short part file behind
        raise SystemExit(f"encoder failed on part {k} (frames {f0}-{f1})")
    (outdir / f"part_{k:03d}.json").write_text(json.dumps(used))


def cmd_render(a, record=True):
    d = pathlib.Path(a.dir).resolve()
    blocking = [f for f in lint(d) if f["sev"] == "B"]
    if blocking:                                 # the rules gate every render, not just the docs
        sys.exit("lint blocks the render:\n" + "\n".join(fmt(f) for f in blocking))
    tl = timeline(d)
    size(tl)
    fps = tl["fps"]
    total = round(tl["totalBeats"] * tl["beat"] * fps)
    f0, f1 = a.f0, min(total if a.f1 is None else a.f1, total)
    if a.workers < 1 or not 0 <= f0 < f1:
        raise SystemExit(f"nothing to render: --workers {a.workers}, frames {f0} to {f1} of {total} (need workers >= 1, from < to)")
    outdir = d / "build"
    outdir.mkdir(exist_ok=True)
    for old in outdir.glob("part_*"):
        old.unlink()
    step = -(-(f1 - f0) // a.workers)
    ranges = [(f0 + i * step, min(f1, f0 + (i + 1) * step)) for i in range(a.workers) if f0 + i * step < f1]
    t0 = time.time()
    ps = [Process(target=worker, args=(d, k, s, e, fps, a.animatic, outdir, a.max_samples, a.shutter)) for k, (s, e) in enumerate(ranges)]
    for p in ps: p.start()
    said = 0
    while any(p.is_alive() for p in ps):          # print each quarter as it passes
        time.sleep(0.5)
        done = sum(int(q.read_text() or 0) for q in outdir.glob("part_*.done"))
        while said < 3 and done >= (said + 1) * (f1 - f0) / 4:
            said += 1; print(f"{25 * said}% ({done} of {f1 - f0} frames, {time.time() - t0:.0f}s)", flush=True)
    for p in ps: p.join()
    if any(p.exitcode for p in ps):
        raise SystemExit("a render worker failed")
    (outdir / "parts.txt").write_text("".join(f"file '{p.name}'\n" for p in sorted(outdir.glob("part_*.mp4"))))
    variant = a.out not in (None, "film.mp4") or os.environ["SIZE"] != f"{tl['width']}x{tl['height']}"   # another name or size
    full = not a.animatic and f0 == 0 and f1 == total and not variant   # only this becomes film.mp4 and the video mux reuses
    name = "film" if full else "animatic" if a.animatic else f"part_{f0}-{f1}" if (f0, f1) != (0, total) else pathlib.Path(a.out or "variant").stem
    video = outdir / ("video.mp4" if full and record else f"video_{name if record else 'replay'}.mp4")   # replay never replaces it
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(outdir / "parts.txt"), "-c", "copy", str(video)])
    out = d / (a.out or f"{name}.mp4")
    mux(d, video, out, f0 / fps, (f1 - f0) / fps)
    mix = d / "audio" / "mix.wav"
    if record and full:
        write_recipe(d, tl, {k: v for k, v in vars(a).items() if k in ("workers", "max_samples", "shutter")}, video)
    used = sum((json.loads(p.read_text()) for p in outdir.glob("part_*.json")), [])
    blur_counts = {n: used.count(n) for n in sorted(set(used)) if n > 4}
    print(f"{f1 - f0} frames in {time.time() - t0:.0f}s (frames per blur sample count beyond 4: {blur_counts or 'none'}) -> {out.name}"
          + ("" if mix.exists() else "  [no audio/mix.wav: silent]"))


# ---------------------------------------------------------------- checks
def gray(path, w=192, h=108):
    import numpy as np
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
              capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def pops(v, ratio=4.0, floor=0.6, planned=()):   # ponytail: whole-frame mean at 192x108; a tiny pop in one corner can hide
    """A flash (a frame unlike both neighbours) or a hard cut (one big change, calm either side) that isn't
    planned: `planned` holds the first frame of each intended cut."""
    import numpy as np
    dd = np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))
    found = []
    med = lambda *ws: max([float(np.median(w)) for w in ws if len(w)] + [floor])   # one-sided at the film's edges
    for i in range(len(dd)):
        spike = min(dd[i - 1], dd[i]) if i else 0
        around = med(dd[max(i - 4, 0): max(i - 1, 0)], dd[i + 1: i + 4])
        cut, calm = dd[i], med(dd[max(i - 4, 0): i], dd[i + 1: i + 5])
        if spike > ratio * around:
            found.append((i, float(spike), float(around)))
        elif i == 0 and cut > ratio * calm and len(dd) > 1 and dd[1] <= ratio * calm:    # frame 0 unlike the rest: a flash
            found.append((0, float(cut), float(calm)))
        elif cut > ratio * calm and not {i, i + 1, i + 2} & set(planned):
            found.append((i + 1, float(cut), float(calm)))
    once = {}                                        # a flash's first edge also reads as a cut: one report a frame
    for f in found:
        once.setdefault(f[0], f)
    return dd, sorted(once.values())


def loop_seam(v):
    """The jump from the last frame back to the first vs a normal step: the median of the last 8. A seamless loop
    moves across the seam like any other frame; the last step alone can't be the yardstick (a pop there hides a seam)."""
    import numpy as np
    fl = float(abs(v[0] - v[-1]).mean())
    step = float(np.median(np.abs(np.diff(v[-9:], axis=0)).mean(axis=(1, 2))))
    return {"firstVsLast": round(fl, 2), "step": round(step, 2), "fail": fl > max(1.0, 1.5 * step)}


SHOWN_JS = """
const hidden = e => { for (let p = e; p && p !== document.documentElement; p = p.parentElement) {
    const cs = getComputedStyle(p); if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return true; }
  return false; };
const insetOf = (cs, q) => { const m = cs.clipPath.match(/^inset\\(([^)]*)\\)/); if (!m) return null;
  const v = m[1].split(/\\s+round\\s+/)[0].trim().split(/\\s+/);
  const [t, r, b, l] = [v[0], v[1] ?? v[0], v[2] ?? v[0], v[3] ?? v[1] ?? v[0]];
  const len = (x, size) => x.endsWith('%') ? parseFloat(x) / 100 * size : parseFloat(x) || 0;
  const w = q.right - q.left, h = q.bottom - q.top;
  return [q.left + len(l, w), q.top + len(t, h), q.right - len(r, w), q.bottom - len(b, h)]; };
const shownBox = (e, r) => {     // e's box cut by its own clip-path inset and by every mask above it; a full-frame stage is the frame
  let a = [r.left, r.top, r.right, r.bottom];
  const cut = c => { a = [Math.max(a[0], c[0]), Math.max(a[1], c[1]), Math.min(a[2], c[2]), Math.min(a[3], c[3])]; };
  for (let p = e; p && p !== document.body; p = p.parentElement) {
    const cs = getComputedStyle(p), q = p.getBoundingClientRect(), ins = insetOf(cs, q);
    if (ins) cut(ins);
    if (p === e || cs.overflow === 'visible') continue;
    if (q.left <= 0 && q.top <= 0 && q.right >= innerWidth && q.bottom >= innerHeight) continue;
    cut([q.left, q.top, q.right, q.bottom]); }
  return a[2] - a[0] > 1 && a[3] - a[1] > 1 ? a : null; };
"""


LAYOUT_JS = """(minPx) => {""" + SHOWN_JS + """
  const vw = innerWidth, vh = innerHeight, items = [];
  const bg = e => { for (let p = e; p; p = p.parentElement) { const cs = getComputedStyle(p);
      if (cs.backgroundImage !== 'none' || p.tagName === 'IMG') return null;   // ponytail: text over images is skipped, judged by eye
      const m = cs.backgroundColor.match(/[\\d.]+/g); if (m && (m.length < 4 || +m[3] > 0.9)) return m.slice(0, 3).map(Number); }
    return [255, 255, 255]; };
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
  [...document.querySelectorAll('body *')].forEach((e, id) => {
    if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2 || hidden(e)) return;
    const a = shownBox(e, r); if (!a) return;
    const cs = getComputedStyle(e), fs = parseFloat(cs.fontSize) * (e.offsetHeight ? r.height / e.offsetHeight : 1);
    const text = e.textContent.trim().slice(0, 40), it = {id, text, r: a, px: Math.round(fs)};
    if (fs < minPx) it.small = true;
    if (a[2] <= 0 || a[3] <= 0 || a[0] >= vw || a[1] >= vh) return;          // wholly out of shot: not in the frame at all
    if (a[0] < -1 || a[1] < -1 || a[2] > vw + 1 || a[3] > vh + 1) it.off = true;   // cut by the frame's edge
    const b = bg(e), c = cs.color.match(/[\\d.]+/g).slice(0, 3).map(Number);
    if (b) { const L1 = lum(c), L2 = lum(b), ratio = (Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05);
      if (ratio < (fs >= 24 ? 3 : 4.5)) it.contrast = +ratio.toFixed(2); }
    items.push(it); });
  const over = [];
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
    const a = items[i].r, b = items[j].r, w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
    const small = Math.min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]));
    if (w > 0 && h > 0 && w * h > .2 * small && !items[i].text.includes(items[j].text) && !items[j].text.includes(items[i].text))
      over.push([items[i].text, items[j].text]); }
  return {items: items.filter(x => x.small || x.off || x.contrast), over};
}"""


def check_layout(d, tl, W, H):
    """Every beat: text below the minimum size for the format, text off the frame, overlapping text, low contrast.
    Boxes are cut by their masks. Small means still small a quarter second later: text popping out isn't read."""
    r = renderer(d)
    min_px = 28 * min(W, H) / 1080
    seen, found = set(), []
    for b in [x + .5 for x in range(int(tl["totalBeats"]))]:
        r.page.evaluate(f"window.seek({b * tl['beat'] + .25!r})")
        later = {it["id"] for it in r.page.evaluate(LAYOUT_JS, min_px)["items"] if it.get("small")}   # the element, not its text
        r.page.evaluate(f"window.seek({b * tl['beat']!r})")
        out = r.page.evaluate(LAYOUT_JS, min_px)
        for it in out["items"]:
            for kind in ("small", "off", "contrast"):
                key = (kind, it["id"] if kind == "small" else it["text"])    # a changing counter is one finding, not one per value
                if it.get(kind) and key not in seen and (kind != "small" or it["id"] in later):
                    seen.add(key)
                    found.append({"kind": kind, "beat": b, "text": it["text"], "px": it["px"],
                                  **({"ratio": it["contrast"]} if kind == "contrast" else {})})
        for a_, b_ in out["over"]:
            if ("overlap", a_ + b_) not in seen:
                seen.add(("overlap", a_ + b_)); found.append({"kind": "overlap", "beat": b, "text": f"{a_} / {b_}"})
    r.close()
    return {"minPx": round(min_px, 1), "found": found}


def check_determinism(d, tl, n=8):   # ponytail: 8 sampled beats, not every frame; raise n if a state bug slips through
    """The same beats rendered in order in one browser and shuffled (with detours) in another must match exactly.
    Catches state kept between frames, which an in-order render hides."""
    import hashlib, random
    beats = [tl["totalBeats"] * (i + .5) / n for i in range(n)]
    hs = lambda r, b: hashlib.sha1(r.shot(b * tl["beat"]).tobytes()).hexdigest()
    r1 = renderer(d); first = {b: hs(r1, b) for b in beats}; r1.close()
    order = beats[:]; random.Random(7).shuffle(order)
    r2 = renderer(d); second = {}
    for b in order:
        r2.page.evaluate(f"window.seek({(tl['totalBeats'] - b) * tl['beat']!r})")    # a detour first
        second[b] = hs(r2, b)
    r2.close()
    return [round(b, 2) for b in beats if first[b] != second[b]]


def align(seg, c):
    """(lag, confidence): where c's shape best matches inside seg, by Pearson correlation at every lag. A raw dot
    product would favour whichever lag overlaps the loudest audio, not the matching shape."""
    import numpy as np
    n = len(c)
    cz = (c - c.mean()) / (np.linalg.norm(c - c.mean()) + 1e-12)
    dot = np.correlate(seg, cz, "valid")                          # cz sums to 0, so seg's mean drops out
    cs, cs2 = np.r_[0, np.cumsum(seg)], np.r_[0, np.cumsum(seg ** 2)]
    var = (cs2[n:] - cs2[:-n]) - (cs[n:] - cs[:-n]) ** 2 / n    # n * variance of each window
    r = dot / np.sqrt(np.maximum(var, 1e-12))
    k = int(np.argmax(r))
    return k, float(r[k])


def check_avsync(d, tl, fps, film):
    """How far each effect's moment in the final encoded audio sits from the same moment in audio/mix.wav, where
    `peaks` already proved it lands on its event. The reference holds the music too, so a drum hit beside an effect
    can't win the correlation. Passes within one frame and 20 ms; a stretch too flat to align is reported, not guessed."""
    import numpy as np
    env = lambda y: np.convolve(np.abs(y), np.ones(96) / 96, "same")          # 2 ms smoothing
    X, M, out = env(load(film, 1)), env(load(d / "audio" / "mix.wav", 1)), []
    tol = min(20, 1000 / fps)
    for e in tl.get("sfx", []):
        t = e["beat"] * tl["beat"]
        c0 = max(int((t - .25) * SR), 0)
        c = M[c0: c0 + int(.5 * SR)]                    # half a second round the event: 90 ms of a slow whoosh is too flat to align
        lo = max(c0 - int(.08 * SR), 0)
        seg = X[lo: lo + len(c) + int(.16 * SR)]
        if len(seg) < len(c) + 2 or c.std() == 0:            # nothing to align: reported, never dropped
            out.append({"file": e["file"], "beat": e["beat"], "errorMs": None, "confidence": 0.0, "ok": None,
                        "note": "too flat or too close to the end to align: listen"}); continue
        k, conf = align(seg, c)
        err = ((lo + k - c0) / SR) * 1000
        out.append({"file": e["file"], "beat": e["beat"], "errorMs": round(err, 1), "confidence": round(conf, 2),
                    "ok": None if conf < .5 else abs(err) <= tol})   # ponytail: a flat stretch (conf < .5) goes to the human listen
    return {"toleranceMs": round(tol, 1), "effects": out}


def check_asserts(d, tl):
    """timeline.js "asserts": [{"sel": "#pill", "appearsBy": "payoff"}, {"sel": ".card", "staysInFrame": ["s01.in", "s01.out"]}].
    Times are cue names or beats."""
    r = renderer(d)
    at = lambda v: tl["cues"][v] if isinstance(v, str) else float(v)
    probe = """(sel) => {""" + SHOWN_JS + """ const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect();
      if (hidden(e)) return {vis: false};
      let a = shownBox(e, r) || [0, 0, 0, 0];           // what shows: cut by its masks, then by the frame
      a = [Math.max(a[0], 0), Math.max(a[1], 0), Math.min(a[2], innerWidth), Math.min(a[3], innerHeight)];
      const shown = Math.max(0, a[2] - a[0]) * Math.max(0, a[3] - a[1]);
      return {vis: r.width > 1 && r.height > 1, inside: r.left >= -1 && r.top >= -1 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1,
              onscreen: shown >= 0.5 * r.width * r.height}; }"""
    fails = []
    for x in tl.get("asserts", []):
        if r.page.evaluate("(sel) => !document.querySelector(sel)", x["sel"]):
            fails.append(f"{x['sel']} matches nothing"); continue
        if "appearsBy" in x:
            b = at(x["appearsBy"]); r.page.evaluate(f"window.seek({b * tl['beat']!r})")
            s_ = r.page.evaluate(probe, x["sel"])
            if not s_["vis"] or not s_["onscreen"]:
                fails.append(f"{x['sel']} not visible in the frame by {x['appearsBy']} (beat {b:g})")
        if "staysInFrame" in x:
            b0, b1 = map(at, x["staysInFrame"])
            for b in [b0 + (b1 - b0) * i / 8 for i in range(9)]:
                r.page.evaluate(f"window.seek({b * tl['beat']!r})")
                s_ = r.page.evaluate(probe, x["sel"])
                if s_["vis"] and not s_["inside"]:
                    fails.append(f"{x['sel']} leaves the frame at beat {b:.2f}"); break
    r.close()
    return fails


def check_facts(d, tl):
    """Every number the page shows, read from its visible text (masks, clip-path insets and the frame applied; input values
    too), sampled every quarter beat, has a facts.md row; an example row needs "Example" in the number's own card.
    Catches what lint can't see: static HTML, arrays, helpers, interpolation. Shown means still there 0.2 s later:
    a counter's in-between values last a frame and claim nothing."""
    r, ledger, found = renderer(d), facts(d), {}
    js = """() => {""" + SHOWN_JS + """
      const out = [], seen = e => { if (/^(SCRIPT|STYLE)$/.test(e.tagName) || hidden(e)) return null;
        const a = shownBox(e, e.getBoundingClientRect());
        return a && a[2] > 0 && a[3] > 0 && a[0] < innerWidth && a[1] < innerHeight; };
      const card = e => { for (let p = e, k = 0; p && p !== document.body && k < 5; p = p.parentElement, k++) {   // up to the card,
          const q = p.getBoundingClientRect(); if (q.width * q.height > 0.5 * innerWidth * innerHeight) break;   // never the stage
          if (/example/i.test(p.innerText || '')) return true; }
        return false; };
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (w.nextNode()) { const e = w.currentNode.parentElement; if (w.currentNode.data.trim() && seen(e)) out.push([w.currentNode.data, card(e)]); }
      for (const e of document.querySelectorAll('input, textarea')) if (e.value && seen(e)) out.push([e.value, card(e)]);
      return out; }"""
    at = lambda t: (r.page.evaluate(f"window.seek({t!r})"), r.page.evaluate(js))[1]
    for b in [k / 4 + .125 for k in range(int(tl["totalBeats"] * 4))]:
        now, later = at(b * tl["beat"]), at(b * tl["beat"] + .2)
        held = {x.strip() for t, _ in later for x in NUM.findall(t)}
        for t, labelled in now:
            for x, row in (u for u in unsourced(t, ledger) if u[0] in held):
                if not row or not labelled:
                    found.setdefault(x, {"text": x, "beat": b, "why": "no facts.md row" if not row else "example without an Example label in its card"})
    r.close()
    return {"found": list(found.values())}


def planned_frames(tl):
    """First frame of every intended cut: each shot's start after the first, and timeline "cuts" (beats or cue names)."""
    at = lambda v: tl["cues"][v] if isinstance(v, str) else float(v)
    return {round(at(b) * tl["beat"] * tl["fps"]) for b in [s_["start"] for s_ in tl.get("shots", [])[1:]] + tl.get("cuts", [])}


def tile_size(W, H):
    """A contact-sheet tile: the frame's shape, long side 320 px."""
    return (320, round(320 * H / W)) if W >= H else (round(320 * W / H), 320)


CHECKS = ("contact", "layout", "determinism", "asserts", "facts", "phone", "first", "poster", "pops", "seams", "loop",
          "peaks", "avsync", "lufs", "loopcheck")


def cmd_check(a):
    import numpy as np
    from PIL import Image, ImageDraw
    d = pathlib.Path(a.dir).resolve()
    tl = timeline(d)
    W, H = size(tl)
    film, fps, beat = d / (a.film or "film.mp4"), tl["fps"], tl["beat"]
    names = a.names or list(CHECKS)
    if not tl.get("loop"):
        names = [x for x in names if x not in ("loop", "loopcheck")] if not a.names else names
    res, bad = {}, []
    if "contact" in names:          # one frame per beat, unblurred, beat number on each tile
        beats = [b + .5 for b in range(int(tl["totalBeats"]))]
        (tw, th), cols = tile_size(W, H), 16
        sheet = Image.new("RGB", (cols * tw, -(-len(beats) // cols) * th), "white")
        dr, r, errs = ImageDraw.Draw(sheet), renderer(d), []
        r.page.on("pageerror", lambda e: errs.append(str(e)))
        for i, b in enumerate(beats):
            x, y = (i % cols) * tw, (i // cols) * th
            sheet.paste(Image.fromarray(r.shot(b * beat).astype("uint8")).resize((tw, th)), (x, y))
            dr.rectangle([x, y, x + 48, y + 16], fill="black"); dr.text((x + 3, y + 2), f"{b:g}", fill="white")
        r.close(); sheet.save(d / "contact.png")
        res["contact"] = {"file": "contact.png", "pageErrors": errs[:5]}
        if errs: bad.append("contact: page errors")
    if "layout" in names:
        res["layout"] = check_layout(d, tl, W, H)
        if res["layout"]["found"]:
            bad.append("layout: " + ", ".join(sorted({f["kind"] for f in res["layout"]["found"]})))
    if "determinism" in names:
        diff = check_determinism(d, tl)
        res["determinism"] = {"differingBeats": diff}
        if diff: bad.append(f"determinism: beats {diff} change with render order (state kept between frames)")
    if "asserts" in names and tl.get("asserts"):
        res["asserts"] = check_asserts(d, tl)
        if res["asserts"]: bad.append("asserts: " + "; ".join(res["asserts"]))
    if "facts" in names:
        res["facts"] = check_facts(d, tl)
        if res["facts"]["found"]:
            bad.append("facts: " + ", ".join(f"'{f['text']}' at beat {f['beat']:g} ({f['why']})" for f in res["facts"]["found"]))
    if not film.exists() and any(x in names for x in ("phone", "first", "poster", "pops", "seams", "loop", "peaks", "avsync", "lufs", "loopcheck")):
        raise SystemExit(f"{film.name} missing: render first (contact runs without it)")
    if "phone" in names:
        sc = "scale=390:-2" if W >= H else "scale=-2:844"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(film), "-vf", f"fps=1,{sc},tile=6x5", str(d / "phone_%02d.png")])
        res["phone"] = {"file": "phone_01.png"}
    if "first" in names:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(film), "-frames:v", "1", str(d / "first.png")])
        res["first"] = {"file": "first.png"}
    if "poster" in names:
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{poster_time(tl):.3f}", "-i", str(film), "-frames:v", "1", str(d / "poster.png")])
        res["poster"] = {"file": "poster.png", "at": round(poster_time(tl), 3)}
    if "pops" in names or "loop" in names:
        v = gray(film)
        if "pops" in names:
            dd, found = pops(v, planned=planned_frames(tl))
            res["pops"] = {"frames": len(v), "median": round(float(np.median(dd)), 2),
                           "found": [{"frame": i, "t": round(i / fps, 3), "beat": round(i / fps / beat, 1), "jump": round(s, 1),
                                      "around": round(o, 1)} for i, s, o in found]}
            if found: bad.append(f"pops: {len(found)}")
        if "loop" in names:
            res["loop"] = loop_seam(v)
            if res["loop"].pop("fail"): bad.append("loop: the seam jumps more than a normal step")
    if "peaks" in names and tl.get("sfx") and not (d / "audio" / "sfx_stem.f32").exists():
        raise SystemExit("no audio/sfx_stem.f32 for peaks: mix first")
    if "peaks" in names and tl.get("sfx"):
        x = np.abs(np.fromfile(d / "audio" / "sfx_stem.f32", np.float32).reshape(-1, 2).mean(1))
        errs = []
        for e in tl.get("sfx", []):
            t = e["beat"] * beat
            lo = max(int((t - .1) * SR), 0)
            i = lo + int(np.argmax(x[lo: lo + int(.2 * SR)]))
            errs.append({"file": e["file"], "beat": e["beat"], "errorMs": round((i / SR - t) * 1000, 1)})
        res["peaks"] = errs
        if any(abs(e["errorMs"]) > 5 for e in errs): bad.append("peaks: an effect is more than 5 ms off")
    if "lufs" in names:
        out = subprocess.run(["ffmpeg", "-nostats", "-i", str(film), "-af", "ebur128=peak=true", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        if "Summary" in out:
            s = out[out.rindex("Summary"):]
            num = r"(-?(?:[\d.]+|inf))"               # a silent track reads -inf, and still gets judged
            i_, tp = float(re.search(r"I:\s+" + num + " LUFS", s)[1]), float(re.search(r"Peak:\s+" + num + " dBFS", s)[1])
            lra = float(re.search(r"LRA:\s+" + num + " LU", s)[1])
            res["lufs"] = {"integrated": i_, "truePeak": tp, "lra": lra}
            if lra > 15: bad.append(f"lufs: loudness range {lra} LU (over 15: quiet parts vanish on a phone)")
            if abs(i_ + 14) > 1 or tp > -1: bad.append("lufs: not -14 +/-1 or true peak above -1")
        else:                                        # no audio, or ffmpeg failed: either way the film isn't -14 LUFS
            res["lufs"] = "not measured: " + (out.strip().splitlines() or ["no output"])[-1]
            bad.append("lufs: no loudness measured (film has no audio, or ffmpeg failed)")
    if "avsync" in names and tl.get("sfx"):
        res["avsync"] = check_avsync(d, tl, fps, film)
        off = [e for e in res["avsync"]["effects"] if e["ok"] is False]
        if off: bad.append(f"avsync: {len(off)} effects off their event in the final file")
    if "seams" in names and len(tl.get("shots", [])) > 1:
        (d / "seams").mkdir(exist_ok=True)
        for sh in tl["shots"][1:]:
            f = round(sh["start"] * beat * fps)
            run(["ffmpeg", "-v", "error", "-y", "-i", str(film), "-vf",
                 f"select='between(n\\,{f - 2}\\,{f + 2})',scale=384:-2,tile=5x1", "-frames:v", "1", "-fps_mode", "vfr",
                 str(d / "seams" / f"seam_{sh['id']}.png")])
        res["seams"] = {"dir": "seams/", "count": len(tl["shots"]) - 1, "note": "frames -2..+2 at every cut: look for a pop or a near-identical frame across the cut"}
    if "loopcheck" in names:
        run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "1", "-i", str(film), "-c", "copy", str(d / "loop_check.mp4")])
        res["loopcheck"] = {"file": "loop_check.mp4", "note": "a human watches the seam"}
    res["failed"], res["ran"], res["film"] = bad, names, film.name
    (d / "checks.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    print("FAIL: " + "; ".join(bad) if bad else "all measured checks pass")
    if bad:
        sys.exit(1)


def cmd_strip(a):
    d = pathlib.Path(a.dir)
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(a.t - .1, 0):.3f}", "-i", str(d / "film.mp4"),
         "-vf", "scale=320:-2,tile=12x1", "-frames:v", "1", str(d / f"strip_{a.t:g}.png")])
    print(d / f"strip_{a.t:g}.png")


def cmd_frames(a):
    from PIL import Image
    d = pathlib.Path(a.dir).resolve()
    tl = timeline(d); size(tl)
    (d / "frames").mkdir(exist_ok=True)
    r = renderer(d)
    for b in a.beats:
        Image.fromarray(r.shot(b * tl["beat"]).astype("uint8")).save(d / "frames" / f"b{b:g}.png")
    r.close()
    print(f"{len(a.beats)} frames in {d / 'frames'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("dir"); p.add_argument("--size", help="WxH, e.g. 1080x1920 (default 1920x1080)")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("mix"); p.add_argument("dir"); p.set_defaults(fn=cmd_mix)
    p = sub.add_parser("render"); p.add_argument("dir"); p.add_argument("--workers", type=int, default=6)
    p.add_argument("--from", dest="f0", type=int, default=0); p.add_argument("--to", dest="f1", type=int)
    p.add_argument("--animatic", action="store_true"); p.add_argument("--out")
    p.add_argument("--max-samples", type=int, default=64, help="blur sample cap (4..64)")
    p.add_argument("--shutter", type=float, default=360, help="shutter angle: 360 = full frame, 180 = crisper")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("doctor"); p.add_argument("dir", nargs="?"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("export"); p.add_argument("dir"); p.add_argument("--film"); p.set_defaults(fn=cmd_export)
    p = sub.add_parser("replay"); p.add_argument("dir"); p.set_defaults(fn=cmd_replay)
    p = sub.add_parser("mux"); p.add_argument("dir"); p.add_argument("--out"); p.set_defaults(fn=cmd_mux)
    p = sub.add_parser("check"); p.add_argument("dir"); p.add_argument("names", nargs="*", choices=CHECKS)
    p.add_argument("--film", help="the rendered file to check (default film.mp4)"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("strip"); p.add_argument("dir"); p.add_argument("t", type=float); p.set_defaults(fn=cmd_strip)
    p = sub.add_parser("frames"); p.add_argument("dir"); p.add_argument("beats", type=float, nargs="+"); p.set_defaults(fn=cmd_frames)
    a = ap.parse_args()
    if a.fn is not cmd_doctor:      # doctor loads it itself, to report where each value came from
        load_env(getattr(a, "dir", None) or ".")
    try:
        a.fn(a)
    except Refused as e:
        sys.exit(f"refused: {e}")
