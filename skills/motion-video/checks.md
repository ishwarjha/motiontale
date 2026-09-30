# Checks

Run from WORKSPACE: `PY ENGINE/film.py check <slug> [names]`. It writes `<slug>/checks.json` (with a `failed` list), prints it, and exits 1 on any measured failure. Paste the result into the report, not just "passed". Thresholds marked (default) are starting points.

| # | Check (name) | Needs film.mp4 | When |
|---|---|---|---|
| 1 | contact | no | the animatic, and before every full render |
| 2 | strip, frames | strip: yes | any move over 15 px a frame, every morph swap |
| 3 | layout | no | every style, every format |
| 4 | asserts, facts | no | asserts: when timeline.js has `asserts`; facts: every film |
| 5 | determinism | no | every film, before a full render |
| 6 | phone, first, poster | yes | every film |
| 7 | pops, seams | yes | every film (seams when there are 2+ shots) |
| 8 | loop, loopcheck | yes | when timeline.js has `"loop": true` |
| 9 | peaks, avsync, lufs | yes | every film with sound |
| 10 | scored critique | — | after every measured check |
| 11 | captions (read `vo/lines.json`), replay (`film.py replay`, not a `check` name) | yes | narrated films; every delivered film |

## 1. contact: one frame per beat
`contact.png`, 16 tiles a row, beat number on each, page errors listed. Name the three worst problems, fix, run again. Usual culprits: an empty tile (dead hold), two tiles alike for more than 1.5 beats, text cut by the mask, a card off the frame, the wrong colour meaning.

## 2. strip and frames: look closer
`film.py strip <slug> <seconds>`: 12 frames in a row around a fast moment. Catches two states' text overlapping in a swap, a constant-speed slide, blur that steps.
`film.py frames <slug> <beat> ...`: single unblurred frames at full size.

## 3. layout: measured at every beat
Text smaller than 28 px scaled to the format's short side (default), text off the frame, two text boxes overlapping by more than 20% of the smaller one, and WCAG contrast under 4.5 (3 for text 24 px and up) against the nearest solid background. Text over an image is skipped: judge it by eye. Each box is cut by its masks first: the hidden part of a rising or sinking word is not measured. Small means still small a quarter second later, so a word popping in or out isn't flagged.

## 4. asserts and facts: the moments that must happen, the numbers that may show
In timeline.js: `"asserts": [{"sel": "#pill", "appearsBy": "payoff"}, {"sel": ".card", "staysInFrame": ["s02.in", "s02.out"]}]`. Times are cue names or beats. A failure names the selector and the beat.

facts: every number in the page's visible text at each beat (not under opacity 0, masked out or off the frame) has a facts.md row with the same whole number; an `example` row needs "Example" on screen with it. A number counts once it holds for a quarter second, so a counter's in-between values don't. Catches what lint can't read: static HTML, arrays, helpers. A range in a row ("1-7") covers only 1 and 7: list each number.

## 5. determinism: order must not matter
Eight beats rendered in order in one browser and shuffled, each after a detour, in another must match byte for byte. A difference means draw() keeps state between frames.

## 6. phone, first, poster
- `phone_NN.png`: sheets at 390 px wide (844 px tall for 9:16). Every headline reads; the focused card fills at least half the width.
- `first.png`: states the pain in words or opens on the payoff, readable at 320 px. Not blank, not the logo, not a half-risen word.
- `poster.png` 0.3 s after the payoff cue, or at a `"poster"` cue when the payoff lands by a morph that is still moving then.

## 7. pops and seams
- Pops: a frame unlike both neighbours, or a hard cut (one frame changes more than 4x the frames around it, default) that isn't planned. Planned cuts are shot starts and the beats in timeline.js `"cuts"` (a tap that swaps the screen, as the real app does). Each one is fixed or planned. Causes: a crop swapped before its pinch closes, a spring starting from a non-zero value, an element shown a frame early, a counter changing inside one frame's samples, a crop swapped at a slightly different scale.
- Seams: `seams/seam_<shot>.png`, frames -2..+2 at every cut. Look for a pop, or near-identical framing across the cut that reads as a glitch.

## 8. loop
Encoded first frame vs last frame: the jump across the seam is under 1.0, or no more than 1.5x a normal step (the median of the last 8 steps). `loop_check.mp4` plays it twice for a human to watch the seam.

## 9. sound
- peaks: every effect's measured peak within ±5 ms of its beat in the effects stem (default). Clicks sync to the press: `"peakFirst": true`.
- avsync: each effect's moment in the **final encoded file**, aligned by envelope correlation against the same moment in `audio/mix.wav`: within one frame and 20 ms. Confidence under 0.5 (a stretch too flat to align) is reported as unmeasurable: check it by ear.
- lufs: integrated -14 ±1, true peak -1 dBTP or lower, loudness range 15 LU or less. `mix` holds only the loudest peaks with a short limiter so the rest gets plain gain, and says if the gain ever rides.

## 10. Scored critique: a harsh motion director, not a proud author
Open contact, strips, seams and phone sheets. Score 1-10:
hook (first 2 s) · readability (at 360 px, without pausing) · composition (hierarchy, negative space, no tangencies) · motion (physical, continuous, no dead frames or default slides) · variety (a new idea every 2-4 s in one system) · brand (real UI, logo, type, palette) · sound (visible actions and peaks feel causally linked) · polish (clean edges, no clipping, flicker or artifacts).
Pair each with its measured check where there is one: readability with layout and phone, motion with determinism and pops, sound with peaks, avsync and lufs, brand with lint and provenance.
Append scores and the 3 worst problems with timestamps to `<slug>/review_log.md`. Fix, re-render only those beats, score again. Pass: every score 8+. After 3 rounds, stop and report what is still under 8.

## 11. Delivery
- captions: `vo/lines.json` match per scene at or above 0.85 (0.75 under 20 words); captions are the script text, never the pronounce.json spelling. `film.py export` writes captions.srt/.vtt from the lines.
- replay: `film.py replay <slug>` prints IDENTICAL: the recipe rebuilds every frame.

## A human must do these
Watch loop_check.mp4 at the seam. Listen to the whole mix on speakers and on a phone: music joins, a late effect, voice under music, a click that plays twice, any effect avsync marked unmeasurable.

## Notes format
```
Problem: <what is wrong, where: shot + beat>
Wanted:  <the result, not the fix>
```

## Report format
- Fixed: each problem, the beat, and the check that now passes
- Still change: worst first
- Listen for: beats a human should hear before shipping
