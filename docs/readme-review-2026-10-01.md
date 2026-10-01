# README claims, judged by TypeSafe Jev, 1 October 2026

Each substantial README claim was sent to TypeSafe Jev (jev-1.13.0) with the code it rests on and one question: supported, overstated or wrong? Every disputed claim went back once with fuller evidence and the author's reply, revised where conceded. Jev returns a ruling with a probability, not reasons; where it still disagreed without naming a defect, the claim is held with its evidence and test.

| ID | Claim (as finally worded) | Round 1 | Round 2 | Outcome |
|---|---|---|---|---|
| C1 | Up to fifteen checks run, depending on the video; ten can fail it: page errors on the contact sheet, layout, determinism, asserts, facts, pops, loop, peaks, avsync and loudness. | overstated (0.50) | overstated (0.55) | Conceded: ten checks can fail, not nine (page errors). README changed. Jev still leaned overstated (0.55) without naming a defect; held. |
| C2 | Every number in the video's visible text is checked every quarter beat against facts.md; an Example row needs an Example label in the number's own card. | overstated (0.54) | overstated (0.61) | Held: the facts check reads visible text and input values every quarter beat, Example label within the number's card (test_engine covers each case). |
| C3 | Lint blocks the render on a number it can read in the code without a facts.md row, a fade, a glow, a timer, a missing or changed capture record, or a mismatched tempo. | overstated (0.89) | overstated (0.71) | Conceded in part: 'a number it can read in the code', the facts check catches the rest. README changed. Rest held: every listed rule is a blocking lint tag. |
| C4 | While capturing, only GET, HEAD and OPTIONS requests leave the browser; pop-ups are covered and WebSocket sends are dropped, unless writes are allowed. | supported (0.52) | - | Agreed: supported |
| C5 | Capture can use your own signed-in Chrome over remote debugging on this machine only, in a tab of its own that it closes, never closing the browser; writes are blocked for the whole browser while it runs. | overstated (0.63) | overstated (0.88) | Conceded: the summary line now says the browser's own service workers aren't blocked over cdp (the capture table already did). |
| C6 | A shots/ image shown on screen with no provenance record, or whose file changed since capture, blocks the render. | overstated (0.73) | supported (0.56) | Agreed: supported after fuller evidence |
| C7 | Effects land within 5 ms of their event in the effects stem, and within one frame (at most 20 ms) in the final file; an effect too quiet to align is flagged for a person to listen to. | overstated (0.86) | supported (0.55) | Agreed: supported after fuller evidence |
| C8 | The music is cut so its drop lands on the payoff cue. | supported (0.51) | - | Agreed: supported |
| C9 | A short limiter takes at most 12 dB off the loudest peaks so the final file lands within 1 LU of -14 LUFS with true peak at or below -1 dBTP. | overstated (0.81) | overstated (0.74) | Conceded: master() aims for -14 LUFS; the loudness check enforces ±1 LU and -1 dBTP. README changed. |
| C10 | Music ducks 15 dB under a voice and comes up for the payoff. | supported (0.41) | - | Agreed: supported |
| C11 | A voice take is transcribed and matched to the script, and every number must be heard as its whole spoken phrase within its own sentence or the take fails. | overstated (0.85) | overstated (0.69) | Held: split() fails the take unless each number is heard as a whole phrase inside its sentence's window (voice self-test covers 5 vs five hundred, swapped sentences, $500). |
| C12 | AI voices come from Google, Microsoft or ElevenLabs, chosen by VOICE_PROVIDER. | overstated (0.49) | supported (0.71) | Agreed: supported after fuller evidence |
| C13 | Motion blur takes 4 to 64 samples a frame, doubling with measured motion. | supported (0.56) | - | Agreed: supported |
| C14 | Captions export as SRT and VTT from voice lines or the timeline's caption list. | supported (0.85) | - | Agreed: supported |
| C15 | YouTube chapters are written only when there are three or more, each at least 10 seconds. | supported (0.87) | - | Agreed: supported |
| C16 | A poster is taken 0.3 s after the payoff or at a poster cue; a GIF preview is 8 seconds at 480 px. | supported (0.60) | - | Agreed: supported |
| C17 | Videos render at 1920x1080, 1080x1080, 1080x1920 or any size set with SIZE (including the App Store's 886x1920), at the timeline's frame rate (60 fps by default), encoded H.264 with AAC sound. | overstated (0.81) | supported (0.51) | Agreed: supported after fuller evidence |
| C18 | A full render of the main video writes a recipe; replay re-renders from it and compares a hash of every decoded frame. | overstated (0.62) | supported (0.65) | Agreed: supported after fuller evidence |
| C19 | Long films get a director with gates, a render budget and resume after a crash or usage limit. | supported (0.52) | - | Agreed: supported |
| C20 | The audit reports rule breaks, stale and unchecked videos, missing critiques and recipes, unlicensed sounds, engine drift, unused screenshots and build leftovers. | overstated (0.54) | overstated (0.83) | Held: each listed item is an audit tag (rule, stale, unchecked, critique, recipe, license, drift, orphan, clean), covered by the audit self-test. |
| C21 | The engine never loads Claude Code's or Codex's API keys from .env, and never prints the value of any key. | wrong (0.78) | supported (0.47) | Agreed: supported after fuller evidence |
| C22 | The sound library is a fixed list: one music track (121 BPM, measured) and eight effects; adding a sound or another track means changing kit.py's list. | overstated (0.54) | wrong (0.61) | Conceded: kit.py lists a fallback music track; the kit keeps whichever downloads first. README changed. |
| C23 | The voice check is English only. | supported (0.84) | - | Agreed: supported |
| C24 | There are twelve styles: app-preview, data-story, editorial, explainer, keynote, morph-loop, sizzle-reel, story, teaser, tour, tutorial, vertical. | overstated (0.84) | supported (0.98) | Agreed: supported after fuller evidence |

Agreed supported: 16 of 24. Conceded and changed in the README: C1, C3, C5, C9, C22. Held with evidence: C2, C11, C20 (and the rest of C1 and C3).
