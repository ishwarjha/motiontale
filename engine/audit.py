"""audit.py: the mechanical half of motion-audit. Walks a workspace, finds every film (a folder with
index.html + timeline.js), and prints one ranked line per finding, blocking first:

  <tag> <what>. <fix>. [path]

  audit.py [workspace]              exit 1 if anything blocking
  audit.py --self-test

Tags (B blocking, P polish, V verify):
  rule      B/P lint findings in a film (run motion-review on it)
  stale     B   film.mp4 is older than its sources: what ships is not what the code says
  unchecked B   film.mp4 has no checks.json, an older one, or failed checks
  license   B   a kit file with no licence row in kit/AUDIO.md
  drift     P   the film's motion.js differs from the engine's: fixes don't reach it
  legacy    P   the film carries its own inline engine instead of motion.js
  critique  P   rendered but no scored critique on record (review_log.md)
  orphan    P   files in shots/ nothing references
  clean     P   build/ leftovers (regenerated on every render)
  recipe    P   rendered with no recipe.json: the film can't be proven rebuildable (film.py replay)
  unrendered V  no film.mp4 yet
  unused    V   kit sounds no film uses
"""
import hashlib, json, os, pathlib, re, sys

ENGINE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
import lint as L  # noqa: E402
from film import CHECKS  # noqa: E402

SEV = {"rule": "B", "stale": "B", "unchecked": "B", "license": "B", "drift": "P", "legacy": "P", "critique": "P",
       "orphan": "P", "clean": "P", "recipe": "P", "unrendered": "V", "unused": "V"}
SKIP = {"build", ".venv", "node_modules", "frames", ".git", "__pycache__"}


def size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else (p.stat().st_size if p.exists() else 0)


def films(ws):
    for root, dirs, files in os.walk(ws):
        dirs[:] = [x for x in dirs if x not in SKIP and x != "clips" and not x.startswith(".")]   # clips/<scene>/ belong to their film
        r = pathlib.Path(root)
        if "index.html" in files and "timeline.js" in files and r != ENGINE / "template":
            yield r


def audit(ws):
    ws = pathlib.Path(ws).resolve()
    out = []
    add = lambda tag, what, fix, path, weight=0, sev=None: out.append(
        {"tag": tag, "sev": sev or SEV[tag], "what": what, "fix": fix, "path": str(path.relative_to(ws)) if path.is_relative_to(ws) and path != ws else "." if path == ws else str(path), "weight": weight})
    engine_js = hashlib.sha1((ENGINE / "motion.js").read_bytes()).digest()
    used_sfx, n, kits = set(), 0, set()
    for d in films(ws):
        n += 1
        kits.add(L.kit_dir(d))
        try:                                         # one broken film is a finding on it, not the end of the audit
            html = (d / "index.html").read_text()
            try:
                tl = L.tl_of(d)
            except Exception as e:
                add("rule", f"timeline.js does not parse ({e.__class__.__name__})", "fix the JSON", d, sev="B"); continue
            used_sfx |= {e["file"] for e in tl.get("sfx", [])} | {x["file"] for x in (tl.get("music"), tl.get("typing")) if x}
            fs = L.lint(d)
            b, p = sum(f["sev"] == "B" for f in fs), sum(f["sev"] == "P" for f in fs)
            if b or p:
                top = ", ".join(sorted({f["tag"] for f in fs if f["sev"] == ("B" if b else "P")}))
                add("rule", f"{b} blocking, {p} polish ({top})", "run motion-review on it", d, weight=b * 10 + p, sev="B" if b else "P")
            mj = d / "motion.js"
            if mj.exists():
                if hashlib.sha1(mj.read_bytes()).digest() != engine_js:
                    add("drift", "motion.js differs from the engine's", "diff it, then copy the engine's in deliberately and re-render", d)
            elif re.search(r"function spring\(", html):
                add("legacy", "inline engine (no motion.js)", "leave it if it ships; start new work with film.py new", d)
            film = d / "film.mp4"
            if not film.exists():
                add("unrendered", "no film.mp4", "film.py render", d); continue
            loaded = [d / x for x in re.findall(r"""<(?:script[^>]*\bsrc|link[^>]*\bhref)\s*=\s*["']([^"':?#]+\.(?:js|css))""", html)]
            srcs = [d / "index.html", d / "timeline.js", mj, d / "audio" / "mix.wav", d / "crops.js", *(d / "shots").glob("*"),
                    *loaded, *(d / "fonts").glob("*")]      # everything the page loads decides the pixels
            newest = max((s for s in srcs if s.exists()), key=lambda s: s.stat().st_mtime)
            if newest.stat().st_mtime > film.stat().st_mtime + 1:
                add("stale", f"film.mp4 is older than {newest.relative_to(d)}", "film.py mix (if sound changed) and render", d)
            ck = d / "checks.json"
            if not ck.exists() or ck.stat().st_mtime < film.stat().st_mtime:
                add("unchecked", "no checks since the last render", "film.py check", d)
            else:
                res = json.loads(ck.read_text())
                missing = set(CHECKS) - set(res.get("ran", [])) - (set() if tl.get("loop") else {"loop", "loopcheck"})
                if res.get("film", "film.mp4") != "film.mp4":
                    add("unchecked", f"checks.json is for {res['film']}, not film.mp4", "film.py check (without --film)", d)
                elif res.get("failed"):
                    add("unchecked", "failing checks: " + "; ".join(res["failed"]), "fix, re-render, film.py check", d)
                elif missing:
                    add("unchecked", "checks never run on this render: " + ", ".join(sorted(missing)), "film.py check (all names)", d)
            if not (d / "recipe.json").exists():
                add("recipe", "no recipe.json", "render with the current engine (it writes one), then film.py replay", d)
            if not (d / "review_log.md").exists() or not (d / "review_log.md").read_text().strip():
                add("critique", "no scored critique on record", "run motion-check (review_log.md)", d)
            if (d / "shots").is_dir():
                refs = html + "".join(x.read_text() for x in [d / "crops.js", *loaded] if x.is_file())
                orphans = [f for f in (d / "shots").iterdir() if f.is_file() and f.name not in refs]
                if orphans:
                    add("orphan", f"{len(orphans)} shots nothing references ({size_mb(sum(f.stat().st_size for f in orphans))})",
                        "delete them or use them", d / "shots", weight=sum(f.stat().st_size for f in orphans) >> 20)
            if size(d / "build") > 50 << 20:
                add("clean", f"build/ holds {size_mb(size(d / 'build'))}", "delete build/ (render recreates it)", d / "build", weight=size(d / "build") >> 20)
        except Exception as e:
            add("rule", f"audit stopped on this film: {type(e).__name__}: {e}", "fix the film, then re-run", d, sev="B")
    for kit_audio in sorted(k for k in kits | {L.kit_dir(ws)} if k):   # every kit a film resolves, as every command finds it
        md = kit_audio.parent / "AUDIO.md"
        if not md.exists():
            continue
        rows = {m[1]: m[2] for m in re.finditer(r"^\|\s*`audio/([^`]+)`\s*\|(.*)$", md.read_text(), re.M)}
        for f in sorted(kit_audio.glob("*")):
            if f.name not in rows:
                add("license", f"{f.name} has no row in kit/AUDIO.md", "measure and list it with kit.py, or delete it", kit_audio)
            elif not re.search(r"licen[cs]e", rows[f.name], re.I):
                add("license", f"{f.name} has no licence link", "add its licence to kit/AUDIO.md", md.parent)
        unused = sorted(set(rows) - used_sfx)
        if unused and n:
            add("unused", f"{len(unused)} kit sounds no film uses: {', '.join(unused)}", "fine to keep; they cost nothing", md.parent)
    order = {"B": 0, "P": 1, "V": 2}
    return n, sorted(out, key=lambda f: (order[f["sev"]], -f["weight"], f["path"]))


def size_mb(b):
    return f"{b / (1 << 30):.1f} GB" if b >= 1 << 30 else f"{b / (1 << 20):.0f} MB"


def self_test():
    import tempfile, shutil, time
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t)
        (ws / "kit" / "audio").mkdir(parents=True)
        (ws / "kit" / "AUDIO.md").write_text("| `audio/a.wav` | a | page | [Licence](x) | 1 ms | 1 ms |\n")
        (ws / "kit" / "audio" / "a.wav").write_bytes(b"x"); (ws / "kit" / "audio" / "b.wav").write_bytes(b"x")
        f = ws / "film"
        shutil.copytree(ENGINE / "template", f); shutil.copy(ENGINE / "motion.js", f / "motion.js")
        (f / "film.mp4").write_bytes(b"x")
        (f / "shots").mkdir(); (f / "shots" / "unused.png").write_bytes(b"x")
        time.sleep(0.01); os.utime(f / "index.html", (time.time() + 5, time.time() + 5))
        n, fs = audit(ws)
        tags = {x["tag"] for x in fs}
        assert n == 1 and {"stale", "unchecked", "license", "critique", "orphan"} <= tags, tags
        assert "drift" not in tags, "a fresh copy of motion.js must not drift"
        assert not any(x["tag"] == "license" and "a.wav" in x["what"] for x in fs), "a Licence link (British spelling) counts (T4)"
    # a check run of one name and an empty critique log don't count as checked (X2)
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t)
        f = ws / "film"
        shutil.copytree(ENGINE / "template", f); shutil.copy(ENGINE / "motion.js", f / "motion.js")
        (f / "film.mp4").write_bytes(b"x"); (f / "recipe.json").write_text("{}")
        time.sleep(0.01)
        (f / "checks.json").write_text('{"lufs": {}, "failed": [], "ran": ["lufs"]}'); (f / "review_log.md").write_text("")
        tags = {x["tag"] for x in audit(ws)[1]}
        assert {"unchecked", "critique"} <= tags, tags
    # a director's clips/<scene>/ folders are part of their film, not films (I31); the kit is found like every
    # other command finds it: MOTION_KIT, else the nearest kit/ above (I32)
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t) / "ws"
        f = ws / "film"
        shutil.copytree(ENGINE / "template", f); shutil.copytree(ENGINE / "template", f / "clips" / "s01")
        (pathlib.Path(t) / "kit" / "audio").mkdir(parents=True)
        (pathlib.Path(t) / "kit" / "AUDIO.md").write_text("x\n"); (pathlib.Path(t) / "kit" / "audio" / "z.wav").write_bytes(b"x")
        n, fs = audit(ws)
        assert n == 1, n
        assert any(x["tag"] == "license" and "z.wav" in x["what"] and x["path"].endswith("kit/audio") for x in fs), fs
    # an edited script the page loads makes the film stale; a shot named only in that script isn't an orphan (R27);
    # a kit found above a film, not at the workspace root, gets its licences audited too (R28)
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t); f = ws / "sub" / "film"
        shutil.copytree(ENGINE / "template", f); shutil.copy(ENGINE / "motion.js", f / "motion.js")
        (ws / "sub" / "kit" / "audio").mkdir(parents=True); (ws / "sub" / "kit" / "AUDIO.md").write_text("x\n")
        (ws / "sub" / "kit" / "audio" / "z.wav").write_bytes(b"x")
        (f / "shots").mkdir(); (f / "shots" / "a.png").write_bytes(b"x")
        (f / "index.html").write_text((f / "index.html").read_text().replace("</body>", '<script src="scenes.js"></script></body>'))
        (f / "scenes.js").write_text("img.src = 'shots/a.png';\n")
        (f / "film.mp4").write_bytes(b"x"); time.sleep(0.01)
        os.utime(f / "scenes.js", (time.time() + 5, time.time() + 5))
        tags = {(x["tag"], x["what"].split()[0]) for x in audit(ws)[1]}
        assert ("stale", "film.mp4") in tags and not any(t_ == "orphan" for t_, _ in tags), tags
        assert ("license", "z.wav") in tags, tags

    # a check of another file (a 9:16 variant, --film) doesn't count as a check of film.mp4 (review of L18)
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t); f = ws / "film"
        shutil.copytree(ENGINE / "template", f); shutil.copy(ENGINE / "motion.js", f / "motion.js")
        (f / "film.mp4").write_bytes(b"x"); (f / "recipe.json").write_text("{}"); (f / "review_log.md").write_text("ok")
        time.sleep(0.01)
        (f / "checks.json").write_text(json.dumps({"failed": [], "ran": list(CHECKS), "film": "film_9x16.mp4"}))
        assert any(x["tag"] == "unchecked" and "film_9x16.mp4" in x["what"] for x in audit(ws)[1]), audit(ws)[1]
    # one broken film is a finding on that film; the rest of the studio is still audited (L16)
    with tempfile.TemporaryDirectory() as t:
        ws = pathlib.Path(t)
        for name in ("a", "b"):
            shutil.copytree(ENGINE / "template", ws / name)
        (ws / "a" / "timeline.js").write_text('const TL = {"beat": 0.5, "totalBeats": 8, "cues": {}, "sfx": [{"file": "x.wav"}]};')
        n, fs = audit(ws)
        assert n == 2 and any(x["path"] == "a" and x["sev"] == "B" for x in fs), fs
    print("audit self-check ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test(); sys.exit()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n, fs = audit(args[0] if args else ".")
    for x in fs:
        print(f"{x['tag']} {x['what']}. {x['fix']}. [{x['path']}]")
        cnt = {s: sum(x["sev"] == s for x in fs) for s in "BPV"}
        print(f"films: {n} · blocking: {cnt['B']} · polish: {cnt['P']} · verify: {cnt['V']}" if cnt["B"] or cnt["P"] else
              f"films: {n}. Studio clean. Ship.")
    sys.exit(1 if any(x["sev"] == "B" for x in fs) else 0)
