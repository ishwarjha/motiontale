"""voice.py: voiceover for narrated films.

  voice.py cut <dir> [--tts]    one take per scene -> sentences cut at the pauses, each checked by transcription
                                -> vo/lines.json. Takes are human recordings: vo/take_01.wav, vo/take_02.wav ...
                                --tts makes missing takes with an AI voice: $VOICE_PROVIDER google (Gemini),
                                microsoft (Azure AI Speech) or elevenlabs; keys in .env. Label the post as AI.
  voice.py place <dir>          lay the lines on the beat grid and write lines, shots, cues and totalBeats into timeline.js

The film folder holds script.md: each scene is "## N. Title" with a "**Voice:**" block, one idea per sentence.
Optional: vo/pronounce.json {"Acme.ai": "Acme dot A I"} (said differently, captioned as written),
vo/voice.json {"provider": "google", "voice": "Charon", "style": "Read this warmly ..."} overrides .env for one film
("style" is Gemini-only).
"""
import argparse, base64, io, json, math, os, pathlib, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, wave
from difflib import SequenceMatcher
from itertools import pairwise
from xml.sax.saxutils import escape, quoteattr
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lint import tl_of, load_env  # noqa: E402
from audiokit import load  # noqa: E402

SR = 24000
GAP, LEAD, TAIL = 0.75, 2, 2        # beats: between sentences, picture before a scene's first line, after its last


def scenes(d):
    s = (d / "script.md").read_text()
    s = s.split("## Source table")[0]
    out = []
    for blk in re.split(r"(?m)^## ", s)[1:]:          # a heading on line 1 counts too
        vo, on = [], False
        for line in blk.split("\n"):
            if "**Voice:**" in line:
                on = True
                vo.append(line.split("**Voice:**")[1].strip()); continue
            if line.startswith("**") or line.startswith("---"):
                on = False
            elif on and line.strip():
                vo.append(line)
        text = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", " ".join(vo))).strip()
        if text:                                         # a heading with no Voice block is a note, not a scene
            out.append({"title": blk.splitlines()[0], "sentences": [x for x in re.split(r"(?<=[.?!])\s+", text) if x]})
    if not out:
        raise SystemExit("script.md has no '## N. Title' scenes with a **Voice:** block")
    return out


def norm_words(t):
    """Lowercased words with numbers spelled out, so '79%' matches 'seventy-nine percent'."""
    from num2words import num2words
    t = re.sub(r"([₹$£])\s?(\d[\d,]*(?:\.\d+)?)", lambda m: f"{m[2]} {dict(zip('₹$£', ('rupees', 'dollars', 'pounds')))[m[1]]}", t)   # said after
    t = t.replace("%", " percent").replace("₹", " rupees ").replace("$", " dollars ").replace("£", " pounds ")
    t = re.sub(r"\d[\d,]*(?:\.\d+)?", lambda m: " " + num2words(float(n) if "." in (n := m.group().replace(",", "")) else int(n)) + " ", t)
    return re.findall(r"[a-z]+", t.lower().replace("-", " ").replace(".ai", " dot a i"))


STYLE = "clear and warm, like a product explainer, with a short pause between sentences"


def need(k):
    return os.environ.get(k) or sys.exit(f"--tts with this provider needs {k} in .env (see .env.example)")


def post(url, body, headers, tries=3):
    """POST; retries 429/5xx and network errors up to `tries` times, waiting what the server asks (at most 60 s).
    Every try may be billed, so the budget is small and the last error is reported."""
    last = ""
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=300).read()
        except urllib.error.HTTPError as e:
            last = f"{e.code}: {e.read().decode(errors='replace')[:300]}"
            if e.code not in (429, 500, 502, 503, 504):
                raise SystemExit(f"TTS error {last}") from None
            wait = float((re.search(r'"retryDelay":\s*"([\d.]+)s"', last) or [0, 20 * (k + 1)])[1])
        except (urllib.error.URLError, TimeoutError) as e:
            last, wait = str(e), 20 * (k + 1)
        if k < tries - 1:
            time.sleep(min(wait, 60))
    raise SystemExit(f"TTS: no response after {tries} tries (last: {last})")


def tts(text, cfg):
    """Text -> 24 kHz mono float32. Provider: vo/voice.json "provider", else $VOICE_PROVIDER, else google.
    google = Gemini TTS, microsoft = Azure AI Speech, elevenlabs = ElevenLabs. All return 16-bit PCM at 24 kHz."""
    prov = cfg.get("provider") or os.environ.get("VOICE_PROVIDER", "google")
    pcm = lambda raw: np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    if prov == "google":                        # Interactions API: text in, one WAV (24 kHz mono s16) out
        body = json.dumps({"model": os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts"),
                           "input": [{"type": "user_input", "content": [{"type": "text", "text": text, "annotations": [
                               {"type": "speech_metadata", "style": cfg.get("style", STYLE)}]}]}],
                           "response_format": {"type": "audio"},
                           "generation_config": {"speech_config": [
                               {"voice": cfg.get("voice") or os.environ.get("GEMINI_TTS_VOICE", "Charon")}]}}).encode()
        r = json.loads(post("https://generativelanguage.googleapis.com/v1beta/interactions", body,
                            {"x-goog-api-key": need("GEMINI_API_KEY"), "Content-Type": "application/json"}))
        audio = [c for st in r.get("steps", []) if st.get("type") == "model_output" for c in st.get("content", [])
                 if c.get("type") == "audio"]
        if not audio:
            sys.exit(f"Gemini TTS: no audio in the reply (steps: {[st.get('type') for st in r.get('steps', [])]})")
        with wave.open(io.BytesIO(base64.b64decode(audio[-1]["data"]))) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SR, 1, 2):
                sys.exit(f"Gemini TTS: expected 24 kHz mono 16-bit WAV, got {w.getframerate()} Hz x{w.getnchannels()}")
            return pcm(w.readframes(w.getnframes()))
    if prov == "microsoft":
        voice = cfg.get("voice") or os.environ.get("AZURE_TTS_VOICE", "en-US-AndrewNeural")
        ssml = (f"<speak version='1.0' xml:lang={quoteattr(voice.rsplit('-', 1)[0])}><voice name={quoteattr(voice)}>"
                f"{escape(text)}</voice></speak>")
        region = need("AZURE_SPEECH_REGION")
        if not re.fullmatch(r"[a-z0-9]+", region):     # the key goes to this host: a region is letters and digits only
            sys.exit(f"AZURE_SPEECH_REGION {region!r} is not a region name like westeurope")
        return pcm(post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1", ssml.encode(),
                        {"Ocp-Apim-Subscription-Key": need("AZURE_SPEECH_KEY"), "Content-Type": "application/ssml+xml",
                         "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm", "User-Agent": "motiontale"}))
    if prov == "elevenlabs":
        voice = cfg.get("voice") or need("ELEVENLABS_VOICE_ID")
        body = json.dumps({"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")}).encode()
        return pcm(post(f"https://api.elevenlabs.io/v1/text-to-speech/{urllib.parse.quote(voice, safe='')}?output_format=pcm_24000", body,
                        {"xi-api-key": need("ELEVENLABS_API_KEY"), "Content-Type": "application/json"}))
    raise SystemExit(f"unknown voice provider '{prov}': use google, microsoft or elevenlabs")


_model = None


def heard(x):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("base.en", device="cpu", compute_type="int8",       # pinned: a new model upload can't move match scores
                              revision="3d3d5dee26484f91867d81cb899cfcf72b96be6c")
    x16 = np.interp(np.arange(0, len(x), SR / 16000), np.arange(len(x)), x).astype(np.float32)
    return [(w.word, w.start, w.end) for s in _model.transcribe(x16, beam_size=5, word_timestamps=True)[0] for w in s.words]


def trim(seg, keep=0.04):
    loud = np.flatnonzero(np.abs(seg) > 0.02)
    if len(loud):
        seg = seg[max(0, loud[0] - int(keep * SR)): loud[-1] + int(keep * SR)]
    seg, f = seg.copy(), int(0.005 * SR)
    seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
    return seg


def split(x, sentences, say):
    """Line the transcript up with the script; cut at the longest pause between sentences."""
    script = [(w, k) for k, s in enumerate(sentences) for w in norm_words(say(s))]
    hw = [(t, a, b) for w, a, b in heard(x) for t in norm_words(w)]
    sm = SequenceMatcher(None, [w for w, _ in script], [w for w, _, _ in hw], autojunk=False)
    m = {blk.a + i: blk.b + i for blk in sm.get_matching_blocks() for i in range(blk.size)}
    if any(not any(i in m for i, (_, kk) in enumerate(script) if kk == k) for k in range(len(sentences))):
        return [], sm.ratio()                          # a sentence the take never says: no cut, a failed match
    first = {k: min(i for i, (_, kk) in enumerate(script) if kk == k and i in m) for k in range(len(sentences))}
    last = {k: max(i for i, (_, kk) in enumerate(script) if kk == k and i in m) for k in range(len(sentences))}
    spoken = set(norm_words("0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 30 40 50 60 70 80 90 100 1000 1000000 1.5")) | {"and"}
    for k, s in enumerate(sentences):                  # each number said exactly, as a whole phrase, in its own sentence
        heardk = [w for w, _, _ in hw[max(m[first[k]] - 1, 0): m[last[k]] + 2]]
        for n in re.findall(r"[$₹£]?\d[\d,]*(?:\.\d+)?%?", say(s)):
            want = norm_words(n)
            if not any(heardk[i:i + len(want)] == want and (i == 0 or heardk[i - 1] not in spoken)
                       and (i + len(want) == len(heardk) or heardk[i + len(want)] not in spoken) for i in range(len(heardk))):
                return [], sm.ratio()
    quiet = np.sqrt(np.convolve(x ** 2, np.ones(480) / 480, "same")) < 0.015
    cuts = [0]
    for k in range(len(sentences) - 1):
        final = max(i for i, (_, kk) in enumerate(script) if kk == k)
        w = hw[m[last[k]]]
        a, b = (w[2] if last[k] == final else w[1]), hw[m[first[k + 1]]][1]
        lo, hi = int(max(0, a - .15) * SR), min(len(x), int((max(a, b) + .6) * SR))   # timestamps drift: look around
        runs, start = [], None
        for i in range(lo, hi):
            if quiet[i] and start is None: start = i
            elif not quiet[i] and start is not None: runs.append((start, i)); start = None
        if start is not None: runs.append((start, hi))
        runs = [r for r in runs if r[1] - r[0] > .08 * SR]
        best = max(runs, key=lambda r: r[1] - r[0]) if runs else None
        cuts.append((best[0] + best[1]) // 2 if best else int(b * SR) - int(.03 * SR))
    cuts.append(len(x))
    return [trim(x[a:b]) for a, b in pairwise(cuts)], sm.ratio()


def cmd_cut(a):
    d = pathlib.Path(a.dir).resolve()
    vo = d / "vo"; vo.mkdir(exist_ok=True)
    rd = lambda n: json.loads((vo / n).read_text()) if (vo / n).exists() else {}
    pron, cfg = rd("pronounce.json"), rd("voice.json")
    def say(t):                                  # pronounce.json: script spelling -> how it's said
        for k, v in pron.items():
            t = t.replace(k, v)
        return t
    out = []
    for i, sc in enumerate(scenes(d), 1):
        take, ai = vo / f"take_{i:02d}.wav", vo / f"take_{i:02d}.tts.wav"   # human and AI takes never share a file
        bar = 0.75 if len(" ".join(sc["sentences"]).split()) < 20 else 0.85   # short scenes: one misheard word costs more
        tries = [take] * take.exists() + [ai] * ai.exists() + [None] * (3 if a.tts else 0)   # None: a new AI take
        if not tries:
            raise SystemExit(f"missing {take.relative_to(d)}: record scene {i} ({sc['title']}), or pass --tts for an AI voice")
        for path in tries:
            x = load(path, SR) if path else tts(" ".join(say(s) for s in sc["sentences"]), cfg)
            parts, match = split(x, sc["sentences"], say)
            if match >= bar and parts:
                if not path:                         # keep a new AI take so a re-cut costs nothing
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(ai)],
                                   input=x.astype(np.float32).tobytes(), check=True)
                break
            print(f"  scene {i}: {path.name if path else 'new AI take'}: transcript match {match:.2f} < {bar}")
        else:
            raise SystemExit(f"scene {i}: no take matched the script (re-record it or fix the script text)")
        src = "take" if path == take else "tts"
        for j, (t, seg) in enumerate(zip(sc["sentences"], parts, strict=True), 1):   # one cut per sentence, or captions drift
            f = f"vo/s{i:02d}_{j:02d}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(d / f)],
                           input=seg.astype(np.float32).tobytes(), check=True)
            out.append({"scene": i, "title": sc["title"], "idx": j, "file": f, "text": t, "dur": round(len(seg) / SR, 3),
                        "match": round(match, 2), "source": src})
        print(f"scene {i:2d}: {len(parts)} lines, match {match:.2f}")
    (vo / "lines.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(len(out), "lines ->", vo / "lines.json")


def cmd_place(a):
    d = pathlib.Path(a.dir).resolve()
    tl = tl_of(d)
    lines, beat = json.loads((d / "vo" / "lines.json").read_text()), tl["beat"]
    t, shots, out, cues = 0.0, [], [], {k: v for k, v in tl.get("cues", {}).items() if not re.match(r"^(s\d\d\.start|L\d+\.\d+)$", k)}
    for sc in sorted({o["scene"] for o in lines}):
        b = t + LEAD
        for o in (o for o in lines if o["scene"] == sc):
            ln = o["dur"] / beat
            lid = f"L{sc}.{o['idx']}"
            out.append({"id": lid, "shot": f"s{sc:02d}", "beat": round(b, 4), "len": round(ln, 4), "text": o["text"], "file": o["file"]})
            cues[lid] = round(b, 4)
            b += ln + GAP
        end = t + math.ceil((b - GAP + TAIL - t) / 4) * 4          # every scene is whole bars: cuts land on downbeats
        heading = next((o.get("title", "") for o in lines if o["scene"] == sc), "")
        old = next((s_ for s_ in tl.get("shots", []) if s_["id"] == f"s{sc:02d}"),          # keep its title and the rest,
                   {"title": re.sub(r"^\d+\.\s*", "", heading)} if heading else {})     # or title it from the script's heading
        shots.append({**old, "id": f"s{sc:02d}", "start": t, "end": end}); cues[f"s{sc:02d}.start"] = t
        t = end
    tl.update(lines=out, shots=shots, cues=cues, totalBeats=t)
    (d / "timeline.js").write_text("const TL = " + json.dumps(tl, indent=1, ensure_ascii=False) + ";\n")
    print(f"{len(out)} lines in {len(shots)} scenes, {t:g} beats ({t * beat:.1f}s) -> timeline.js")


def self_test():
    """place(): lines on the grid with lead-in, gaps and tail; every scene whole bars; other cues kept."""
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t); (d / "vo").mkdir()
        (d / "timeline.js").write_text('const TL = {"beat": 0.5, "cues": {"payoff": 3}, "sfx": []};')
        (d / "vo" / "lines.json").write_text(json.dumps([
            {"scene": 1, "idx": 1, "file": "a", "text": "A.", "dur": 1.0}, {"scene": 1, "idx": 2, "file": "b", "text": "B.", "dur": 1.5},
            {"scene": 2, "idx": 1, "file": "c", "text": "C.", "dur": 0.4}]))
        cmd_place(argparse.Namespace(dir=t))
        tl = tl_of(d)
        b = [ln["beat"] for ln in tl["lines"]]
        assert b[0] == 2 and b[1] == 2 + 2 + 0.75, b                  # lead-in 2, then 1.0 s = 2 beats + gap
        assert all(s["start"] % 4 == 0 and s["end"] % 4 == 0 for s in tl["shots"]), tl["shots"]
        assert tl["lines"][2]["beat"] == tl["shots"][1]["start"] + 2 and tl["cues"]["payoff"] == 3, tl
    # cut(): a human take is never overwritten by TTS (I1); a cached AI take stays labelled tts when re-cut (X1)
    g = globals(); real = g["tts"], g["split"]
    g["tts"] = lambda text, cfg: np.full(SR, 0.2, np.float32)
    g["split"] = lambda x, sentences, say: ([x[:100]], 0.99 if x.max() > 0.15 else 0.1)    # the human take scores low
    try:
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t); (d / "vo").mkdir()
            (d / "script.md").write_text("# Film\n\n## 1. Intro\n**Voice:** Hello there.\n")
            human = d / "vo" / "take_01.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5", str(human)], check=True)
            before = human.read_bytes()
            cmd_cut(argparse.Namespace(dir=t, tts=True))
            assert human.read_bytes() == before, "the human take was overwritten"
            src = lambda: {ln["source"] for ln in json.loads((d / "vo" / "lines.json").read_text())}
            assert src() == {"tts"}, src()
            human.unlink()
            cmd_cut(argparse.Namespace(dir=t, tts=False))                     # re-cut from the cached AI take
            assert src() == {"tts"}, "re-cut relabelled an AI take as a human take"
    finally:
        g["tts"], g["split"] = real
    # post(): at most 3 tries per request, server-requested waits capped at 60 s, network errors retried then reported (S8)
    import email.message, io as _io
    naps, attempts = [], []
    real_open, real_sleep = urllib.request.urlopen, time.sleep
    def fake_open(req, timeout):
        attempts.append(1)
        if len(attempts) % 2:
            raise urllib.error.HTTPError(req.full_url, 429, "busy", email.message.Message(), _io.BytesIO(b'{"retryDelay": "600s"}'))
        raise urllib.error.URLError("connection reset")
    urllib.request.urlopen, time.sleep = fake_open, naps.append
    try:
        try:
            post("https://example.test", b"{}", {}); raise AssertionError("post returned without a response")
        except SystemExit as e:
            assert "connection reset" in str(e) or "429" in str(e), e
        assert len(attempts) == 3 and max(naps) <= 60, (len(attempts), naps)
        naps.clear()                                  # a fractional server delay is honoured, not replaced (S22)
        urllib.request.urlopen = lambda req, timeout: (_ for _ in ()).throw(urllib.error.HTTPError(
            req.full_url, 503, "busy", email.message.Message(), _io.BytesIO(b'{"retryDelay": "7.5s"}')))
        try:
            post("https://example.test", b"{}", {})
        except SystemExit:
            pass
        assert naps == [7.5, 7.5], naps
    finally:
        urllib.request.urlopen, time.sleep = real_open, real_sleep
    # Gemini: the documented Interactions request and WAV response; a reply with no audio is a clear error (S6, X13)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\x00\x10" * 240)
    wav = base64.b64encode(buf.getvalue()).decode()
    ok = {"steps": [{"type": "model_output", "content": [{"type": "audio", "mime_type": "audio/wav", "data": wav}]}]}
    calls, real_post = [], g["post"]
    replies = [ok, {"steps": [{"type": "model_output", "content": [{"type": "text", "text": "no"}]}]}]
    g["post"] = lambda url, body, headers, tries=6: calls.append((url, json.loads(body))) or json.dumps(replies.pop(0)).encode()
    os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY") or "k"
    try:
        x = tts("Hello.", {"provider": "google", "voice": "Kore"})
        url, body = calls[0]
        assert url.endswith("/v1beta/interactions") and body["input"][0]["content"][0]["text"] == "Hello.", calls
        assert body["generation_config"]["speech_config"] == [{"voice": "Kore"}] and body["response_format"] == {"type": "audio"}
        assert len(x) == 240 and abs(x[0] - 0x1000 / 32768) < 1e-6, (len(x), x[:2])   # WAV header not decoded as samples
        try:
            tts("Hello.", {"provider": "google"}); raise AssertionError("a reply without audio was accepted")
        except SystemExit as e:
            assert "no audio" in str(e), e
    finally:
        g["post"] = real_post
    # the Azure key only ever goes to <region>.tts.speech.microsoft.com (S3)
    sent, real_post = [], g["post"]
    g["post"] = lambda url, body, headers, tries=6: sent.append(url) or b"\0\0"
    env = {k: os.environ.get(k) for k in ("AZURE_SPEECH_REGION", "AZURE_SPEECH_KEY")}
    try:
        os.environ.update(AZURE_SPEECH_KEY="k", AZURE_SPEECH_REGION="attacker.example/#")
        try:
            tts("hi", {"provider": "microsoft"}); raise AssertionError(f"request sent to {sent}")
        except SystemExit:
            assert sent == [], sent
        os.environ["AZURE_SPEECH_REGION"] = "westeurope"
        tts("hi", {"provider": "microsoft"})
        assert sent == ["https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1"], sent
        # the voice name can't inject SSML, and the locale is everything before the voice (S10)
        import xml.etree.ElementTree as ET
        bodies = []
        g["post"] = lambda url, body, headers, tries=3: bodies.append(body) or b"\0\0"
        tts("hi & <bye>", {"provider": "microsoft", "voice": "en-US-A' /><audio src='https://x.test'/><voice name='b"})
        tts("hi", {"provider": "microsoft", "voice": "fil-PH-AngeloNeural"})
        root = ET.fromstring(bodies[0])
        assert not list(root.iter("audio")), bodies[0]
        assert root.find("voice").text == "hi & <bye>", bodies[0]
        assert ET.fromstring(bodies[1]).get("{http://www.w3.org/XML/1998/namespace}lang") == "fil-PH", bodies[1]
    finally:
        g["post"] = real_post
        for k, v in env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    # ElevenLabs: the voice id is one path segment, whatever it contains (S21)
    urls, real_post = [], g["post"]
    g["post"] = lambda url, body, headers, tries=3: urls.append(url) or b"\x00\x00" * 10
    os.environ.update(VOICE_PROVIDER="elevenlabs", ELEVENLABS_API_KEY=os.environ.get("ELEVENLABS_API_KEY") or "k")
    try:
        tts("Hi.", {"voice": "a/b?c"})
    finally:
        g["post"] = real_post; os.environ.pop("VOICE_PROVIDER")
    assert urls[0].startswith("https://api.elevenlabs.io/v1/text-to-speech/a%2Fb%3Fc?"), urls
    # scenes(): a heading on line 1 is a scene; a heading with no Voice block is not one; decimals are spoken (I28)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "script.md").write_text("## 1. Hook\n**Voice:** Start here.\n\n## Notes\nnone\n\n## 2. End\n**Voice:** Done.\n")
        assert [sc["title"] for sc in scenes(d)] == ["1. Hook", "2. End"], scenes(d)
    assert norm_words("1.5x") == ["one", "point", "five", "x"], norm_words("1.5x")
    # place(): what a shot already carries (a chapter title) survives a re-place (I11)
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t); (d / "vo").mkdir()
        (d / "timeline.js").write_text('const TL = {"beat": 0.5, "cues": {}, "shots": [{"id": "s01", "start": 0, "end": 8, "title": "Intro"}]};')
        (d / "vo" / "lines.json").write_text(json.dumps([{"scene": 1, "idx": 1, "file": "a", "text": "A.", "dur": 1.0}]))
        cmd_place(argparse.Namespace(dir=t))
        assert tl_of(d)["shots"][0].get("title") == "Intro", tl_of(d)["shots"]
        (d / "timeline.js").write_text('const TL = {"beat": 0.5, "cues": {}};')          # a first placement titles shots from
        (d / "vo" / "lines.json").write_text(json.dumps([{"scene": 1, "title": "2. How it works", "idx": 1, "file": "a", "text": "A.", "dur": 1.0}]))
        cmd_place(argparse.Namespace(dir=t))                                             # the script's headings (R17)
        assert tl_of(d)["shots"][0].get("title") == "How it works", tl_of(d)["shots"]
    # split(): a sentence the take never says is a failed match, not an exception; a code bug is not a "bad take" (I9)
    real_heard = g["heard"]
    g["heard"] = lambda x: [(" start", 0.1, 0.4), (" here", 0.4, 0.7)]
    try:
        parts, match = split(np.zeros(SR * 2, np.float32), ["Start here.", "Done now."], lambda s: s)
        assert parts == [] and match < 1, (parts, match)
    finally:
        g["heard"] = real_heard
    # a number is said exactly or the take fails, however well the other words match (X8)
    g["heard"] = lambda x: [(w, i * .3, i * .3 + .25) for i, w in enumerate(" Pay nine hundred dollars now please thanks".split())]
    try:
        parts, match = split(np.zeros(SR * 3, np.float32), ["Pay 500 dollars now please thanks."], lambda s: s)
        assert parts == [], (parts, match)
        g["heard"] = lambda x: [(w, i * .3, i * .3 + .25) for i, w in enumerate(" Pay five hundred dollars now please thanks".split())]
        parts, match = split(np.zeros(SR * 3, np.float32), ["Pay 500 dollars now please thanks."], lambda s: s)
        assert len(parts) == 1, (parts, match)
        g["heard"] = lambda x: [(w, i * .3, i * .3 + .25) for i, w in enumerate(" It costs five hundred".split())]
        assert len(split(np.zeros(SR * 3, np.float32), ["It costs 500."], lambda s: s)[0]) == 1   # a full stop isn't a decimal
        # R16: a number is its whole spoken phrase ("5" isn't inside "five hundred"), in its own sentence; "$500" is said
        # "five hundred dollars"
        say_ = lambda words: (lambda x: [(w, i * .3, i * .3 + .25) for i, w in enumerate(words.split())])
        g["heard"] = say_("pay five hundred dollars now please thanks")
        assert split(np.zeros(SR * 3, np.float32), ["Pay 5 dollars now please thanks."], lambda s: s)[0] == []
        g["heard"] = say_("pay five hundred dollars now please thanks")
        assert len(split(np.zeros(SR * 3, np.float32), ["Pay $500 now please thanks."], lambda s: s)[0]) == 1
        g["heard"] = say_("we saved nine hundred hours in spring then five hundred hours in autumn this year")
        assert split(np.zeros(SR * 6, np.float32), ["We saved 500 hours in spring.", "Then 900 hours in autumn this year."], lambda s: s)[0] == []
    finally:
        g["heard"] = real_heard
    g["split"] = lambda x, sentences, say: 1 / 0
    try:
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t); (d / "vo").mkdir()
            (d / "script.md").write_text("# Film\n\n## 1. Intro\n**Voice:** Hello there.\n")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5",
                            str(d / "vo" / "take_01.wav")], check=True)
            try:
                cmd_cut(argparse.Namespace(dir=t, tts=False)); raise AssertionError("a code bug was read as a bad take")
            except ZeroDivisionError:
                pass
    finally:
        g["split"] = real[1]
    print("voice self-check ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test(); sys.exit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("cut"); p.add_argument("dir"); p.add_argument("--tts", action="store_true"); p.set_defaults(fn=cmd_cut)
    p = sub.add_parser("place"); p.add_argument("dir"); p.set_defaults(fn=cmd_place)
    a = ap.parse_args()
    load_env(a.dir)                             # the film's workspace .env, same as film.py
    a.fn(a)
