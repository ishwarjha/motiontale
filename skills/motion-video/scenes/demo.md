# Scene: demo, a cursor with the camera following

Build it in `<slug>/index.html`, or in `<slug>/clips/demo/` when the film is built from clips (see SKILL.md, Scenes). Follow `<slug>/CLAUDE.md`.

## Brief
- Feature: {{one of the brief's features}}
- Before state: {{what the screen shows before; built by editing the real page}}
- Actions: {{click X → type Y → result Z, each on a beat}}
- Length: {{20 beats (editorial default); 1 action per bar in tour}}
- Hands off to: {{shape}}

## Technique
- A cursor moves over real screenshots. The camera is one transform on one container, following the cursor with eased keyframes, one move at a time. Zoom is interpolated in log space: `exp(lerp(log z0, log z1, k))`.
- Every state is a screenshot. To get the "before" state, edit the real page (in the site copy or DevTools), seed the data so it tells one story, and screenshot it. Never paint over a screenshot.
- The cursor image is a real cursor screenshot too, not a drawn arrow.

## Rules
- The click lands on a beat, and the cursor arrives a little before it.
- Typing reveals characters over time from a real screenshot of the finished field (clip-path), with the kit typing recording under it: timeline.js `"typing": {"file": "sfx-typing-1396.wav", "from": <beat>, "to": <beat>, "gainDb": -14}` (the span has to fit the recording, or `mix` refuses it).
- Swap to the next screenshot only where it can't be seen changing: under the cursor's click (list its beat in timeline.js `"cuts"`, or the pop scan flags it), or where both shots match pixel for pixel.

## Gotchas
- The click file has a press peak and a release peak. Sync the press, which is the first hit. Set `"peakFirst": true` on its sfx entry so `film.py mix` syncs the first hit, then confirm with `film.py check <slug> peaks`.
- Effects peak late (click 137 ms, typing 1216 ms in kit/AUDIO.md). Placing by peak handles this, placing by file start doesn't.
- `film.py render` doubles blur samples from 4 as `window.motion` measures faster moves (15 px a frame → 8, 30 → 16, up to 64). Past that it still steps: slow the move. Pass the cursor and camera elements in the `studio(draw, PROBE)` selector.
- Screenshots at 2x and shown at 1x keep text sharp through the zoom. Keep the maximum zoom at or under the capture scale.

## Done when
The pop scan finds nothing, the contact sheet shows one action per beat or bar, and the phone sheet can read the field being used. End your reply with "What I'd still change".
