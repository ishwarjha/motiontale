# Style: vertical social cut

*Also known as: kinetic typography, beat-synced typography, short-form vertical, social cutdown.*

Made for a muted, thumb-scrolling feed. Text carries the story, and it loops. Values marked (default) are starting points to edit.

- **Use for:** vertical social feeds and mobile viewing.
- **Length:** 15-30 s. **Voice:** none. Sound is a bonus, never needed. **Format:** 9:16 at 1080x1920 (`SIZE=1080x1920`), made from the film's own timeline where one exists.
- **Scenes:** hook (the pain as text, fully on screen at frame one) → demo or morph (one feature) → proof → end card that loops back into frame one.
- **Music:** the kit track, taken from bars around the drop so the payoff lands on it (`film.py mix` starts the track so its drop lands on `music.payoffCue`).

## Canvas
Warm white #F7F8F6 (default). Keep text out of the top and bottom 15% (default), where the app's own UI sits. Check the target app.

## Type
Manrope 800 (default), with headlines at 96 px or larger (default) on a 1080-wide frame, and never more than 3 lines. One accent word each. The words say the whole story, so test that it reads with the sound off.

## UI
Crop to one component and shoot it again at the component's size. Never shrink a full page to fit. It uses the editorial card, filling 80% or more of the width (default).

## Motion grammar
- Faster than editorial: a change on every beat, and holds of 1 beat at most.
- Words rise out of the mask line, one per beat. The pain line in the hook is already risen at frame one, because frame one is the thumbnail.
- The last beat returns every element to its frame-one position, so the loop is seamless.

## Camera
Vertical moves only (pan down to the next item). Zoom is in log space. There's no sideways travel, which reads badly on a narrow frame.

## Transitions
Morphs only. The end card's dot shrinks into the hook's first word, so the loop has no seam.

## Colour meaning
Green means good news. #C24A1B is only for "late".

## Banned
Everything on the editorial list. Also banned: text in the platform's UI zones, anything that needs sound to make sense, a link styled to look clickable (the link goes in the first reply; the domain as plain text on the end card is fine), and a first frame without words.
