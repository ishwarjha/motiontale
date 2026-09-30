# Style: editorial light launch film

*Also known as: Swiss style, International Typographic Style, Swiss minimal, kinetic typography.*

The default house style. Swap in the brand's canvas, green and fonts, and keep the grammar.

- **Use for:** a launch announcement, a homepage hero or a changelog headline.
- **Length:** 30-70 s. **Voice:** none, music only. **Formats:** 16:9 first, then 1:1 and 9:16 reframed.
- **Scenes:** hook (12 beats) → demo (20 beats) → morph → proof → end card. The film is about 5 clips on one timeline.
- **Music:** 110-125 BPM with a drop (the kit track is 121). The payoff lands on the drop.

## Canvas
Warm white #F7F8F6, with a soft 5% tint of the accent behind whatever is in focus. No dark scenes.

## Type
Headlines are Manrope 800 (default), letter-spacing -0.045em. Each headline gets one accent word in Instrument Serif italic (default), in the brand accent (default green #0B8F63). `film.py new` copies both into the film's `fonts/` (OFL, licences beside them); another brand font goes there too.

## UI
Real crops sit on white cards: radius 20, 1px #E6E9E7 border, shadow 0 12px 32px rgba(21,32,27,.08). A card is the only frame UI ever sits in.

## Motion grammar
- Text rises out of a mask line, one word per beat. Nothing fades in and nothing blurs in.
- Every change starts on a beat. Springs have a small overshoot.
- Holds are 1.5 beats at most.

## Camera
One transform on one container. It follows the cursor in the demo, with zoom interpolated in log space. One move at a time, with eased keyframes.

## Transitions
Morphs, never cuts. A dot grows into a button, a button stretches into a card, and a card shrinks into the next dot.

## Colour meaning
Green means good news. #C24A1B is only for "late".

## Banned
3D, glows, particles, gradients on UI, crossfades, and any hold longer than a beat and a half.
