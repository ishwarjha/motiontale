# Motiontale

Motion videos written as code: launch films, explainers, tutorials, product tours, data stories, brand and history stories, highlight reels and social cuts, in twelve styles, for a product, a result, a lesson or an idea.

You describe the video to your coding agent in plain words. Motiontale interviews you once, gathers the real material (your product's screens, your data, your sources), writes the film as a web page, renders it frame by frame with motion blur, puts real recorded sound on the beat, and checks it before you see it. Every number on screen has a source, every screen comes from the real thing, and every frame can be rebuilt from its code.

It ships as a plugin for Claude Code and Codex. The skills are plain Markdown and `AGENTS.md` carries the rules, so an agent that reads skills or `AGENTS.md` can follow the same workflow, and the engine is a Python command-line tool you can also run by hand.

It suits anyone who would rather edit a line than re-shoot a video: founders, product and marketing teams, educators, analysts, and developers showing their work.

## What it does

- **Twelve styles, one engine.** Editorial (Swiss style), explainer, product tour, vertical kinetic type, keynote reveal, morph loop, story, teaser, data story (animated infographic), tutorial (screencast), app preview and sizzle reel. Each style has a card with its length, formats, scenes, music and banned moves.
- **Real screens, not drawings.** Captures pages and single elements from a site or app at 2x, with transparent crops for pieces that move on their own. It can use your logged-in Chrome, blocks every write request while it captures, and records where each pixel came from.
- **Numbers you can defend.** Every number, price or date on screen needs a row in `facts.md` with its source and date, or is shown as demo data labelled "Example". Lint blocks the render on numbers it can read in the code, and a check reads every number the rendered frames actually show.
- **Real sound, on the beat.** Music and effects are real recordings, measured once. Each effect lands on its event by its measured peak, the music is cut so its drop lands on your payoff, a voice ducks the music, and the master reaches -14 LUFS with a short limiter instead of squashing the mix.
- **Voice, if you want it.** Record it yourself, or choose an AI voice (Google, Microsoft or ElevenLabs), labelled as AI. Every sentence is transcribed and matched to the script, numbers word for word, before it's placed on the beat grid.
- **Motion that holds up.** Closed-form springs, one camera, shapes that change into the next thing instead of cutting. Motion blur takes 4 to 64 samples a frame, sized to the motion it measures.
- **Checked before you see it.** Fifteen measured checks: text size, overlap, contrast and off-frame text; determinism; the moments that must happen; sourced numbers; flashes and unplanned cuts; the loop seam; sound on its event; loudness. Then a scored critique on eight axes.
- **One timeline, every format.** 16:9, 1:1 and 9:16 come from the same film, reframed, never cropped.
- **Ready to post.** Captions (SRT and VTT), YouTube chapters when YouTube will use them, a poster frame and a GIF preview.
- **Rebuildable.** Each render writes a recipe; `replay` rebuilds the film from it.

## Install

You need Python 3.11 or later, ffmpeg on your PATH, and Claude Code or Codex signed in.

**1. Add the plugin.**

Claude Code:
```bash
claude plugin marketplace add ishwarjha/motiontale      # or a local path to this folder
claude plugin install motiontale@motiontale
```

Codex:
```bash
codex plugin marketplace add <path to this folder or its git URL>
codex plugin add motiontale@motiontale
cp <plugin>/.codex/agents/*.toml ~/.codex/agents/      # Codex plugins don't ship custom agents
```

**2. Set up a workspace**, the folder your films will live in:
```bash
python3 -m venv .venv && .venv/bin/pip install -r <plugin>/engine/requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python <plugin>/engine/kit.py                  # downloads and measures the sound kit into ./kit
cp <plugin>/.env.example .env                             # only if you want an AI voice: fill in one provider
.venv/bin/python <plugin>/engine/film.py doctor           # shows your login, keys and kit
```

Claude Code and Codex use your own logins. The engine never reads their API keys, and it never prints a key.

## How a film gets made

1. **Brief.** One round of questions: what it is, who watches, the pain in the customer's words, three features and the payoff, the call to action, the style and formats, references, the voice, and the facts with their sources. Anything your prompt already answers is skipped.
2. **Shotlist.** You approve it before anything is built.
3. **Capture.** Your real screens and elements, with provenance and suggested facts.
4. **Stills.** A few key frames for you to approve before the full render.
5. **Build, render, check.** The film is written as code, rendered, and put through every check and the critique. Failures are fixed, not shown to you.
6. **Deliver.** The MP4, the reframed cuts, captions, chapters, a poster and a GIF, plus a note of what was fixed and what a person should still listen for.

The more of the brief your prompt answers, the faster this goes. The prompts below answer all of it.

## Prompts by style

Replace everything in angle brackets. Give numbers exactly as your source shows them, with the source. If you have no real number yet, say so; the film will label demo data "Example" rather than invent one.

### Editorial (Swiss style)

**Best for:** a launch announcement, a homepage hero, a changelog headline. Clean type, one accent word, the product doing the talking. 30 to 70 seconds, music only.

```text
Make an editorial (Swiss style) launch film for <product>, 45 seconds, 16:9 first, then 1:1 and 9:16 reframed from the same timeline.

What it is: <product> helps <who> <do what>. Viewers are <audience>; after watching they should <action>.
The pain, in the customer's words: "<pain line>".
Features, in order: <feature 1>, <feature 2>, <feature 3>. The payoff: <result or number>, source <url or document, date>.
Call to action: "<CTA>", link <url>.

Capture from <url> (log in with my Chrome over cdp if it needs a login): the screen for each feature, and as transparent element crops <the button, card or chip that should move on its own>. Seed or patch <the state the screen doesn't show on its own>.
Look: warm canvas, one accent word per headline in the serif italic, real crops on white cards. Words rise one per beat; things change shape into the next thing, never cut or fade.
Sound: music only from the kit, payoff on the drop, a click on each real press, a pop on each thing that lands.
Facts: <each number or quote with its source and date>.
Deliver: film.mp4 and the 1:1 and 9:16 cuts, poster at the payoff, a GIF preview. Every check passing and every critique score 8 or more before you show me.
```

### Explainer

**Best for:** a sales page, a demo follow-up email, a pitch meeting. A voice tells the story and the screens prove it. 60 to 90 seconds.

```text
Make a 75-second explainer for <product>, 16:9 first, then 1:1.

Viewers are <buyers or users>. After watching they should <book a demo, start a trial, reply>.
The problem, in the customer's words: "<pain line>". Why it matters: <cost of the problem>, source <url, date>.
How it works, in three steps: <step 1>, <step 2>, <step 3>. The proof: <real result>, source <url or case study, date>.
Call to action: "<CTA>", link <url>.

Voice: <my recording: I'll put one take per scene in vo/ | an AI voice from <google, microsoft or elevenlabs>, labelled as AI>. Write script.md with one scene per step, then cut and place it on the beat grid. Say numbers exactly as the script writes them; add pronunciations for <product name, acronyms> in pronounce.json.
Captures from <url>: each step's screen, plus element crops for <the parts that should move>.
Chapters: a title for each step so the film exports YouTube chapters if it runs long enough.
Stat cards for each number, the source under it. Music ducks under the voice and comes up for the payoff on the drop.
Deliver: film.mp4, captions.srt and .vtt, the 1:1 cut, poster, GIF. All checks passing and a scored critique of 8 or more.
```

### Product tour

**Best for:** onboarding, a help centre, a "see it in action" page. Chaptered, step by step, voiced. A full tour runs 4 to 7 minutes; a short one under 90 seconds keeps each step to a title and one zoom.

```text
Make a product tour of <product>, about <5 minutes | 90 seconds>, 16:9 only.

Viewers are <new users | evaluators>. By the end they should know how to <main job> and <next step>.
Open with the pain in one line: "<pain line>", and a promise: "<promise>".
Chapters, in order, each with a title: <1. step>, <2. step>, <3. step>, <…>. For each, show the real screen, zoom to the part that matters, and end on the result.
Capture from <url> with my logged-in Chrome over cdp (writes stay blocked): every screen above, in the state it reaches after the step. Use a demo account, and patch out any personal data rather than blurring it.
Voice: <my recording | an AI voice, labelled as AI>, one scene per chapter. Music loops quietly under the voice, no drop.
Call to action only at the end: "<CTA>", link <url>.
Facts: <any number shown, with its source and date>.
Deliver: film.mp4 with YouTube chapters, captions, poster, GIF. Render one film at a time. Every check passing.
```

### Vertical (kinetic typography)

**Best for:** Reels, Shorts and TikTok, where people watch without sound. Big words on the beat, one feature, a loop back to frame one. 15 to 30 seconds.

```text
Make a 20-second vertical for <product>, 1080x1920, made from the <film name> timeline if it exists, otherwise its own.

Frame one is the thumbnail: the pain as words, fully on screen: "<pain line>".
Then one feature: <feature>, shown on its real screen or as a morph from <shape> into <shape>.
Then the proof: <number>, source <url, date>. End card: "<CTA>", with <domain> as plain text (the link goes in the first comment), looping back into frame one.
Headlines 96 px or larger, nothing in the platform's UI zones, readable with the sound off.
Sound: the kit track around its drop so the proof lands on it. Sound is a bonus, never needed to follow the film.
Deliver: film.mp4 at 9:16, poster, GIF. Check the phone sheet for readability, and the loop seam.
```

### Keynote (product reveal)

**Best for:** an event opener, a big release, a pinned brand post. One statement at a time, slow and large, the product revealed on the drop. 30 to 60 seconds.

```text
Make a 45-second keynote-style reveal for <product or release>, 16:9, then 1:1.

Open on the statement people should remember, already on screen at frame one: "<statement>". One statement per bar after that.
Build to the reveal: <what is revealed> on one real crop, no cursor chasing. The proof on the drop: <number or result>, source <url, date>.
End card: "<CTA>", <url>.
Look: flat contrast, large type, no glows or light effects; dark only if the product itself is dark.
Captures: <the screen or element to reveal>, as a transparent crop so it can rise on its own.
Sound: music only, one change per bar, the proof on the drop.
Deliver: film.mp4, the 1:1 cut, poster on the reveal, GIF. Every check passing and a critique score of 8 or more.
```

### Morph loop

**Best for:** a social post or a homepage loop that shows the whole product in one breath. One card changes shape through every state and ends where it began. 16 to 24 seconds.

```text
Make a morph loop for <product>, 20 seconds, 1:1 first, then 9:16 and 16:9 reframed.

Two bars of the pain in words: "<pain line>".
Then one card morphs through these real states, one per bar: <state 1>, <state 2>, <state 3>, <state 4>, <state 5>. Each state is a real capture or crop; the card never cuts, it changes shape into the next state.
The last state folds back into the first frame so the loop has no seam, and the music is continuous across it.
Captures from <url>: each state above; transparent crops for <the elements that move>.
Something changes on every beat. No voice.
Deliver: film.mp4 and the other two formats, loop_check.mp4 so I can watch the seam twice, GIF.
```

### Story (narrative animation)

**Best for:** a brand film, an about page, a keynote opener, the history of a problem. A start, a turn and an end, with a new visual every few seconds. 45 to 150 seconds.

```text
Make a 90-second story film about <the story: how the problem began, what changed, where it is now>, <16:9 | 9:16>.

Open on the most striking image in the first two seconds: <image or line>.
Chapters, each with a title: <1. before>, <2. the turn>, <3. after>, <4. …>. A new visual payoff every 3 to 5 seconds.
Every date, name, quote and number needs a source: <each one with its source and date>. Quotes shown with who said them.
Captures: <any product screens that appear>; the rest is type and shapes, never drawn product UI.
Voice: <none | my recording | an AI voice, labelled as AI>. Chapter turns on downbeats, the payoff on the drop.
End card: "<CTA>", <url>.
Deliver: film.mp4, captions if voiced, chapters if the film runs long enough, poster after the payoff settles, GIF.
```

### Teaser

**Best for:** a post that has to stop the scroll, a changelog headline, the first reply under a launch. The payoff first, then the one action that got there. 8 to 20 seconds.

```text
Make a 15-second teaser for <feature or release>, in 9:16 and 16:9 from one timeline.

Frame one shows the payoff itself, fully on screen: "<payoff line>".
Then the one action that got there: <action> on the real screen, or a morph from <before> to <after>.
Then the proof: <number>, source <url, date>. End card: "<CTA>", <url>.
Captures: <the screen and element for the action>.
Sound: the kit track, the proof on the drop, a click on the press.
The accent colour means the result only.
Deliver: both formats, poster, GIF.
```

### Data story (animated infographic)

**Best for:** a results announcement, a customer-impact reel, a quarterly recap, a stat-led explainer. A headline makes the claim; the charts prove it. 30 to 60 seconds.

```text
Make a 45-second data story, 16:9 first, then 1:1.

Open on a headline that states the claim, in words, no number yet: "<claim>".
Then one chart per insight, two to four of them: <chart 1: what it shows, the values, source and date>, <chart 2: …>. Bars from zero, scales from the data's real range, lines that draw themselves.
Put the data in data.js from <CSV or table>, each value with its facts.md row.
Then a stat card for each headline number and the biggest one on the drop: <number>, source <url, date>.
End card: "<CTA>", <url>.
Voice: <none | my recording | an AI voice, labelled as AI>.
Deliver: film.mp4, the 1:1 cut, poster, GIF. The facts check has to pass on every number the frames show.
```

### Tutorial (screencast)

**Best for:** onboarding, help articles, a "how to" under a feature launch, a support reply. The result first, then each step on the real screen. 30 to 90 seconds.

```text
Make a 60-second tutorial: "How to <task> in <product>", 16:9.

Open on the finished result for two seconds: <result screen>.
Steps, each with a numbered title held on screen: <Step 1: …>, <Step 2: …>, <Step 3: …>. For each, show the real screen before and after the click, and declare the click as a cut so the screen swap is intentional.
Capture from <url> with my logged-in Chrome over cdp (writes stay blocked), on a demo account: every before and after state above. If you type into a field, reveal the real typed state with the typing sound.
Voice: <my recording | an AI voice, labelled as AI>. Captions always, from the same list the screen shows.
End card: the help link <url>.
Deliver: film.mp4, captions.srt and .vtt, poster, GIF.
```

### App preview (app demo)

**Best for:** an App Store or Google Play preview, a mobile feature launch, a 9:16 social post. Real phone screens, real taps. 15 to 30 seconds.

```text
Make a 25-second app preview for <app>, 1080x1920 (886x1920 for the App Store cut), then 16:9 with the phone beside the headline.

Open on the app's best screen with a headline above it: "<headline>".
Then taps and swipes on real screens: <screen 1 → action → screen 2>, <…>. One screen becomes the next through a shared element; declare each tap's screen change as a cut.
Screens: <from the Android emulator or my phone: I'll put the screenshots in a folder, import them with their source>, or capture <url> at phone size.
The proof: <number or rating>, source <store page or dashboard, date>.
End card: <the store's official badge file if I supply it, otherwise the store name as text>.
No voice. The kit track.
Deliver: the 9:16 film, the App Store size, the 16:9 cut, poster, GIF.
```

### Sizzle reel (highlight reel)

**Best for:** a launch-week or year-in-review recap, an investor or partner pitch opener, an event opener. The strongest moments, faster and faster, the biggest number on the drop. 45 to 90 seconds.

```text
Make a 60-second sizzle reel of <what: this year's releases | launch week | the product>, 16:9 first, then a 9:16 cut.

Open on the strongest moment: <image or line>. Not the biggest number; that waits for the drop.
Highlights, one per bar, getting faster (4 beats, then 2, then 1): <highlight 1 on its real screen>, <highlight 2>, <…>. Each crop swaps at the moment its card is smallest, so no cut shows.
Stat cards for each real number: <number, source, date>, <…>. Quotes only if attributed: "<quote>" — <name, where published, date>.
The biggest number on the drop and held for a full bar: <number>, source <url, date>.
End card: "<CTA>", <url>.
No voice. Rising music from the kit.
Deliver: film.mp4, the 9:16 cut, poster, GIF.
```

## Running the engine yourself

The skills run all of this for you. To drive it by hand:

```bash
PY=.venv/bin/python; E=<plugin>/engine
$PY $E/film.py new myfilm --size 1080x1920                  # template, fonts and rules file; --size for a vertical or square first cut
$PY $E/capture.py myfilm                                     # real UI from myfilm/capture.json
$PY $E/capture.py import myfilm phone.png <source url>       # a screenshot taken elsewhere, with its source
python3 $E/lint.py myfilm                                    # rule breaks, blocking first
$PY $E/film.py mix myfilm && $PY $E/film.py render myfilm && $PY $E/film.py check myfilm
SIZE=1080x1920 $PY $E/film.py render myfilm --out film_9x16.mp4
$PY $E/film.py export myfilm && $PY $E/film.py replay myfilm
python3 $E/audit.py .                                        # the whole workspace, ranked
```

## What the checks measure

| Check | What it proves |
|---|---|
| contact, phone, first, poster | One frame per beat to look at; a phone-size sheet; the thumbnail; the poster |
| layout | Text large enough, inside the frame, not overlapping, with enough contrast, at every beat |
| determinism | The same frame renders the same way in any order |
| asserts | The moments you list in timeline.js happen, and the elements you name stay in frame |
| facts | Every number the frames show has a source (or an Example label) |
| pops, seams | No one-frame flashes, no cuts you didn't plan |
| loop, loopcheck | A looping film has no seam |
| peaks, avsync | Every effect lands on its event, and still does in the final file |
| lufs | -14 LUFS, true peak at or below -1 dBTP, loudness range 15 LU or less |

Known limit: when six render workers run at once, a replay can differ from the film by an invisible fraction of a level on zoomed text; with one worker it's exact.

## Tests

```bash
python3 tests/test_plugin.py                 # the plugin contract, a few seconds
.venv/bin/python engine/test_engine.py       # renders a film, plants a fault for every check, about 5 minutes
```

## Layout

| Path | What it is |
|---|---|
| `skills/` | motion-brief, motion-capture, motion-video (styles, scenes, checks), motion-director, motion-check, motion-review, motion-audit, motion-extend |
| `engine/` | `film.py`, `capture.py`, `voice.py`, `kit.py`, `lint.py`, `audit.py`, `motion.js`, `render.py`, `audiokit.py`, `template/` |
| `agents/`, `.codex/agents/` | Scene builder and critic, for Claude and Codex |
| `AGENTS.md` | The rules every agent follows |
| `docs/` | Plan, issues and their fixes, the latest review |
| `tests/` | The plugin contract |
