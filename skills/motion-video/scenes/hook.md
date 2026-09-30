# Scene: hook, the words land on the beat

Build it in `<slug>/index.html`, or in `<slug>/clips/hook/` when the film is built from clips (see SKILL.md, Scenes) (index.html + timeline.js). Follow `<slug>/CLAUDE.md`.

## Brief
- Pain line: {{PAIN, the brief's pain line, word for word}}
- Turn line: {{one line that names the product, from the brief's product line}}
- Length: {{12 beats (editorial default); 1 bar per statement in keynote}}
- Hands off to: {{the shape the next clip starts from, e.g. the accent word shrinks into a dot}}

## Technique
Words rise out of a mask line, one word per beat. Each word is a span in an `overflow:hidden` line box, with translateY going from 115% to 0 on a closed-form spring that starts on its beat. Nothing fades or blurs in. The accent word is the only Instrument Serif word.

## Rules
- Frame one states the pain, fully risen, because it's the thumbnail. The rise starts from the second line, or the pain line drops out and the turn line rises.
- Word beats come from timeline.js cues, never from constants in index.html.
- A long word still gets one beat. If a line has more words than beats, cut words. Don't speed up.

## Gotchas
- Spring overshoot pushes a word up past its line and the mask clips it. Leave headroom in the line box (line-height of about 1.15 or more).
- Wait for fonts before the first seek (render.py waits on `document.fonts.ready`). A missing font silently falls back and changes every word width.
- Letter-spacing of -0.045em can make the italic accent word collide with its neighbour. Add a thin space.

## Done when
contact.png shows one new word per beat tile, the first tile reads as the pain, and nothing is half-visible at a beat boundary. End your reply with "What I'd still change".
