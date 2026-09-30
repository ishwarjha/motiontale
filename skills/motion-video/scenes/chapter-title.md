# Scene: chapter title (explainer, tour)

Build it in `<slug>/index.html`, or in `<slug>/clips/chapter-title/` when the film is built from clips (see SKILL.md, Scenes). One clip holds every chapter title. Follow `<slug>/CLAUDE.md`.

## Brief
- Chapters: {{1. <name> … N. <name>, from the brief's features or the tour's workflow steps}}
- Length each: {{4 beats (default)}}
- Rail: {{top of frame, one pill per chapter}}

## Technique
The chapter's pill in the rail grows into the title card. The chapter number and name rise out of the mask line, one word per beat, with one accent word. Then the card shrinks back into its pill, and the pill stays filled. The next scene starts from that pill's position.

## Rules
- A chapter starts on a downbeat. `voice.py place` rounds scenes to whole bars, so pad there and don't stretch.
- The title uses the product's own words for the step, taken from the page's menu or button text.
- The rail shows every chapter from the first title on, so viewers can see how far along they are.

## Gotchas
- With many chapters, the pills get small. Check the rail in the phone sheet, and drop the names from the pills (keep numbers) if they don't read.
- The pill-to-card grow is a morph (radius tracks size). Scaling the pill blurs its text, so resize the box instead.
- The voice's chapter intro and the title must start on the same cue.

## Done when
Each title lasts its beats with no hold longer than 1.5 beats, and the rail state is right in every contact tile. End your reply with "What I'd still change".
