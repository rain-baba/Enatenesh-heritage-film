# Experiments

Each entry: hypothesis, change, result. Logged calls are in `runs.jsonl`.

## E1. TTS model: gemini-3.1-flash-tts-preview vs gemini-3.8-flash-tts

- **Hypothesis:** the newer 3.8 TTS model (the one the brief recommends) speaks Amharic at least as
  clearly as 3.1, at similar latency.
- **Change:** smoke test with 3.1 on a short greeting; radio cut v1 with 3.8 on all 11 lines.
- **Result so far:** 3.1 spoke "ሰላም፣ እንኳን ደህና መጣችሁ" fully and correctly in 5.1 s (checked by ear,
  native speaker). 3.8 returned audio in 6 to 18 s per line, but with the long style prompt it
  read the instruction aloud (see FAILURES F3). With the short prefix, 3.8 still returned 12.7 s
  for a 49-character line (about twice plausible), while 3.1 had spoken the same pattern correctly.
  **Decision:** 3.1 as primary, 3.8 lite and 2.5 as quota fallbacks. Newer is not better for this
  language and prompt style.

## E2. Style prompt format for TTS

- **Hypothesis:** a short `Say <style> in Amharic: <text>` prefix steers tone without being spoken,
  whereas a long free-standing instruction gets read aloud.
- **Change:** v1 long instruction on its own line; v2 short prefix with a colon. Same voice
  (Sulafat), same text.
- **Result:** v1: 10 of 11 lines implausibly long (s04: 19.9 s for 16 characters). v2: pending.

## E3. Fitting 60 to 90 s without regenerating narration

- **Hypothesis:** a 1.14x pitch-preserving speed-up (`atempo`) plus tighter padding brings the
  radio cut under 90 s without sounding rushed, and costs no TTS quota.
- **Change:** radio cut v2 (102.5 s: 84.4 s of voice, 1.1 s padding per shot, 3.5 s end card) to
  v3: `voice_tempo` 1.14, padding 0.25 s before and 0.45 s after each line, minimum shot 3.5 s,
  end card 3.0 s. Narration files untouched (cached), 0 new model calls.
- **Result:** 88.0 s (computed by `timeline.build`: 89.3 s at 1.12, 88.0 at 1.14, 87.4 at 1.15).
  Whether 1.14 sounds rushed is a question for user test 1.

## E4. Mixed TTS models within one film

- **Observation:** the daily quota fallback (FAILURES F4) means s01 to s08 were voiced by
  `gemini-3.1-flash-tts-preview` and s09 to s11 by `gemini-2.5-flash-preview-tts`, same voice
  name (Sulafat).
- **Question for user test 1:** does the voice audibly change at s09? If it does, regenerate
  s09 to s11 on 3.1 tomorrow's quota, or s01 to s08 on 2.5.

## E5. Fixing TTS mispronunciation: respelling vs replacing

- **Hypothesis:** words a native listener flagged can be fixed in the text without touching the
  model: replace a word with a common synonym, or respell a name phonetically in Ethiopic script.
- **Change (after user test 1):** ያስተዋውቀኝ → ያሳየኝ (s07) and መምህር → አስተማሪ (s09) replaced by
  synonyms; the nickname ጨጓራ cannot be replaced, so it is respelled ጨግዋራ (ጓ written out as ግዋ)
  for the TTS only. The displayed subtitle uses "Chegwara". Also መምህር's line was flagged by
  Hana, ያስተዋውቀኝ by Beza, ጨጓራ by Helen.
- **Result:** pending second listen by Helen, Hana and Beza.

## E6. Reference images first, then keyframes conditioned on them

- **Hypothesis (the brief's suggested practice):** generating one reference image per character
  and passing it to every keyframe keeps the father recognisably the same person across shots.
- **Change:** 3 references (father waist up, girl head and shoulders, grown daughter), passed as
  `input_image_N` to FLUX.2 klein with "Keep each character's face, hair, clothing and
  proportions exactly as in the reference images", plus the same style block and description
  text in every prompt.
- **Result:** in keyframes v1 the father is the same man in all 10 shots he appears in (slim,
  short hair, moustache, cream shirt, dark trousers), and the girl keeps her braids, red ribbons
  and blue dress in all 7 of hers, judged from a contact sheet. The per-shot outfit override in
  s11 (suit) worked without losing his face. Unreferenced extras drifted (FAILURES F7).
  **Verdict:** this practice beat my instinct, which was to describe the characters well and
  rely on fixed seeds.

## E7. Several candidates per keyframe, chosen by eye

- **Hypothesis:** for the shots that came out wrong after two prompt revisions (s03 the fall,
  s08 homework with a stray person, s10 the coffee ceremony), generating three seeds per shot and
  choosing one is faster than rewriting the prompt again and hoping.
- **Change:** new `python -m pipeline.run candidates s03 s08 s10`: three seeds per shot
  (seed, +7, +14) into `outputs/candidates/`, same prompt and references. Prompts were also made
  more concrete: the fall as lying on his back "as if asleep"; s08 "exactly two people and nobody
  else"; s10 names the buna ceremony elements (jebena, rekebot, habesha kemis, netela, grass,
  incense). s08 is now a Ken Burns shot to save GPU time.
- **Result:** pending; the choice and the reason go here.
