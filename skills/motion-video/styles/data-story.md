# Style: data story

*Also known as: animated infographic, data visualisation video, data animation.*

Numbers as the protagonist: a chart that draws itself from a real CSV, one insight per chart, every value from facts.md.

- **Use for:** a results announcement, a customer-impact reel, an annual or quarterly recap, a stat-led explainer.
- **Length:** 30-60 s. **Voice:** optional (voiceover-sync). **Formats:** 16:9 first, 1:1.
- **Scenes:** hook (a headline in words: the claim the data will prove, no number yet) → chart (one per insight, 2-4) → stat-card → proof → end card.
- **Music:** the kit track (121 BPM) unless a slower one is added to kit.py's list; steady; chart draws land on downbeats.

## Data rule
Every chart reads `<slug>/data/*.csv`, listed in facts.md as a `fact` with its source and date. Values on screen are computed from the CSV in the page, never typed. Axis starts at zero for bars (default).

## Canvas, type
From the brand. Tabular figures for every number (`font-variant-numeric: tabular-nums`) so counters don't jitter.

## Motion grammar
- Open on the headline, fully on screen at frame one; the first number arrives on the next bar. A statistic is evidence, not a hook.
- Lines draw with `drawPath()`; bars grow from the baseline; one series at a time.
- The insight (the one number that matters) lifts off the chart and becomes the next shot.
- Counters show whole real values only, floored to the frame.

## Camera
Still while a chart draws. Push to the insight only after it lands.

## Colour meaning
One accent for the series that carries the insight; every other series is neutral grey.

## Banned
3D charts, pie charts over 4 slices, dual axes, a number not in the CSV, easing a counter through values that never existed.
