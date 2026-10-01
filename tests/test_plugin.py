"""Plugin contract: manifests agree, every skill/style/scene/agent follows its shape, adapters stay in sync.
Stdlib only, runs in a second: python3 tests/test_plugin.py"""
import json, pathlib, re, subprocess, sys, tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MV = ROOT / "skills" / "motion-video"
j = lambda p: json.loads((ROOT / p).read_text())


def front(p):
    m = re.match(r"---\n(.*?)\n---\n", p.read_text(), re.S)
    assert m, f"{p}: no frontmatter"
    return dict(re.findall(r"^(\w+): (.+)$", m[1], re.M))


# manifests: one name, one version, across hosts
names = {j(".claude-plugin/plugin.json")["name"], j(".codex-plugin/plugin.json")["name"],
         j(".claude-plugin/marketplace.json")["plugins"][0]["name"], j(".agents/plugins/marketplace.json")["plugins"][0]["name"]}
assert names == {"motiontale"}, names
assert j(".claude-plugin/plugin.json")["version"] == j(".codex-plugin/plugin.json")["version"]
assert (ROOT / j(".codex-plugin/plugin.json")["skills"]).is_dir()

# skills: frontmatter name matches the folder; the orchestrator stays under 100 lines
for s in (ROOT / "skills").glob("*/SKILL.md"):
    f = front(s)
    assert f.get("name") == s.parent.name and f.get("description"), s
assert len((MV / "SKILL.md").read_text().splitlines()) < 100, "motion-video/SKILL.md must stay under 100 lines"

# every engine file the skill names exists
for ref in ("film.py", "voice.py", "kit.py", "lint.py", "audit.py", "capture.py", "motion.js", "render.py", "template/index.html", "template/timeline.js", "requirements.txt"):
    assert (ROOT / "engine" / ref).exists(), ref

# styles: the contract motion-extend promises, and scenes that exist
scenes = {p.stem for p in (MV / "scenes").glob("*.md")}
for st in (MV / "styles").glob("*.md"):
    t = st.read_text()
    for k in ("**Use for:**", "**Length:**", "**Scenes:**", "**Music:**", "## Motion grammar", "## Banned"):
        assert k in t, f"{st.name}: missing {k}"
    line = re.search(r"\*\*Scenes:\*\*(.*)", t)[1].lower().replace("end card", "endcard")
    used = {s for s in scenes if re.search(rf"\b{re.escape(s)}\b", line)}
    assert len(used) >= 2, f"{st.name}: Scenes line names {used}, want 2+ from scenes/"

# scenes: same shape everywhere
for sc in (MV / "scenes").glob("*.md"):
    t = sc.read_text()
    for k in ("## Brief", "## Technique", "## Gotchas", "## Done when", "What I'd still change"):
        assert k in t, f"{sc.name}: missing {k}"

# agents: every Claude agent has a Codex twin with the same description
for a in (ROOT / "agents").glob("*.md"):
    f = front(a)
    twin = ROOT / ".codex" / "agents" / (a.stem.replace("-", "_") + ".toml")
    assert twin.exists(), f"no Codex twin for {a.name}"
    c = tomllib.loads(twin.read_text())
    assert c["name"] == a.stem.replace("-", "_") and c["description"] == f["description"] and c["developer_instructions"].strip(), twin
    body = lambda t: " ".join(t.replace("`", "").split())            # same instructions, each tool's own formatting (T8)
    assert body(c["developer_instructions"]) == body(a.read_text().split("---", 2)[2]), f"{twin.name} instructions differ from {a.name}"

# the skills the workflow routes through exist
for sk in ("motion-video", "motion-brief", "motion-capture", "motion-director", "motion-check", "motion-review", "motion-audit", "motion-extend"):
    assert (ROOT / "skills" / sk / "SKILL.md").exists(), sk

# the review and audit engines still catch what their skills promise
for tool in ("lint.py", "audit.py"):
    r = subprocess.run([sys.executable, str(ROOT / "engine" / tool), "--self-test"], capture_output=True, text=True)
    assert r.returncode == 0, f"{tool} self-test: {r.stderr[-400:]}"

assert "lint.py" in (ROOT / "skills/motion-review/SKILL.md").read_text() and "audit.py" in (ROOT / "skills/motion-audit/SKILL.md").read_text()

# descriptions are triggers, not workflow summaries (agents follow a summary instead of reading the skill)
for s_ in (ROOT / "skills").glob("*/SKILL.md"):
    d_ = front(s_)["description"]
    assert d_.startswith("Use when") and len(d_) <= 500, f"{s_.parent.name}: description must start 'Use when', <= 500 chars"

# files the skills name exist (ENGINE/x -> engine/x; film-relative paths like <slug>/..., vo/, shots/ are skipped)
FILM = ("<", "{", "vo/", "shots/", "data/", "clips/", "audio/", "frames/", "seams/", "kit/", "refs/", "~")
checked = set()
for s_ in list((ROOT / "skills").rglob("*.md")) + [ROOT / "AGENTS.md", ROOT / "README.md"]:
    for ref in re.findall(r"`([\w./-]+\.(?:md|py|js|json|toml))`", s_.read_text()):
        if ref.startswith(FILM) or "/" not in ref and not (MV / ref).exists() and not (ROOT / ref).exists() \
                and ref in ("BRIEF.md", "facts.md", "shotlist.md", "script.md", "production.json", "review_log.md",
                            "ANIMATION_GUIDE.md", "capture.json", "crops.js", "provenance.json", "timeline.js", "index.html",
                            "checks.json", "recipe.json", "facts.suggested.md", "motion.js", "CLAUDE.md", "SKILL.md", "lines.json", "data.js"):
            continue
        path = ROOT / "engine" / ref[7:] if ref.startswith("ENGINE/") else None
        cands = [path] if path else [s_.parent / ref, MV / ref, ROOT / ref, ROOT / "engine" / ref]
        assert any(c.exists() for c in cands), f"{s_.relative_to(ROOT)} names missing {ref}"
        checked.add(ref)
assert {"../motion-video/checks.md", "ENGINE/capture.py"} <= checked, f"the pattern stopped matching known references: {sorted(checked)[:10]}"   # T8

# the routing hook is wired and executable
hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())
# hooks/hooks.json loads by default; a "hooks" key naming it again merges it twice (S23)
assert "hooks" not in j(".claude-plugin/plugin.json") and "SessionStart" in hooks["hooks"]
assert (ROOT / "hooks" / "session-start").stat().st_mode & 0o111, "hooks/session-start must be executable"

# the hook's JSON stays valid for any workspace path, and it is silent outside a workspace (S11)
import tempfile
with tempfile.TemporaryDirectory() as t:
    ws = pathlib.Path(t) / 'odd \\ "path"\nname'
    (ws / "kit").mkdir(parents=True); (ws / "kit" / "AUDIO.md").write_text("x")
    out = subprocess.run(["bash", str(ROOT / "hooks" / "session-start")], cwd=ws, capture_output=True, text=True).stdout
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert str(ws) in ctx, ctx
    assert subprocess.run(["bash", str(ROOT / "hooks" / "session-start")], cwd=t, capture_output=True, text=True).stdout == ""
    # a kit set by MOTION_KIT (the kit folder) makes a workspace too, as it does for every engine command (D18)
    out = subprocess.run(["bash", str(ROOT / "hooks" / "session-start")], cwd=t, capture_output=True, text=True,
                         env={**__import__("os").environ, "MOTION_KIT": str(ws / "kit")}).stdout
    assert "Motiontale workspace" in out, out

# checks and intake answers are referred to by name: numbers drift when a list changes (D1, D2, T8)
numbered = re.compile(r"checks\.md,?\s*(check\s*)?#?\d|\bcheck\s+\d+\b|\bchecks\s+\d+(\s+and\s+\d+)?\b|\bintake\s+\d|SKILL step \d"
                      r"|\b(with|after)\s+\d+(\s+and\s+\d+|-\d+)\b")                 # "with 3 and 6", "after 1-9" (R43)
docs = [*ROOT.glob("skills/**/*.md"), *ROOT.glob("agents/*.md"), *ROOT.glob(".codex/agents/*.toml"), ROOT / "AGENTS.md"]
stale = [f"{f.relative_to(ROOT)}: {m.group()}" for f in docs for m in numbered.finditer(f.read_text())]
assert not stale, "numbered references: " + "; ".join(stale)

# script/bootstrap and script/setup: present, executable, valid bash; the pip fallback pins exactly what uv.lock pins
for sc in ("bootstrap", "setup"):
    f = ROOT / "script" / sc
    assert f.stat().st_mode & 0o111 and subprocess.run(["bash", "-n", str(f)]).returncode == 0, f"script/{sc} must be executable valid bash"
assert "script/bootstrap" in (ROOT / "script" / "setup").read_text() and "uv sync" in (ROOT / "script" / "bootstrap").read_text()
pins = lambda t: sorted(l.split(";")[0].strip() for l in t.splitlines() if "==" in l and not l.startswith("#"))
lock = {m[1]: m[2] for m in re.finditer(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"', (ROOT / "uv.lock").read_text())}
req = dict(x.split("==") for x in pins((ROOT / "engine" / "requirements.txt").read_text()))
assert all(lock.get(k) == v for k, v in req.items()) and len(req) >= 5, "engine/requirements.txt has drifted from uv.lock: re-export it"

# lint's summary: a clean film says so, once (the score line sat inside the findings loop)
with tempfile.TemporaryDirectory() as t:
    subprocess.run([sys.executable, str(ROOT / "engine" / "film.py"), "new", f"{t}/v"], check=True, capture_output=True)
    out = subprocess.run([sys.executable, str(ROOT / "engine" / "lint.py"), f"{t}/v"], capture_output=True, text=True).stdout
assert out.strip() == "Clean. Render it.", out

# one version everywhere: installs are pinned to it, so a fix only reaches users when it goes up
vers = {j(".claude-plugin/plugin.json")["version"], j(".codex-plugin/plugin.json")["version"],
        re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)[1]}
assert len(vers) == 1, f"versions differ: {vers}"

# every setting the engine reads is documented in .env.example
env_doc = (ROOT / ".env.example").read_text()
engine_py = [f for f in (ROOT / "engine").glob("*.py") if not f.name.startswith("test_")]    # tests set PATH etc. for themselves
read = {k for f in engine_py for k in re.findall(r"""os\.environ(?:\.get)?[\[(]\s*["']([A-Z_]+)["']""", f.read_text())}
read |= {k for f in engine_py for k in re.findall(r"""need\(\s*["']([A-Z_]+)["']""", f.read_text())}
missing = read - {"SIZE"} - set(re.findall(r"^([A-Z_]+)=", env_doc, re.M))
assert not missing, f".env.example lacks {missing}"
assert (ROOT / ".gitignore").read_text().splitlines()[0] == ".env", ".env must stay out of git"

# the always-on rules carry every hard rule
rules = (ROOT / "AGENTS.md").read_text()
for k in ("Real product UI", "No invented numbers", "pure function of time", "Never synthesize", "timeline.js", "never cropped", "film.py check"):
    assert k in rules, f"AGENTS.md lost: {k}"

print(f"plugin contract ok: {len(list((ROOT / 'skills').glob('*/SKILL.md')))} skills, "
      f"{len(list((MV / 'styles').glob('*.md')))} styles, {len(scenes)} scenes, {len(list((ROOT / 'agents').glob('*.md')))} agents")
