# Scene: chart, data drawn from a real CSV

Build it in `<slug>/index.html`, or in `<slug>/clips/chart/` when the film is built from clips (see SKILL.md, Scenes). Follow `<slug>/CLAUDE.md`.

## Brief
- Data: {{data/metric.csv, with its facts.md row}}
- Chart: {{line | bar}} of {{column}} over {{column}}
- Insight: {{the one value that matters, and why}}
- Hands off to: {{the insight number becomes the next shot}}

## Technique
- Turn the CSV into `data.js` (`const DATA = [...]`, rows as written) and load it with a `<script>` tag before your code: the page opens from `file://`, where `fetch` of a local file is blocked. Keep the CSV beside it as the source. Scale from the data's real min and max; bars from zero.
- Lines: an SVG path with `drawPath(path, k)` from motion.js, k on a spring from the cue; the dot at the path's end follows `path.getPointAtLength`.
- Bars: height = value × `sp(b, cue + i * 0.5)`; one bar per half beat.
- The insight label lifts off the chart with `pop()` and keeps its value; the next shot starts from that label.

## Gotchas
- A counter or label that changes every frame smears under motion blur: show whole values, taken at the nearest frame (`Math.round(t * fps) / fps`: every blur sample of a frame rounds to it).
- Tabular figures, or digits jitter as they change.
- `getTotalLength` is only right after fonts and layout settle: compute lengths after `document.fonts.ready`.

## Done when
Every value on screen is computed from the CSV, the CSV is a `fact` row in facts.md, lint shows no `invent` line, and the pop scan is clean. End your reply with "What I'd still change".
