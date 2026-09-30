# Style: one-shape UI morph loop

*Also known as: morphing animation, morph transition, shape morphing, product UI animation.*

One element never cuts. It morphs through 8-12 real UI states of the product, a cursor drives each change, and the film loops.

- **Use for:** a social post or homepage loop that shows the whole product in one breath.
- **Length:** 16-24 s (8-12 bars at about 120 BPM). **Voice:** none. **Formats:** 1:1 and 9:16 first, 16:9 reframed.
- **Scenes:** hook (2 bars, the pain in words) → morph (the state list, one state per bar) → end card that folds back into the first frame.
- **Music:** 115-125 BPM, starts on a downbeat. Something changes on every beat.

## The state list (the shotlist gate for this style)
8-12 states, each a real UI element of the product, re-shot as a transparent crop, with the real data it shows. Example order: logo → CTA button → field typed into → loader → success check → dashboard card → chart draws itself → tooltip → command palette → toast → logo.

## Canvas, type, UI
Take them from the brand. Default: the editorial card's canvas and type. One accent colour.

## Motion grammar
- One container for the whole film. Only size, radius, fill and contents change (see scenes/morph.md, including spring presets and text-swap timing).
- A cursor does every change with a real click. The click sound syncs to the press.
- Springs with at most a tiny overshoot. No bouncy easing.

## Camera
Mostly still. The container moves, not the camera. At most one slow push per 4 bars.

## Transitions
None. There is nothing to transition between: it is one shape.

## Banned
Cuts, crossfades, a second element standing in for the first, glows, gradients on UI, particle bursts, a beat with nothing changing.

## Done when
The pops and loop checks pass: no pops, and the encoded last frame equals the first, cursor included.
