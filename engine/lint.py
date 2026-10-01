"""lint.py: the mechanical half of motion-review. Reads one film folder's source (index.html, timeline.js,
CLAUDE.md, assets) and prints one line per rule break, blocking first:

  <file>:L<n>: <tag> <what>. <fix>.

  lint.py <film dir>               exit 1 if anything blocking
  lint.py --self-test

Tags (B = blocking, P = polish, V = verify by eye/source):
  clock B  not a pure function of time (CSS animation/transition, timers, rAF, clocks, Math.random)
  fade  B  opacity driven by a curve, or a blur-in: things change shape, they don't fade
  look  B  a banned default (gradient, glow, 3D, particles)
  cue   B  cue() names a cue timeline.js doesn't have (the page throws)
  asset B  a referenced image, voice line or kit sound that doesn't exist
  voice B  voice lines exist but CLAUDE.md doesn't say where the voice came from, or hides TTS
  blur  P  will-change on something the camera may scale (soft text)
  crop  P  a hard-coded 1920/1080 layout: won't reframe to 1:1 or 9:16
  beat  P  a literal beat instead of a timeline cue (moving a moment becomes a hunt)
  sync  P  a click effect without "peakFirst": true (fires on the release)
  hide  P  visibility: visible on a child (shows through a hidden parent)
  redraw V product film with no real crop on screen: is the UI drawn by hand?
  invent B a number, price or date on screen with no facts.md row, a fact row with no source, or an example
           shown without its "Example" label
"""
import hashlib, json, os, pathlib, re, subprocess, sys

TAGS = {"clock": "B", "fade": "B", "look": "B", "cue": "B", "asset": "B", "voice": "B", "invent": "B",
        "blur": "P", "crop": "P", "beat": "P", "sync": "P", "hide": "P", "redraw": "V"}
LINE_RULES = [  # (tag, regex, what, fix)
    ("clock", r"@keyframes|\banimation\s*:|\btransition\s*:", "CSS animation or transition", "drive it from draw(b) with sp()/track()"),
    ("clock", r"\bset(Timeout|Interval)\b|requestAnimationFrame", "a timer", "compute the value from b in draw()"),
    ("clock", r"\bDate\.now\b|\bperformance\.now\b|\bnew Date\(", "a wall clock", "use b (beats) only"),
    ("clock", r"\bMath\.random\b", "Math.random", "mulberry32(seed) from motion.js"),
    ("fade", r"filter\s*:\s*blur|\bblur\(", "a blur-in", "reveal with a mask line (rise) or a shape change"),
    ("look", r"(linear|radial|conic)-gradient", "a gradient", "flat colour from the style card"),
    ("look", r"(box-?shadow|text-?shadow|drop-shadow)\s*[:=(]\s*['\"]?(?:[a-z#][^;'\"]*?\s)?0(?:px)?\s+0(?:px)?\s+[1-9]", "a glow (a shadow with no offset)",
     "remove it; depth comes from the card shadow only (drop-shadow with its offset on a transparent crop)"),
    ("look", r"perspective\s*\(|rotate[XY]\s*\(|translate3d|preserve-3d", "3D", "stay flat"),
    ("look", r"particle", "particles", "remove them"),
    ("blur", r"will-change", "will-change", "remove it: the camera scales text and it goes soft"),
    ("hide", r"visibility\s*[:=]\s*['\"]?visible", "visibility: visible", "use inherit: a visible child shows through a hidden parent"),
    ("crop", r"\b(1920|1080)\s*(px)?\b(?![^\n]*FMT)", "a hard-coded frame size", "lay out from FMT.W/FMT.H and pick()"),
]


def calls(code, fn):
    """Arguments (raw text) of every fn(...) call on a line; commas inside quotes or brackets don't split."""
    out = []
    for m in re.finditer(rf"\b{fn}\(", code):
        args, cur, depth, quote, i = [], "", 0, None, m.end()
        while i < len(code):
            ch = code[i]
            if quote:
                cur += ch
                if ch == quote and code[i - 1] != "\\": quote = None
            elif ch in "'\"`": quote = ch; cur += ch
            elif ch in "([{": depth += 1; cur += ch
            elif ch in ")]}" and depth: depth -= 1; cur += ch
            elif ch == ")": break
            elif ch == "," and not depth: args.append(cur.strip()); cur = ""
            else: cur += ch
            i += 1
        out.append(args + [cur.strip()])
    return out


def facts(d):
    """facts.md rows: | claim as shown | source | date | kind (fact|example) |. Header (the row above a divider) and divider skipped."""
    p = d / "facts.md"
    rows = []
    if p.exists():
        lines = p.read_text().splitlines()
        divider = lambda l: l.strip().startswith("|") and set(l.strip()) <= set("|-: ")
        for n, line in enumerate(lines, 1):
            cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
            if len(cells) >= 4 and not divider(line) and not (n < len(lines) and divider(lines[n])):   # header: above the divider
                rows.append({"line": n, "claim": cells[0], "source": cells[1], "date": cells[2], "kind": cells[3].lower()})
    return rows


NUM = re.compile(r"[₹$£€]\s?\d[\d,.]*\d|[₹$£€]\s?\d|(?<![\w.#])-?\d[\d,.]*\s?%|(?<![\w.#])-?\d(?:[\d,.]*\d)?x\b"   # money, %, 10x
                 r"|(?<![\w.#])\d[\d,.]*\d(?![\w.])|(?<![\w.#])\d(?![\w.%])")   # a sign only where it isn't a range (2019-2020)


def unsourced(text, ledger):
    """Numbers in text with no facts.md row as (number, None), or shown from an example row as (number, row).
    A row covers a number only when the same whole number is in its claim."""
    out = []
    for x in (x.strip() for x in NUM.findall(text)):
        row = next((r for r in ledger if x in (y.strip() for y in NUM.findall(r["claim"]))), None)
        if not row or row["kind"] == "example":
            out.append((x, row))
    return out


AUDIO = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg")


class Refused(Exception):
    """An input the engine won't use. Commands report it and exit 1; nothing else is caught."""


def inside(base, rel):
    """A timeline file reference, resolved. Raises unless it stays under base and is an audio file (no playlists)."""
    base = pathlib.Path(base).resolve()
    p = (base / rel).resolve()
    if not p.is_relative_to(base) or p.suffix.lower() not in AUDIO:
        raise Refused(f"{rel}: must be an audio file inside {base}")
    return p


def tl_of(d):
    """timeline.js is `const TL = {...};`: the JSON between the first = and the last ;."""
    s = (pathlib.Path(d) / "timeline.js").read_text()
    return json.loads(s[s.index("=") + 1: s.rindex(";")])


def kit_dir(d):
    """The sound kit: $MOTION_KIT, else the nearest kit/AUDIO.md above the film, else above the plugin. None if absent."""
    if os.environ.get("MOTION_KIT"):
        return pathlib.Path(os.environ["MOTION_KIT"]) / "audio"
    here = pathlib.Path(__file__).resolve().parent
    for base in (pathlib.Path(d).resolve(), here):
        for p in (base, *base.parents):
            if (p / "kit" / "AUDIO.md").exists():
                return p / "kit" / "audio"
    return None


# Claude Code and Codex logins are first-class; an agent API key is only the fallback. An exported
# ANTHROPIC_API_KEY also makes Claude Code bill the API instead of the login, so it stays unloaded when logged in.
AGENT_KEYS = {"ANTHROPIC_API_KEY": "claude", "OPENAI_API_KEY": "codex"}


def local_login(cli):
    """How that CLI is signed in, as it reports it ("claude.ai", "ChatGPT", ...), or "" when it isn't."""
    cmd = {"claude": ["claude", "auth", "status", "--json"], "codex": ["codex", "login", "status"]}[cli]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if cli == "claude":
        try:
            st = json.loads(r.stdout)
        except ValueError:
            return ""
        return st.get("authMethod") or "unknown method" if st.get("loggedIn") else ""
    out = (r.stdout + r.stderr).strip()
    return out.split("using", 1)[-1].strip() if r.returncode == 0 and out.lower().startswith("logged in") else ""


def load_env(start="."):
    """Load the workspace's .env (next to the kit this film uses) into os.environ: only keys .env.example documents,
    never a parent folder's .env. Values already in the shell win. Agent keys (AGENT_KEYS) are never loaded: nothing in
    the engine calls an agent, and a child process can't configure the session that launched it. `doctor` reports them.
    Returns {key: "loaded" | "shell"}."""
    kit = kit_dir(pathlib.Path(start))
    path = kit.parent.parent / ".env" if kit else None
    out = {}
    if not path or not path.is_file():
        return out
    known = set(re.findall(r"^([A-Z_]+)=", (pathlib.Path(__file__).resolve().parent.parent / ".env.example").read_text(), re.M))
    for line in path.read_text().splitlines():
        k, sep, v = line.strip().partition("=")
        k, v = k.strip().removeprefix("export ").strip(), v.strip()
        if len(v) > 1 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]                          # a matched pair of quotes: the value is everything inside
        else:
            v = re.split(r"\s+#", v, maxsplit=1)[0]   # unquoted: " # comment" is not part of the value
        if line.lstrip().startswith("#") or not sep or not k or not v or k not in known:
            continue
        if k in AGENT_KEYS:
            continue
        if k in os.environ:
            out[k] = "shell"
        else:
            os.environ[k] = v
            out[k] = "loaded"
    out["_file"] = str(path)
    return out


def lint(d):
    d = pathlib.Path(d).resolve()
    out = []
    add = lambda f, n, tag, what, fix: out.append({"file": f, "line": n, "tag": tag, "sev": TAGS[tag], "what": what, "fix": fix})
    html = (d / "index.html").read_text()
    tl = tl_of(d)
    cues = set(tl.get("cues", {}))
    tempos = [tl.get("bpm"), 60 / tl["beat"] if tl.get("beat") else None, (tl.get("music") or {}).get("bpm")]
    if len({round(x, 2) for x in tempos if x}) > 1:        # bars are cut at music.bpm, everything else at beat
        add("timeline.js", 0, "cue", f"tempo differs: bpm {tempos[0]}, 60/beat {tempos[1] and round(tempos[1], 3)}, music.bpm {tempos[2]}",
            "one tempo: set all three from the track's measured bpm")
    ledger = facts(d)
    for r in ledger:
        if r["kind"] not in ("fact", "example"):
            add("facts.md", r["line"], "invent", f"kind '{r['kind']}' for {r['claim']}", "use fact or example")
        elif r["kind"] == "fact" and (not r["source"] or not r["date"]):
            add("facts.md", r["line"], "invent", f"fact '{r['claim']}' has no source or date", "add the URL or file and its date")
    sources = [("index.html", html)]                  # the page and its own scripts and stylesheets: the same rules
    for src in re.findall(r"""<(?:script[^>]*\bsrc|link[^>]*\bhref)\s*=\s*["']([^"':?#]+\.(?:js|css))(?:[?#][^"']*)?["']""", html):
        f = d / src
        if src == "timeline.js" or not f.resolve().is_relative_to(d):
            continue
        if not f.is_file():
            add("index.html", 0, "asset", f"missing file {src}", "restore it or remove the tag")
        else:
            sources.append((src, f.read_text()))
    shown = []                                            # (file, line, shots/ path) wherever the page names a shot
    for name, text in sources:
        lines = text.splitlines()
        for n, line in enumerate(lines, 1):
            code = re.sub(r"/\*.*?\*/", "", line).split("//")[0]
            shown += [(name, n, f) for f in re.findall(r"shots/[^'\"`)\s>$]+\.(?:png|jpe?g|webp)", line)]
            for tag, rx, what, fix in LINE_RULES:
                if re.search(rx, code, re.I):
                    add(name, n, tag, what, fix)
            m = re.search(r"\.style\.opacity\s*=\s*([^;]+)", code)
            if m and not re.fullmatch(r"\s*['\"]?[01]['\"]?\s*|.*\?\s*['\"]?[01]['\"]?\s*:\s*['\"]?[01]['\"]?\s*", m[1]):
                add(name, n, "fade", "opacity follows a curve", "switch visibility 0/1 and move it (rise, pop, flood) instead")
            for c in re.findall(r"cue\(\s*['\"]([^'\"]+)['\"]\s*\)", code):
                if c not in cues:
                    add(name, n, "cue", f"cue '{c}' is not in timeline.js", "add it to cues or fix the name")
            for b in re.findall(r"\b(?:sp|track|rise)\(\s*b\s*,\s*(\d+\.?\d*)", code) + re.findall(r"\[\s*(\d+\.?\d*)\s*,\s*\{\s*x\s*:", code):
                if float(b) > 0:
                    add(name, n, "beat", f"literal beat {b}", "name it in timeline.js cues and use cue()")
            for src in re.findall(r"""(?:src\s*=\s*|url\()\s*['"]?([^'")\s>]+\.(?:png|jpe?g|webp|svg|gif|ttf|otf|woff2?))""", line):
                if "${" not in src and not src.startswith(("http", "data:")) and not (d / src).exists():
                    add(name, n, "asset", f"missing file {src}", "screenshot it into shots/ or fix the path")
            texts = [a[1] for a in calls(code, "words") if len(a) > 1] + [a[3] for a in calls(code, "h") if len(a) > 3] \
                + re.findall(r"\.(?:innerHTML|textContent)\s*=\s*['\"`]([^'\"`]*)", code)
            texts = [t[1:-1] for t in texts if t[:1] in "'\"`" and t[-1:] == t[:1]]
            for txt in texts:                              # visible copy only: tags and ${} code stripped
                txt = re.sub(r"<[^>]*>|\$\{[^}]*\}", " ", txt)
                # ponytail: "Example" label searched within 3 lines of the text, not the rendered card; `check facts` reads the render
                near = " ".join(lines[max(0, n - 4): n + 3]).lower()
                for x, row in unsourced(txt, ledger):
                    if not row:
                        add(name, n, "invent", f"'{x}' on screen has no facts.md row", "add | claim | source | date | fact | or cut it")
                    elif row["kind"] == "example" and "example" not in (txt.lower() + " " + near):
                        add(name, n, "invent", f"'{x}' is example data shown without an Example label", "label the card Example")
    shots_used = any("shots/" in text for _, text in sources)
    prov = json.loads((d / "provenance.json").read_text()) if (d / "provenance.json").exists() else None
    if shots_used and prov is None:                      # every shot on screen is traceable: no record, no render
        first = shown[0][:2] if shown else ("index.html", 0)
        add(*first, "asset", "shots/ images on screen but no provenance.json", "capture them with capture.py")
    where = {f: (name, n) for name, n, f in reversed(shown)}
    files = {f for *_, f in shown} | ({f"shots/{x.name}" for x in (d / "shots").glob("*") if x.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")}
                                      if (d / "shots").is_dir() else set())
    for f in sorted(files) if prov is not None and shots_used else []:
        name, n = where.get(f, ("index.html", 0))       # 0: loaded by a built path (`shots/${x}.png`) or unused
        if f not in prov:
            add(name, n, "asset", f"{f} has no provenance entry", "capture it with capture.py (or add its source)")
        elif not (prov[f].get("url") or prov[f].get("source") or prov[f].get("derivedFrom") in prov) or not prov[f].get("sha256"):
            add(name, n, "asset", f"{f}: its provenance record has no source or no sha256", "re-capture or import it (capture.py import)")
        elif prov[f].get("sha256") and (d / f).is_file() and hashlib.sha256((d / f).read_bytes()).hexdigest() != prov[f]["sha256"]:
            add(name, n, "asset", f"{f} changed since it was captured (sha256 differs)", "re-capture it, or restore the captured file")
    if (d / "shots").is_dir() and not shots_used:
        add("index.html", 0, "redraw", "shots/ exists but the page shows no real crop", "use the crops; never draw product UI")
    kit = kit_dir(d)

    def ref(base, f, what, fix):                 # a timeline file: inside its folder, an audio file, present
        try:
            if not inside(base, f).exists():
                add("timeline.js", 0, "asset", f"{what} {f} is missing", fix)
        except Refused as err:
            add("timeline.js", 0, "asset", str(err), fix)

    for e in tl.get("sfx", []):
        if kit:
            ref(kit, e["file"], "sfx", "pick a measured kit sound or add it with kit.py")
        if "click" in e["file"] and not e.get("peakFirst"):
            add("timeline.js", 0, "sync", f"click at beat {e['beat']} syncs to its loudest hit", 'add "peakFirst": true')
        if e["beat"] > tl["totalBeats"]:
            add("timeline.js", 0, "cue", f"sfx {e['file']} at beat {e['beat']} is after the end", "move it inside totalBeats")
    m = tl.get("music")
    if m and kit:
        ref(kit, m["file"], "music", "use a measured kit track")
    lines = tl.get("lines", [])
    for ln in lines:
        ref(d, ln["file"], "voice line", "run voice.py cut")
    if lines:
        rules = (d / "CLAUDE.md").read_text() if (d / "CLAUDE.md").exists() else ""
        vl = next((l for l in rules.splitlines() if l.strip().startswith("- Voice:")), "")
        tts = any(o.get("source") == "tts" for o in json.loads((d / "vo" / "lines.json").read_text())) if (d / "vo" / "lines.json").exists() else False
        if not vl or "VOICE_SOURCE" in vl:
            add("CLAUDE.md", 0, "voice", "voice lines exist but the voice source is not written down", "set the Voice line in CLAUDE.md")
        elif tts and "TTS" not in vl:
            add("CLAUDE.md", 0, "voice", "the takes are TTS but CLAUDE.md doesn't say so", "say TTS and label the post as AI")
    order = {"B": 0, "P": 1, "V": 2}
    return sorted(out, key=lambda f: (order[f["sev"]], f["file"], f["line"]))


def fmt(f):
    return f"{f['file']}:L{f['line']}: {f['tag']} {f['what']}. {f['fix']}."


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        (d / "timeline.js").write_text('const TL = {"totalBeats": 8, "cues": {"a": 1}, "sfx": [{"file": "sfx-click-1.wav", "beat": 2}]};')
        (d / "index.html").write_text("\n".join([
            "<style>.x{transition: all 1s; background: linear-gradient(#fff,#000)} .m>span{will-change:transform}</style>",
            "e.style.opacity = sp(b, cue('a'));",
            "f.style.opacity = k > 0.5 ? 1 : 0;",
            "const r = Math.random(); g.style.opacity = 1;",
            "place(x, 0, 0, 1920, 1080); sp(b, 4); cue('nope');",
            "h('div', 'n', p, 'Save ₹249 today');",
            "<img src='shots/missing.png'>",
        ]))
        (d / "facts.md").write_text("| claim as shown | source | date | kind |\n|---|---|---|---|\n"
                                    "| 42% | https://x.test | 2026-01 | fact |\n| ₹999 | seeded demo | | example |\n| 7 days | | | fact |\n")
        (d / "index.html").write_text((d / "index.html").read_text() + "\n" + "\n".join([
            "", "", "", "", "h('div', 'n', p, 'Up 42% this year');", "", "", "", "", "",
            "h('div', 'n', p, 'Plan ₹999');"]))
        tags = [(f["tag"], f["line"]) for f in lint(d)]
        assert ("invent", 12) not in tags, "a sourced fact must pass"
        assert ("invent", 18) in tags, "example data without an Example label must block"
        assert any(f["file"] == "facts.md" and f["line"] == 5 for f in lint(d)), "a fact row with no source must block"
        # a header row is the one above the divider, whatever it says (I26)
        (d / "facts2").mkdir()
        (d / "facts2" / "facts.md").write_text("| Claim | Source | Date | Kind |\n|---|---|---|---|\n| 42% | https://x.test | 2026-01 | fact |\n")
        assert [r["claim"] for r in facts(d / "facts2")] == ["42%"], facts(d / "facts2")
        # a drop shadow with an offset is the card shadow on a transparent crop; zero offset is a glow (I27)
        glow = lambda css: any(tag == "look" and re.search(rx, css, re.I) for tag, rx, *_ in LINE_RULES)
        assert not glow("filter: drop-shadow(0 12px 32px rgba(21,32,27,.08));") and glow("filter: drop-shadow(0 0 12px #0B8F63);")
        # the film's tempo is one number: bpm, beat and music.bpm agree (I18)
        tl0 = (d / "timeline.js").read_text()
        (d / "timeline.js").write_text('const TL = {"bpm": 121, "beat": 0.4958677685950413, "totalBeats": 8, "cues": {}, '
                                       '"music": {"file": "m.mp3", "bpm": 120}};')
        assert any(f["tag"] == "cue" and "tempo" in f["what"] for f in lint(d)), "a second tempo must block"
        (d / "timeline.js").write_text(tl0)

        # multipliers and signs are numbers too (R11)
        assert [x for x, _ in unsourced("10x faster, 1.5x more, -5% churn", [])] == ["10x", "1.5x", "-5%"], unsourced("10x faster, 1.5x more, -5% churn", [])
        glow = lambda css: any(tag == "look" and re.search(rx, css, re.I) for tag, rx, *_ in LINE_RULES)
        # glows in every spelling; a spread-only ring and an offset shadow aren't glows (R32)
        glows = ("box-shadow: 0px 0px 24px #0B8F63", "e.style.boxShadow = '0 0 24px red'", "filter: drop-shadow(red 0 0 20px)", "text-shadow: 0 0 8px #fff")
        fine = ("box-shadow: 0 0 0 2px #E6E9E7", "box-shadow: 0 12px 32px rgba(21,32,27,.08)", "filter: drop-shadow(0 12px 32px rgba(0,0,0,.1))")
        assert all(glow(c) for c in glows) and not any(glow(c) for c in fine), ([c for c in glows if not glow(c)], [c for c in fine if glow(c)])
        # a number matches a row only as a whole number: "9" is not in "999 customers" (X4)
        assert unsourced("9 customers", facts(d) + [{"claim": "999 customers", "kind": "fact"}]) == [("9", None)]
        want = {("clock", 1), ("look", 1), ("blur", 1), ("fade", 2), ("clock", 4), ("crop", 5), ("beat", 5), ("cue", 5),
                ("invent", 6), ("asset", 7), ("sync", 0)}
        assert want <= set(tags), want - set(tags)
        assert ("fade", 3) not in tags and ("fade", 4) not in tags, tags     # 0/1 switches are fine
        # a voice line outside the film is a finding, not a crash (S5)
        tl = json.loads((d / "timeline.js").read_text().split("=", 1)[1].rsplit(";", 1)[0])
        tl["lines"] = [{"file": "../../x.wav", "beat": 0, "len": 1, "text": "a"}]
        (d / "timeline.js").write_text("const TL = " + json.dumps(tl) + ";")
        assert any(f["tag"] == "asset" and "inside" in f["what"] for f in lint(d)), "escaping voice line not reported"
        # .env: only the workspace's own file (the folder holding kit/), only documented keys, shell wins (S7)
        keys = ("GEMINI_TTS_VOICE", "ELEVENLABS_MODEL", "AZURE_TTS_VOICE", "ANTHROPIC_API_KEY", "NOT_OURS")
        saved = {k: os.environ.pop(k, None) for k in keys}
        try:
            ws = d / "ws"; (ws / "kit").mkdir(parents=True); (ws / "kit" / "AUDIO.md").write_text("x")
            (ws / "film").mkdir()
            (d / ".env").write_text("ELEVENLABS_MODEL=from-parent\n")                     # above the workspace
            (ws / ".env").write_text("# comment\nGEMINI_TTS_VOICE='Kore'\nNOT_OURS=1\nANTHROPIC_API_KEY=sk-test\nAZURE_TTS_VOICE=\n")
            os.environ["ELEVENLABS_MODEL"] = "shell"
            got = load_env(ws / "film")
            assert os.environ["GEMINI_TTS_VOICE"] == "Kore" and os.environ["ELEVENLABS_MODEL"] == "shell", got
            assert "NOT_OURS" not in os.environ, "loaded a key .env.example doesn't document"
            # agent keys have no consumer in the engine: never loaded (S12)
            assert "ANTHROPIC_API_KEY" not in os.environ, got
            del os.environ["ELEVENLABS_MODEL"]
            # values: an inline comment after an unquoted value is dropped; only matching quotes are removed (S14)
            os.environ.pop("GEMINI_TTS_VOICE", None)
            (ws / ".env").write_text("GEMINI_TTS_VOICE=Kore # warm\nAZURE_TTS_VOICE=\"en-US A#1\"\nELEVENLABS_MODEL='v2\"\n")
            load_env(ws / "film")
            got = [os.environ.pop(k, None) for k in ("GEMINI_TTS_VOICE", "AZURE_TTS_VOICE", "ELEVENLABS_MODEL")]
            assert got == ["Kore", "en-US A#1", "'v2\""], got
            (ws / ".env").unlink()
            assert load_env(ws / "film") == {} and "ELEVENLABS_MODEL" not in os.environ, "read a .env above the workspace"
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    # login status: "Not logged in" is not a login, and the reported method is passed through (S13)
    real_run = subprocess.run
    for cli, out, rc, want in (("codex", "Logged in using ChatGPT", 0, "ChatGPT"), ("codex", "Not logged in", 0, ""),
                               ("codex", "Not logged in", 1, ""), ("claude", '{"loggedIn": true, "authMethod": "claude.ai"}', 0, "claude.ai"),
                               ("claude", '{"loggedIn": false}', 1, ""), ("claude", "not json", 0, "")):
        subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a, rc, out, "")
        try:
            assert local_login(cli) == want, (cli, out, local_login(cli))
        finally:
            subprocess.run = real_run
    # every rule fires on its case and stays quiet on the correct form (T5)
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t); (ws / "kit" / "audio").mkdir(parents=True); (ws / "kit" / "AUDIO.md").write_text("x")
        (ws / "kit" / "audio" / "sfx-pop-1.wav").write_bytes(b"x")
        d = ws / "f"; (d / "shots").mkdir(parents=True); (d / "vo").mkdir()
        (d / "vo" / "l1.wav").write_bytes(b"x")
        (d / "timeline.js").write_text(json.dumps({"beat": 0.5, "totalBeats": 8, "cues": {}, "sfx": [{"file": "sfx-pop-1.wav", "beat": 9}],
                                                   "music": {"file": "music-9.mp3", "bpm": 120}, "lines": [{"file": "vo/l1.wav", "beat": 0}]}
                                                  ).join(["const TL = ", ";"]))
        (d / "facts.md").write_text("| claim as shown | source | date | kind |\n|---|---|---|---|\n| 12 seats | seeded demo | | example |\n")
        (d / "provenance.json").write_text("{}")
        (d / "index.html").write_text("\n".join([
            "e.style.visibility = 'visible';",
            "h('div', 'n', p, 'Example: 12 seats');",
            "<img src='shots/a.png'>"]))
        (d / "shots" / "a.png").write_bytes(b"x")
        got = {(f["tag"], f["what"]) for f in lint(d)}
        tags = {g[0] for g in got}
        assert "hide" in tags, got
        assert not any(tag == "invent" for tag, _ in got), got                      # labelled example passes
        assert any(tag == "asset" and "provenance" in w for tag, w in got), got
        assert any(tag == "asset" and "music" in w for tag, w in got), got
        assert any(tag == "cue" and "after the end" in w for tag, w in got), got
        assert "voice" in tags, got
        # provenance fails closed: no provenance.json at all blocks, and a shot changed since capture blocks (X5)
        (d / "provenance.json").unlink()
        assert any(f["tag"] == "asset" and "provenance.json" in f["what"] for f in lint(d)), lint(d)
        (d / "provenance.json").write_text(json.dumps({"shots/a.png": {"url": "https://x.test", "sha256": "0" * 64}}))
        assert any(f["tag"] == "asset" and "changed" in f["what"] for f in lint(d)), lint(d)
        import hashlib
        (d / "provenance.json").write_text(json.dumps({"shots/a.png": {"url": "https://x.test", "sha256": hashlib.sha256(b"x").hexdigest()}}))
        assert not any("shots/a.png" in f["what"] for f in lint(d)), lint(d)
        # a path built in a template literal isn't a finding by itself (E7), and the image it loads is still checked:
        # every image in shots/ needs its provenance, whatever references it
        (d / "shots" / "b.png").write_bytes(b"y")
        (d / "index.html").write_text("<img src='shots/a.png'>\nimg.src = `shots/${name}.png`;")
        got = [f["what"] for f in lint(d) if f["tag"] == "asset" and "shots/" in f["what"]]
        assert got == ["shots/b.png has no provenance entry"], got
        (d / "shots" / "b.png").unlink(); (d / "index.html").write_text("<img src='shots/a.png'>")
        # shots referenced only from a script, or only by a built path, still need provenance, without a crash; and a
        # script gets every per-line rule, not only the pattern list (review of X5, X6)
        (d / "provenance.json").rename(d / "prov.bak")
        (d / "scenes.js").write_text("img.src = 'shots/a.png';\ne.style.opacity = sp(b, 3);\nh('div', 'n', p, 'Save 42%');\n")
        (d / "index.html").write_text('<script src="scenes.js"></script>')
        got = {(f["file"], f["tag"]) for f in lint(d) if f["sev"] == "B"}
        assert {("scenes.js", "asset"), ("scenes.js", "fade"), ("scenes.js", "invent")} <= got, got
        (d / "index.html").write_text("img.src = `shots/${name}.png`;")
        assert any(f["tag"] == "asset" and "provenance.json" in f["what"] for f in lint(d)), lint(d)
        # a provenance record says where and has a hash; a script the page loads must exist, query string or not (R10, R9)
        (d / "prov.bak").rename(d / "provenance.json"); (d / "scenes.js").unlink()
        (d / "index.html").write_text("<img src='shots/a.png'>")
        keep = (d / "provenance.json").read_text()
        (d / "provenance.json").write_text('{"shots/a.png": {}}')
        assert any(f["tag"] == "asset" and "record" in f["what"] for f in lint(d)), lint(d)
        (d / "provenance.json").write_text(keep)
        (d / "tick.js").write_text("setInterval(f, 16);\n")
        (d / "index.html").write_text('<img src="shots/a.png"><script src="tick.js?v=1"></script><script src="gone.js"></script>')
        got = {(f["file"], f["tag"]) for f in lint(d)}
        assert ("tick.js", "clock") in got and any(f["tag"] == "asset" and "gone.js" in f["what"] for f in lint(d)), got
        (d / "tick.js").unlink()
        # the page's own local scripts and stylesheets are linted too (X6)
        (d / "custom.js").write_text("const tick = setInterval(step, 16);\n")
        (d / "extra.css").write_text(".x { transition: all 1s; }\n")
        (d / "index.html").write_text('<link rel="stylesheet" href="extra.css"><script src="custom.js"></script>\n<img src="shots/a.png">')
        assert {("custom.js", "clock"), ("extra.css", "clock")} <= {(f["file"], f["tag"]) for f in lint(d)}, lint(d)
        (d / "index.html").write_text("h('div', 'n', p, 'Hello');")                  # shots/ but no crop on screen
        assert any(f["tag"] == "redraw" for f in lint(d)), lint(d)
    print("lint self-check ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test(); sys.exit()
    fs = lint(sys.argv[1])
    for f in fs:
        print(fmt(f))
    b = sum(f["sev"] == "B" for f in fs)
    print(f"score: {b} blocking, {sum(f['sev'] == 'P' for f in fs)} polish, {sum(f['sev'] == 'V' for f in fs)} to verify"
          if fs else "Clean. Render it.")
    sys.exit(1 if any(f["sev"] == "B" for f in fs) else 0)
