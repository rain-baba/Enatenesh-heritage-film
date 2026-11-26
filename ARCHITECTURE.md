# Architecture

## One contract, five stages

```
                         storyboard.json  ──validated by──>  schema/storyboard.schema.json
                                │
   ┌──────────────┬─────────────┼──────────────┬─────────────────┐
   ▼              ▼             ▼              ▼                 ▼
narration      keyframes      shots          music            assemble
Gemini TTS     FLUX.2 klein   Ken Burns /    ACE-Step 1.5     FFmpeg
(per line)     (Cloudflare)   Wan 2.2        (Kaggle GPU,     (local, no models)
               refs first     (Kaggle GPU)   imported)
   │              │             │              │                 │
outputs/       outputs/refs/  outputs/       outputs/music/   outputs/final/
narration/     outputs/       shots/         candidates/,     film_16x9.mp4
sNN.wav        keyframes/     sNN.mp4        score.wav        film_9x16.mp4
               sNN.png                                        radio_cut.mp4
```

`storyboard.json` is the only thing a person edits. It holds, per shot: the reason the shot
exists, shot size, characters, image prompt, motion prompt, seed, Amharic narration, English
subtitle, and render mode. Globally it holds the style block, character descriptions and
reference prompts, every model id and setting, timing, music caption and cue notes, and the
end card. Each stage reads it and writes only its own folder in `outputs/`.

| Stage | Module | Reads | Writes | Runs on |
|---|---|---|---|---|
| validate | `common.load_storyboard` | storyboard + schema | (nothing; stops on error) | local |
| narration | `pipeline/narration.py` | `shots[].narration`, `models.tts` | `outputs/narration/sNN.wav` | Gemini API |
| keyframes | `pipeline/keyframes.py` | style, characters, `shots[].image_prompt`, seed | `outputs/refs/*.png`, `outputs/keyframes/sNN.png` | Cloudflare Workers AI |
| shots | `pipeline/shots.py` | keyframes, narration timing, `render` | `outputs/shots/sNN.mp4` (1080x1080 masters) | local FFmpeg; Wan clips from Kaggle |
| music | `pipeline/music.py` | `music.chosen` | `outputs/music/score.wav` | ACE-Step on Kaggle, imported |
| assemble | `pipeline/assemble.py` | everything above | `outputs/final/*.mp4` | local FFmpeg |

`python -m pipeline.run film` runs validate → narration → keyframes → shots → music → assemble.
The GPU stages run in a Kaggle notebook (`kaggle/wan_i2v.py`, `kaggle/ace_step.py`) that clones
this repo; their outputs come back with `python -m pipeline.run import <zip>`, which also appends
their call log to `runs.jsonl`.

## The edit is cut to the voice

`pipeline/timeline.py` turns narration into a timeline: each shot lasts
`pad_before + narration_length / voice_tempo + pad_after`, but at least `min_shot_s`. Shots and
assembly both use the same timeline, so the picture always follows the voice. The radio cut
(narration over a placeholder pad on black) is the same assembly with a black picture, which is
why it predicted the final film's length exactly (84.3 s).

## Caching: only what changed is regenerated

Every output has a sidecar `<file>.hash` holding a hash of everything that determines it:

| Output | Hash inputs |
|---|---|
| narration line | text, TTS model, voice, style instruction |
| reference / keyframe | full prompt, seed, image model and size, SHA of each reference image |
| shot master | render mode, SHA of the source (keyframe or Wan clip), duration, size, fps |
| Wan clip | SHA of the keyframe, motion prompt, seed, video settings (shared by Kaggle and local code) |
| score | SHA of the chosen candidate |

A stage skips any output whose sidecar matches (`cached`). Because a keyframe's hash includes
the SHA of the reference images, changing a character's description regenerates that reference
and then every keyframe that uses it, and nothing else. Changing one narration line regenerates
one audio file; if its length changes, that shot's Ken Burns master re-renders locally and the
final edit is reassembled, but no other model is called. `run` ends by printing how many new model calls were logged.

`pipeline.run pick <shot> <seed>` promotes a chosen candidate image to a keyframe byte for byte,
and refuses if the candidate's hash does not match the storyboard's current prompt, so the
storyboard can never silently disagree with the image on disk.

## Failure handling

| Failure | Handling | Where |
|---|---|---|
| Network errors, HTTP 5xx, per-minute 429 | Retry with exponential backoff (3 s or 10 s base) | `common.with_retries`, `narration.tts` |
| Daily quota exhausted (429 "PerDay") | Mark that model unusable for the run, move to `fallback_models`; stop rather than mix voices if none is left | `narration.run` (FAILURES F4, F9) |
| TTS reads the instruction aloud | Duration guard: audio longer than `chars/6 + 3` s is logged `rejected` and retried | `narration.speak` (F3) |
| Image safety filter (Cloudflare 3030) | Logged `flagged`, retried on seed+1000 and seed+2000; a shot flagged three times is skipped and listed, the rest continue | `keyframes._one` (F6) |
| Wan clip missing or stale | Shot falls back to Ken Burns automatically | `shots.run` |
| GPU out of memory on a T4 | Encode prompts with the text encoder alone, free it, then load the denoiser | `kaggle/wan_i2v.py` (F11) |
| Kaggle session restarts | One self-contained cell; clips saved with their hash as each finishes | `kaggle/README.md` (F12) |
| Bad storyboard | JSON Schema plus cross-checks (unique ids, known characters) before any stage runs | `common.load_storyboard` |

Every model call, successful or not, is one line in `runs.jsonl`: id, timestamp, stage, shot,
model, parameters (including the full prompt), seed, latency, GPU seconds, cost, status
(`ok`, `error`, `rejected`, `flagged`) and, for TTS, audio length and token usage.

## Audio and picture

- **Mix:** narration normalised to -16 LUFS, score to `music_lufs` (-21), score ducked under the
  voice with `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms), then a
  two-pass `loudnorm` to -14 LUFS integrated, -1 dBTP. Measured on the final film: -14.0 LUFS.
- **Narration speed:** `voice_tempo` (1.14) applies a pitch-preserving `atempo` in the edit, so
  the film fits 60 to 90 s without regenerating audio (EXPERIMENTS E3).
- **Picture:** square 1080x1080 shot masters. Each export shows the whole square centred over a
  blurred, darkened copy of itself, so nothing is cropped in either 16:9 or 9:16 (E10).
- **Subtitles:** generated from the timeline as SRT, at most two lines per cue, wrapped at 42
  (16:9) or 26 (9:16) characters, burned in with libass. FFmpeg runs from the assembly folder so
  the subtitle path has no Windows drive letter.
- **End card:** drawn with Pillow from `end_card.lines`: title, credit, dedication, "Made with AI"
  and every model used.
- **Export:** H.264 (CRF 20) + AAC 192 kbps, constant 24 fps, `+faststart`.

## Secrets

API keys live only in `.env` (git-ignored); `.env.example` lists the names. Code reads them with
`common.need()`, which fails with a clear message if one is missing. `AGENTS.md` tells coding
agents never to read, print or commit `.env`.
