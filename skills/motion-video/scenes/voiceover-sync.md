# Scene: voiceover sync (narrated styles)

Not a clip: the step that turns a script into timed lines in timeline.js, so every picture cue can anchor to a spoken line. Engine: `ENGINE/voice.py`.

## Brief
- Script: `<slug>/script.md`. Each scene is `## N. Title`, then `**On screen:**`, then `**Voice:**` with one idea per sentence. Anything after a `## Source table` heading is ignored (put sources there).
- Voice source: {{human recording by <name> | TTS, labelled as AI}}, from the brief's voice answer, written into `<slug>/CLAUDE.md`.
- Pronunciations: `<slug>/vo/pronounce.json`, e.g. `{"Acme.ai": "Acme dot A I"}`. Captions keep the script's spelling.

## Voice rule
"Never synthesize" covers music and effects, with no exceptions. A voice is either:
1. **A human recording (the default).** One take per scene, saved as `<slug>/vo/take_01.wav`, `take_02.wav` ... (any format ffmpeg reads). Run `PY ENGINE/voice.py cut <slug>`. It cuts each take into sentences at the pauses and checks each against the script by transcription. A missing or mismatched take stops the run: re-record it. It never falls back to TTS.
2. **TTS, only if the brief chose it.** `PY ENGINE/voice.py cut <slug> --tts`. A human take that fails its match is replaced by an AI take for that scene, so one film can mix both voices; lines.json records each line's source, and CLAUDE.md must then say TTS. Provider from `.env` (`VOICE_PROVIDER`: google = Gemini TTS, microsoft = Azure AI Speech, elevenlabs = ElevenLabs; keys in `.env`, see the plugin's `.env.example`), or per film in `<slug>/vo/voice.json` `{"provider": ..., "voice": ...}`. The AI take is saved as `vo/take_NN.tts.wav`, next to (never over) a human `take_NN.wav`, so re-cuts cost nothing and stay labelled AI. Write "TTS voice" and the provider into CLAUDE.md and label it as AI on the post.

## Technique
- `voice.py cut` writes `vo/lines.json` (file, text, duration, match, source). `PY ENGINE/voice.py place <slug>` lays each line on the beat grid (2-beat lead-in, 0.75-beat gaps, 2-beat tail, every scene rounded up to whole bars) and writes `lines`, `shots` (`s01`...), cues (`L3.2` = line start, `s03.start`) and `totalBeats` into timeline.js, keeping your other cues, sfx and music.
- Picture cues are line cues plus an offset in beats: `cue('L3.2') + 1`, `cue('L3.2') + line.len`. Never seconds.
- `film.py mix` ducks the music 15 dB under every line and brings it up only around the payoff cue.

## Gotchas
- Word timestamps drift by a few hundred ms. The cutter searches either side for the real pause: trust its cuts over the transcript.
- Short scenes fail on one misheard word: the bar is 0.75 under 20 words, 0.85 otherwise.
- "79%" in the script matches "seventy-nine percent" in the voice (numbers are spelled out for the match); the caption shows "79%".
- Place the payoff (music drop) in a gap between lines, or the voice fights it.
- The model can't hear delivery. A human listens for pace, mispronounced names and breaths cut at sentence joins.

## Done when
Every scene's match clears its bar, timeline.js has a line for every sentence, and `film.py check <slug> contact` shows no page errors (a missing cue throws). End your reply with "What I'd still change".
