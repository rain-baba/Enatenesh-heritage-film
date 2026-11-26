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
    """Load everything on the CPU first. A T4 has ~14.5 GB usable: the UMT5 text encoder
    (~11 GB fp16) and the 5B transformer (~10 GB fp16) do not fit together, and diffusers'
    model offload ran out of memory (FAILURES F11). So prompts are encoded first with the text
    encoder alone on the GPU, then it is dropped and the transformer and VAE take its place."""
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16}[dtype_name]
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
    return WanImageToVideoPipeline.from_pretrained(model_id, vae=vae, torch_dtype=dtype)


def encode_all(pipe, prompts: list[str]):
    """Phase 1: text encoder alone on the GPU; returns embeddings per prompt, then frees it."""
    import gc
    import torch
    pipe.text_encoder.to("cuda")
    out = {}
    with torch.no_grad():
        for p in prompts:
            pe, ne = pipe.encode_prompt(prompt=p, negative_prompt=NEGATIVE, do_classifier_free_guidance=True,
                                        device=torch.device("cuda"))
            out[p] = (pe.cpu(), ne.cpu())
    pipe.text_encoder.to("cpu")
    pipe.text_encoder = None
    gc.collect()
    torch.cuda.empty_cache()
    # Phase 2: denoiser and VAE on the GPU
    pipe.transformer.to("cuda")
    pipe.vae.to("cuda")
    pipe.vae.enable_tiling()
    return out


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
        embeds = encode_all(pipe, [s["motion_prompt"] for s in pending])
        print(f"pipeline loaded and prompts encoded in {time.time() - t_load:.0f}s on {torch.cuda.get_device_name(0)}")

    for s in pending:
        sid, out = s["id"], out_dir / f"{s['id']}.mp4"
        image = Image.open(OUT / "keyframes" / f"{sid}.png").convert("RGB").resize((cfg["width"], cfg["height"]))
        params = {k: cfg[k] for k in ("width", "height", "num_frames", "steps", "guidance")} | {
            "dtype": args.dtype, "prompt": s["motion_prompt"]}
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        try:
            pe, ne = embeds[s["motion_prompt"]]
            frames = pipe(image=image, prompt_embeds=pe.to("cuda"), negative_prompt_embeds=ne.to("cuda"),
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
