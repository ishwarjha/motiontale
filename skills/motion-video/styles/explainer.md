# Style: narrated B2B explainer

*Also known as: explainer video, motion-graphics explainer, animated explainer.*

The voice leads. The picture shows the one thing the voice is saying. Values marked (default) are starting points to edit. Colours and fonts are carried over from the editorial card, so replace them with the brand's.

- **Use for:** a sales page, a demo follow-up email or a pitch meeting.
- **Length:** 60-90 s. **Voice:** yes, a human recording by default. TTS only if the brief chose it, and then labelled as AI. No voice: captions carry the script (timeline.js `captions`, drawn and exported from one list) and time comes from the bar grid, one caption per 4-8 beats. **Formats:** 16:9, then 1:1.
- **Story:** a protagonist problem story. One role (from the intake, never an invented name) has the pain. The product removes it, and a real number proves it.
- **Chapters:** problem → product → proof → call to action. Each one opens with a chapter-title (default 4 beats).
- **Scenes:** hook → chapter-title → stat-card(s) → demo → morph → proof → end card, all timed by voiceover-sync.
- **Music:** the kit track (121 BPM), ducked 15 dB under the voice by `film.py mix`, full on the drop. The drop lands on the proof.

## Canvas
Warm white #F7F8F6 (default). One tinted panel sits behind the chapter currently playing.

## Type
- Headlines are Manrope 800 at -0.045em (default), with one Instrument Serif italic accent word each.
- Captions show the spoken sentence in Manrope 600 (default), bottom-centred, at 40 px or larger. They're always on: the film has to work muted.
- Stat numbers are Manrope 800 (default) and the biggest thing on screen.

## UI
Real crops on white cards (editorial card values). Only one card is in focus at a time, and anything else steps back to 60% scale.

## Motion grammar
- Time comes from the voice, not the bar. Each sentence starts on the beat grid (`voice.py place`: 0.75-beat gaps, 2-beat lead-in, 2-beat tail, scenes in whole bars).
- A caption rises out of the mask line as a whole sentence, and drops back when the sentence ends.
- One claim per screen: a stat card holds one number, one line and one source, and nothing else.
- While the voice talks over a still screen, the camera drifts slowly (it's a single move, not a hold). A still frame with no voice for more than 1.5 beats counts as a dead hold.

## Camera
It's slower than editorial: one push-in per sentence at most, drifting between them. It follows the cursor only inside the demo.

## Transitions
A chapter-title pill shrinks into the chapter rail, and the rail becomes the anchor for the next scene. Stat cards morph out of the card before them.

## Colour meaning
Green means good news. #C24A1B is only for the pain, meaning late or lost. Source lines are grey #6B7671 (default).

## Banned
Everything on the editorial list. Also banned: more than one number per screen, a number without an on-screen source, stock footage, a caption that differs from the script, and the voice naming a feature the screen doesn't show.
