# Enatenesh (እናቴነሽ): a heritage short made by a pipeline

A 60 to 90 second film about my father, narrated in Amharic with English subtitles and an
original score. It is generated from one file, `storyboard.json`, by a small pipeline:
keyframes, moving shots, music, narration and assembly.

## Run it

Requirements: Python 3.10+, FFmpeg on your PATH, and free API keys (Gemini, Cloudflare).

```bash
pip install -r requirements.txt
cp .env.example .env              # then fill in your keys
python -m pipeline.smoke_test     # one call per provider, logged to runs.jsonl
python -m pipeline.run film       # the whole film -> outputs/final/film_16x9.mp4, film_9x16.mp4
```

`make film` does the same. Other commands:

| Command | What it does |
|---|---|
| `python -m pipeline.run validate` | Check `storyboard.json` against `schema/storyboard.schema.json` |
| `python -m pipeline.run radio` | Narration over placeholder music on black (`outputs/final/radio_cut.mp4`) |
| `python -m pipeline.run narration s04` | Regenerate one stage, optionally for chosen shots only |
| `python -m pipeline.run import wan_out.zip` | Bring in Wan 2.2 / ACE-Step outputs made on Kaggle |

Every stage caches its outputs by a hash of its inputs. Change one shot's prompt or line,
re-run `film`, and only that shot's model calls run again. The run ends by printing how many
new model calls it logged.

The GPU stages (Wan 2.2 video, ACE-Step music) run on Kaggle; see `kaggle/README.md`. Without
them the pipeline still produces a complete film, using a slow pan and zoom over each keyframe
and a placeholder score.

## Repository

| Path | Contents |
|---|---|
| `storyboard.json` | The contract: shots, reasons, prompts, seeds, narration, subtitles, music cues |
| `schema/` | JSON Schema, validated before every run |
| `pipeline/` | One module per stage, plus `common.py` (cache, retries, logging) |
| `kaggle/` | GPU scripts for Wan 2.2 and ACE-Step |
| `runs.jsonl` | One line per model call: model, parameters, seed, latency, cost |
| `outputs/` | Generated media, kept so a run can be inspected |
| `DESIGN.md` | Audience, intent, user tests and what changed |
