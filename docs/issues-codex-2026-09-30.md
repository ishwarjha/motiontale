# Motiontale issues: adversarial Codex review, 30 September 2026

Codex CLI (read-only sandbox, high reasoning effort) reviewed `motiontale/` and the workspace files independently of `issues-2026-09-30.md`. Codex marked every finding "verified" by a code path or probe. Two spot-checked here (X3, X9). Nothing has been fixed.

It returned 34 findings: 16 are new (below); 18 confirm existing issues, several at a higher severity (last table).

## New

| ID | Sev | Issue | Evidence (Codex) | Fix direction |
|---|---|---|---|---|
| X1 | high | Re-cutting a cached AI take erases its TTS provenance; lint then can't see the voice is AI | `engine/voice.py:166`: an existing `take_01.wav` always sets `source="take"`; a probe rewrote an AI line's source | Persist provenance next to each take; keep it across re-cuts |
| X2 | high | Unknown check names and an empty `review_log.md` count as a clean, checked film in the audit | `engine/film.py:603`, `engine/audit.py:83`: `names=["typo"]` gave `failed: []`; audit accepted it (extends I5) | Validate names; audit requires a complete check set bound to the current film |
| X3 | high | The documented workflow can't create a film: motion-brief writes `BRIEF.md`/`facts.md`/`shotlist.md` first, then `film.py new` refuses the non-empty folder | `engine/film.py:53-55` (spot-checked) | Create the film before the brief, or refuse only when template files would be overwritten |
| X4 | medium | Common ways to show an invented number pass lint: static HTML (`<h1>Save $999</h1>`), interpolated text; "9 customers" passes against a "999 customers" row | `engine/lint.py:176` (extends I25) | Check the rendered text (DOM at each beat) against whole claims |
| X5 | medium | Provenance fails open: a `shots/` image passes when `provenance.json` is absent; recorded SHA-256 hashes are never compared | `engine/lint.py:190` | Require provenance for every referenced capture; verify the hashes |
| X6 | medium | Lint reads only `index.html`: a `custom.js` with `setInterval` passes | `engine/lint.py:148` | Lint every local script and stylesheet the page loads |
| X7 | medium | Music normalisation after ducking cancels it: with continuous narration, music and voice both end at about -18 dB RMS | `engine/film.py:147` (probe: music -18.02, voice -18.00) | Normalise stems first, then apply music gain and ducking |
| X8 | medium | Voice match is one score per scene: "Pay 900 dollars" spoken for scripted "Pay 500 dollars" scored 0.962 and passed | `engine/voice.py:178` | Check each cut; require exact agreement on numbers and names |
| X9 | medium | `place()` ignores a width or height of 0 and keeps the previous size, which is state carried between frames | `engine/motion.js:62` `if (w)` (spot-checked) | Test `w != null`, not truthiness |
| X10 | medium | Assertions pass on a missing selector (`staysInFrame`) and on an element fully off-screen (`appearsBy`) | `engine/film.py:499` | Fail missing targets; "appears" means it intersects the viewport |
| X11 | medium | The pop scan misses a persistent jump (a hard cut): it takes the minimum of the two adjacent deltas, so only one-frame flashes count | `engine/film.py:373` (synthetic black-to-white: 0 pops) | Also flag isolated large transitions outside planned cuts |
| X12 | medium | The counter-quantisation rule in `proof.md` doesn't hold one value across a blurred frame: `floor(t*60)` on frame 60's centred samples gives `[59,59,60,60]` | `skills/motion-video/scenes/proof.md:16` | Use the frame index from the renderer, or round at the shutter centre |
| X13 | medium | Gemini response parsing assumes a first candidate with audio in its first part: empty candidates raise IndexError, a text part KeyError | `engine/voice.py:87` ([API allows no candidates](https://ai.google.dev/api/generate-content)) | Validate candidates, parts and mime type; report the finish reason |
| X14 | medium | Rebuilding the kit deletes unchosen fallback files, even ones existing films use | `engine/kit.py:88` | Never delete measured assets that films reference |
| X15 | medium | AUDIO.md prints the drop bar 1-based, while `dropBar` and `bars` are 0-based: copying the number shifts the drop by one bar | `engine/kit.py:107` vs `engine/film.py` `music_bars` | Publish 0-based indices, or convert at the input |
| X16 | medium | A separate clip project per technique, even for short films, then draw code is copied into the film and later fixes start in the clip | `skills/motion-video/SKILL.md:29` | Build short films in one timeline; use clips only for long multi-agent films |

## Confirms existing issues

| Codex finding | Existing ID | Note |
|---|---|---|
| Partial render or animatic replaces the video that `mux` uses | I4 | Adds the animatic case |
| Capture ids escape the film folder | S4 | Codex rates it high; absolute ids escape too |
| Azure region redirects the keyed request | S3 | Reproduced against an intercepted request |
| SSML voice injection | S10 | Codex injected an `<audio src=…>` element |
| `storageState` file unprotected | S2 | Cites Playwright's auth docs |
| Render doesn't enforce lint | I6 | Replay too |
| Checks hard-code `film.mp4` | L18 | Codex rates it medium: a 9:16 render with `--out` is never checked |
| Worker ignores the encoder's exit code | I14 | Reproduced with a mocked ffmpeg |
| Failed audio measurement becomes a pass; a silent effect vanishes from avsync; the engine test accepts an empty effects list | I2, T2 | Adds the vanished-effect case |
| Loop check: `firstVsLast=100, lastStep=155` passes | I24 | Concrete reproduction |
| Local CSV fetch fails under `file://` | I29 | Now backed by MDN's CORS rules |
| Caption timestamp carry | I10 | Reproduced |
| Invented "Checked" numbers in AUDIO.md | I19 | |
| Agent-key fallback has no consumer | S12 | Codex rates it medium |
| `/test.py` has no assertions | T9 | |
| Hook JSON escaping | S11 | Reproduced with a backslash and a newline |
| Stale check and intake numbers | D1, D2 | |
| Third-party handles, emoji, filler | C1, C3, C4 | |

## Priority change

Put X1, X3 and X2 alongside I1–I6 at the top of the fix plan: X3 blocks the documented workflow outright, and X1 hides that a voice is AI.
