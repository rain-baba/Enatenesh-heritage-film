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

## F4. Daily TTS quota exhausted, and 3.8 still spoke the short prefix (12:16)

- **What happened:** rerunning the radio cut, `gemini-3.8-flash-tts` returned HTTP 429
  "You exceeded your current quota". Radio cut v1 (11 lines) plus retries had used up the free
  daily allowance for that model. Before the 429, s01 came back at 12.7 s and 12.2 s for 49
  characters: the duration guard from F3 caught that 3.8 was still speaking part of the
  `Say ...:` prefix. The first attempt also failed DNS resolution inside the agent sandbox (F2 again).
- **Tried:** waiting is not an option on the day of the deadline.
- **Fix:** free-tier quotas are per model, so the storyboard now lists a primary TTS model and
  fallbacks: `gemini-3.1-flash-tts-preview` (it spoke the smoke-test prefix correctly),
  then `gemini-2.5-flash-preview-tts`, then `gemini-3.8-flash-lite-tts`. A daily-quota 429 or three
  implausible results in a row marks a model unusable for the rest of the run and moves to the
  next one; a per-minute 429 backs off 10, 20, 40 s first. Every switch is logged. Tested with a
  mocked API before running for real.
- **Lesson:** the binding constraint on the free tier is requests per model per day, not money.
  Rejected and retried calls spend the same quota as good ones.

## F5. The coding agent's weekly quota ran out (13:02)

- **What happened:** Antigravity returned "Individual quota reached... Resets in 166h" on its
  default model (Gemini 4 Hydrogen High) after about two hours of use, mid-way through running the
  keyframes stage. Earlier it had also returned repeated "No capacity available" (HTTP 503) errors
  for the same model.
- **Tried:** switching models in the agent. Gemini Flash did not help; **Claude Opus 4.6** inside
  Antigravity worked (quota is per model). Fallback plan if that runs out too: run the same
  commands by hand in PowerShell; every step of the pipeline is an ordinary command.
- **Lesson:** the agent is a convenience, not a dependency. Because the pipeline is plain
  `python -m pipeline.run <stage>` commands, losing the agent cost minutes, not the project.

## F6. Cloudflare's safety filter flagged a character reference image (13:19)

- **What happened:** `flux-2-klein-4b` returned HTTP 400, code 3030, "Your output has been
  flagged", on the first character reference. The filter judges the generated *output*, so the
  same prompt can pass on one seed and fail on another. Full-body images of a child are the most
  likely trigger.
- **Fix:**
  1. Reference prompts changed from full-body sheets to portraits (father waist up, girl head
     and shoulders); the girl's description no longer lists clothing details or an exact age.
     The fall (s03) now reads "lying on the ground with his eyes closed as if asleep".
  2. A flagged output is logged as `status: "flagged"` and retried on seed+1000 and seed+2000.
     The seed actually used is in `runs.jsonl`.
  3. A shot flagged on all three seeds no longer stops the stage: the others still generate and
     the run ends by listing which prompts to rephrase.
  Tested against a mocked API before running for real.
