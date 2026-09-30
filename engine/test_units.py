"""Fast checks of the engine's pure functions: no browser, no render. Run: .venv/bin/python engine/test_units.py"""
import pathlib, sys
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import film  # noqa: E402

# I10: a caption time never rounds back a second
assert film.srt_time(1.9996, ",") == "00:00:02,000", film.srt_time(1.9996, ",")
assert film.srt_time(3661.25, ".") == "01:01:01.250"

# I20: blur samples double past 15 px/frame, and never pass the cap
assert [film.samples(m, 64) for m in (15, 15.1, 30, 30.1, 1000)] == [4, 8, 8, 16, 64]
assert film.samples(1000, 48) == 48

# I21: explicit bars must cover the film exactly
tl = {"totalBeats": 16, "music": {"bars": [0, 1, 2, 3, 4]}, "cues": {}}
for bars in ([0, 1, 2, 3, 4], [0, 1, 2]):
    tl["music"]["bars"] = bars
    try:
        film.music_bars(tl, 2.0, 100); raise AssertionError(f"{len(bars)} bars for a 4-bar film accepted")
    except SystemExit as e:
        assert "4 bars long" in str(e), e
tl["music"] = {"dropBar": 8, "firstDownbeat": 0}                 # no bars and no payoffCue: say so, no KeyError
try:
    film.music_bars(tl, 2.0, 100); raise AssertionError("missing payoffCue accepted")
except SystemExit as e:
    assert "payoffCue" in str(e), e

# I22: a flash in the first or last frames is found
v = np.zeros((40, 4, 4)); v[1] = 255; v[38] = 255
assert [f[0] for f in film.pops(v)[1]] == [1, 38], film.pops(v)[1]                 # each once
v = np.zeros((40, 4, 4)); v[0] = 255; v[39] = 255                                   # the very first and last frames (R40)
assert [f[0] for f in film.pops(v)[1]] == [0, 39], film.pops(v)[1]

# I24: a loop seam is judged against the steps before it, not only the last one
steps = np.cumsum(np.r_[0, np.ones(30)]) * 1.0                   # a steady 1-level drift a frame
v = steps[:, None, None] * np.ones((31, 4, 4)); v[-1] += 155    # the last frame jumps
assert film.loop_seam(v)["fail"], film.loop_seam(v)
v = np.zeros((31, 4, 4))
assert not film.loop_seam(v)["fail"]
v = np.cumsum(np.ones(31))[:, None, None] * np.ones((31, 4, 4)); v[-1] = 5          # a pop on the last frame hides a seam
assert film.loop_seam(v)["fail"], film.loop_seam(v)                                  # the old last-step rule passed it (R29)

# E17 (and S16): a mix whose peaks are too high for plain gain gets a short limiter first, so loudnorm stays linear
# (no compressing), lands -14 LUFS under -1 dBTP, and the limiter's look-ahead doesn't move the sound in time
import contextlib, io, re, subprocess, tempfile
with tempfile.TemporaryDirectory() as t:
    x = np.zeros((film.SR * 6, 2), np.float32); x[::film.SR // 2] = 0.9             # sparse loud clicks: high crest
    x += 0.12 * np.sin(np.arange(len(x)) * 2 * np.pi * 220 / film.SR)[:, None]
    raw, wav = pathlib.Path(t) / "raw.f32", pathlib.Path(t) / "mix.wav"; x.tofile(raw)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        film.master(raw, wav)
    assert "rides" not in out.getvalue(), out.getvalue()
    m = subprocess.run(["ffmpeg", "-nostats", "-i", str(wav), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = m[m.rindex("Summary"):]
    i_, tp = float(re.search(r"I:\s+(-?[\d.]+) LUFS", m)[1]), float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", m)[1])
    assert abs(i_ + 14) <= 1 and tp <= -1, (i_, tp)
    y = film.load(wav, 1)
    a, b = x.mean(1)[film.SR: 2 * film.SR], y[film.SR: 2 * film.SR]
    lag = int(np.argmax(np.correlate(b, a, "full"))) - (len(a) - 1)
    assert lag == 0, lag                                                                  # no look-ahead delay

# T7: audiokit's own check runs, and a track too short to hold a drop says so
subprocess.run([sys.executable, str(pathlib.Path(film.__file__).parent / "audiokit.py")], check=True, capture_output=True)
import audiokit
try:
    audiokit.find_drop(np.zeros(film.SR * 8), np.arange(8.0)); raise AssertionError("an 8-bar track gave a drop")
except SystemExit as e:
    assert "bars" in str(e), e

# L5, E15: one poster time: a "poster" cue if the film sets one, else just after the payoff; music: null is fine
tl = {"beat": 0.5, "totalBeats": 16, "cues": {"payoff": 8}, "music": None}
assert film.poster_time(tl) == 8 * 0.5 + 0.3, film.poster_time(tl)
tl["cues"]["poster"] = 10
assert film.poster_time(tl) == 5.0, film.poster_time(tl)

# X12: every blur sample of frame f rounds back to f, so a counter quantised with Math.round(t * fps) holds one
# value across the frame (floor splits it: frame 60 -> [59, 59, 60, 60])
for n in (4, 8, 16, 32, 64):
    for f in (0, 1, 59, 60, 1234):
        ts = film.sample_times(f, n, 60)
        assert {round(t * 60) for t in ts} == {f}, (n, f, [t * 60 for t in ts])

# E3: contact tiles keep the frame's shape (a 1:1 film isn't squashed into 16:9 tiles)
assert [film.tile_size(*s) for s in ((1920, 1080), (1080, 1080), (1080, 1920))] == [(320, 180), (320, 320), (180, 320)]

# E16: the render browser finishes every compositor stage before each screenshot
import render
assert "--run-all-compositor-stages-before-draw" in render.FLAGS

# avsync alignment picks the lag where the shapes match best, not where the audio is loudest: a louder stretch beside
# the true position used to win a raw dot product (data-story's whoosh read 22 ms off at confidence 0.59; true 0 ms)
c = np.linspace(0, 1, 4000) + 0.05 * np.sin(np.arange(4000) / 9)       # a shape rising into its event
seg = np.r_[np.zeros(300), c, 40 + np.zeros(700)]                      # true lag 300, then something loud (raw picks 1000)
lag, conf = film.align(seg, c)
assert lag == 300 and conf > 0.99, (lag, conf)

# R19: music.bars must be bars the track has
tl = {"totalBeats": 8, "music": {"bars": [999, 999], "firstDownbeat": 0}, "cues": {}}
for bars in ([999, 999], [-1, -1], [1.5, 2]):
    tl["music"]["bars"] = bars
    try:
        film.music_bars(tl, 2.0, 100); raise AssertionError(f"bars {bars} accepted")
    except SystemExit as e:
        assert "track" in str(e), e

# R21: avsync reports every effect, a flat one as unmeasured, instead of dropping it
with tempfile.TemporaryDirectory() as t:
    d = pathlib.Path(t); (d / "audio").mkdir()
    silent = d / "audio" / "mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4", str(silent)], check=True)
    res = film.check_avsync(d, {"beat": 0.5, "sfx": [{"file": "x.wav", "beat": 4}]}, 60, silent)
    assert len(res["effects"]) == 1 and res["effects"][0]["ok"] is None, res

# R38: the limiter takes at most 12 dB off the peaks; a mix that needs more says so, and blames the peaks
with tempfile.TemporaryDirectory() as t:
    x = np.zeros((film.SR * 6, 2), np.float32); x[::film.SR // 2] = 0.95
    x += 0.004 * np.sin(np.arange(len(x)) * 2 * np.pi * 220 / film.SR)[:, None]
    raw = pathlib.Path(t) / "raw.f32"; x.tofile(raw)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        film.master(raw, pathlib.Path(t) / "mix.wav")
    held = float(re.search(r"held at (-?[\d.]+) dBFS", out.getvalue())[1])
    assert held >= 20 * np.log10(0.95) - 12.1 and "peaks" in out.getvalue(), out.getvalue()

# R41: cuts may name cues, like asserts and captions
assert film.planned_frames({"beat": 0.5, "fps": 60, "cues": {"tap": 4}, "cuts": ["tap", 6], "shots": []}) == {120, 180}

print("unit checks ok")
