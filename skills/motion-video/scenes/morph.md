# Scene: morph, one element that never cuts

Build it in `<slug>/index.html`, or in `<slug>/clips/morph/` when the film is built from clips (see SKILL.md, Scenes). Follow `<slug>/CLAUDE.md`.

## Brief
- From: {{e.g. the dot left by the hook}}
- Through: {{button → card → result card}}
- Colour change: {{e.g. pending → paid, green}}
- Hands off to: {{shape}}

## Technique
- There's one DOM element for the whole scene. Only its size, radius, fill and contents change. Each property is a sum of springs, one per change, with every change on a beat.
- The contents are transparent re-shot crops (Playwright `screenshot(omit_background=True)` on the real element). They swap only while the element is small, or while a flood covers them.
- A colour change is a flood circle growing from the cursor's point, using `clip-path: circle(r at x y)` with r on a spring. It's never a fade.

- Spring presets for the engine's `spring(x, freq, zeta)`, time in beats (defaults, tune by eye): snappy 0.9/0.8 for buttons, toggles, leading edges · normal 0.62/0.74 (the engine's default) for cards, containers, camera · heavy 0.45/0.95 for big type and logo lockups, no visible overshoot · playful 0.7/0.5 for stickers and mascots only.
- Text inside the morphing element enters just after the morph starts and leaves just before the next one, so two states' text never overlap.
- Tab or selection indicators: the leading edge on the snappy spring, the trailing edge on the default one, so the indicator stretches as it moves.

## Rules
- There's no second element standing in for the first. If you can't morph it, restage it.
- The radius tracks the size, so a pill stays a pill as it grows into a card (radius 20 at card size).
- The accent tint behind the element grows and shrinks with it.

## Gotchas
- Scaling a crop with `transform: scale` blurs text. Size the box and swap to a crop shot at that size.
- A crop re-shot at a slightly different scale pops. Shoot every crop at the same device scale.
- Two springs retargeting the same property must share one start value. That's the sum-of-springs rule, otherwise it jumps.

- In a looping morph, the last frame equals the first including the cursor's position and its velocity (all springs settled), or the seam hitches.

- A flood must over-scale past the element's corners and take about 0.3 s; faster and half the element changes in one frame.
- A handoff to the next shape starts only after the first has fully landed, or it pops.

## Done when
The pop scan finds nothing, and no two consecutive contact tiles show different elements where there should be one. End your reply with "What I'd still change".
