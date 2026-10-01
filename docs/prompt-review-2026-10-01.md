# README prompts, judged by TypeSafe Jev, 1 October 2026

Question: do the twelve style prompts give the agent enough to use the skills to the fullest? Jev (jev-1.13.0) returns rulings with probabilities, not reasons, and rejects open questions, so the review ran as rounds of rulings.

1. Jev rated 20 skill capabilities for each style's prompt (with its style card): covered, partial, missing, or not applicable. All twelve came out "lacking" overall (0.58 to 0.85).
2. The author answered each flagged capability with the skill text, conceding where it was right. Jev ruled on each answer and picked a fix.
3. On the six points still split, Jev chose the best answer from the author's and alternatives.

| Cap | Point | Outcome |
|---|---|---|
| K4 | No prompt asked for references | Conceded (0.97). References line in all 12 prompts |
| K5 | No prompt or interview asked for logo, typefaces, colours; brand is a critique axis | Conceded (0.99, prompts and skill). Brand line in all 12 prompts; motion-brief question 9 |
| K3 | Seven prompts named screens without URL, sign-in or demo account | Conceded (0.96). Added. A recheck then picked publish permission (0.38) as the remaining gap: motion-brief question 3 and README checklist item 3 ask whether everything on screen is public yet |
| K9 | Pronunciations asked only in the explainer | Conceded (0.80). Added to tour, story, data-story, tutorial |
| K8 | Keynote's "music only" read as "no effects" | Author's answer chosen (0.64): reworded to "music and effects, no voice" |
| K11 | First frame not stated in editorial, explainer, tour | Jev's answer chosen over the author's (0.58 vs 0.22): first-frame line added |
| K13 | Formats | Jev's answer (0.39, narrowly): "where it will be posted" added once, to the checklist and motion-brief question 5 |
| K2 | Five short prompts had a one-number facts line | Tie (author 0.37, facts line 0.36): full Facts line added for consistency |
| K1, K12, K14, K16, K18, K19, K20 | Brief, asserts, deliverables, gates, long-film routing, listening, look | Author's answer accepted: the skills apply these with nothing from the user |
| K10, K15 | Captions, loop | Author's answer chosen (0.82, 0.90): no change |

Re-run of step 1 on the updated prompts: references covered in 11 of 12 (was 0), brand in 12 (was 0), gaps per prompt down in every style (teaser 12 to 5, vertical 12 to 7). The overall ruling stays "lacking" (0.52 to 0.80) because step 1 sees no round-2 answers and re-flags the points Jev accepted there.
