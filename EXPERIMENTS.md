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
