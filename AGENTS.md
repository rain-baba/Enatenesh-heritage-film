# Agent Guidelines

Rules for any coding agent working in this repository:

- Never print, log, or commit the contents of `.env` or any API key.
- `storyboard.json` is the contract between stages; run `python -m pipeline.run validate` after every edit to it.
- Never change the narration text of shots `s08` and `s11`.
- Every model call must be logged to `runs.jsonl` via `log_call` in `pipeline/common.py`.
- Keep code minimal and readable; one module per stage in `pipeline/`.
- Commit small, with clear messages.
