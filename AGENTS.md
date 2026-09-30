# Motiontale: always-on rules

You make motion videos as programs: one index.html that paints any moment with window.seek(t), rendered frame by frame by engine/film.py. The workflow lives in skills/motion-video/SKILL.md; follow it for any video request.

1. Real product UI only: screenshots and crops of the real pages. Never redraw UI. Missing state: edit the real page and screenshot it.
2. No invented numbers, names, prices, quotes or logos. Every number on screen has a facts.md row (fact with source and date, or example shown labelled "Example"); lint blocks the render on numbers it can read in the source, and `check facts` on every number the render shows.
3. Every frame is a pure function of time: motion.js + studio(draw). No CSS animations or transitions, timers, requestAnimationFrame, Math.random (use mulberry32), or state kept between frames. No will-change on anything the camera scales.
4. Every time lives in timeline.js, in beats. Picture and sound read the same file.
5. Music and effects are real recordings from kit/audio, placed so their measured peaks land on their beats. Never synthesize them. Voice is a human take unless the user chose TTS, which is then labelled as AI.
6. Banned: centered title on a gradient, everything fading in, corner labels, frame borders, glows, particles, 3D, gradients on UI, crossfades.
7. Formats are reframed from one timeline (SIZE=1080x1920 etc.), never cropped.
8. Before showing anything: film.py check passes and the scored critique (skills/motion-video/checks.md) has every score 8+, or 3 rounds are done and you say what is still under 8.
9. You can't hear: tell the user which beats a human must listen to.
10. Keys live in the workspace .env (template: .env.example) and are referred to by name. Never paste one into a prompt, script or screenshot. Claude Code and Codex use their local logins; the engine never reads an agent API key (`film.py doctor` shows login status).

Before any render, engine/lint.py shows no blocking line (skills/motion-review). Workspace health: skills/motion-audit. Start every film with skills/motion-brief; real UI comes from skills/motion-capture (provenance.json); long runs use skills/motion-director.

Agents: motion-scene-builder builds one clip; motion-critic reviews a film. New styles or scene techniques: skills/motion-extend.
