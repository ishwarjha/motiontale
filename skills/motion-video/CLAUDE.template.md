# Video rules

## Product
No product on screen (the brief rules it out)? Skip motion-capture and the UI section of the style card; the facts rule below still holds.
- Every product pixel comes from shots/: real screenshots and crops, with positions in crops.js. Never redraw UI.
- Need a state the screenshots don't have? Change the real page and screenshot it. Seed demo data so it tells one story.
- No invented numbers, names or prices. Every number, price, date or quote on screen has a facts.md row:
  `| claim as shown | source | date | kind |`, kind `fact` (matches its source) or `example` (demo data, shown with an "Example" label).
  A number on screen with no row blocks the render (lint) or fails `check facts`.
- ../kit/ and other film folders are shared and read-only. Write everything into this folder.

## Engine
- One index.html with window.seek(t) and window.motion(t). Every frame is a pure function of time: no CSS animations, transitions, timers or requestAnimationFrame, and nothing remembered between frames.
- Every time lives in timeline.js, written in beats. The picture and the sound both read it.
- Springs are closed-form (a formula of time) with a small overshoot. A value that changes target more than once is a sum of springs, one per change.
- The camera is one transform on one container. Eased keyframes, one move at a time, zoom interpolated in log space.
- Randomness is seeded (mulberry32 with a fixed seed), never Math.random. Same seed, same film.
- No `will-change` on anything the camera scales: it rasterizes once and text goes soft when zoomed.
- Layout reads innerWidth/innerHeight. Every format comes from this one timeline, reframed and never cropped.

## Render
- 1920x1080 (or the SIZE of the format), 60 fps. `film.py render` blends 4 motion-blur samples a frame, doubling with measured motion up to 64. H.264, yuv420p, AAC.

## Sound
- Music and effects come from ../kit/audio (real recordings, listed in ../kit/AUDIO.md). Never synthesize them.
- Voice: VOICE_SOURCE. Replace with one of: "none", "human recording by <name>", or "TTS (voice.py --tts; provider google, microsoft or elevenlabs from .env or vo/voice.json): labelled as AI on the post".
- The music starts on a downbeat. Place each effect so its measured peak lands on its event. Sync clicks to the press, not the release. Loudness -14 LUFS.

## Banned everywhere (model defaults)
- Centered title on a gradient, everything fading in, corner labels, frame borders, glow on UI, generic particle bursts.

## Keys
- API keys live in .env (e.g. GEMINI_API_KEY). Refer to them by name. Never paste a key into a prompt, script or screenshot.

## Before you show me
- Render one frame per beat into contact.png, look at it, and fix the three worst problems.
- Run every check in checks.md for this style, including the scored critique: every score 8 or more.
- Tell me what you fixed, what you would still change, and what a human needs to listen for.

# Look

Paste the chosen card from skills/motion-video/styles/ here and edit its default values.
