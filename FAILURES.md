# Failures

What broke, what I tried, what fixed it. Evidence is in `runs.jsonl` (`status` = `error` or `rejected`).

## F1. Gemini text call timed out in the smoke test (11:37)

- **What happened:** `gemini-flash-latest` did not answer within 60 s (`Read timed out`). TTS and
  Cloudflare calls in the same run worked, so the key and network were fine.
- **Tried:** listed the models the key can see (the smoke test prints them).
- **Fix:** pinned the explicit `gemini-3.8-flash` instead of the alias and raised the timeout
  to 120 s. Text generation is not on the film's critical path, so this did not block anything.
- **Lesson:** aliases hide which model actually answers; pin model ids in the storyboard.

## F2. The coding agent's sandbox blocked the first network call (11:47)

- **What happened:** Antigravity ran `python -m pipeline.run radio` inside a sandbox with no network,
  so the first TTS call (s01) failed. It is the `error` line for s01 in `runs.jsonl`.
- **Fix:** the agent re-ran the command with network access. The retry and cache meant nothing
  else had to be redone.

## F3. Radio cut v1 was 254 s instead of about 85 s: the TTS read the instruction aloud (12:06)

- **What happened:** each narration line came back 2 to 12 times longer than it should. Line s04
  (16 characters, about 2 s of speech) returned 19.9 s of audio: about 14 s of speech, a 3 s gap,
  then the real line. Silence analysis (`ffmpeg silencedetect`) showed continuous speech, not
  padding. `gemini-3.8-flash-tts` was reading my long English style instruction
  ("Read the following Amharic text aloud as a grown daughter...") as part of the text.
  Only s07 came back at a plausible length (50 chars, 6.4 s).
- **Why the smoke test missed it:** the smoke test used the short pattern
  `Say warmly in Amharic: <text>` and came back correct.
- **Fix:**
  1. Style is now a short prefix with a colon: `Say warmly and naturally, like a daughter
     remembering her father, in Amharic: <text>`.
  2. A plausibility guard: audio longer than `chars / 6 + 3` seconds is rejected, logged with
     `status: "rejected"`, and retried up to three times.
  3. Leading and trailing silence is trimmed from every line so shots are cut to the voice.
- **Lesson:** a TTS model has no separate channel for instructions; anything in the prompt can be
  spoken. Measure output duration against text length on every call, not once.
