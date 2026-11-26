"""ACE-Step 1.5 score candidates, one per seed in storyboard.music.candidate_seeds.
Runs on a Kaggle GPU notebook from inside an ACE-Step-1.5 checkout (see kaggle/README.md).

    python /kaggle/working/repo/kaggle/ace_step.py --acestep /kaggle/working/ACE-Step-1.5

Writes outputs/music/candidates/seed_<seed>.wav, appends one line per candidate to
remote_runs.jsonl, and zips both into /kaggle/working/music_out.zip."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from pipeline.common import OUT, log_call  # noqa: E402

REMOTE_LOG = REPO / "remote_runs.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--acestep", required=True, help="path to the ACE-Step-1.5 checkout")
    ap.add_argument("--dit", default="acestep-v15-turbo")
    args = ap.parse_args()
    sys.path.insert(0, args.acestep)

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    m = json.loads((REPO / "storyboard.json").read_text(encoding="utf-8"))["music"]
    out_dir = OUT / "music" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(args.acestep) / "gen_tmp"

    t_load = time.time()
    dit = AceStepHandler()
    dit.initialize_service(project_root=args.acestep, config_path=args.dit, device="cuda")
    print(f"ACE-Step loaded in {time.time() - t_load:.0f}s")

    model = f"ACE-Step/Ace-Step1.5:{args.dit}"
    for seed in m["candidate_seeds"]:
        params = GenerationParams(caption=m["caption"], lyrics="[Instrumental]" if m["instrumental"] else "",
                                  instrumental=m["instrumental"], bpm=m["bpm"], keyscale=m["keyscale"],
                                  duration=m["duration_s"], seed=seed, thinking=False)
        config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[seed], audio_format="wav")
        logged = {"caption": m["caption"], "bpm": m["bpm"], "keyscale": m["keyscale"],
                  "duration_s": m["duration_s"], "instrumental": m["instrumental"], "lm": False}
        t0 = time.time()
        result = generate_music(dit, None, params, config, save_dir=str(tmp))
        dt = time.time() - t0
        if not result.success:
            log_call("music", model, params=logged, seed=seed, latency_s=dt, gpu_s=dt, status="error",
                     error=str(result.error), runs_file=REMOTE_LOG)
            print(f"  seed {seed}: FAILED {result.error}")
            continue
        dest = out_dir / f"seed_{seed}.wav"
        shutil.copyfile(result.audios[0]["path"], dest)
        log_call("music", model, params=logged, seed=seed, latency_s=dt, gpu_s=dt, runs_file=REMOTE_LOG)
        print(f"  seed {seed}: {dt:.1f}s -> {dest.name}")

    zpath = Path("/kaggle/working/music_out.zip") if Path("/kaggle/working").exists() else REPO / "music_out.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for f in out_dir.iterdir():
            z.write(f, f.relative_to(REPO).as_posix())
        if REMOTE_LOG.exists():
            z.write(REMOTE_LOG, "remote_runs.jsonl")
    print(f"wrote {zpath}")


if __name__ == "__main__":
    main()
