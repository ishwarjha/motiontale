# Scene: end card, it loops

Build it in `<slug>/index.html`, or in `<slug>/clips/endcard/` when the film is built from clips (see SKILL.md, Scenes). Follow `<slug>/CLAUDE.md`.

## Brief
- Product name and mark: {{from shots/, a real crop}}
- CTA: {{the brief's call to action, word for word}}
- Link text: {{the brief's link; shown as text, the real link goes in the first reply}}
- Loops into: {{frame one of this clip, or of the film for vertical}}

## Technique
It arrives by morph from the last scene's shape. The name rises out of the mask line and the CTA button grows from a dot. Then everything returns to the loop's start state: the tint shrinks with the dot, and the last frame equals the first.

## Rules
- The last frame equals the first. Design the end state to be the start state instead of freezing on the CTA.
- The CTA gets at least 1 beat fully readable, and at most 1.5 beats of hold.
- The music ends on a downbeat, or loops cleanly at the same bar.

## Gotchas
- `seek(0)` and `seek(end)` can match on the page and still differ in the MP4, because the encoder and the motion blur of the last frame change them. Check the encoded file (checks.md, loop).
- With motion blur, the last frame's subframes sample past the end. Clamp time at the end or wrap it so they sample the start.
- A spring that hasn't settled by the end leaves a tiny offset, which shows as a jump in the loop. Start the return spring early enough to settle.

## Done when
The loop check in checks.md passes on the MP4, and the phone sheet reads the CTA. End your reply with "What I'd still change".
