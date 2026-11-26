"""One entry point for the whole pipeline.

    python -m pipeline.run film                 # every local stage, then both exports
    python -m pipeline.run radio                # narration + placeholder score on black
    python -m pipeline.run <stage> [shot ids]   # validate | narration | keyframes | shots | music
    python -m pipeline.run import <zip>         # bring in Kaggle outputs (Wan clips, ACE-Step)
    python -m pipeline.run candidates s03 s08   # 3 keyframe options per shot to choose from
    python -m pipeline.run pick s03 117         # make candidate s03_seed117 the keyframe

Every stage reads storyboard.json and skips work whose inputs have not changed,
so after editing one shot only that shot's model calls run again."""
from __future__ import annotations

import sys
import time

from .common import RUNS, load_storyboard
from . import assemble, keyframes, music, narration, shots


def _calls() -> int:
    return sum(1 for _ in open(RUNS, encoding="utf-8")) if RUNS.exists() else 0


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    cmd, rest = argv[0], set(argv[1:])
    before, t0 = _calls(), time.time()

    print("validate: storyboard.json")
    sb = load_storyboard()
    print(f"  ok: {len(sb['shots'])} shots, language={sb['language']}")

    if cmd == "validate":
        return
    if cmd == "import":
        from .import_remote import run as imp
        imp(argv[1])
    elif cmd == "radio":
        print("narration"); narration.run()
        print("music"); music.run()
        print("assemble (radio cut)"); assemble.run("radio")
    elif cmd == "film":
        print("narration"); narration.run()
        print("keyframes"); keyframes.run()
        print("shots"); shots.run()
        print("music"); music.run()
        print("assemble"); assemble.run("film")
    elif cmd in {"narration", "keyframes", "shots"}:
        {"narration": narration, "keyframes": keyframes, "shots": shots}[cmd].run(rest or None)
    elif cmd == "pick":
        keyframes.pick(argv[1], int(argv[2]))
    elif cmd == "candidates":
        keyframes.candidates(rest)
    elif cmd == "music":
        music.run()
    elif cmd == "assemble":
        assemble.run(next(iter(rest), "film"))
    else:
        raise SystemExit(f"Unknown command {cmd!r}.\n{__doc__}")

    new = _calls() - before
    print(f"\ndone in {time.time() - t0:.1f}s; {new} new model call(s) logged to runs.jsonl")


if __name__ == "__main__":
    main(sys.argv[1:])
