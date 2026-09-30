# Style: chaptered product tour

*Also known as: product tour, product demo, product walkthrough.*

A calm walk through the real workflow, one chapter per step. People watch it to learn the product, not to be sold on it. Values marked (default) are starting points to edit.

- **Use for:** onboarding, a help centre, or a "see it in action" page.
- **Length:** 4-7 min. A short tour (under about 90 s) keeps each step to a title and one zoom on its screen, chapters on any downbeat. **Voice:** yes, a human recording by default, or TTS labelled as AI. **Formats:** 16:9 only, because UI at tour detail doesn't survive 9:16.
- **Chapters:** one per workflow step from the intake's features (3 or more). Each chapter is a chapter-title → demo of that step → one-line result.
- **Scenes:** hook (short: the pain and a promise) → [chapter-title → demo → morph into the result] × N → end card with the CTA. The CTA shows only at the end.
- **Music:** the kit track, looped through `music.bars` in timeline.js (bars measured to loop cleanly; film.py joins jumps with 8 ms fades), ducked 15 dB under the voice by `film.py mix`. There's no drop. Chapters start on downbeats (whole bars).

## Canvas
Warm white #F7F8F6 (default). There's a chapter rail along the top: one pill per chapter, and the current pill is filled.

## Type
Chapter titles are Manrope 800 (default) with one accent word each. Captions follow the explainer rules. There are no other headlines, because the UI is the content.

## UI
Full-page screenshots at 1:1 pixel scale, so the product reads at its real size. They sit on one large white card with the editorial card border and shadow. Crops only appear during zoom-ins.

## Motion grammar
- One action per bar (default): a click, a type or a scroll. The cursor moves along a curve and lands before the click sound.
- Typing uses the kit typing recording, sliced to the length of the typed text.
- Every chapter ends on its result state for 1 beat, then the result morphs into the next chapter-title.

## Camera
It follows the cursor, with log-space zoom. It zooms in to read a field and back out to show where you are. Never zoom twice without pulling back out.

## Transitions
A chapter-title grows out of that chapter's pill in the rail and shrinks back into it. There are no cuts between chapters.

## Colour meaning
Green means done or saved. #C24A1B is only for "late" or an error the step fixes.

## Banned
Everything on the editorial list. Also banned: a CTA before the end, skipping a click the viewer would have to make, sped-up screen footage, and a chapter longer than its voice.
