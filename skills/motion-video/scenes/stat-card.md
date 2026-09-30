# Scene: stat card, one claim per screen (explainer, tour)

Build it in `<slug>/index.html`, or in `<slug>/clips/stat-card/` when the film is built from clips (see SKILL.md, Scenes) (or several cards in one clip, one after another). Follow `<slug>/CLAUDE.md`.

## Brief
- Claim: {{one number + one line, e.g. from a page or a cited study the user supplied}}
- Source: {{publisher, date checked; shown on screen in small type}}
- Spoken line: {{the sentence that says it; the card lives while it's spoken}}

## Technique
The card morphs out of the previous card or dot. The number counts up, following the proof rules. The line rises out of the mask line. The source sits under it in small grey type. The card lives from the spoken line's start to its end, anchored to the line's cue (`L3.5`) and its end (the cue plus the line's `len` in timeline.js).

## Rules
- One number, one line and one source. A second claim gets a second card.
- Every number has a source the user can open. No source means no card.
- The caption and the card say the same number the same way. Spelled-out numbers exist only in `vo/pronounce.json` (what the voice says), never on screen.

## Gotchas
- The voice says "seventy-nine percent" while the screen shows "79%". `voice.py`'s number spelling makes them match for the transcript check, but the caption must show the script's form.
- Three cards in a row are a slideshow. Morph each into the next, and change the camera between them.
- Proof-scene counter gotchas apply: tabular-nums, one value per frame, no "-0".

## Done when
Every card in contact.png has exactly one number, the phone sheet can read the source, and each card's first beat matches its line's cue. End your reply with "What I'd still change".
