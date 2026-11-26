# Enatenesh (እናቴነሽ) — A Father's Love

A heritage short by Segenet, made by a pipeline.

An 84-second film about my late father, who raised me on his own and called me *Enatenesh*.
Narrated in Amharic, with English subtitles, an original score ducked under the voice, and an
end card stating it was made with AI. Exported in 9:16 and 16:9.

The film is generated from one file, `storyboard.json`, by five stages: narration, keyframes,
moving shots, music and assembly. Change one shot and only that shot is regenerated.

## Run it

Requirements: Python 3.10+, FFmpeg (with `ffprobe`) on your PATH, a free Gemini API key and a
free Cloudflare account.

```bash
git clone https://github.com/rain-baba/Enatenesh-heritage-film
cd Enatenesh-heritage-film
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env  — then add your keys
python -m pipeline.run film       # or: make film
```

Result: `outputs/final/film_9x16.mp4` and `outputs/final/film_16x9.mp4`.

From a fresh clone every output is already present with its input hash, so `film` makes
**0 model calls** and only re-assembles (about 2 minutes). To regenerate everything from the
storyboard, delete the generated media first (`make clean-film`), then run `film`.

## Commands

| Command | What it does |
|---|---|
| `python -m pipeline.run validate` | Check `storyboard.json` against `schema/storyboard.schema.json` |
| `python -m pipeline.run film` | Every local stage, then both exports |
| `python -m pipeline.run radio` | Narration over a placeholder pad on black (the user-test prototype) |
| `python -m pipeline.run narration s04` | One stage, optionally for chosen shots only (`keyframes`, `shots` too) |
| `python -m pipeline.run candidates s03 s10` | Three keyframe options per shot in `outputs/candidates/` |
| `python -m pipeline.run pick s03 117` | Make candidate `s03_seed117` the keyframe (checks it matches the prompt) |
| `python -m pipeline.run import wan_out.zip` | Bring in Wan 2.2 or ACE-Step outputs made on Kaggle |
| `python -m pipeline.smoke_test` | One call per provider, latency logged |

Every run ends with `N new model call(s) logged to runs.jsonl`.

### Regenerate one shot

Edit one shot's `narration` (or `image_prompt`) in `storyboard.json`, then run
`python -m pipeline.run film`. Only that line's audio (or that keyframe) is regenerated; every
other stage reports `cached`, and the run reports **1 new model call**.

## The GPU stages

Wan 2.2 (moving shots) and ACE-Step 1.5 (music) need a GPU and run in a Kaggle notebook that
clones this repo: see `kaggle/README.md`. Without them the pipeline still produces a complete
film: every shot uses a slow pan and zoom over its keyframe, and the score falls back to a
placeholder pad. The final cut uses Ken Burns for all shots by choice (EXPERIMENTS E11).

## Stack

| Stage | Model | Where | Licence |
|---|---|---|---|
| Narration | gemini-2.5-flash-preview-tts, voice Sulafat | Gemini API, free tier | Google terms; Google claims no ownership |
| Keyframes | FLUX.2 [klein] 4B (9B for s03, s10) | Cloudflare Workers AI, free tier | Apache 2.0 (4B); FLUX non-commercial (9B) |
| Moving shots | Wan 2.2 TI2V-5B | Kaggle, Tesla T4 | Apache 2.0 |
| Music | ACE-Step 1.5 turbo | Kaggle, Tesla T4 | MIT |
| Assembly | FFmpeg 9.1, Pillow | local | |
| Coding agent | Antigravity (Gemini, then Claude Opus 4.6) and Claude | | |

Actual cost $0; list-price equivalent about $0.52 including all iteration (COSTS.md).

## Repository

| Path | Contents |
|---|---|
| `storyboard.json` | The contract: shots, reasons, prompts, seeds, narration, subtitles, music cues |
| `schema/` | JSON Schema, validated before every run |
| `pipeline/` | One module per stage, plus `common.py` (validation, cache, retries, logging) and `timeline.py` |
| `kaggle/` | GPU scripts for Wan 2.2 and ACE-Step, and notebook instructions |
| `runs.jsonl` | One line per model call: model, parameters, seed, latency, GPU time, cost, status |
| `outputs/` | Every generated image, audio file and video, with input-hash sidecars |
| `DESIGN.md` | Audience, intent, both user tests and what they changed |
| `ARCHITECTURE.md` | Stages, contracts, caching, failure handling |
| `EXPERIMENTS.md` | Hypothesis, change, result |
| `FAILURES.md` | What broke, what I tried, what fixed it |
| `COSTS.md` | Measured latency and GPU minutes, list-price equivalents |
| `ETHICS.md` | Consent, licences, labelling |
| `AGENTS.md` | Rules for coding agents working in this repo |
