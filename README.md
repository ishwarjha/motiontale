# Motiontale

Motion videos made as code, in any style, by Claude Code or Codex. A film is one `index.html` whose `window.seek(t)` paints any moment; `engine/film.py` renders it frame by frame with motion blur, mixes real measured sound onto the beat grid, and checks the result. Three things are checked before anyone sees a film: real product UI with provenance, every on-screen number sourced, and measured quality. The checks and their limits are below.


## Layout

| Path | What it is |
|---|---|
| `skills/motion-brief/` | Interview → `BRIEF.md`, `facts.md`, `shotlist.md`; approval after the shotlist and after the stills |
| `skills/motion-capture/` | Real pages and elements by selector at 2x, transparent crops, state patches, `provenance.json`, suggested facts |
| `skills/motion-video/` | The film pipeline and hard rules. `styles/` (one card per style), `scenes/` (one prompt per technique), `checks.md`, `CLAUDE.template.md` |
| `skills/motion-director/` | Long or multi-agent productions: `production.json` gates, subagent playbook, resume, effort and render budget |
| `skills/motion-check/` | Every measured check plus the 8-axis scored critique |
| `skills/motion-review/` | Source review of one film against the rules (`engine/lint.py` does the mechanical half) |
| `skills/motion-audit/` | Whole-workspace audit: rule breaks, stale renders, unchecked films, missing recipes, drift, licences, clutter (`engine/audit.py`) |
| `skills/motion-extend/` | Add a style or a scene technique |
| `engine/` | `film.py` (new, mix, render, mux, replay, check, export, doctor, strip, frames), `capture.py`, `voice.py`, `kit.py`, `lint.py`, `audit.py`, `motion.js`, `render.py`, `audiokit.py`, `template/` |
| `agents/`, `.codex/agents/` | Scene builder and critic, for Claude and Codex |
| `AGENTS.md` | Always-on rules for Codex and any agent that reads AGENTS.md |
| `.claude-plugin/`, `.codex-plugin/`, `.agents/plugins/` | Manifests and marketplaces |
| `docs/strategy-2026-09-30.md` | Decisions, what is built, what is next |
| `tests/test_plugin.py` | The contract: manifests agree, every skill/style/scene/agent has its shape, lint and audit self-tests |

## Styles

editorial (Swiss style) · explainer · tour (product demo) · vertical (kinetic typography) · keynote (product reveal) · morph-loop (morphing animation) · story (narrative animation) · teaser (product teaser) · data-story (animated infographic) · tutorial (screencast) · app-preview (app demo) · sizzle-reel (highlight reel). Add more with motion-extend: a new file in `styles/` is the whole change.

## What the engine checks

- **Deterministic:** frames are a pure function of time; `check determinism` renders beats in shuffled order to prove it; Chrome runs with single-threaded, non-partial raster so antialiasing varies in about 1 run in 64 (glyph edges, measured); `replay` rebuilds every frame from `recipe.json`.
- **Motion blur that adapts:** 4 samples a frame, doubling with measured motion up to 64; `--shutter 180` for a crisper look.
- **Sound on its event:** effects placed by measured peak, then verified in the final encoded file (`avsync`: within one frame and 20 ms); -14 LUFS, true peak ≤ -1 dBTP, loudness range ≤ 15 LU; stems exported, and `mux` swaps a new mix in without re-rendering.
- **Readable and in frame:** `layout` measures text size, off-frame text, overlaps and WCAG contrast at every beat; `asserts` in timeline.js prove the moments that must happen do.
- **Real and sourced:** `capture.py` records where every pixel came from; `lint.py` blocks shots without provenance and numbers without a `facts.md` row.
- **Delivered:** `export` writes captions (SRT/VTT), YouTube chapters, a poster and a GIF preview.

## Setup (once per workspace)

A workspace is any folder with a `kit/` (sound) and a venv. Films go in folders inside it.

```bash
python3 -m venv .venv && .venv/bin/pip install -r <plugin>/engine/requirements.txt
.venv/bin/python -m playwright install chromium          # ffmpeg must be on PATH
.venv/bin/python <plugin>/engine/kit.py                  # downloads + measures the Mixkit kit into ./kit
cp <plugin>/.env.example .env                             # AI voice keys, if you use TTS; fill what you need
.venv/bin/python <plugin>/engine/film.py doctor           # which login and keys are active
```

Claude Code and Codex use your local logins (`claude auth login`, `codex login`); the engine never reads an agent API key. AI voices (Gemini, Azure AI Speech, ElevenLabs) are only used by `voice.py cut --tts`; a human recording needs no key.

## Install

Claude Code:
```bash
claude plugin marketplace add ~/devai/motion-claude/motiontale
claude plugin install motiontale@motiontale
```

Codex:
```bash
codex plugin marketplace add ~/devai/motion-claude/motiontale
codex plugin add motiontale@motiontale
cp ~/devai/motion-claude/motiontale/.codex/agents/*.toml ~/.codex/agents/   # custom agents are not shipped by plugins
```

Then ask for a video ("make a 60-second launch film for <url>") or run the engine directly:

```bash
PY=.venv/bin/python; E=<plugin>/engine
$PY $E/film.py new myfilm && $PY $E/capture.py myfilm            # after writing myfilm/capture.json
python3 $E/lint.py myfilm                                         # rule breaks, blocking first
$PY $E/film.py mix myfilm && $PY $E/film.py render myfilm && $PY $E/film.py check myfilm
SIZE=1080x1920 $PY $E/film.py render myfilm --out film_9x16.mp4
$PY $E/film.py export myfilm && $PY $E/film.py replay myfilm
python3 $E/audit.py .                                             # the whole workspace, ranked
```

## Tests

```bash
python3 tests/test_plugin.py                  # contract + lint/audit self-tests, a few seconds
.venv/bin/python engine/test_engine.py        # renders the template film, every check, replay, export: about 5 minutes
```
