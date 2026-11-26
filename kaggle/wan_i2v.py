"""Wan 2.2 TI2V-5B image-to-video for the shots marked render="wan".
Runs on a Kaggle GPU notebook (see kaggle/README.md), not locally.

    python kaggle/wan_i2v.py                 # every wan shot whose inputs changed
    python kaggle/wan_i2v.py s01 s04         # only these shots
    python kaggle/wan_i2v.py --dtype bf16    # default fp16 (T4 has no native bf16)

Writes outputs/shots/wan/<shot>.mp4 (+ .hash sidecar) and appends one line per
call to remote_runs.jsonl, then zips both into /kaggle/working/wan_out.zip."""
from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from pipeline.common import OUT, is_fresh, log_call, mark_fresh  # noqa: E402
from pipeline.shots import wan_hash  # noqa: E402

REMOTE_LOG = REPO / "remote_runs.jsonl"
NEGATIVE = ("blurry, distorted face, extra fingers, deformed hands, morphing, flicker, text, watermark, "
            "low quality, static, oversaturated")


def load_pipe(model_id: str, dtype_name: str):
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16}[dtype_name]
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(model_id, vae=vae, torch_dtype=dtype)
    pipe.enable_model_cpu_offload()  # a T4 has 16 GB; offload keeps the text encoder off the GPU
    pipe.vae.enable_tiling()
    return pipe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", nargs="*")
    ap.add_argument("--dtype", default="fp16", choices=["fp16", "bf16"])
    args = ap.parse_args()

    import torch
    from diffusers.utils import export_to_video
    from PIL import Image

    sb = json.loads((REPO / "storyboard.json").read_text(encoding="utf-8"))
    cfg = sb["models"]["video"]
    todo = [s for s in sb["shots"] if (s["id"] in args.shots if args.shots else s["render"] == "wan")]
    out_dir = OUT / "shots" / "wan"
    out_dir.mkdir(parents=True, exist_ok=True)

    pending = [s for s in todo if not is_fresh(out_dir / f"{s['id']}.mp4", wan_hash(sb, s))]
    print(f"{len(pending)} of {len(todo)} wan shots need generating: {[s['id'] for s in pending]}")
    if pending:
        t_load = time.time()
        pipe = load_pipe(cfg["model"], args.dtype)
        print(f"pipeline loaded in {time.time() - t_load:.0f}s on {torch.cuda.get_device_name(0)}")

    for s in pending:
        sid, out = s["id"], out_dir / f"{s['id']}.mp4"
        image = Image.open(OUT / "keyframes" / f"{sid}.png").convert("RGB").resize((cfg["width"], cfg["height"]))
        params = {k: cfg[k] for k in ("width", "height", "num_frames", "steps", "guidance")} | {
            "dtype": args.dtype, "prompt": s["motion_prompt"]}
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        try:
            frames = pipe(image=image, prompt=s["motion_prompt"], negative_prompt=NEGATIVE,
                          height=cfg["height"], width=cfg["width"], num_frames=cfg["num_frames"],
                          num_inference_steps=cfg["steps"], guidance_scale=cfg["guidance"],
                          generator=torch.Generator("cpu").manual_seed(s["seed"])).frames[0]
            export_to_video(frames, str(out), fps=cfg.get("fps", 24))
        except Exception as e:  # log the failure, keep going with the next shot
            dt = time.time() - t0
            log_call("shots", cfg["model"], params=params, seed=s["seed"], shot=sid, latency_s=dt, gpu_s=dt,
                     status="error", error=repr(e), runs_file=REMOTE_LOG)
            print(f"  {sid}: FAILED after {dt:.0f}s: {e!r}")
            torch.cuda.empty_cache()
            continue
        dt = time.time() - t0
        mark_fresh(out, wan_hash(sb, s))
        log_call("shots", cfg["model"], params=params, seed=s["seed"], shot=sid, latency_s=dt, gpu_s=dt,
                 runs_file=REMOTE_LOG, extra={"gpu": torch.cuda.get_device_name(0),
                                              "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)})
        print(f"  {sid}: {dt / 60:.1f} min, peak {torch.cuda.max_memory_allocated() / 1e9:.1f} GB")

    zpath = Path("/kaggle/working/wan_out.zip") if Path("/kaggle/working").exists() else REPO / "wan_out.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for f in out_dir.iterdir():
            z.write(f, f.relative_to(REPO).as_posix())
        if REMOTE_LOG.exists():
            z.write(REMOTE_LOG, "remote_runs.jsonl")
    print(f"wrote {zpath}")


if __name__ == "__main__":
    main()
