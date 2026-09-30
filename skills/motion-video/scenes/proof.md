# Scene: proof, one real number

Build it in `<slug>/index.html`, or in `<slug>/clips/proof/` when the film is built from clips (see SKILL.md, Scenes). Follow `<slug>/CLAUDE.md`.

## Brief
- Number: {{the brief's payoff number, exactly as the page shows it, with unit and precision}}
- Where it's from: {{page URL or screenshot in shots/}}
- Counts from: {{0, or a real "before" value}}
- Lands on: {{the drop cue}}

## Technique
A counter runs up to the real number and lands on the music drop. The card holding it morphs in from the scene before.

## Rules
- Do the arithmetic before animating it. Write the start, end and every value shown in timeline.js, and check that the last one equals the page's number character for character.
- Each blurred frame shows one real value. Compute the counter from time rounded to the nearest frame (`Math.round(t * fps) / fps`): a frame's blur samples sit around its centre, so they all round to it and show the same number. Rounding down splits a frame between two numbers, and the blur mixes them into mush.
- No "-0.00", no "NaN", no extra decimals. Format with the page's own precision, and clamp at the start.
- Ease out so the last digits settle a beat before the drop, then the number sits still on the drop while the payoff shape lands.

## Gotchas
- Digits change width. Use `font-variant-numeric: tabular-nums` so the number doesn't jitter.
- The spring overshoot must not overshoot the number. Clamp the counter value, and let only the card spring.
- A currency or unit comes from the page, not from locale formatting.

## Done when
Frame-stepping the MP4 across the count shows readable digits in every frame. The final value matches the page. The effect peak on the drop passes the peaks check in checks.md. End your reply with "What I'd still change".
