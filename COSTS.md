# Costs

Everything ran on free tiers: **actual spend $0.00**. Measured figures come from `runs.jsonl`
(96 logged calls as of film v3) and the Kaggle cell output. List-price equivalents use the price
survey shared in the cohort Slack (prices checked by its author on 25 Nov 2026), not my own
billing, so treat them as estimates.

## Measured, per stage

| Stage | Model | Where | Calls (ok / other) | Median latency | Output | GPU time |
|---|---|---|---|---|---|---|
| Narration | gemini-3.8-flash-tts | Gemini API free | 11 / 4 | 11.0 s per line | radio cut v1, rejected (read prompt aloud) | n/a |
| Narration | gemini-3.1-flash-tts-preview | Gemini API free | 8 / 1 | 7.1 s per line | radio cut v2 | n/a |
| Narration | gemini-2.5-flash-preview-tts | Gemini API free | 11 / 3 | 11.6 s per line | **final narration, 89.9 s of audio** | n/a |
| Narration | gemini-2.5-pro-preview-tts | Gemini API free | 0 / 2 | n/a | no free quota | n/a |
| References | flux-2-klein-4b | Cloudflare Workers AI free | 3 / 3 | 14.1 s | 3 character references | n/a |
| Keyframes | flux-2-klein-4b | Cloudflare Workers AI free | 17 / 1 | 24.0 s | 11 keyframes and revisions | n/a |
| Candidates | flux-2-klein-4b | Cloudflare Workers AI free | 15 / 0 | 15.8 s | 3 per shot to choose from | n/a |
| Candidates | flux-2-klein-9b | Cloudflare Workers AI free | 6 / 1 | 16.3 s | s03, s10 options | n/a |
| Moving shots | Wan 2.2 TI2V-5B | Kaggle, Tesla T4 | 4 / 1 (OOM) | 8.7 min per clip | 4 clips, 512x512, 81 frames, 25 steps | **34.9 min** + 5.5 min load |
| Music | ACE-Step 1.5 turbo (DiT only) | Kaggle, Tesla T4 | 3 / 0 | 7.9 s per 95 s track | 3 candidates | **0.5 min** + ~5 min install |
| Assembly | FFmpeg 9.1 | laptop CPU | n/a | ~95 s for both exports | 2 films, 84.3 s, -14.0 LUFS | n/a |

Notes on the numbers:
- A Wan clip is about 4 min of denoising (25 steps at ~10 s per step on the T4) plus about
  4.5 min of fp32 tiled VAE decoding and export. Peak memory 14.7 GB of the T4's 14.56 GiB.
- Re-running the whole pipeline from a clone with nothing changed makes **0 model calls** and
  takes about 2 minutes (assembly only).
- Latency includes retries and back-off: one s06 line took 81 s through three empty TTS
  responses and a rate limit.

## List-price equivalent for this film

| Stage | What was used | Rate (cohort price survey) | Equivalent |
|---|---|---|---|
| Narration | ~382 s of TTS audio generated in total (all versions) | Gemini 3.8 Flash TTS ≈ $0.00225 per 10 s | ≈ $0.09 |
| Images, 4B | 36 images | klein 4B on Workers AI ≈ $0.0014 per image | ≈ $0.05 |
| Images, 9B | 6 images | klein 9B ≈ 1,364 neurons ≈ $0.015 per image | ≈ $0.09 |
| Video | 4 clips at 512 px | hosted Wan 2.2 480p (WaveSpeed) $0.05 per 5 s clip | ≈ $0.20 |
| Music | 3 × 95 s | hosted ACE-Step 1.5 (WaveSpeed) $0.0003 per s | ≈ $0.09 |
| **Total** | | | **≈ $0.52** |

The final film alone (11 lines, 11 keyframes, 3 references, 1 score, no video) would be about
$0.10 at list price. Most of the spend-equivalent went into iteration, which is the point of
measuring it.

## Frontier comparison

I had no billing, so no frontier model was run. From the same survey, the paid equivalents for
this film would be: Gemini Omni Flash video ≈ $0.07 per second (≈ $5 for 70 s of video),
Nano Banana 2.1 ≈ $0.034 per image (≈ $0.50 for 14 images), Lyria 3.5 $0.08 per song. That is
roughly 10 to 15 times the open-model list price, mostly because of video.

## The real constraint: free-tier limits hit today

| Limit | When | Effect | Workaround |
|---|---|---|---|
| Gemini TTS requests per model per day | 12:16 (3.8), 12:3x (3.1), 14:41 and 15:00 (2.5) | Could not regenerate s09/s10 after user test 1 | Fallback models; kept v2 recordings to keep one voice (F4, F9) |
| Cloudflare 10,000 neurons per day | 16:16 | No more keyframes; the 9B model used ~10× the neurons of the 4B | Kept existing s11 (F10) |
| Antigravity weekly quota (default model) | 13:02, resets in 166 h | Agent unavailable on that model | Claude Opus in Antigravity, then plain PowerShell (F5) |
| Kaggle T4 16 GB | 16:30 | Wan out of memory | Two-phase loading (F11) |
| Kaggle session restarts | 17:30 | Lost installs, re-downloaded 29 GB | One self-contained cell (F12) |

Money was never the constraint. Requests per model per day, neurons per day and GPU memory were.
